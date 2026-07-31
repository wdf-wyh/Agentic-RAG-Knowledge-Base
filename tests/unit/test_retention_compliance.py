"""数据保留与合规导出单元测试。"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.config import settings
from src.services.compliance_export_service import ComplianceExportService
from src.services.retention_service import RetentionService


def test_retention_cleanup_dry_run(tmp_path, monkeypatch):
    monkeypatch.setattr(settings.Config, "ENABLE_DATA_RETENTION", True)
    monkeypatch.setattr(settings.Config, "DATA_RETENTION_DAYS", 30)
    monkeypatch.setattr(settings.Config, "AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(settings.Config, "TRACE_STORAGE_PATH", str(tmp_path / "traces"))

    conv_dir = tmp_path / "conversations" / "tenant-a"
    conv_dir.mkdir(parents=True)
    old_ts = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    new_ts = datetime.now(timezone.utc).isoformat()
    (conv_dir / "old.json").write_text(
        json.dumps([{"role": "user", "content": "hi", "timestamp": old_ts}]),
        encoding="utf-8",
    )
    (conv_dir / "new.json").write_text(
        json.dumps([{"role": "user", "content": "hi", "timestamp": new_ts}]),
        encoding="utf-8",
    )

    trace_dir = tmp_path / "traces" / "tenant-a"
    trace_dir.mkdir(parents=True)
    (trace_dir / "old-trace.json").write_text(
        json.dumps({"created_at": old_ts.replace("T", " ")[:19], "trace_id": "1"}),
        encoding="utf-8",
    )

    audit_path = tmp_path / "audit.jsonl"
    audit_path.write_text(
        "\n".join(
            [
                json.dumps({"timestamp": old_ts, "tenant_id": "tenant-a", "action": "old"}),
                json.dumps({"timestamp": new_ts, "tenant_id": "tenant-a", "action": "new"}),
                json.dumps({"timestamp": old_ts, "tenant_id": "other", "action": "keep"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    service = RetentionService()
    service.conversation_root = tmp_path / "conversations"
    service.trace_root = tmp_path / "traces"
    service.audit_path = audit_path

    preview = service.cleanup(tenant_id="tenant-a", dry_run=True)
    assert preview["deleted_conversations"] == 1
    assert preview["deleted_traces"] == 1
    assert preview["trimmed_audit_events"] == 1
    assert (conv_dir / "old.json").exists()

    result = service.cleanup(tenant_id="tenant-a", dry_run=False)
    assert result["deleted_conversations"] == 1
    assert not (conv_dir / "old.json").exists()
    assert (conv_dir / "new.json").exists()
    assert not (trace_dir / "old-trace.json").exists()
    remaining = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line]
    actions = {item["action"] for item in remaining}
    assert "old" not in actions
    assert "new" in actions
    assert "keep" in actions


def test_compliance_export_zip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings.Config, "AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(settings.Config, "TRACE_STORAGE_PATH", str(tmp_path / "traces"))

    conv_dir = tmp_path / "conversations" / "tenant-b"
    conv_dir.mkdir(parents=True)
    (conv_dir / "c1.json").write_text("[]", encoding="utf-8")

    trace_dir = tmp_path / "traces" / "tenant-b"
    trace_dir.mkdir(parents=True)
    (trace_dir / "t1.json").write_text("{}", encoding="utf-8")

    (tmp_path / "audit.jsonl").write_text(
        json.dumps({"tenant_id": "tenant-b", "action": "auth.login"}) + "\n"
        + json.dumps({"tenant_id": "other", "action": "skip"}) + "\n",
        encoding="utf-8",
    )

    service = ComplianceExportService()
    # Monkeypatch roots by writing into CWD-relative paths used by service.
    # Use chdir to tmp_path so ./conversations resolves correctly.
    import os

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        content, filename = service.build_zip("tenant-b")
    finally:
        os.chdir(old_cwd)

    assert filename.startswith("compliance_tenant-b_")
    assert filename.endswith(".zip")
    assert content[:2] == b"PK"
