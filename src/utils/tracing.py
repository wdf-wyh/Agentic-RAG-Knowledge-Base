"""Agent 执行追踪"""
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.config.settings import Config

logger = logging.getLogger(__name__)


@dataclass
class TraceStep:
    step: int
    type: str  # thought | action | observation | answer | error
    content: str
    tool: Optional[str] = None
    duration_ms: float = 0
    tokens: int = 0


@dataclass
class AgentTrace:
    trace_id: str
    question: str
    mode: str
    steps: List[TraceStep] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    total_duration_ms: float = 0
    success: bool = True
    answer: str = ""
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["steps"] = [asdict(s) for s in self.steps]
        return d


class TraceCollector:
    """收集并持久化 Agent 追踪"""

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or Config.TRACE_STORAGE_PATH)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._current: Optional[AgentTrace] = None
        self._start_time: float = 0

    def start(self, question: str, mode: str = "agent") -> str:
        trace_id = str(uuid.uuid4())[:12]
        self._current = AgentTrace(
            trace_id=trace_id,
            question=question,
            mode=mode,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._start_time = time.time()
        return trace_id

    def add_step(self, step: int, step_type: str, content: str, tool: str = None, duration_ms: float = 0):
        if not self._current:
            return
        self._current.steps.append(TraceStep(
            step=step,
            type=step_type,
            content=content[:2000],
            tool=tool,
            duration_ms=duration_ms,
        ))
        if tool and tool not in self._current.tools_used:
            self._current.tools_used.append(tool)

    def finish(self, answer: str, success: bool = True):
        if not self._current:
            return None
        self._current.answer = answer[:5000]
        self._current.success = success
        self._current.total_duration_ms = round((time.time() - self._start_time) * 1000, 2)
        self._save(self._current)
        trace = self._current
        self._current = None
        return trace

    def _save(self, trace: AgentTrace):
        path = self.storage_dir / f"{trace.trace_id}.json"
        path.write_text(json.dumps(trace.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def list_traces(self, limit: int = 50) -> List[Dict[str, Any]]:
        files = sorted(self.storage_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        traces = []
        for fp in files[:limit]:
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                traces.append({
                    "trace_id": data.get("trace_id"),
                    "question": data.get("question", "")[:80],
                    "mode": data.get("mode"),
                    "success": data.get("success"),
                    "tools_used": data.get("tools_used", []),
                    "total_duration_ms": data.get("total_duration_ms"),
                    "created_at": data.get("created_at"),
                    "step_count": len(data.get("steps", [])),
                })
            except Exception:
                continue
        return traces

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        path = self.storage_dir / f"{trace_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


# 全局追踪收集器
_global_collector = TraceCollector()


def get_trace_collector() -> TraceCollector:
    return _global_collector
