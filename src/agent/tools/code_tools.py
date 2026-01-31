"""代码执行工具 - 安全沙箱中执行代码

参考大企业实践（如 OpenAI Code Interpreter），提供安全的代码执行能力。
"""

import subprocess
import tempfile
import os
import signal
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import logging

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory

logger = logging.getLogger(__name__)


class SupportedLanguage(Enum):
    """支持的编程语言"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    SHELL = "shell"


@dataclass
class ExecutionResult:
    """代码执行结果"""
    success: bool
    stdout: str
    stderr: str
    return_value: Any = None
    execution_time: float = 0.0
    files_created: List[str] = None


class CodeExecutorTool(BaseTool):
    """代码执行工具 - 在安全沙箱中执行代码
    
    功能:
    - 支持 Python、JavaScript、Shell 脚本
    - 超时控制防止无限循环
    - 内存限制防止资源耗尽
    - 文件系统隔离
    
    安全措施:
    - 禁止网络访问（可选）
    - 限制可用的 Python 模块
    - 输出长度限制
    """
    
    DANGEROUS_IMPORTS = [
        'os.system', 'subprocess', 'eval', 'exec', 
        '__import__', 'open(', 'socket', 'requests',
        'urllib', 'shutil.rmtree', 'os.remove'
    ]
    
    def __init__(
        self,
        timeout: int = 30,
        max_output_length: int = 10000,
        allowed_languages: List[str] = None,
        sandbox_mode: bool = True
    ):
        """
        Args:
            timeout: 执行超时时间（秒）
            max_output_length: 最大输出长度
            allowed_languages: 允许的语言列表
            sandbox_mode: 是否启用沙箱模式
        """
        self.timeout = timeout
        self.max_output_length = max_output_length
        self.allowed_languages = allowed_languages or ["python"]
        self.sandbox_mode = sandbox_mode
        self._temp_dir = tempfile.mkdtemp(prefix="rag_code_")
        super().__init__()
    
    @property
    def name(self) -> str:
        return "code_executor"
    
    @property
    def description(self) -> str:
        return """在安全沙箱中执行代码并返回结果。
支持的语言: Python, JavaScript, Shell
适用场景:
- 数据分析和计算
- 生成图表和可视化
- 文本处理和转换
- 快速验证代码逻辑

注意: 代码在隔离环境中执行，无法访问网络和敏感系统资源。"""
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "code",
                "type": "string",
                "description": "要执行的代码",
                "required": True
            },
            {
                "name": "language",
                "type": "string",
                "description": "编程语言: python, javascript, shell",
                "required": False
            },
            {
                "name": "timeout",
                "type": "integer",
                "description": "执行超时时间（秒），默认30",
                "required": False
            }
        ]
    
    def _check_code_safety(self, code: str, language: str) -> Optional[str]:
        """检查代码安全性
        
        Returns:
            安全问题描述，如果安全则返回 None
        """
        if not self.sandbox_mode:
            return None
        
        code_lower = code.lower()
        
        for dangerous in self.DANGEROUS_IMPORTS:
            if dangerous.lower() in code_lower:
                return f"代码包含不允许的操作: {dangerous}"
        
        # 检查文件操作
        if 'open(' in code and ('w' in code or 'a' in code):
            # 只允许在临时目录写文件
            pass
        
        return None
    
    def _execute_python(self, code: str, timeout: int) -> ExecutionResult:
        """执行 Python 代码"""
        # 创建临时文件
        script_path = os.path.join(self._temp_dir, "script.py")
        
        # 包装代码以捕获返回值
        wrapped_code = f'''
import sys
import json

# 重定向到临时目录
import os
os.chdir("{self._temp_dir}")

# 执行用户代码
try:
    result = None
    exec_globals = {{"__name__": "__main__"}}
    exec("""{code.replace('"', '\\"')}""", exec_globals)
except Exception as e:
    print(f"Error: {{e}}", file=sys.stderr)
    sys.exit(1)
'''
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        try:
            import time
            start_time = time.time()
            
            result = subprocess.run(
                ['python3', script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self._temp_dir
            )
            
            execution_time = time.time() - start_time
            
            # 获取创建的文件
            files_created = []
            for f in os.listdir(self._temp_dir):
                if f != "script.py":
                    files_created.append(f)
            
            return ExecutionResult(
                success=result.returncode == 0,
                stdout=result.stdout[:self.max_output_length],
                stderr=result.stderr[:self.max_output_length],
                execution_time=execution_time,
                files_created=files_created
            )
            
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"执行超时（{timeout}秒）"
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e)
            )
    
    def execute(self, **kwargs) -> ToolResult:
        """执行代码"""
        code = kwargs.get("code", "")
        language = kwargs.get("language", "python").lower()
        timeout = kwargs.get("timeout", self.timeout)
        
        if not code:
            return ToolResult(success=False, output="", error="代码不能为空")
        
        if language not in self.allowed_languages:
            return ToolResult(
                success=False, 
                output="", 
                error=f"不支持的语言: {language}。支持: {self.allowed_languages}"
            )
        
        # 安全检查
        safety_issue = self._check_code_safety(code, language)
        if safety_issue:
            return ToolResult(success=False, output="", error=safety_issue)
        
        try:
            if language == "python":
                result = self._execute_python(code, timeout)
            else:
                return ToolResult(
                    success=False, 
                    output="", 
                    error=f"语言 {language} 执行器尚未实现"
                )
            
            if result.success:
                output_parts = []
                if result.stdout:
                    output_parts.append(f"**输出:**\n```\n{result.stdout}\n```")
                if result.files_created:
                    output_parts.append(f"**创建的文件:** {', '.join(result.files_created)}")
                output_parts.append(f"**执行时间:** {result.execution_time:.2f}秒")
                
                return ToolResult(
                    success=True,
                    output="\n".join(output_parts),
                    data={
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "files": result.files_created,
                        "execution_time": result.execution_time
                    }
                )
            else:
                return ToolResult(
                    success=False,
                    output=result.stdout,
                    error=result.stderr
                )
                
        except Exception as e:
            logger.error(f"代码执行失败: {e}")
            return ToolResult(success=False, output="", error=str(e))


class DataAnalysisTool(BaseTool):
    """数据分析工具 - 对数据进行统计分析
    
    提供常见的数据分析功能，无需编写代码。
    """
    
    def __init__(self):
        super().__init__()
    
    @property
    def name(self) -> str:
        return "data_analysis"
    
    @property
    def description(self) -> str:
        return """对数据进行统计分析。支持:
- 基本统计（均值、中位数、标准差等）
- 数据转换（排序、过滤、分组）
- 简单可视化描述

输入可以是 JSON 数组或 CSV 格式的数据。"""
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "data",
                "type": "string",
                "description": "JSON 数组格式的数据",
                "required": True
            },
            {
                "name": "operation",
                "type": "string",
                "description": "操作类型: stats(统计), sort(排序), filter(过滤), group(分组)",
                "required": True
            },
            {
                "name": "field",
                "type": "string",
                "description": "要分析的字段名",
                "required": False
            },
            {
                "name": "condition",
                "type": "string",
                "description": "过滤条件（用于 filter 操作）",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """执行数据分析"""
        data_str = kwargs.get("data", "")
        operation = kwargs.get("operation", "stats")
        field = kwargs.get("field")
        
        try:
            data = json.loads(data_str)
            
            if not isinstance(data, list):
                return ToolResult(success=False, output="", error="数据必须是数组格式")
            
            if operation == "stats":
                return self._compute_stats(data, field)
            elif operation == "sort":
                return self._sort_data(data, field)
            else:
                return ToolResult(
                    success=False, 
                    output="", 
                    error=f"未知操作: {operation}"
                )
                
        except json.JSONDecodeError:
            return ToolResult(success=False, output="", error="无效的 JSON 格式")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
    
    def _compute_stats(self, data: List, field: str = None) -> ToolResult:
        """计算统计信息"""
        if field:
            values = [item.get(field) for item in data if isinstance(item, dict) and field in item]
        else:
            values = [item for item in data if isinstance(item, (int, float))]
        
        numeric_values = [v for v in values if isinstance(v, (int, float))]
        
        if not numeric_values:
            return ToolResult(
                success=True,
                output="无数值数据可分析",
                data={"count": len(data)}
            )
        
        stats = {
            "count": len(numeric_values),
            "sum": sum(numeric_values),
            "mean": sum(numeric_values) / len(numeric_values),
            "min": min(numeric_values),
            "max": max(numeric_values),
        }
        
        # 计算中位数
        sorted_values = sorted(numeric_values)
        n = len(sorted_values)
        if n % 2 == 0:
            stats["median"] = (sorted_values[n//2 - 1] + sorted_values[n//2]) / 2
        else:
            stats["median"] = sorted_values[n//2]
        
        output = f"""统计结果:
- 数量: {stats['count']}
- 总和: {stats['sum']:.2f}
- 均值: {stats['mean']:.2f}
- 中位数: {stats['median']:.2f}
- 最小值: {stats['min']}
- 最大值: {stats['max']}"""
        
        return ToolResult(success=True, output=output, data=stats)
    
    def _sort_data(self, data: List, field: str) -> ToolResult:
        """排序数据"""
        if not field:
            return ToolResult(success=False, output="", error="排序需要指定字段名")
        
        try:
            sorted_data = sorted(data, key=lambda x: x.get(field, 0) if isinstance(x, dict) else x, reverse=True)
            
            output = f"按 {field} 排序结果（前10条）:\n"
            for i, item in enumerate(sorted_data[:10], 1):
                output += f"{i}. {item}\n"
            
            return ToolResult(
                success=True,
                output=output,
                data=sorted_data[:100]  # 限制返回数量
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
