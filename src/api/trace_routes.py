"""Agent 追踪 API"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request

from src.api.auth import get_current_user
from src.api.dependencies import get_request_context
from src.api.permissions import require_roles
from src.models.auth import RequestContext, UserIdentity
from src.models.audit import AuditEvent
from src.services.audit_service import get_audit_service
from src.utils.tracing import get_trace_collector

router = APIRouter(
    prefix="/traces",
    tags=["Tracing"],
    dependencies=[Depends(get_current_user), Depends(require_roles("admin", "auditor"))],
)


@router.get("")
async def list_traces(
    request: Request,
    limit: int = 50,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    tenant_id = user.tenant_id if user else "default"
    collector = get_trace_collector(tenant_id)
    get_audit_service().record(
        AuditEvent(
            request_id=context.request_id,
            actor_id=user.user_id if user else "anonymous",
            actor_name=user.username if user else "anonymous",
            tenant_id=tenant_id,
            action="trace.list",
            resource="traces",
            path=request.url.path,
            method=request.method,
            client_ip=context.client_ip,
            details={"limit": limit},
        )
    )
    return {"traces": collector.list_traces(limit=limit)}


@router.get("/{trace_id}")
async def get_trace(
    trace_id: str,
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    tenant_id = user.tenant_id if user else "default"
    collector = get_trace_collector(tenant_id)
    trace = collector.get_trace(trace_id)
    if not trace:
        raise HTTPException(404, "追踪记录不存在")
    get_audit_service().record(
        AuditEvent(
            request_id=context.request_id,
            actor_id=user.user_id if user else "anonymous",
            actor_name=user.username if user else "anonymous",
            tenant_id=tenant_id,
            action="trace.read",
            resource=trace_id,
            path=request.url.path,
            method=request.method,
            client_ip=context.client_ip,
        )
    )
    return trace
