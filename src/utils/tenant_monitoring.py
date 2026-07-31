"""租户级运行监控"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import Dict


@dataclass
class TenantMetrics:
    request_count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0


class TenantMonitor:
    """按租户收集请求统计。"""

    def __init__(self):
        self._lock = Lock()
        self._tenant_metrics: Dict[str, TenantMetrics] = defaultdict(TenantMetrics)
        self._tenant_latencies: Dict[str, list[float]] = defaultdict(list)

    def record_request(self, tenant_id: str, status_code: int, duration_ms: float) -> None:
        tenant = tenant_id or "default"
        with self._lock:
            metrics = self._tenant_metrics[tenant]
            metrics.request_count += 1
            metrics.total_latency_ms += duration_ms
            if status_code >= 400:
                metrics.error_count += 1

            latencies = self._tenant_latencies[tenant]
            latencies.append(duration_ms)
            if len(latencies) > 1000:
                del latencies[: len(latencies) - 1000]
            metrics.p95_latency_ms = self._percentile(latencies, 95)

    def snapshot(self) -> Dict[str, dict]:
        with self._lock:
            result: Dict[str, dict] = {}
            for tenant, metric in self._tenant_metrics.items():
                avg_latency = metric.total_latency_ms / metric.request_count if metric.request_count else 0.0
                error_rate = metric.error_count / metric.request_count if metric.request_count else 0.0
                result[tenant] = {
                    "request_count": metric.request_count,
                    "error_count": metric.error_count,
                    "error_rate": round(error_rate, 4),
                    "avg_latency_ms": round(avg_latency, 2),
                    "p95_latency_ms": round(metric.p95_latency_ms, 2),
                }
            return result

    def to_prometheus(self) -> str:
        lines = [
            "# HELP rag_tenant_requests_total Total requests per tenant",
            "# TYPE rag_tenant_requests_total counter",
            "# HELP rag_tenant_errors_total Total error responses per tenant",
            "# TYPE rag_tenant_errors_total counter",
            "# HELP rag_tenant_avg_latency_ms Average latency per tenant in milliseconds",
            "# TYPE rag_tenant_avg_latency_ms gauge",
            "# HELP rag_tenant_p95_latency_ms P95 latency per tenant in milliseconds",
            "# TYPE rag_tenant_p95_latency_ms gauge",
        ]
        for tenant, snapshot in self.snapshot().items():
            lines.append(f'rag_tenant_requests_total{{tenant="{tenant}"}} {snapshot["request_count"]}')
            lines.append(f'rag_tenant_errors_total{{tenant="{tenant}"}} {snapshot["error_count"]}')
            lines.append(f'rag_tenant_avg_latency_ms{{tenant="{tenant}"}} {snapshot["avg_latency_ms"]}')
            lines.append(f'rag_tenant_p95_latency_ms{{tenant="{tenant}"}} {snapshot["p95_latency_ms"]}')
        return "\n".join(lines) + "\n"

    @staticmethod
    def _percentile(values: list[float], pct: int) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        idx = int((pct / 100) * (len(ordered) - 1))
        return ordered[idx]


tenant_monitor = TenantMonitor()
