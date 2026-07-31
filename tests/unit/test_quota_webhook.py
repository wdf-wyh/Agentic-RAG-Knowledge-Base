"""配额与 Webhook 单元测试。"""
from fastapi import HTTPException

from src.config import settings
from src.services.quota_service import QuotaService
from src.services.webhook_service import WebhookService


def test_quota_estimate_and_record():
    service = QuotaService()
    usage = service.record_query(
        "tenant-a",
        question="你好世界" * 10,
        provider="deepseek",
        estimated_output_tokens=100,
    )
    assert usage["query_count"] == 1
    assert usage["estimated_input_tokens"] > 0
    assert usage["estimated_output_tokens"] == 100
    assert usage["estimated_cost_usd"] >= 0


def test_quota_enforcement_blocks(monkeypatch):
    monkeypatch.setattr(settings.Config, "ENABLE_QUOTA_ENFORCEMENT", True)
    monkeypatch.setattr(settings.Config, "QUOTA_DAILY_QUERIES", 1)
    service = QuotaService()
    service.record_query("tenant-b", question="q1", estimated_output_tokens=1)
    decision = service.evaluate("tenant-b")
    assert decision.allowed is False
    try:
        service.ensure_allowed("tenant-b")
        assert False, "should raise"
    except HTTPException as exc:
        assert exc.status_code == 429


def test_webhook_subscription_and_sign(monkeypatch):
    monkeypatch.setattr(settings.Config, "WEBHOOK_URL", "http://example.local/hook")
    monkeypatch.setattr(settings.Config, "WEBHOOK_SECRET", "secret")
    monkeypatch.setattr(settings.Config, "WEBHOOK_EVENTS", "quota.exceeded,webhook.test")
    service = WebhookService()
    assert service.enabled() is True
    assert service.subscribed("quota.exceeded") is True
    assert service.subscribed("unknown.event") is False
    signature = service._sign(b'{"ok":true}')
    assert signature.startswith("sha256=")
