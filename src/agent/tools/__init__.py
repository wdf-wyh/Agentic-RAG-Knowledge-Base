"""Agent 工具模块"""

from src.agent.tools.base import (
    BaseTool,
    ToolResult,
    ToolCategory,
    ToolRegistry,
    global_registry,
    register_tool,
)
from src.agent.tools.rag_tools import RAGSearchTool, DocumentListTool
from src.agent.tools.file_tools import (
    ReadFileTool,
    WriteFileTool,
    ListDirectoryTool,
    MoveFileTool,
    CreateDirectoryTool,
)
from src.agent.tools.web_tools import WebSearchTool
from src.agent.tools.trending_tools import BaiduTrendingTool, TrendingNewsAggregatorTool
from src.agent.tools.analysis_tools import DocumentAnalysisTool, SummarizeTool
from src.agent.tools.image_tools import ImageAnalysisTool, BatchImageAnalysisTool
from src.agent.tools.notification_tools import (
    SystemNotifyTool,
    SoundAlertTool,
    TaskCompletionNotifyTool,
    notify,
    alert,
    task_complete,
)

__all__ = [
    # 基础类
    "BaseTool",
    "ToolResult", 
    "ToolCategory",
    "ToolRegistry",
    "global_registry",
    "register_tool",
    # RAG 工具
    "RAGSearchTool",
    "DocumentListTool",
    # 文件工具
    "ReadFileTool",
    "WriteFileTool",
    "ListDirectoryTool",
    "MoveFileTool",
    "CreateDirectoryTool",
    # 网页搜索
    "WebSearchTool",
    # 热搜工具
    "BaiduTrendingTool",
    "TrendingNewsAggregatorTool",
    # 分析工具
    "DocumentAnalysisTool",
    "SummarizeTool",
    # 图像分析工具
    "ImageAnalysisTool",
    "BatchImageAnalysisTool",
    # 通知工具
    "SystemNotifyTool",
    "SoundAlertTool",
    "TaskCompletionNotifyTool",
    "notify",
    "alert",
    "task_complete",
]
