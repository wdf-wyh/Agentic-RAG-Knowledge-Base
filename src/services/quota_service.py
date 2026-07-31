"""租户成本与配额治理。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from threading import Lock
from typing import Dict, Optional

from fastapi import HTTPException, status

from src.config.settings import Config


# 粗略单价（USD / 1K tokens），用于成本估算治理，非账单结算
_PROVIDER_RATES = {
    "openai": {"input": 0.00015, "output": 0.0006},
    "deepseek": {"input": 0.00014, "output": 0.00028},
    "gemini": {"input": 0.0001, "output": 0.0004},
    "ollama": {"input": 0.0, "output": 0.0},
}


@dataclass
class TenantUsage:
    day: str
    query_count: int = 0
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    blocked_count: int = 0


@dataclass
class QuotaDecision:
    allowed: bool
    reason: str = ""
    usage: dict = field(default_factory=dict)
    limits: dict = field(default_factory=dict)


class QuotaService:
    """按租户按日统计查询量、估算 token 与成本，并做硬门禁。"""

    def __init__(self):
        self._lock = Lock()
        self._usage: Dict[str, TenantUsage] = {}

    @staticmethod
    def estimate_tokens(text: str) -> int:
        if not text:
            return 0
        # 中英混合粗估：约 4 字符 ≈ 1 token
        return max(1, len(text) // 4)

    @staticmethod
    def estimate_cost(provider: str, input_tokens: int, output_tokens: int) -> float:
        rates = _PROVIDER_RATES.get((provider or "").lower(), _PROVIDER_RATES["openai"])
        return (input_tokens / 1000.0) * rates["input"] + (output_tokens / 1000.0) * rates["output"]

    def _today(self) -> str:
        return date.today().isoformat()

    def _get_or_reset(self, tenant_id: str) -> TenantUsage:
        tenant = tenant_id or Config.DEFAULT_TENANT_ID
        today = self._today()
        usage = self._usage.get(tenant)
        if usage is None or usage.day != today:
            usage = TenantUsage(day=today)
            self._usage[tenant] = usage
        return usage

    def limits(self) -> dict:
        return {
            "daily_queries": Config.QUOTA_DAILY_QUERIES,
            "daily_tokens": Config.QUOTA_DAILY_TOKENS,
            "daily_cost_usd": Config.QUOTA_DAILY_COST_USD,
            "enforcement_enabled": Config.ENABLE_QUOTA_ENFORCEMENT,
        }

    def snapshot(self, tenant_id: Optional[str] = None) -> dict:
        with self._lock:
            if tenant_id:
                usage = self._get_or_reset(tenant_id)
                return {tenant_id: self._usage_dict(usage)}
            return {tid: self._usage_dict(self._get_or_reset(tid)) for tid in list(self._usage.keys())}

    def _usage_dict(self, usage: TenantUsage) -> dict:
        total_tokens = usage.estimated_input_tokens + usage.estimated_output_tokens
        return {
            "day": usage.day,
            "query_count": usage.query_count,
            "estimated_input_tokens": usage.estimated_input_tokens,
            "estimated_output_tokens": usage.estimated_output_tokens,
            "estimated_tokens": total_tokens,
            "estimated_cost_usd": round(usage.estimated_cost_usd, 6),
            "blocked_count": usage.blocked_count,
        }

    def evaluate(self, tenant_id: str) -> QuotaDecision:
        limits = self.limits()
        with self._lock:
            usage = self._usage_dict(self._get_or_reset(tenant_id))

        if not Config.ENABLE_QUOTA_ENFORCEMENT:
            return QuotaDecision(allowed=True, usage=usage, limits=limits)

        if usage["query_count"] >= Config.QUOTA_DAILY_QUERIES:
            return QuotaDecision(
                allowed=False,
                reason=f"已达每日查询上限 {Config.QUOTA_DAILY_QUERIES}",
                usage=usage,
                limits=limits,
            )
        if usage["estimated_tokens"] >= Config.QUOTA_DAILY_TOKENS:
            return QuotaDecision(
                allowed=False,
                reason=f"已达每日 token 上限 {Config.QUOTA_DAILY_TOKENS}",
                usage=usage,
                limits=limits,
            )
        if usage["estimated_cost_usd"] >= Config.QUOTA_DAILY_COST_USD:
            return QuotaDecision(
                allowed=False,
                reason=f"已达每日成本上限 ${Config.QUOTA_DAILY_COST_USD}",
                usage=usage,
                limits=limits,
            )
        return QuotaDecision(allowed=True, usage=usage, limits=limits)

    def ensure_allowed(self, tenant_id: str) -> QuotaDecision:
        decision = self.evaluate(tenant_id)
        if decision.allowed:
            return decision
        with self._lock:
            self._get_or_reset(tenant_id).blocked_count += 1
        try:
            from src.services.webhook_service import get_webhook_service

            get_webhook_service().emit(
                "quota.exceeded",
                {
                    "tenant_id": tenant_id,
                    "reason": decision.reason,
                    "usage": decision.usage,
                    "limits": decision.limits,
                },
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": decision.reason,
                "usage": decision.usage,
                "limits": decision.limits,
            },
        )

    def record_query(
        self,
        tenant_id: str,
        *,
        question: str = "",
        answer: str = "",
        provider: str = "",
        estimated_output_tokens: Optional[int] = None,
    ) -> dict:
        input_tokens = self.estimate_tokens(question)
        output_tokens = (
            estimated_output_tokens
            if estimated_output_tokens is not None
            else self.estimate_tokens(answer)
        )
        cost = self.estimate_cost(provider or Config.MODEL_PROVIDER, input_tokens, output_tokens)
        with self._lock:
            usage = self._get_or_reset(tenant_id)
            usage.query_count += 1
            usage.estimated_input_tokens += input_tokens
            usage.estimated_output_tokens += output_tokens
            usage.estimated_cost_usd += cost
            return self._usage_dict(usage)


_quota_service: QuotaService | None = None


def get_quota_service() -> QuotaService:
    global _quota_service
    if _quota_service is None:
        _quota_service = QuotaService()
    return _quota_service
