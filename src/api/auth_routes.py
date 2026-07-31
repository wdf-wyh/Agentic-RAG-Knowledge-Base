"""认证 API"""
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from src.api.auth import (
    authenticate_user,
    create_access_token,
    create_access_token_for_identity,
    get_current_user,
    verify_token,
)
from src.api.dependencies import get_request_context
from src.config.settings import Config
from src.models.auth import RequestContext, UserIdentity
from src.models.audit import AuditEvent
from src.services.audit_service import get_audit_service
from src.services.oidc_service import (
    build_authorization_url,
    create_login_state,
    identity_from_code,
    is_oidc_enabled,
    verify_login_state,
)
router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(req: LoginRequest, request: Request, context: RequestContext = Depends(get_request_context)):
    if not authenticate_user(req.username, req.password):
        get_audit_service().record(
            AuditEvent(
                request_id=context.request_id,
                actor_name=req.username,
                action="auth.login",
                resource="session",
                outcome="failure",
                path=request.url.path,
                method=request.method,
                client_ip=context.client_ip,
                details={"reason": "invalid_credentials"},
            )
        )
        raise HTTPException(401, "用户名或密码错误")
    token = create_access_token(req.username)
    user = verify_token(token)
    if user is None:
        raise HTTPException(500, "令牌生成后校验失败")
    get_audit_service().record(
        AuditEvent(
            request_id=context.request_id,
            actor_id=user.user_id,
            actor_name=user.username,
            tenant_id=user.tenant_id,
            action="auth.login",
            resource="session",
            path=request.url.path,
            method=request.method,
            client_ip=context.client_ip,
            details={"roles": user.roles},
        )
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": req.username,
        "tenant_id": user.tenant_id,
        "roles": user.roles,
    }


@router.get("/me")
async def me(user: UserIdentity = Depends(get_current_user)):
    return {"user": user.model_dump() if user else None, "auth_enabled": Config.ENABLE_AUTH}


@router.get("/status")
async def auth_status():
    return {
        "enabled": Config.ENABLE_AUTH or is_oidc_enabled(),
        "password_login_enabled": Config.ENABLE_AUTH,
        "oidc_enabled": is_oidc_enabled(),
        "oidc_login_url": "/api/auth/oidc/login" if is_oidc_enabled() else None,
        "demo_users": ["admin", "demo", "auditor"] if Config.ENABLE_AUTH else [],
    }


@router.get("/oidc/login")
async def oidc_login():
    if not is_oidc_enabled():
        raise HTTPException(404, "OIDC 未启用")
    state = create_login_state()
    return RedirectResponse(build_authorization_url(state))


@router.get("/oidc/callback")
async def oidc_callback(
    request: Request,
    context: RequestContext = Depends(get_request_context),
    code: str = "",
    state: str = "",
    error: str = "",
    error_description: str = "",
):
    if not is_oidc_enabled():
        raise HTTPException(404, "OIDC 未启用")
    if error:
        raise HTTPException(400, error_description or error)
    if not code or not state or not verify_login_state(state):
        raise HTTPException(400, "无效的 OIDC 回调参数")

    try:
        user = identity_from_code(code)
    except Exception as exc:
        get_audit_service().record(
            AuditEvent(
                request_id=context.request_id,
                action="auth.oidc_login",
                resource="session",
                outcome="failure",
                path=request.url.path,
                method="GET",
                client_ip=context.client_ip,
                details={"reason": str(exc)},
            )
        )
        raise HTTPException(400, f"OIDC 登录失败: {exc}") from exc

    token = create_access_token_for_identity(user)
    get_audit_service().record(
        AuditEvent(
            request_id=context.request_id,
            actor_id=user.user_id,
            actor_name=user.username,
            tenant_id=user.tenant_id,
            action="auth.oidc_login",
            resource="session",
            path=request.url.path,
            method="GET",
            client_ip=context.client_ip,
            details={"roles": user.roles, "auth_type": user.auth_type},
        )
    )

    redirect_url = Config.OIDC_FRONTEND_CALLBACK_URL
    separator = "&" if "?" in redirect_url else "?"
    return RedirectResponse(f"{redirect_url}{separator}{urlencode({'oidc_token': token})}")
