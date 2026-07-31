"""JWT 鉴权"""
import time
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.config.settings import Config
from src.models.auth import UserIdentity

security = HTTPBearer(auto_error=False)

# 简单用户存储（演示用）
_DEMO_USERS = {
    "admin": {
        "password": "admin123",
        "user_id": "u-admin",
        "tenant_id": Config.DEFAULT_TENANT_ID,
        "roles": ["admin", "auditor"],
    },
    "demo": {
        "password": "demo123",
        "user_id": "u-demo",
        "tenant_id": "tenant-demo",
        "roles": ["user"],
    },
    "auditor": {
        "password": "audit123",
        "user_id": "u-auditor",
        "tenant_id": Config.DEFAULT_TENANT_ID,
        "roles": ["auditor"],
    },
}

try:
    from jose import jwt, JWTError
except ImportError:
    jwt = None
    JWTError = Exception


def create_access_token(username: str, expires_hours: int = 24) -> str:
    if jwt is None:
        raise RuntimeError("请安装 python-jose: pip install python-jose[cryptography]")
    user = _DEMO_USERS[username]
    return create_access_token_for_identity(
        UserIdentity(
            username=username,
            user_id=user["user_id"],
            tenant_id=user["tenant_id"],
            roles=user["roles"],
            auth_type="password",
        ),
        expires_hours=expires_hours,
    )


def create_access_token_for_identity(user: UserIdentity, expires_hours: int = 24) -> str:
    if jwt is None:
        raise RuntimeError("请安装 python-jose: pip install python-jose[cryptography]")
    payload = {
        "sub": user.username,
        "user_id": user.user_id,
        "tenant_id": user.tenant_id,
        "roles": user.roles,
        "auth_type": user.auth_type,
        "exp": int(time.time()) + expires_hours * 3600,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)


def verify_token(token: str) -> Optional[UserIdentity]:
    if jwt is None:
        return None
    try:
        payload = jwt.decode(token, Config.JWT_SECRET, algorithms=[Config.JWT_ALGORITHM])
        username = payload.get("sub")
        if not username:
            return None
        return UserIdentity(
            username=username,
            user_id=payload.get("user_id", username),
            tenant_id=payload.get("tenant_id", Config.DEFAULT_TENANT_ID),
            roles=payload.get("roles", []),
            auth_type=payload.get("auth_type", "jwt"),
        )
    except JWTError:
        return None


def authenticate_user(username: str, password: str) -> bool:
    user = _DEMO_USERS.get(username)
    return bool(user and user["password"] == password)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[UserIdentity]:
    """可选鉴权：未启用时返回 None"""
    from src.services.oidc_service import is_oidc_enabled

    if not Config.ENABLE_AUTH and not is_oidc_enabled():
        return None
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="需要登录")
    user = verify_token(credentials.credentials)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="无效或过期的令牌")
    return user
