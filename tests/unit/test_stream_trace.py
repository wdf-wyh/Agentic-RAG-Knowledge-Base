from types import SimpleNamespace

from src.utils.tracing import StreamTraceBuilder, TraceCollector, record_agent_trace


def test_record_agent_trace_from_thought_process(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.tracing.Config.TRACE_STORAGE_PATH", str(tmp_path / "traces"))

    step = SimpleNamespace(
        step=1,
        thought="先检索知识库",
        action="rag_search",
        action_input="工资标准",
        observation="找到相关文档",
    )
    trace = record_agent_trace(
        "工资标准是多少？",
        mode="smart",
        tenant_id="t1",
        thought_process=[step],
        answer="根据制度，标准为……",
        success=True,
        tools_used=["rag_search"],
    )

    assert trace is not None
    assert trace.mode == "smart"
    assert "rag_search" in trace.tools_used
    assert len(trace.steps) >= 3

    listed = TraceCollector(tenant_id="t1").list_traces()
    assert len(listed) == 1
    assert listed[0]["question"].startswith("工资标准")


def test_stream_trace_builder_ingests_smart_events(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.tracing.Config.TRACE_STORAGE_PATH", str(tmp_path / "traces"))

    builder = StreamTraceBuilder("你好", mode="smart-stream")
    builder.ingest(SimpleNamespace(type="intent", step=0, data={
        "intent": "direct_answer",
        "confidence": 0.9,
        "reasoning": "问候语",
    }))
    builder.ingest(SimpleNamespace(type="action", step=1, data={"tool": "rag_search", "input": "你好"}))
    builder.ingest(SimpleNamespace(type="observation", step=1, data={"text": "命中文档"}))
    builder.ingest(SimpleNamespace(type="answer", step=1, data="你好，我是助手"))
    builder.ingest(SimpleNamespace(type="done", step=0, data={"tools_used": ["rag_search"], "iterations": 1}))

    trace = builder.save("t2")
    assert trace is not None
    assert trace.success is True
    assert trace.answer == "你好，我是助手"
    assert "rag_search" in trace.tools_used
    assert any(s.type == "thought" for s in trace.steps)
    assert any(s.type == "action" and s.tool == "rag_search" for s in trace.steps)


def test_stream_trace_builder_records_errors(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.tracing.Config.TRACE_STORAGE_PATH", str(tmp_path / "traces"))

    builder = StreamTraceBuilder("失败案例", mode="agent-stream")
    builder.ingest(SimpleNamespace(type="error", step=0, data="LLM 超时"))
    trace = builder.save("t3")

    assert trace is not None
    assert trace.success is False
    assert "超时" in trace.answer
    assert any(s.type == "error" for s in trace.steps)
