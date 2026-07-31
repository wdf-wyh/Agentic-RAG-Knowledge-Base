"""审计日志服务"""
import json
from pathlib import Path
from threading import Lock
from typing import List

from src.config.settings import Config
from src.models.audit import AuditEvent


class AuditService:
    """以 JSONL 方式落盘审计事件，便于后续接入外部系统。"""

    def __init__(self, storage_path: str | None = None):
        base_path = storage_path or Config.AUDIT_LOG_PATH
        self.storage_path = Path(base_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def record(self, event: AuditEvent) -> None:
        line = json.dumps(event.model_dump(), ensure_ascii=False)
        with self._lock:
            with self.storage_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        try:
            from src.services.webhook_service import get_webhook_service

            get_webhook_service().emit(event.action, event.model_dump())
        except Exception:
            # Webhook 失败不影响主流程
            pass

    def list_events(self, limit: int = 100) -> List[dict]:
        if not self.storage_path.exists():
            return []

        with self._lock:
            lines = self.storage_path.read_text(encoding="utf-8").splitlines()

        events = []
        for line in reversed(lines[-limit:]):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events


_audit_service: AuditService | None = None


def get_audit_service() -> AuditService:
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service
