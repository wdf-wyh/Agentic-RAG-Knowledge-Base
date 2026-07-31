"""企业事件 Webhook 推送。"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

import requests

from src.config.settings import Config

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="webhook")


class WebhookService:
    """把关键业务事件异步推送到外部系统。"""

    def __init__(self):
        self._recent: list[dict] = []

    def enabled(self) -> bool:
        return bool(Config.WEBHOOK_URL.strip())

    def subscribed(self, event_type: str) -> bool:
        events = {item.strip() for item in Config.WEBHOOK_EVENTS.split(",") if item.strip()}
        return "*" in events or event_type in events

    def emit(self, event_type: str, payload: dict, *, async_delivery: bool = True) -> Optional[dict]:
        if not self.enabled() or not self.subscribed(event_type):
            return None

        envelope = {
            "event_type": event_type,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "payload": payload,
        }
        if async_delivery:
            _executor.submit(self._deliver, envelope)
            return {"queued": True, "event_type": event_type}
        return self._deliver(envelope)

    def _sign(self, body: bytes) -> Optional[str]:
        secret = Config.WEBHOOK_SECRET.strip()
        if not secret:
            return None
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    def _deliver(self, envelope: dict) -> dict:
        body = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "AgenticRAG-Webhook/1.0",
            "X-RAG-Event": envelope["event_type"],
        }
        signature = self._sign(body)
        if signature:
            headers["X-RAG-Signature"] = signature

        result: dict[str, Any] = {
            "event_type": envelope["event_type"],
            "url": Config.WEBHOOK_URL,
            "ok": False,
            "status_code": None,
            "error": None,
            "timestamp": envelope["timestamp"],
        }
        try:
            response = requests.post(
                Config.WEBHOOK_URL,
                data=body,
                headers=headers,
                timeout=Config.WEBHOOK_TIMEOUT_SECONDS,
            )
            result["status_code"] = response.status_code
            result["ok"] = 200 <= response.status_code < 300
            if not result["ok"]:
                result["error"] = response.text[:300]
        except Exception as exc:
            result["error"] = str(exc)
            logger.warning("webhook delivery failed event=%s error=%s", envelope["event_type"], exc)

        self._recent.append(result)
        if len(self._recent) > 50:
            self._recent = self._recent[-50:]
        return result

    def recent_deliveries(self, limit: int = 20) -> list[dict]:
        return list(reversed(self._recent[-limit:]))

    def status(self) -> dict:
        return {
            "enabled": self.enabled(),
            "url_configured": bool(Config.WEBHOOK_URL.strip()),
            "events": [item.strip() for item in Config.WEBHOOK_EVENTS.split(",") if item.strip()],
            "recent": self.recent_deliveries(10),
        }


_webhook_service: WebhookService | None = None


def get_webhook_service() -> WebhookService:
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = WebhookService()
    return _webhook_service
