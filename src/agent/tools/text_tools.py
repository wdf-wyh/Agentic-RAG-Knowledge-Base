"""文本处理工具 - 字数统计、编码解码、正则匹配、文本格式转换"""

import re
import json
import hashlib
import base64
import urllib.parse
import logging
from typing import List, Dict, Any
from collections import Counter

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory

logger = logging.getLogger(__name__)


class WordCountTool(BaseTool):
    """文本统计工具"""

    @property
    def name(self) -> str:
        return "word_count"

    @property
    def description(self) -> str:
        return "统计文本的字数、词数、行数、段落数等信息。支持中英文混合文本。"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "text",
                "type": "string",
                "description": "要统计的文本内容",
                "required": True,
            }
        ]

    def execute(self, **kwargs) -> ToolResult:
        text = kwargs.get("text", "")
        if not text:
            return ToolResult(success=False, output="", error="请提供要统计的文本")

        # 基本统计
        char_count = len(text)
        char_no_space = len(text.replace(" ", "").replace("\n", "").replace("\t", ""))
        lines = text.split("\n")
        line_count = len(lines)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        para_count = len(paragraphs)

        # 中文字符统计
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))

        # 英文单词统计
        english_words = len(re.findall(r"[a-zA-Z]+", text))

        # 数字统计
        numbers = len(re.findall(r"\d+", text))

        # 标点统计
        punctuation = len(re.findall(r"[^\w\s]", text))

        # 预估阅读时间（中文约500字/分钟，英文约200词/分钟）
        reading_time_min = max(chinese_chars / 500, english_words / 200)

        output = (
            f"📝 文本统计\n"
            f"  总字符数: {char_count}（不含空白: {char_no_space}）\n"
            f"  中文字符: {chinese_chars}\n"
            f"  英文单词: {english_words}\n"
            f"  数字: {numbers}\n"
            f"  标点符号: {punctuation}\n"
            f"  行数: {line_count}\n"
            f"  段落数: {para_count}\n"
            f"  预估阅读时间: {reading_time_min:.1f} 分钟"
        )
        return ToolResult(
            success=True,
            output=output,
            data={
                "char_count": char_count,
                "char_no_space": char_no_space,
                "chinese_chars": chinese_chars,
                "english_words": english_words,
                "numbers": numbers,
                "line_count": line_count,
                "para_count": para_count,
                "reading_time_minutes": round(reading_time_min, 1),
            },
        )


class TextEncodingTool(BaseTool):
    """文本编码/解码工具"""

    @property
    def name(self) -> str:
        return "text_encoding"

    @property
    def description(self) -> str:
        return (
            "文本编码和解码工具。支持 Base64、URL编码、MD5/SHA256哈希、"
            "Unicode转义等操作。用于数据编码转换和生成文本摘要。"
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "text",
                "type": "string",
                "description": "要处理的文本",
                "required": True,
            },
            {
                "name": "operation",
                "type": "string",
                "description": "操作类型: 'base64_encode', 'base64_decode', 'url_encode', 'url_decode', 'md5', 'sha256', 'unicode_escape', 'unicode_unescape'",
                "required": True,
            },
        ]

    def execute(self, **kwargs) -> ToolResult:
        text = kwargs.get("text", "")
        operation = kwargs.get("operation", "")

        if not text:
            return ToolResult(success=False, output="", error="请提供要处理的文本")

        try:
            if operation == "base64_encode":
                result = base64.b64encode(text.encode("utf-8")).decode("ascii")
            elif operation == "base64_decode":
                result = base64.b64decode(text).decode("utf-8")
            elif operation == "url_encode":
                result = urllib.parse.quote(text, safe="")
            elif operation == "url_decode":
                result = urllib.parse.unquote(text)
            elif operation == "md5":
                result = hashlib.md5(text.encode("utf-8")).hexdigest()
            elif operation == "sha256":
                result = hashlib.sha256(text.encode("utf-8")).hexdigest()
            elif operation == "unicode_escape":
                result = text.encode("unicode_escape").decode("ascii")
            elif operation == "unicode_unescape":
                result = text.encode("utf-8").decode("unicode_escape")
            else:
                return ToolResult(success=False, output="", error=f"不支持的操作: {operation}")

            output = f"🔐 文本编码 ({operation})\n输入: {text[:100]}{'...' if len(text) > 100 else ''}\n结果: {result}"
            return ToolResult(success=True, output=output, data={"result": result, "operation": operation})
        except Exception as e:
            return ToolResult(success=False, output="", error=f"编码/解码错误: {e}")


class RegexTool(BaseTool):
    """正则表达式工具"""

    @property
    def name(self) -> str:
        return "regex_match"

    @property
    def description(self) -> str:
        return "正则表达式匹配工具。在文本中搜索匹配正则模式的内容，提取手机号、邮箱、URL等信息。"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "text",
                "type": "string",
                "description": "要搜索的文本",
                "required": True,
            },
            {
                "name": "pattern",
                "type": "string",
                "description": "正则表达式模式。也可以使用预设: 'email'(邮箱), 'phone'(手机号), 'url'(网址), 'ip'(IP地址), 'date'(日期)",
                "required": True,
            },
            {
                "name": "replace_with",
                "type": "string",
                "description": "替换文本（可选）。提供此参数时执行替换操作。",
                "required": False,
            },
        ]

    # 预设模式
    PRESETS = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone": r"1[3-9]\d{9}",
        "url": r"https?://[^\s<>\"']+",
        "ip": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        "date": r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",
        "chinese": r"[\u4e00-\u9fff]+",
    }

    def execute(self, **kwargs) -> ToolResult:
        text = kwargs.get("text", "")
        pattern = kwargs.get("pattern", "")
        replace_with = kwargs.get("replace_with")

        if not text or not pattern:
            return ToolResult(success=False, output="", error="请提供文本和正则表达式")

        # 使用预设模式
        actual_pattern = self.PRESETS.get(pattern, pattern)

        try:
            compiled = re.compile(actual_pattern)
        except re.error as e:
            return ToolResult(success=False, output="", error=f"正则表达式错误: {e}")

        if replace_with is not None:
            # 替换模式
            result = compiled.sub(replace_with, text)
            count = len(compiled.findall(text))
            output = f"🔍 正则替换 (替换了 {count} 处)\n模式: {actual_pattern}\n结果:\n{result[:2000]}"
            return ToolResult(success=True, output=output, data={"result": result, "count": count})
        else:
            # 匹配模式
            matches = compiled.findall(text)
            if not matches:
                output = f"🔍 正则匹配\n模式: {actual_pattern}\n未找到匹配项"
            else:
                match_list = matches[:50]  # 限制返回数量
                output = (
                    f"🔍 正则匹配 (找到 {len(matches)} 个匹配)\n"
                    f"模式: {actual_pattern}\n"
                    f"匹配结果:\n" + "\n".join(f"  {i+1}. {m}" for i, m in enumerate(match_list))
                )
                if len(matches) > 50:
                    output += f"\n  ... 还有 {len(matches) - 50} 个匹配"

            return ToolResult(success=True, output=output, data={"matches": matches[:100], "count": len(matches)})


class JsonFormatterTool(BaseTool):
    """JSON 格式化和验证工具"""

    @property
    def name(self) -> str:
        return "json_formatter"

    @property
    def description(self) -> str:
        return "JSON 格式化、压缩、验证工具。可以美化JSON、压缩JSON、提取JSON中的指定字段。"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "text",
                "type": "string",
                "description": "JSON 文本",
                "required": True,
            },
            {
                "name": "operation",
                "type": "string",
                "description": "操作: 'format'(美化), 'minify'(压缩), 'validate'(验证), 'extract'(提取字段)",
                "required": False,
            },
            {
                "name": "path",
                "type": "string",
                "description": "JSON路径(用于extract操作)，用.分隔，如 'data.items.0.name'",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> ToolResult:
        text = kwargs.get("text", "")
        operation = kwargs.get("operation", "format")
        json_path = kwargs.get("path", "")

        if not text:
            return ToolResult(success=False, output="", error="请提供 JSON 文本")

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            return ToolResult(
                success=False,
                output=f"❌ JSON 验证失败\n错误: {e}\n位置: 第 {e.lineno} 行, 第 {e.colno} 列",
                error=f"JSON 解析错误: {e}",
            )

        if operation == "format":
            result = json.dumps(data, indent=2, ensure_ascii=False)
            output = f"📋 JSON 格式化\n{result[:5000]}"
        elif operation == "minify":
            result = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
            output = f"📋 JSON 压缩\n{result[:5000]}"
        elif operation == "validate":
            info = self._analyze_json(data)
            output = f"✅ JSON 有效\n{info}"
            return ToolResult(success=True, output=output, data={"valid": True})
        elif operation == "extract":
            if not json_path:
                return ToolResult(success=False, output="", error="extract 操作需要提供 path 参数")
            try:
                value = data
                for key in json_path.split("."):
                    if isinstance(value, list):
                        value = value[int(key)]
                    elif isinstance(value, dict):
                        value = value[key]
                    else:
                        return ToolResult(success=False, output="", error=f"无法在路径 '{json_path}' 中导航")
                result = json.dumps(value, indent=2, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
                output = f"📋 JSON 提取 ({json_path})\n{result[:5000]}"
            except (KeyError, IndexError, ValueError) as e:
                return ToolResult(success=False, output="", error=f"路径 '{json_path}' 无效: {e}")
        else:
            return ToolResult(success=False, output="", error=f"不支持的操作: {operation}")

        return ToolResult(success=True, output=output, data={"result": data})

    def _analyze_json(self, data: Any, depth: int = 0) -> str:
        """分析 JSON 结构"""
        lines = []
        if isinstance(data, dict):
            lines.append(f"类型: Object, 字段数: {len(data)}")
            lines.append(f"字段: {', '.join(list(data.keys())[:20])}")
        elif isinstance(data, list):
            lines.append(f"类型: Array, 元素数: {len(data)}")
            if data:
                lines.append(f"首个元素类型: {type(data[0]).__name__}")
        else:
            lines.append(f"类型: {type(data).__name__}, 值: {str(data)[:100]}")
        return "\n".join(lines)


class TextDiffTool(BaseTool):
    """文本对比工具"""

    @property
    def name(self) -> str:
        return "text_diff"

    @property
    def description(self) -> str:
        return "对比两段文本的差异，显示新增、删除和修改的内容。"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {"name": "text1", "type": "string", "description": "第一段文本（原文）", "required": True},
            {"name": "text2", "type": "string", "description": "第二段文本（新文本）", "required": True},
        ]

    def execute(self, **kwargs) -> ToolResult:
        import difflib

        text1 = kwargs.get("text1", "")
        text2 = kwargs.get("text2", "")

        if not text1 and not text2:
            return ToolResult(success=False, output="", error="请提供两段要对比的文本")

        lines1 = text1.splitlines(keepends=True)
        lines2 = text2.splitlines(keepends=True)

        diff = list(difflib.unified_diff(lines1, lines2, fromfile="原文", tofile="新文本", lineterm=""))

        if not diff:
            output = "✅ 两段文本完全相同"
            return ToolResult(success=True, output=output, data={"identical": True, "changes": 0})

        added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

        diff_text = "\n".join(diff[:200])
        output = (
            f"📊 文本对比\n"
            f"新增 {added} 行, 删除 {removed} 行\n\n"
            f"{diff_text}"
        )
        if len(diff) > 200:
            output += f"\n... 还有 {len(diff) - 200} 行差异"

        return ToolResult(
            success=True,
            output=output,
            data={"identical": False, "added": added, "removed": removed},
        )
