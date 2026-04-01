"""计算器工具 - 数学运算、单位换算、进制转换"""

import math
import ast
import operator
import logging
from typing import List, Dict, Any

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory

logger = logging.getLogger(__name__)


# 安全的数学运算符
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# 安全的数学函数
SAFE_MATH_FUNCS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "ceil": math.ceil,
    "floor": math.floor,
    "pi": math.pi,
    "e": math.e,
    "factorial": math.factorial,
    "gcd": math.gcd,
    "pow": pow,
}

# 单位换算表
UNIT_CONVERSIONS = {
    # 长度 (统一到米)
    "length": {
        "mm": 0.001, "毫米": 0.001,
        "cm": 0.01, "厘米": 0.01,
        "m": 1.0, "米": 1.0,
        "km": 1000.0, "千米": 1000.0, "公里": 1000.0,
        "inch": 0.0254, "英寸": 0.0254,
        "ft": 0.3048, "英尺": 0.3048,
        "yard": 0.9144, "码": 0.9144,
        "mile": 1609.344, "英里": 1609.344,
        "里": 500.0,
    },
    # 重量 (统一到千克)
    "weight": {
        "mg": 0.000001, "毫克": 0.000001,
        "g": 0.001, "克": 0.001,
        "kg": 1.0, "千克": 1.0, "公斤": 1.0,
        "t": 1000.0, "吨": 1000.0,
        "oz": 0.0283495, "盎司": 0.0283495,
        "lb": 0.453592, "磅": 0.453592,
        "斤": 0.5, "两": 0.05,
    },
    # 温度 (特殊处理)
    "temperature": {
        "℃": "celsius", "摄氏度": "celsius", "C": "celsius",
        "℉": "fahrenheit", "华氏度": "fahrenheit", "F": "fahrenheit",
        "K": "kelvin", "开尔文": "kelvin",
    },
    # 面积 (统一到平方米)
    "area": {
        "mm²": 0.000001, "cm²": 0.0001,
        "m²": 1.0, "平方米": 1.0,
        "km²": 1000000.0, "平方公里": 1000000.0,
        "亩": 666.667, "公顷": 10000.0,
        "ft²": 0.092903, "平方英尺": 0.092903,
        "acre": 4046.86, "英亩": 4046.86,
    },
    # 数据存储 (统一到字节)
    "data": {
        "B": 1, "字节": 1,
        "KB": 1024, "千字节": 1024,
        "MB": 1024**2, "兆字节": 1024**2,
        "GB": 1024**3, "吉字节": 1024**3,
        "TB": 1024**4, "太字节": 1024**4,
        "PB": 1024**5,
    },
    # 时间 (统一到秒)
    "time": {
        "ms": 0.001, "毫秒": 0.001,
        "s": 1.0, "秒": 1.0,
        "min": 60.0, "分钟": 60.0,
        "h": 3600.0, "小时": 3600.0,
        "day": 86400.0, "天": 86400.0,
        "week": 604800.0, "周": 604800.0,
        "month": 2592000.0, "月": 2592000.0,
        "year": 31536000.0, "年": 31536000.0,
    },
    # 速度 (统一到 m/s)
    "speed": {
        "m/s": 1.0,
        "km/h": 0.277778, "千米/时": 0.277778, "公里/小时": 0.277778,
        "mph": 0.44704, "英里/时": 0.44704,
        "knot": 0.514444, "节": 0.514444,
    },
}


def _safe_eval(expression: str) -> float:
    """安全地计算数学表达式（只允许基本运算和数学函数）"""
    # 预处理：支持中文运算符
    expression = expression.replace("×", "*").replace("÷", "/").replace("（", "(").replace("）", ")")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"表达式语法错误: {e}")

    def _eval_node(node):
        if isinstance(node, ast.Expression):
            return _eval_node(node.body)
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"不允许的常量类型: {type(node.value)}")
        elif isinstance(node, ast.BinOp):
            op_func = SAFE_OPERATORS.get(type(node.op))
            if not op_func:
                raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
            left = _eval_node(node.left)
            right = _eval_node(node.right)
            if isinstance(node.op, ast.Pow) and right > 1000:
                raise ValueError("指数过大，请使用较小的值")
            return op_func(left, right)
        elif isinstance(node, ast.UnaryOp):
            op_func = SAFE_OPERATORS.get(type(node.op))
            if not op_func:
                raise ValueError(f"不支持的一元运算符: {type(node.op).__name__}")
            return op_func(_eval_node(node.operand))
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in SAFE_MATH_FUNCS:
                func = SAFE_MATH_FUNCS[node.func.id]
                args = [_eval_node(arg) for arg in node.args]
                if callable(func):
                    return func(*args)
                return func  # 常量如 pi, e
            raise ValueError(f"不允许调用函数: {getattr(node.func, 'id', '?')}")
        elif isinstance(node, ast.Name):
            if node.id in SAFE_MATH_FUNCS:
                val = SAFE_MATH_FUNCS[node.id]
                if not callable(val):
                    return val
            raise ValueError(f"未知变量: {node.id}")
        else:
            raise ValueError(f"不支持的表达式节点: {type(node).__name__}")

    return _eval_node(tree)


class CalculatorTool(BaseTool):
    """安全数学计算器"""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return (
            "安全数学计算器，支持加减乘除、幂运算、常用数学函数(sqrt, sin, cos, log等)。"
            "支持中文运算符(×÷)。用于精确数学计算。"
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "expression",
                "type": "string",
                "description": "数学表达式，如 '2 + 3 * 4'、'sqrt(144)'、'log(100, 10)'",
                "required": True,
            }
        ]

    def execute(self, **kwargs) -> ToolResult:
        expression = kwargs.get("expression", "")
        if not expression:
            return ToolResult(success=False, output="", error="请提供数学表达式")

        try:
            result = _safe_eval(expression)
            # 格式化输出
            if isinstance(result, float) and result == int(result) and abs(result) < 1e15:
                display = str(int(result))
            elif isinstance(result, float):
                display = f"{result:.10g}"
            else:
                display = str(result)

            output = f"🔢 计算结果\n{expression} = {display}"
            return ToolResult(success=True, output=output, data={"expression": expression, "result": result})
        except ValueError as e:
            return ToolResult(success=False, output="", error=str(e))
        except ZeroDivisionError:
            return ToolResult(success=False, output="", error="除零错误")
        except OverflowError:
            return ToolResult(success=False, output="", error="数值溢出，结果太大")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"计算错误: {e}")


class UnitConverterTool(BaseTool):
    """单位换算工具"""

    @property
    def name(self) -> str:
        return "unit_converter"

    @property
    def description(self) -> str:
        return (
            "单位换算工具，支持长度、重量、温度、面积、数据存储、时间、速度等单位换算。"
            "支持中文单位(如 公里、千克、摄氏度)。"
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "value",
                "type": "number",
                "description": "要换算的数值",
                "required": True,
            },
            {
                "name": "from_unit",
                "type": "string",
                "description": "原始单位，如 'km'、'千米'、'℃'",
                "required": True,
            },
            {
                "name": "to_unit",
                "type": "string",
                "description": "目标单位，如 'mile'、'英里'、'℉'",
                "required": True,
            },
        ]

    def _find_category(self, unit: str) -> tuple:
        """查找单位所在的分类"""
        for cat, units in UNIT_CONVERSIONS.items():
            if unit in units:
                return cat, units[unit]
        return None, None

    def _convert_temperature(self, value: float, from_type: str, to_type: str) -> float:
        """温度特殊换算"""
        # 先转为摄氏度
        if from_type == "fahrenheit":
            celsius = (value - 32) * 5 / 9
        elif from_type == "kelvin":
            celsius = value - 273.15
        else:
            celsius = value

        # 从摄氏度转目标
        if to_type == "fahrenheit":
            return celsius * 9 / 5 + 32
        elif to_type == "kelvin":
            return celsius + 273.15
        return celsius

    def execute(self, **kwargs) -> ToolResult:
        try:
            value = float(kwargs.get("value", 0))
        except (ValueError, TypeError):
            return ToolResult(success=False, output="", error="请提供有效的数值")

        from_unit = kwargs.get("from_unit", "")
        to_unit = kwargs.get("to_unit", "")

        from_cat, from_factor = self._find_category(from_unit)
        to_cat, to_factor = self._find_category(to_unit)

        if from_cat is None:
            return ToolResult(success=False, output="", error=f"不支持的单位: {from_unit}")
        if to_cat is None:
            return ToolResult(success=False, output="", error=f"不支持的单位: {to_unit}")
        if from_cat != to_cat:
            return ToolResult(success=False, output="", error=f"不能在 {from_cat} 和 {to_cat} 之间换算")

        # 温度特殊处理
        if from_cat == "temperature":
            result = self._convert_temperature(value, from_factor, to_factor)
        else:
            # 通用换算: 先转为基准单位，再转为目标单位
            base_value = value * from_factor
            result = base_value / to_factor

        output = f"📐 单位换算\n{value} {from_unit} = {result:.6g} {to_unit}"
        return ToolResult(
            success=True,
            output=output,
            data={"value": value, "from_unit": from_unit, "to_unit": to_unit, "result": result},
        )


class BaseConverterTool(BaseTool):
    """进制转换工具"""

    @property
    def name(self) -> str:
        return "base_converter"

    @property
    def description(self) -> str:
        return "进制转换工具，支持二进制、八进制、十进制、十六进制之间的相互转换。"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "value",
                "type": "string",
                "description": "要转换的数值，如 '255'、'0xFF'、'0b11111111'、'0o377'",
                "required": True,
            },
            {
                "name": "from_base",
                "type": "integer",
                "description": "原始进制: 2(二进制), 8(八进制), 10(十进制), 16(十六进制)。如果值带有前缀(0x/0b/0o)可自动检测。",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> ToolResult:
        value_str = str(kwargs.get("value", "")).strip()
        from_base = kwargs.get("from_base")

        if not value_str:
            return ToolResult(success=False, output="", error="请提供要转换的数值")

        try:
            # 自动检测进制
            if from_base:
                decimal_value = int(value_str, int(from_base))
            elif value_str.startswith(("0x", "0X")):
                decimal_value = int(value_str, 16)
            elif value_str.startswith(("0b", "0B")):
                decimal_value = int(value_str, 2)
            elif value_str.startswith(("0o", "0O")):
                decimal_value = int(value_str, 8)
            else:
                decimal_value = int(value_str)

            output = (
                f"🔄 进制转换: {value_str}\n"
                f"  十进制:   {decimal_value}\n"
                f"  二进制:   {bin(decimal_value)}\n"
                f"  八进制:   {oct(decimal_value)}\n"
                f"  十六进制: {hex(decimal_value).upper().replace('X', 'x')}"
            )
            return ToolResult(
                success=True,
                output=output,
                data={
                    "decimal": decimal_value,
                    "binary": bin(decimal_value),
                    "octal": oct(decimal_value),
                    "hex": hex(decimal_value),
                },
            )
        except ValueError:
            return ToolResult(success=False, output="", error=f"无法将 '{value_str}' 转换为数值，请检查进制是否正确")
