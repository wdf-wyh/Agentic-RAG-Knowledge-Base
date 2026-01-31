"""对话历史管理器 - 管理多轮对话上下文"""

from typing import List, Dict, Optional
from datetime import datetime
import uuid
import json
from pathlib import Path
from threading import Lock

from src.models.schemas import ConversationMessage


class ConversationManager:
    """对话管理器，负责维护和管理对话历史
    
    线程安全：使用 Lock 保护共享状态
    """
    
    def __init__(self, storage_path: str = "./conversations"):
        """初始化对话管理器
        
        Args:
            storage_path: 对话历史存储路径
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        
        # 内存中的活跃会话缓存
        self.active_sessions: Dict[str, List[ConversationMessage]] = {}
        
        # 线程安全锁
        self._lock = Lock()
        
    def create_conversation(self) -> str:
        """创建新的对话会话
        
        Returns:
            会话ID
        """
        conversation_id = str(uuid.uuid4())
        with self._lock:
            self.active_sessions[conversation_id] = []
        return conversation_id
    
    def add_message(
        self, 
        conversation_id: str, 
        role: str, 
        content: str,
        save_to_disk: bool = False
    ) -> ConversationMessage:
        """添加消息到对话历史
        
        Args:
            conversation_id: 会话ID
            role: 消息角色 ('user' 或 'assistant')
            content: 消息内容
            save_to_disk: 是否立即保存到磁盘
            
        Returns:
            添加的消息对象
        """
        with self._lock:
            if conversation_id not in self.active_sessions:
                self.active_sessions[conversation_id] = []
        
        message = ConversationMessage(
            role=role,
            content=content,
            timestamp=datetime.now().isoformat()
        )
        
        self.active_sessions[conversation_id].append(message)
        
        if save_to_disk:
            self.save_conversation(conversation_id)
        
        return message
    
    def get_history(
        self, 
        conversation_id: str, 
        max_messages: Optional[int] = None
    ) -> List[ConversationMessage]:
        """获取对话历史
        
        Args:
            conversation_id: 会话ID
            max_messages: 最多返回的消息数量（从最近开始）
            
        Returns:
            消息列表
        """
        if conversation_id not in self.active_sessions:
            # 尝试从磁盘加载
            self.load_conversation(conversation_id)
        
        history = self.active_sessions.get(conversation_id, [])
        
        if max_messages and len(history) > max_messages:
            return history[-max_messages:]
        
        return history
    
    def format_history_for_llm(
        self, 
        conversation_id: str, 
        max_turns: int = 3
    ) -> str:
        """格式化历史对话用于LLM上下文
        
        Args:
            conversation_id: 会话ID
            max_turns: 最多包含的对话轮数
            
        Returns:
            格式化的历史文本
        """
        history = self.get_history(conversation_id)
        
        # 只取最近的几轮对话
        if len(history) > max_turns * 2:
            history = history[-(max_turns * 2):]
        
        if not history:
            return "（无历史对话）"
        
        formatted = ""
        for i, msg in enumerate(history, 1):
            role_name = "👤 用户" if msg.role == "user" else "🤖 助手"
            # 添加序号和时间戳，让上下文更清晰
            formatted += f"{i}. {role_name}: {msg.content}\n"
        
        return formatted.strip()
    
    def clear_conversation(self, conversation_id: str):
        """清空指定会话的历史
        
        Args:
            conversation_id: 会话ID
        """
        if conversation_id in self.active_sessions:
            self.active_sessions[conversation_id] = []
    
    def save_conversation(self, conversation_id: str):
        """保存对话到磁盘
        
        Args:
            conversation_id: 会话ID
        """
        if conversation_id not in self.active_sessions:
            return
        
        file_path = self.storage_path / f"{conversation_id}.json"
        
        history_data = [
            msg.model_dump() for msg in self.active_sessions[conversation_id]
        ]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)
    
    def load_conversation(self, conversation_id: str) -> bool:
        """从磁盘加载对话
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            是否成功加载
        """
        file_path = self.storage_path / f"{conversation_id}.json"
        
        if not file_path.exists():
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
            
            self.active_sessions[conversation_id] = [
                ConversationMessage(**msg) for msg in history_data
            ]
            return True
        except Exception as e:
            print(f"加载对话失败: {e}")
            return False
    
    def list_conversations(self) -> List[str]:
        """列出所有保存的对话ID
        
        Returns:
            会话ID列表
        """
        return [f.stem for f in self.storage_path.glob("*.json")]
    
    def delete_conversation(self, conversation_id: str):
        """删除对话
        
        Args:
            conversation_id: 会话ID
        """
        # 从内存中删除
        if conversation_id in self.active_sessions:
            del self.active_sessions[conversation_id]
        
        # 从磁盘删除
        file_path = self.storage_path / f"{conversation_id}.json"
        if file_path.exists():
            file_path.unlink()
