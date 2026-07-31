"""PII 与 ABAC 单元测试。"""
from src.config import settings
from src.models.auth import UserIdentity
from src.security.abac import AbacEngine
from src.security.pii import detect_pii, redact_pii


def test_pii_redaction_email_phone_id():
    text = "联系我 email@example.com 或手机 13812345678，身份证 110101199001011234"
    findings = detect_pii(text)
    kinds = {item.kind for item in findings}
    assert "email" in kinds
    assert "phone_cn" in kinds
    assert "id_card_cn" in kinds

    redacted, _ = redact_pii(text)
    assert "email@example.com" not in redacted
    assert "13812345678" not in redacted
    assert "[EMAIL]" in redacted
    assert "[PHONE]" in redacted
    assert "[ID_CARD]" in redacted


def test_pii_disabled(monkeypatch):
    monkeypatch.setattr(settings.Config, "ENABLE_PII_REDACTION", False)
    text = "a@b.com"
    redacted, findings = redact_pii(text)
    assert redacted == text
    assert findings == []


def test_abac_admin_can_write_kb():
    engine = AbacEngine()
    admin = UserIdentity(username="a", user_id="1", roles=["admin"], tenant_id="default")
    decision = engine.evaluate(admin, "write", "knowledge_base")
    assert decision.allowed is True


def test_abac_user_cannot_delete_files(monkeypatch):
    monkeypatch.setattr(settings.Config, "ENABLE_ABAC", True)
    monkeypatch.setattr(settings.Config, "ENABLE_AUTH", True)
    engine = AbacEngine()
    user = UserIdentity(username="u", user_id="2", roles=["user"], tenant_id="tenant-demo")
    decision = engine.evaluate(user, "delete", "files")
    assert decision.allowed is False


def test_abac_auditor_can_read_audit(monkeypatch):
    monkeypatch.setattr(settings.Config, "ENABLE_ABAC", True)
    monkeypatch.setattr(settings.Config, "ENABLE_AUTH", True)
    engine = AbacEngine()
    auditor = UserIdentity(username="r", user_id="3", roles=["auditor"], tenant_id="default")
    decision = engine.evaluate(auditor, "read", "audit")
    assert decision.allowed is True
