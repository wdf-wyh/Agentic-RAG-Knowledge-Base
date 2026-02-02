"""记忆管理工具 - 长期记忆存储和检索

参考大企业实践（如 Anthropic Memory, OpenAI Memory），提供:
- 短期记忆（会话内）
- 长期记忆（跨会话）
- 实体记忆（用户偏好、重要事实）
"""

import json
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """记忆类型"""
    FACT = "fact"           # 事实记忆（用户告诉的信息）
    PREFERENCE = "preference"  # 偏好记忆
    ENTITY = "entity"       # 实体记忆（人物、项目等）
    SUMMARY = "summary"     # 对话摘要
    INSIGHT = "insight"     # 洞察和推断


@dataclass
class Memory:
    """记忆项"""
    id: str
    type: MemoryType
    content: str
    source: str  # 来源（对话ID或手动添加）
    created_at: str
    updated_at: str
    importance: float = 0.5  # 重要性 0-1
    access_count: int = 0    # 访问次数
    tags: List[str] = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['type'] = self.type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Memory":
        data['type'] = MemoryType(data['type'])
        return cls(**data)


class MemoryStore:
    """记忆存储管理器"""
    
    def __init__(self, storage_path: str = "./memory"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self._memories: Dict[str, Memory] = {}
        self._load_memories()
    
    def _load_memories(self):
        """从磁盘加载记忆"""
        memory_file = self.storage_path / "memories.json"
        if memory_file.exists():
            try:
                with open(memory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for item in data:
                    memory = Memory.from_dict(item)
                    self._memories[memory.id] = memory
                logger.info(f"加载了 {len(self._memories)} 条记忆")
            except Exception as e:
                logger.error(f"加载记忆失败: {e}")
    
    def _save_memories(self):
        """保存记忆到磁盘"""
        memory_file = self.storage_path / "memories.json"
        try:
            data = [m.to_dict() for m in self._memories.values()]
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存记忆失败: {e}")
    
    def add(
        self, 
        content: str, 
        memory_type: MemoryType,
        source: str = "manual",
        importance: float = 0.5,
        tags: List[str] = None
    ) -> Memory:
        """添加记忆"""
        import uuid
        now = datetime.now().isoformat()
        
        memory = Memory(
            id=str(uuid.uuid4())[:8],
            type=memory_type,
            content=content,
            source=source,
            created_at=now,
            updated_at=now,
            importance=importance,
            tags=tags or []
        )
        
        self._memories[memory.id] = memory
        self._save_memories()
        
        logger.info(f"添加记忆: [{memory.type.value}] {content[:50]}...")
        return memory
    
    def search(
        self, 
        query: str = None, 
        memory_type: MemoryType = None,
        tags: List[str] = None,
        limit: int = 10
    ) -> List[Memory]:
        """搜索记忆"""
        results = list(self._memories.values())
        
        # 按类型过滤
        if memory_type:
            results = [m for m in results if m.type == memory_type]
        
        # 按标签过滤
        if tags:
            results = [m for m in results if any(t in (m.tags or []) for t in tags)]
        
        # 按关键词过滤
        if query:
            query_lower = query.lower()
            results = [m for m in results if query_lower in m.content.lower()]
        
        # 按重要性和访问次数排序
        results.sort(key=lambda m: (m.importance, m.access_count), reverse=True)
        
        # 更新访问次数
        for m in results[:limit]:
            m.access_count += 1
        self._save_memories()
        
        return results[:limit]
    
    def delete(self, memory_id: str) -> bool:
        """删除记忆"""
        if memory_id in self._memories:
            del self._memories[memory_id]
            self._save_memories()
            return True
        return False
    
    def update_importance(self, memory_id: str, importance: float) -> bool:
        """更新记忆重要性"""
        if memory_id in self._memories:
            self._memories[memory_id].importance = min(1.0, max(0.0, importance))
            self._memories[memory_id].updated_at = datetime.now().isoformat()
            self._save_memories()
            return True
        return False
    
    def get_context_for_query(self, query: str, max_memories: int = 5) -> str:
        """获取与查询相关的记忆上下文"""
        memories = self.search(query=query, limit=max_memories)
        
        if not memories:
            return ""
        
        context_parts = ["【长期记忆】"]
        for m in memories:
            context_parts.append(f"- [{m.type.value}] {m.content}")
        
        return "\n".join(context_parts)


# 全局记忆存储实例
memory_store = MemoryStore()


class MemoryTool(BaseTool):
    """记忆管理工具"""
    
    def __init__(self, store: MemoryStore = None):
        self.store = store or memory_store
        super().__init__()
    
    @property
    def name(self) -> str:
        return "memory"
    
    @property
    def description(self) -> str:
        return """管理长期记忆。可以存储、检索和管理跨会话的重要信息。
适用场景:
- 记住用户偏好（如"用户喜欢简洁的回答"）
- 存储重要事实（如"用户的项目名是 RAG 知识库"）
- 保存实体信息（如"用户的团队有5人"）

操作类型:
- add: 添加新记忆
- search: 搜索相关记忆
- delete: 删除记忆
- list: 列出所有记忆"""
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "action",
                "type": "string",
                "description": "操作类型: add, search, delete, list",
                "required": True
            },
            {
                "name": "content",
                "type": "string",
                "description": "记忆内容（add 操作必需）",
                "required": False
            },
            {
                "name": "memory_type",
                "type": "string",
                "description": "记忆类型: fact, preference, entity, summary, insight",
                "required": False
            },
            {
                "name": "query",
                "type": "string",
                "description": "搜索关键词（search 操作使用）",
                "required": False
            },
            {
                "name": "memory_id",
                "type": "string",
                "description": "记忆ID（delete 操作必需）",
                "required": False
            },
            {
                "name": "importance",
                "type": "number",
                "description": "重要性 0-1，默认 0.5",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """执行记忆操作"""
        action = kwargs.get("action", "").lower()
        
        if action == "add":
            return self._add_memory(**kwargs)
        elif action == "search":
            return self._search_memory(**kwargs)
        elif action == "delete":
            return self._delete_memory(**kwargs)
        elif action == "list":
            return self._list_memories(**kwargs)
        else:
            return ToolResult(
                success=False,
                output="",
                error=f"未知操作: {action}。支持: add, search, delete, list"
            )
    
    def _add_memory(self, **kwargs) -> ToolResult:
        """添加记忆"""
        content = kwargs.get("content", "")
        if not content:
            return ToolResult(success=False, output="", error="记忆内容不能为空")
        
        type_str = kwargs.get("memory_type", "fact")
        try:
            memory_type = MemoryType(type_str)
        except ValueError:
            memory_type = MemoryType.FACT
        
        importance = kwargs.get("importance", 0.5)
        
        memory = self.store.add(
            content=content,
            memory_type=memory_type,
            importance=importance
        )
        
        return ToolResult(
            success=True,
            output=f"✓ 已添加记忆 [{memory.type.value}]: {content[:100]}...\nID: {memory.id}",
            data=memory.to_dict()
        )
    
    def _search_memory(self, **kwargs) -> ToolResult:
        """搜索记忆"""
        query = kwargs.get("query", "")
        type_str = kwargs.get("memory_type")
        
        memory_type = None
        if type_str:
            try:
                memory_type = MemoryType(type_str)
            except ValueError:
                pass
        
        memories = self.store.search(query=query, memory_type=memory_type)
        
        if not memories:
            return ToolResult(
                success=True,
                output="未找到相关记忆",
                data=[]
            )
        
        output_parts = [f"找到 {len(memories)} 条相关记忆:\n"]
        for m in memories:
            output_parts.append(f"[{m.id}] ({m.type.value}) {m.content}")
            output_parts.append(f"    重要性: {m.importance:.1f}, 访问: {m.access_count}次\n")
        
        return ToolResult(
            success=True,
            output="\n".join(output_parts),
            data=[m.to_dict() for m in memories]
        )
    
    def _delete_memory(self, **kwargs) -> ToolResult:
        """删除记忆"""
        memory_id = kwargs.get("memory_id", "")
        if not memory_id:
            return ToolResult(success=False, output="", error="需要提供记忆ID")
        
        if self.store.delete(memory_id):
            return ToolResult(success=True, output=f"✓ 已删除记忆 {memory_id}")
        else:
            return ToolResult(success=False, output="", error=f"未找到记忆 {memory_id}")
    
    def _list_memories(self, **kwargs) -> ToolResult:
        """列出所有记忆"""
        memories = self.store.search(limit=50)
        
        if not memories:
            return ToolResult(success=True, output="暂无存储的记忆", data=[])
        
        # 按类型分组
        grouped: Dict[str, List[Memory]] = {}
        for m in memories:
            type_name = m.type.value
            if type_name not in grouped:
                grouped[type_name] = []
            grouped[type_name].append(m)
        
        output_parts = [f"共有 {len(memories)} 条记忆:\n"]
        for type_name, type_memories in grouped.items():
            output_parts.append(f"\n**{type_name.upper()}** ({len(type_memories)}条)")
            for m in type_memories[:5]:
                output_parts.append(f"  - [{m.id}] {m.content[:60]}...")
        
        return ToolResult(
            success=True,
            output="\n".join(output_parts),
            data=[m.to_dict() for m in memories]
        )
