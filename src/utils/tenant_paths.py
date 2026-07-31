"""租户级存储路径工具"""
import re
from pathlib import Path

from src.config.settings import Config


def sanitize_tenant_id(tenant_id: str | None) -> str:
    tenant = (tenant_id or Config.DEFAULT_TENANT_ID).strip() or Config.DEFAULT_TENANT_ID
    return re.sub(r"[^a-zA-Z0-9._-]", "_", tenant)


def tenant_scoped_path(base_path: str, tenant_id: str | None) -> str:
    base = Path(base_path)
    tenant = sanitize_tenant_id(tenant_id)
    return str(base / tenant)
