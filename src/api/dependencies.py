"""API 通用依赖"""
from fastapi import Request

from src.models.auth import RequestContext


def get_request_context(request: Request) -> RequestContext:
    """从 request.state 获取统一请求上下文。"""

    context = getattr(request.state, "request_context", None)
    if context is None:
        context = RequestContext(
            request_id="missing-request-id",
            path=request.url.path,
            method=request.method,
            client_ip=request.client.host if request.client else None,
        )
        request.state.request_context = context
    return context
