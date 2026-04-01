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
from src.agent.tools.aggregated_search import AggregatedSearchTool
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
# 新增工具
from src.agent.tools.datetime_tools import CurrentTimeTool, DateCalculatorTool, WorldClockTool
from src.agent.tools.calculator_tools import CalculatorTool, UnitConverterTool, BaseConverterTool
from src.agent.tools.text_tools import (
    WordCountTool,
    TextEncodingTool,
    RegexTool,
    JsonFormatterTool,
    TextDiffTool,
)
from src.agent.tools.translation_tools import TranslateTool, LanguageDetectTool
from src.agent.tools.system_tools import SystemInfoTool, ProcessListTool, NetworkInfoTool
from src.agent.tools.weather_tools import WeatherTool

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
    "AggregatedSearchTool",
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
    # 日期时间工具
    "CurrentTimeTool",
    "DateCalculatorTool",
    "WorldClockTool",
    # 计算器工具
    "CalculatorTool",
    "UnitConverterTool",
    "BaseConverterTool",
    # 文本处理工具
    "WordCountTool",
    "TextEncodingTool",
    "RegexTool",
    "JsonFormatterTool",
    "TextDiffTool",
    # 翻译工具
    "TranslateTool",
    "LanguageDetectTool",
    # 系统信息工具
    "SystemInfoTool",
    "ProcessListTool",
    "NetworkInfoTool",
    # 天气工具
    "WeatherTool",
]
