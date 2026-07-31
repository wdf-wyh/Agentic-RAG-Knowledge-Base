"""企业合规导出包。"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

from src.config.settings import Config
from src.services.quota_service import get_quota_service
from src.utils.tenant_paths import sanitize_tenant_id, tenant_scoped_path


class ComplianceExportService:
    """导出指定租户的会话、Trace、审计与配额快照。"""

    def build_zip(self, tenant_id: str) -> tuple[bytes, str]:
        tenant = sanitize_tenant_id(tenant_id)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"compliance_{tenant}_{stamp}.zip"

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            manifest = {
                "tenant_id": tenant,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "contents": {
                    "conversations": 0,
                    "traces": 0,
                    "audit_events": 0,
                },
            }

            conv_dir = Path(tenant_scoped_path("./conversations", tenant))
            if conv_dir.exists():
                for path in sorted(conv_dir.glob("*.json")):
                    zf.write(path, arcname=f"conversations/{path.name}")
                    manifest["contents"]["conversations"] += 1

            trace_dir = Path(tenant_scoped_path(Config.TRACE_STORAGE_PATH, tenant))
            if trace_dir.exists():
                for path in sorted(trace_dir.glob("*.json")):
                    zf.write(path, arcname=f"traces/{path.name}")
                    manifest["contents"]["traces"] += 1

            audit_events = self._filter_audit_events(tenant)
            manifest["contents"]["audit_events"] = len(audit_events)
            zf.writestr(
                "audit.jsonl",
                "\n".join(json.dumps(item, ensure_ascii=False) for item in audit_events)
                + ("\n" if audit_events else ""),
            )

            quota = {
                "limits": get_quota_service().limits(),
                "usage": get_quota_service().snapshot(tenant).get(tenant),
            }
            zf.writestr("quota.json", json.dumps(quota, ensure_ascii=False, indent=2))
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        return buffer.getvalue(), filename

    def _filter_audit_events(self, tenant_id: str) -> list[dict]:
        path = Path(Config.AUDIT_LOG_PATH)
        if not path.exists():
            return []
        events: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(event.get("tenant_id") or "") == tenant_id:
                events.append(event)
        return events


_compliance_export_service: ComplianceExportService | None = None


def get_compliance_export_service() -> ComplianceExportService:
    global _compliance_export_service
    if _compliance_export_service is None:
        _compliance_export_service = ComplianceExportService()
    return _compliance_export_service
