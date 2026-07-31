"""基础安全护栏"""
import re
from typing import Optional

from fastapi import HTTPException, status

from src.config.settings import Config

_PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all|previous|prior)\s+instructions",
    r"system\s+prompt",
    r"developer\s+message",
    r"reveal\s+(your|the)\s+(prompt|instructions)",
    r"bypass\s+(security|guardrails|restrictions)",
    r"act\s+as\s+root",
]


def validate_user_text(text: Optional[str], field_name: str = "question") -> None:
    """对用户输入做最小长度与注入检查。"""
    if not Config.ENABLE_SECURITY_GUARDRAILS or not text:
        return

    content = text.strip()
    if len(content) > Config.MAX_INPUT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"{field_name} 超过最大长度限制 ({Config.MAX_INPUT_CHARS} 字符)",
        )

    lowered = content.lower()
    for pattern in _PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} 触发安全护栏，请移除疑似提示词注入内容",
            )
