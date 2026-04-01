"""翻译工具 - 利用 LLM 进行多语言翻译"""

import logging
from typing import List, Dict, Any

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory
from src.config.settings import Config

logger = logging.getLogger(__name__)


# 支持的语言列表
SUPPORTED_LANGUAGES = {
    "zh": "中文", "en": "英语", "ja": "日语", "ko": "韩语",
    "fr": "法语", "de": "德语", "es": "西班牙语", "pt": "葡萄牙语",
    "ru": "俄语", "ar": "阿拉伯语", "it": "意大利语", "nl": "荷兰语",
    "th": "泰语", "vi": "越南语",
    # 中文别名
    "中文": "中文", "英语": "英语", "日语": "日语", "韩语": "韩语",
    "法语": "法语", "德语": "德语", "西班牙语": "西班牙语",
    "俄语": "俄语", "阿拉伯语": "阿拉伯语",
}


class TranslateTool(BaseTool):
    """LLM 翻译工具"""

    @property
    def name(self) -> str:
        return "translate"

    @property
    def description(self) -> str:
        return (
            "文本翻译工具，利用大语言模型在多种语言之间进行翻译。"
            "支持中文、英语、日语、韩语、法语、德语、西班牙语等。"
            "可自动检测源语言。"
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
                "description": "要翻译的文本",
                "required": True,
            },
            {
                "name": "target_language",
                "type": "string",
                "description": "目标语言，如 'en'(英语), 'zh'(中文), 'ja'(日语)。也支持中文名如 '英语'、'日语'。",
                "required": True,
            },
            {
                "name": "source_language",
                "type": "string",
                "description": "源语言(可选)，不指定则自动检测。",
                "required": False,
            },
            {
                "name": "style",
                "type": "string",
                "description": "翻译风格(可选): 'formal'(正式), 'casual'(口语化), 'technical'(技术文档), 'literary'(文学)。默认自动判断。",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> ToolResult:
        text = kwargs.get("text", "")
        target_lang = kwargs.get("target_language", "zh")
        source_lang = kwargs.get("source_language", "")
        style = kwargs.get("style", "")

        if not text:
            return ToolResult(success=False, output="", error="请提供要翻译的文本")

        # 解析目标语言
        target_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
        source_name = SUPPORTED_LANGUAGES.get(source_lang, source_lang) if source_lang else "自动检测"

        # 构建翻译提示
        style_instruction = ""
        if style == "formal":
            style_instruction = "请使用正式、书面的语言风格。"
        elif style == "casual":
            style_instruction = "请使用口语化、自然的语言风格。"
        elif style == "technical":
            style_instruction = "请使用精确的技术术语，保持专业性。"
        elif style == "literary":
            style_instruction = "请使用优美、文学化的语言风格。"

        prompt = (
            f"请将以下文本翻译为{target_name}。\n"
            f"{'源语言: ' + source_name + '。' if source_lang else ''}\n"
            f"{style_instruction}\n"
            f"只输出翻译结果，不要添加任何解释或额外内容。\n\n"
            f"原文:\n{text}"
        )

        try:
            import requests
            config = Config()
            response = requests.post(
                f"{config.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": config.MODEL_NAME,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3},
                },
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()
            translated = result.get("response", "").strip()

            if not translated:
                return ToolResult(success=False, output="", error="翻译结果为空")

            output = (
                f"🌐 翻译结果 ({source_name} → {target_name})"
                f"{' [' + style + ']' if style else ''}\n\n"
                f"原文:\n{text[:500]}{'...' if len(text) > 500 else ''}\n\n"
                f"译文:\n{translated}"
            )
            return ToolResult(
                success=True,
                output=output,
                data={
                    "original": text,
                    "translated": translated,
                    "source_language": source_name,
                    "target_language": target_name,
                    "style": style or "default",
                },
            )
        except requests.exceptions.ConnectionError:
            return ToolResult(success=False, output="", error="无法连接到 Ollama 服务，请确保 Ollama 正在运行。")
        except Exception as e:
            logger.error(f"翻译失败: {e}")
            return ToolResult(success=False, output="", error=f"翻译失败: {e}")


class LanguageDetectTool(BaseTool):
    """语言检测工具"""

    @property
    def name(self) -> str:
        return "detect_language"

    @property
    def description(self) -> str:
        return "检测文本的语言类型。支持识别中文、英语、日语、韩语等多种语言。"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "text",
                "type": "string",
                "description": "要检测语言的文本",
                "required": True,
            }
        ]

    def execute(self, **kwargs) -> ToolResult:
        import re
        text = kwargs.get("text", "")
        if not text:
            return ToolResult(success=False, output="", error="请提供要检测的文本")

        # 基于字符集的简单语言检测
        scores = {}
        total = len(text.replace(" ", "").replace("\n", ""))
        if total == 0:
            return ToolResult(success=False, output="", error="文本为空")

        chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
        japanese_kana = len(re.findall(r"[\u3040-\u309f\u30a0-\u30ff]", text))
        korean = len(re.findall(r"[\uac00-\ud7af\u1100-\u11ff]", text))
        cyrillic = len(re.findall(r"[\u0400-\u04ff]", text))
        arabic = len(re.findall(r"[\u0600-\u06ff]", text))
        latin = len(re.findall(r"[a-zA-Z]", text))
        thai = len(re.findall(r"[\u0e00-\u0e7f]", text))

        if chinese > 0:
            scores["中文"] = chinese / total
        if japanese_kana > 0:
            scores["日语"] = (japanese_kana + chinese * 0.3) / total  # 日语也用汉字
        if korean > 0:
            scores["韩语"] = korean / total
        if cyrillic > 0:
            scores["俄语"] = cyrillic / total
        if arabic > 0:
            scores["阿拉伯语"] = arabic / total
        if thai > 0:
            scores["泰语"] = thai / total
        if latin > 0 and not any([chinese, japanese_kana, korean, cyrillic, arabic, thai]):
            scores["英语(或其他拉丁语系)"] = latin / total

        if not scores:
            detected = "未知"
            confidence = 0.0
        else:
            detected = max(scores, key=scores.get)
            confidence = scores[detected]

        output = (
            f"🔤 语言检测\n"
            f"检测结果: {detected} (置信度: {confidence:.1%})\n"
            f"文本片段: {text[:100]}{'...' if len(text) > 100 else ''}"
        )
        if len(scores) > 1:
            output += "\n其他可能: " + ", ".join(
                f"{lang}({score:.1%})" for lang, score in sorted(scores.items(), key=lambda x: -x[1]) if lang != detected
            )

        return ToolResult(
            success=True,
            output=output,
            data={"detected_language": detected, "confidence": confidence, "scores": scores},
        )
