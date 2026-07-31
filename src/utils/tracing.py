"""Agent 执行追踪"""
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.config.settings import Config
from src.utils.tenant_paths import tenant_scoped_path

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

    def __init__(self, storage_dir: Optional[str] = None, tenant_id: Optional[str] = None):
        self.storage_dir = Path(storage_dir or tenant_scoped_path(Config.TRACE_STORAGE_PATH, tenant_id))
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


# 全局追踪收集器（仅用于 list/get；写入请用独立实例避免并发互相覆盖 _current）
_global_collectors: Dict[str, TraceCollector] = {}


def get_trace_collector(tenant_id: Optional[str] = None) -> TraceCollector:
    tenant = tenant_id or Config.DEFAULT_TENANT_ID
    collector = _global_collectors.get(tenant)
    if collector is None:
        collector = TraceCollector(tenant_id=tenant)
        _global_collectors[tenant] = collector
    return collector


def _new_writer(tenant_id: Optional[str] = None) -> TraceCollector:
    """每次写入使用独立 collector，避免流式并发请求互相覆盖。"""
    return TraceCollector(tenant_id=tenant_id or Config.DEFAULT_TENANT_ID)


def record_agent_trace(
    question: str,
    mode: str,
    *,
    tenant_id: Optional[str] = None,
    thought_process: Optional[List[Any]] = None,
    answer: str = "",
    success: bool = True,
    tools_used: Optional[List[str]] = None,
) -> Optional[AgentTrace]:
    """从 AgentResponse / thought_process 持久化一条追踪记录。"""
    collector = _new_writer(tenant_id)
    collector.start(question, mode=mode)
    step_count = 0

    for step in thought_process or []:
        step_num = int(getattr(step, "step", None) or (step_count + 1))
        thought = getattr(step, "thought", None)
        action = getattr(step, "action", None)
        action_input = getattr(step, "action_input", None)
        observation = getattr(step, "observation", None)

        if thought:
            collector.add_step(step_num, "thought", str(thought))
        if action and action != "__final__":
            collector.add_step(step_num, "action", str(action_input or ""), tool=str(action))
        if observation:
            collector.add_step(step_num, "observation", str(observation))
        step_count = max(step_count, step_num)

    recorded_tools = set(collector._current.tools_used if collector._current else [])
    for tool in tools_used or []:
        if tool and tool not in recorded_tools:
            step_count += 1
            collector.add_step(step_count, "action", "", tool=str(tool))
            recorded_tools.add(tool)

    return collector.finish(answer or "", success=success)


class StreamTraceBuilder:
    """从流式 StreamEvent 累积步骤，结束后一次性落盘。"""

    def __init__(self, question: str, mode: str):
        self.question = question
        self.mode = mode
        self.steps: List[tuple] = []  # (step, type, content, tool)
        self.answer = ""
        self.success = True
        self.tools_used: List[str] = []
        self._step = 0
        self._started = False

    def ingest(self, event: Any) -> None:
        et = getattr(event, "type", None)
        if not et:
            return
        self._started = True
        step = getattr(event, "step", None) or 0
        data = getattr(event, "data", None)

        if et == "intent":
            self._step = max(self._step, 1)
            payload = data if isinstance(data, dict) else {}
            content = (
                f"intent={payload.get('intent')}, "
                f"confidence={payload.get('confidence')}, "
                f"reasoning={payload.get('reasoning', '')}"
            )
            self.steps.append((1, "thought", content, None))
        elif et == "thinking_end":
            self._step = step or (self._step + 1)
            content = data if isinstance(data, str) else str(data or "")
            self.steps.append((self._step, "thought", content, None))
        elif et == "action":
            self._step = step or (self._step + 1)
            payload = data if isinstance(data, dict) else {}
            tool = payload.get("tool") if isinstance(payload, dict) else None
            inp = payload.get("input", "") if isinstance(payload, dict) else str(data or "")
            self.steps.append((self._step, "action", str(inp), tool))
            if tool and tool not in self.tools_used:
                self.tools_used.append(tool)
        elif et == "observation":
            self._step = step or self._step or (self._step + 1)
            payload = data if isinstance(data, dict) else {}
            text = payload.get("text", "") if isinstance(payload, dict) else str(data or "")
            self.steps.append((self._step, "observation", str(text), None))
        elif et == "answer":
            text = data if isinstance(data, str) else str(data or "")
            if text.strip():
                self.answer = text
        elif et == "answer_token":
            token = data if isinstance(data, str) else str(data or "")
            if token:
                self.answer = (self.answer or "") + token
        elif et == "error":
            self.success = False
            err = data if isinstance(data, str) else str(data or "")
            self._step += 1
            self.steps.append((self._step, "error", err, None))
            if not self.answer:
                self.answer = err
        elif et in ("done", "meta") and isinstance(data, dict):
            for tool in data.get("tools_used") or []:
                if tool and tool not in self.tools_used:
                    self.tools_used.append(tool)

    def save(self, tenant_id: Optional[str] = None) -> Optional[AgentTrace]:
        if not self._started and not self.answer and not self.steps:
            return None
        collector = _new_writer(tenant_id)
        collector.start(self.question, mode=self.mode)
        for step_num, step_type, content, tool in self.steps:
            collector.add_step(step_num, step_type, content, tool=tool)

        recorded = set(collector._current.tools_used if collector._current else [])
        n = self._step
        for tool in self.tools_used:
            if tool and tool not in recorded:
                n += 1
                collector.add_step(n, "action", "", tool=tool)
                recorded.add(tool)

        return collector.finish(self.answer or "", success=self.success)
