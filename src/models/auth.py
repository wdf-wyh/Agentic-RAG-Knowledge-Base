"""认证与请求上下文模型"""
from typing import List, Optional

from pydantic import BaseModel, Field


class UserIdentity(BaseModel):
    """当前请求的用户身份。"""

    username: str
    user_id: str
    tenant_id: str = "default"
    roles: List[str] = Field(default_factory=list)
    auth_type: str = "jwt"


class RequestContext(BaseModel):
    """请求级上下文，供审计与可观测性使用。"""

    request_id: str
    path: str
    method: str
    user: Optional[UserIdentity] = None
    client_ip: Optional[str] = None
