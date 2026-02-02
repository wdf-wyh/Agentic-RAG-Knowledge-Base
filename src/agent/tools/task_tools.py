"""日程和任务管理工具 - 管理待办事项和提醒

参考大企业实践（如 Google Calendar API, Notion API），提供:
- 待办事项管理
- 定时提醒
- 任务追踪
"""

import json
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """任务优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(Enum):
    """任务状态"""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """任务"""
    id: str
    title: str
    description: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.TODO
    due_date: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    tags: List[str] = None
    subtasks: List[Dict] = None
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['priority'] = self.priority.value
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Task":
        data['priority'] = TaskPriority(data.get('priority', 'medium'))
        data['status'] = TaskStatus(data.get('status', 'todo'))
        return cls(**data)


class TaskManager:
    """任务管理器"""
    
    def __init__(self, storage_path: str = "./tasks"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self._tasks: Dict[str, Task] = {}
        self._load_tasks()
    
    def _load_tasks(self):
        """加载任务"""
        task_file = self.storage_path / "tasks.json"
        if task_file.exists():
            try:
                with open(task_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for item in data:
                    task = Task.from_dict(item)
                    self._tasks[task.id] = task
            except Exception as e:
                logger.error(f"加载任务失败: {e}")
    
    def _save_tasks(self):
        """保存任务"""
        task_file = self.storage_path / "tasks.json"
        try:
            data = [t.to_dict() for t in self._tasks.values()]
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存任务失败: {e}")
    
    def add(
        self,
        title: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_date: str = None,
        tags: List[str] = None
    ) -> Task:
        """添加任务"""
        import uuid
        now = datetime.now().isoformat()
        
        task = Task(
            id=str(uuid.uuid4())[:8],
            title=title,
            description=description,
            priority=priority,
            status=TaskStatus.TODO,
            due_date=due_date,
            created_at=now,
            updated_at=now,
            tags=tags or []
        )
        
        self._tasks[task.id] = task
        self._save_tasks()
        return task
    
    def update_status(self, task_id: str, status: TaskStatus) -> Optional[Task]:
        """更新任务状态"""
        if task_id in self._tasks:
            self._tasks[task_id].status = status
            self._tasks[task_id].updated_at = datetime.now().isoformat()
            self._save_tasks()
            return self._tasks[task_id]
        return None
    
    def get_tasks(
        self,
        status: TaskStatus = None,
        priority: TaskPriority = None,
        include_done: bool = False
    ) -> List[Task]:
        """获取任务列表"""
        tasks = list(self._tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        elif not include_done:
            tasks = [t for t in tasks if t.status != TaskStatus.DONE and t.status != TaskStatus.CANCELLED]
        
        if priority:
            tasks = [t for t in tasks if t.priority == priority]
        
        # 按优先级和到期日期排序
        priority_order = {TaskPriority.URGENT: 0, TaskPriority.HIGH: 1, TaskPriority.MEDIUM: 2, TaskPriority.LOW: 3}
        tasks.sort(key=lambda t: (priority_order[t.priority], t.due_date or "9999"))
        
        return tasks
    
    def get_overdue_tasks(self) -> List[Task]:
        """获取逾期任务"""
        now = datetime.now().isoformat()[:10]  # YYYY-MM-DD
        return [
            t for t in self._tasks.values()
            if t.status == TaskStatus.TODO and t.due_date and t.due_date < now
        ]
    
    def delete(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self._tasks:
            del self._tasks[task_id]
            self._save_tasks()
            return True
        return False


# 全局任务管理器
task_manager = TaskManager()


class TaskTool(BaseTool):
    """任务管理工具"""
    
    def __init__(self, manager: TaskManager = None):
        self.manager = manager or task_manager
        super().__init__()
    
    @property
    def name(self) -> str:
        return "task_manager"
    
    @property
    def description(self) -> str:
        return """管理待办任务和提醒。
操作类型:
- add: 添加新任务
- list: 列出任务
- complete: 完成任务
- delete: 删除任务
- overdue: 查看逾期任务

示例用法:
- "添加任务：明天下午提交报告"
- "列出所有高优先级任务"
- "完成任务 abc123"
"""
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "action",
                "type": "string",
                "description": "操作类型: add, list, complete, delete, overdue",
                "required": True
            },
            {
                "name": "title",
                "type": "string",
                "description": "任务标题（add 操作必需）",
                "required": False
            },
            {
                "name": "description",
                "type": "string",
                "description": "任务描述",
                "required": False
            },
            {
                "name": "priority",
                "type": "string",
                "description": "优先级: low, medium, high, urgent",
                "required": False
            },
            {
                "name": "due_date",
                "type": "string",
                "description": "到期日期 (YYYY-MM-DD)",
                "required": False
            },
            {
                "name": "task_id",
                "type": "string",
                "description": "任务ID（complete/delete 操作必需）",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """执行任务操作"""
        action = kwargs.get("action", "").lower()
        
        if action == "add":
            return self._add_task(**kwargs)
        elif action == "list":
            return self._list_tasks(**kwargs)
        elif action == "complete":
            return self._complete_task(**kwargs)
        elif action == "delete":
            return self._delete_task(**kwargs)
        elif action == "overdue":
            return self._get_overdue(**kwargs)
        else:
            return ToolResult(
                success=False,
                output="",
                error=f"未知操作: {action}"
            )
    
    def _add_task(self, **kwargs) -> ToolResult:
        """添加任务"""
        title = kwargs.get("title", "")
        if not title:
            return ToolResult(success=False, output="", error="任务标题不能为空")
        
        priority_str = kwargs.get("priority", "medium")
        try:
            priority = TaskPriority(priority_str)
        except ValueError:
            priority = TaskPriority.MEDIUM
        
        task = self.manager.add(
            title=title,
            description=kwargs.get("description", ""),
            priority=priority,
            due_date=kwargs.get("due_date")
        )
        
        output = f"""✓ 任务已创建
- ID: {task.id}
- 标题: {task.title}
- 优先级: {task.priority.value}
- 到期: {task.due_date or '未设置'}"""
        
        return ToolResult(success=True, output=output, data=task.to_dict())
    
    def _list_tasks(self, **kwargs) -> ToolResult:
        """列出任务"""
        priority_str = kwargs.get("priority")
        priority = None
        if priority_str:
            try:
                priority = TaskPriority(priority_str)
            except ValueError:
                pass
        
        tasks = self.manager.get_tasks(priority=priority)
        
        if not tasks:
            return ToolResult(success=True, output="暂无待办任务 ✨", data=[])
        
        # 按优先级分组显示
        output_parts = [f"📋 共有 {len(tasks)} 个待办任务:\n"]
        
        priority_icons = {
            TaskPriority.URGENT: "🔴",
            TaskPriority.HIGH: "🟠",
            TaskPriority.MEDIUM: "🟡",
            TaskPriority.LOW: "🟢"
        }
        
        for task in tasks:
            icon = priority_icons.get(task.priority, "⚪")
            due_info = f" (到期: {task.due_date})" if task.due_date else ""
            output_parts.append(f"{icon} [{task.id}] {task.title}{due_info}")
        
        return ToolResult(
            success=True,
            output="\n".join(output_parts),
            data=[t.to_dict() for t in tasks]
        )
    
    def _complete_task(self, **kwargs) -> ToolResult:
        """完成任务"""
        task_id = kwargs.get("task_id", "")
        if not task_id:
            return ToolResult(success=False, output="", error="需要提供任务ID")
        
        task = self.manager.update_status(task_id, TaskStatus.DONE)
        if task:
            return ToolResult(
                success=True,
                output=f"✅ 任务已完成: {task.title}",
                data=task.to_dict()
            )
        else:
            return ToolResult(success=False, output="", error=f"未找到任务 {task_id}")
    
    def _delete_task(self, **kwargs) -> ToolResult:
        """删除任务"""
        task_id = kwargs.get("task_id", "")
        if not task_id:
            return ToolResult(success=False, output="", error="需要提供任务ID")
        
        if self.manager.delete(task_id):
            return ToolResult(success=True, output=f"🗑️ 任务已删除: {task_id}")
        else:
            return ToolResult(success=False, output="", error=f"未找到任务 {task_id}")
    
    def _get_overdue(self, **kwargs) -> ToolResult:
        """获取逾期任务"""
        tasks = self.manager.get_overdue_tasks()
        
        if not tasks:
            return ToolResult(success=True, output="没有逾期任务 👍", data=[])
        
        output_parts = [f"⚠️ 有 {len(tasks)} 个逾期任务:\n"]
        for task in tasks:
            output_parts.append(f"- [{task.id}] {task.title} (应于 {task.due_date} 完成)")
        
        return ToolResult(
            success=True,
            output="\n".join(output_parts),
            data=[t.to_dict() for t in tasks]
        )
