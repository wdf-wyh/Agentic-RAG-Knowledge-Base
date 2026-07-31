"""权限依赖"""
from typing import Optional

from fastapi import Depends, HTTPException, status

from src.api.auth import get_current_user
from src.models.auth import UserIdentity
from src.security.abac import get_abac_engine


def require_roles(*roles: str):
    """要求用户具备任一角色。"""

    async def dependency(user: Optional[UserIdentity] = Depends(get_current_user)) -> Optional[UserIdentity]:
        if user is None:
            return None
        user_roles = set(user.roles or [])
        if not user_roles.intersection(roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要以下角色之一: {', '.join(roles)}",
            )
        return user

    return dependency


def require_policy(action: str, resource: str):
    """ABAC：按动作+资源评估属性策略。"""

    async def dependency(user: Optional[UserIdentity] = Depends(get_current_user)) -> Optional[UserIdentity]:
        decision = get_abac_engine().evaluate(user, action, resource)
        if not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=decision.reason,
            )
        return user

    return dependency