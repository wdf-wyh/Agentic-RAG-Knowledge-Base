"""请求上下文中间件"""
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware

from src.api.auth import verify_token
from src.config.settings import Config
from src.models.auth import RequestContext
from src.utils.tenant_monitoring import tenant_monitor

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """为每个请求生成 request_id，并输出统一结构化日志。"""

    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        client_ip = request.client.host if request.client else None
        tenant_id = Config.DEFAULT_TENANT_ID
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            identity = verify_token(token)
            if identity is not None:
                tenant_id = identity.tenant_id
        request.state.request_context = RequestContext(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            client_ip=client_ip,
        )
        request.state.request_started_at = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - request.state.request_started_at) * 1000, 2)
        tenant_monitor.record_request(tenant_id=tenant_id, status_code=response.status_code, duration_ms=duration_ms)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed request_id=%s tenant_id=%s method=%s path=%s status_code=%s duration_ms=%s client_ip=%s",
            request_id,
            tenant_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            client_ip,
        )
        return response
