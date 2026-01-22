"""工具基类和通用工具定义"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class ToolCategory(Enum):
    """工具分类"""
    RETRIEVAL = "retrieval"      # 检索类
    FILE_OPERATION = "file"      # 文件操作类
    WEB_SEARCH = "web"           # 网页搜索类
    ANALYSIS = "analysis"        # 分析类
    NOTIFICATION = "notification" # 通知类
    UTILITY = "utility"          # 通用工具类


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: str
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """工具基类 - 所有工具必须继承此类"""
    
    def __init__(self):
        self._validate_definition()
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称（唯一标识）"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述（供 LLM 理解）"""
        pass
    
    @property
    @abstractmethod
    def category(self) -> ToolCategory:
        """工具分类"""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> List[Dict[str, Any]]:
        """工具参数列表
        
        Returns:
            参数列表，每个参数包含:
            - name: 参数名
            - type: 参数类型
            - description: 参数描述
            - required: 是否必需
        """
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """执行工具
        
        Args:
            **kwargs: 工具参数
            
        Returns:
            ToolResult 执行结果
        """
        pass
    
    def _validate_definition(self):
        """验证工具定义"""
        if not self.name:
            raise ValueError("工具必须有名称")
        if not self.description:
            raise ValueError("工具必须有描述")
    
    def _validate_params(self, **kwargs) -> Optional[str]:
        """验证输入参数
        
        Returns:
            错误信息，如果验证通过返回 None
        """
        for param in self.parameters:
            if param.get("required", True) and param["name"] not in kwargs:
                return f"缺少必需参数: {param['name']}"
        return None
    
    def __call__(self, **kwargs) -> ToolResult:
        """使工具可调用"""
        # 验证参数
        error = self._validate_params(**kwargs)
        if error:
            return ToolResult(success=False, output="", error=error)
        
        return self.execute(**kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "parameters": self.parameters
        }
    
    def to_function_schema(self) -> Dict[str, Any]:
        """转换为 OpenAI Function Calling 格式"""
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param["name"]] = {
                "type": param["type"],
                "description": param["description"]
            }
            if param.get("required", True):
                required.append(param["name"])
        
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }


class ToolRegistry:
    """工具注册表 - 管理所有可用工具"""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._categories: Dict[ToolCategory, List[str]] = {cat: [] for cat in ToolCategory}
    
    def register(self, tool: BaseTool):
        """注册工具"""
        if tool.name in self._tools:
            raise ValueError(f"工具 '{tool.name}' 已存在")
        
        self._tools[tool.name] = tool
        self._categories[tool.category].append(tool.name)
    
    def get(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self._tools.get(name)
    
    def get_by_category(self, category: ToolCategory) -> List[BaseTool]:
        """按分类获取工具"""
        return [self._tools[name] for name in self._categories[category]]
    
    def list_all(self) -> List[BaseTool]:
        """列出所有工具"""
        return list(self._tools.values())
    
    def get_descriptions(self) -> str:
        """获取所有工具描述"""
        descriptions = []
        for tool in self._tools.values():
            params_desc = ", ".join([
                f"{p['name']}: {p['type']}"
                for p in tool.parameters
            ])
            descriptions.append(f"- {tool.name}({params_desc}): {tool.description}")
        return "\n".join(descriptions)
    
    def to_function_schemas(self) -> List[Dict[str, Any]]:
        """转换为 OpenAI Function Calling 格式列表"""
        return [tool.to_function_schema() for tool in self._tools.values()]


# 全局工具注册表
global_registry = ToolRegistry()


def register_tool(tool: BaseTool):
    """注册工具到全局注册表"""
    global_registry.register(tool)
    return tool
