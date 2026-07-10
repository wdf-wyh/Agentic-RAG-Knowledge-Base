"""JWT 鉴权"""
import os
import time
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.config.settings import Config

security = HTTPBearer(auto_error=False)

# 简单用户存储（演示用）
_DEMO_USERS = {
    "admin": "admin123",
    "demo": "demo123",
}

try:
    from jose import jwt, JWTError
except ImportError:
    jwt = None
    JWTError = Exception


def create_access_token(username: str, expires_hours: int = 24) -> str:
    if jwt is None:
        raise RuntimeError("请安装 python-jose: pip install python-jose[cryptography]")
    payload = {
        "sub": username,
        "exp": int(time.time()) + expires_hours * 3600,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)


def verify_token(token: str) -> Optional[str]:
    if jwt is None:
        return None
    try:
        payload = jwt.decode(token, Config.JWT_SECRET, algorithms=[Config.JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def authenticate_user(username: str, password: str) -> bool:
    return _DEMO_USERS.get(username) == password


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """可选鉴权：未启用时返回 None"""
    if not Config.ENABLE_AUTH:
        return None
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="需要登录")
    user = verify_token(credentials.credentials)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="无效或过期的令牌")
    return user
