"""租户数据保留（TTL）清理服务。"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from src.config.settings import Config
from src.utils.tenant_paths import sanitize_tenant_id, tenant_scoped_path

logger = logging.getLogger(__name__)


def _parse_iso(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        # support "2024-01-01T12:00:00" and "2024-01-01 12:00:00"
        normalized = value.replace("Z", "+00:00").replace(" ", "T", 1)
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _file_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


class RetentionService:
    """按 TTL 清理会话、Trace，并裁剪审计日志。"""

    def __init__(self):
        self.conversation_root = Path("./conversations")
        self.trace_root = Path(Config.TRACE_STORAGE_PATH)
        self.audit_path = Path(Config.AUDIT_LOG_PATH)

    def status(self) -> dict:
        return {
            "enabled": Config.ENABLE_DATA_RETENTION,
            "retention_days": Config.DATA_RETENTION_DAYS,
            "conversation_root": str(self.conversation_root),
            "trace_root": str(self.trace_root),
            "audit_path": str(self.audit_path),
        }

    def cleanup(self, tenant_id: Optional[str] = None, *, dry_run: bool = False) -> dict:
        days = max(1, Config.DATA_RETENTION_DAYS)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        tenant = sanitize_tenant_id(tenant_id) if tenant_id else None

        result = {
            "enabled": Config.ENABLE_DATA_RETENTION,
            "dry_run": dry_run,
            "retention_days": days,
            "cutoff": cutoff.isoformat(),
            "tenant_id": tenant,
            "deleted_conversations": 0,
            "deleted_traces": 0,
            "trimmed_audit_events": 0,
            "kept_audit_events": 0,
        }

        if not Config.ENABLE_DATA_RETENTION and not dry_run:
            result["skipped"] = True
            result["reason"] = "ENABLE_DATA_RETENTION=false"
            return result

        result["deleted_conversations"] = self._cleanup_json_files(
            self.conversation_root,
            tenant,
            cutoff,
            dry_run=dry_run,
            kind="conversation",
        )
        result["deleted_traces"] = self._cleanup_json_files(
            self.trace_root,
            tenant,
            cutoff,
            dry_run=dry_run,
            kind="trace",
        )
        trimmed, kept = self._trim_audit(tenant, cutoff, dry_run=dry_run)
        result["trimmed_audit_events"] = trimmed
        result["kept_audit_events"] = kept
        return result

    def _cleanup_json_files(
        self,
        root: Path,
        tenant: Optional[str],
        cutoff: datetime,
        *,
        dry_run: bool,
        kind: str,
    ) -> int:
        deleted = 0
        if tenant:
            dirs = [Path(tenant_scoped_path(str(root), tenant))]
        else:
            if not root.exists():
                return 0
            dirs = [p for p in root.iterdir() if p.is_dir()]

        for directory in dirs:
            if not directory.exists():
                continue
            for path in directory.glob("*.json"):
                if self._is_expired(path, cutoff, kind=kind):
                    deleted += 1
                    if not dry_run:
                        try:
                            path.unlink(missing_ok=True)
                        except Exception as exc:
                            logger.warning("failed to delete %s: %s", path, exc)
        return deleted

    def _is_expired(self, path: Path, cutoff: datetime, *, kind: str) -> bool:
        stamp = None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if kind == "conversation" and isinstance(data, list) and data:
                stamp = _parse_iso(str(data[-1].get("timestamp", "")))
            elif kind == "trace" and isinstance(data, dict):
                stamp = _parse_iso(str(data.get("created_at", "")))
        except Exception:
            stamp = None
        if stamp is None:
            stamp = _file_mtime(path)
        return stamp < cutoff

    def _trim_audit(
        self,
        tenant: Optional[str],
        cutoff: datetime,
        *,
        dry_run: bool,
    ) -> tuple[int, int]:
        if not self.audit_path.exists():
            return 0, 0

        lines = self.audit_path.read_text(encoding="utf-8").splitlines()
        kept_lines: list[str] = []
        trimmed = 0
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                kept_lines.append(line)
                continue

            event_tenant = str(event.get("tenant_id") or "")
            if tenant and event_tenant and event_tenant != tenant:
                kept_lines.append(line)
                continue

            stamp = _parse_iso(str(event.get("timestamp", "")))
            if stamp is not None and stamp < cutoff:
                trimmed += 1
                continue
            kept_lines.append(line)

        if not dry_run and trimmed > 0:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            self.audit_path.write_text("\n".join(kept_lines) + ("\n" if kept_lines else ""), encoding="utf-8")
        return trimmed, len(kept_lines)


_retention_service: RetentionService | None = None


def get_retention_service() -> RetentionService:
    global _retention_service
    if _retention_service is None:
        _retention_service = RetentionService()
    return _retention_service
