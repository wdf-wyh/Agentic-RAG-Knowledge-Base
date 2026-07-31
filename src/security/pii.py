"""PII 检测与脱敏。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from src.config.settings import Config

_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    ("phone_cn", re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)"), "[PHONE]"),
    ("id_card_cn", re.compile(r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)"), "[ID_CARD]"),
    ("bank_card", re.compile(r"(?<!\d)(?:62|4\d|5[1-5])\d{14,17}(?!\d)"), "[BANK_CARD]"),
    ("ipv4", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"), "[IP]"),
]


@dataclass
class PiiFinding:
    kind: str
    count: int


def detect_pii(text: str) -> List[PiiFinding]:
    if not text:
        return []
    findings: list[PiiFinding] = []
    for kind, pattern, _ in _PATTERNS:
        matches = pattern.findall(text)
        if matches:
            findings.append(PiiFinding(kind=kind, count=len(matches)))
    return findings


def redact_pii(text: str) -> Tuple[str, List[PiiFinding]]:
    """对文本做 PII 脱敏，返回脱敏后文本与命中统计。"""
    if not text or not Config.ENABLE_PII_REDACTION:
        return text, []

    findings = detect_pii(text)
    if not findings:
        return text, []

    redacted = text
    for _, pattern, replacement in _PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted, findings


def sanitize_output_text(text: str) -> str:
    redacted, _ = redact_pii(text)
    return redacted
