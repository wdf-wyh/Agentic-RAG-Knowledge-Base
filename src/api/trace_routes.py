"""Agent 追踪 API"""
from fastapi import APIRouter, HTTPException

from src.utils.tracing import get_trace_collector

router = APIRouter(prefix="/traces", tags=["Tracing"])


@router.get("")
async def list_traces(limit: int = 50):
    collector = get_trace_collector()
    return {"traces": collector.list_traces(limit=limit)}


@router.get("/{trace_id}")
async def get_trace(trace_id: str):
    collector = get_trace_collector()
    trace = collector.get_trace(trace_id)
    if not trace:
        raise HTTPException(404, "追踪记录不存在")
    return trace
