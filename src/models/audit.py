"""审计日志模型"""
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    """企业级审计事件。"""

    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    request_id: str
    actor_id: str = "anonymous"
    actor_name: str = "anonymous"
    tenant_id: str = "default"
    action: str
    resource: str
    outcome: str = "success"
    path: str
    method: str
    details: Dict[str, Any] = Field(default_factory=dict)
    client_ip: Optional[str] = None
