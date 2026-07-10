"""评测与回测 API"""
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from src.config.settings import Config
from src.evaluation.rag_evaluator import RAGEvaluator
from src.api.routes import load_assistant, get_assistant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/eval", tags=["Evaluation"])

_backtest_status = {
    "running": False,
    "progress": 0,
    "total": 0,
    "current_strategy": "",
    "phase": "",
    "result": None,
}


class BacktestRequest(BaseModel):
    dataset_path: str = Field(default="data/demo_dataset/qa_pairs.json")
    methods: Optional[List[str]] = Field(default=["vector", "bm25", "hybrid"])
    rerank_options: Optional[List[bool]] = Field(default=[False])
    top_k: Optional[int] = None


@router.get("/dataset")
async def get_demo_dataset():
    """获取演示评测数据集"""
    from pathlib import Path
    path = Path("data/demo_dataset/qa_pairs.json")
    if not path.exists():
        raise HTTPException(404, "演示数据集不存在")
    import json
    return {"cases": json.loads(path.read_text(encoding="utf-8"))}


@router.post("/backtest")
async def run_backtest(req: BacktestRequest):
    """运行 RAG 回测（同步）

    无 API Key 时自动使用本地轻量依赖：
    sentence-transformers 嵌入 + BM25 + hybrid + CrossEncoder rerank
    """
    evaluator = RAGEvaluator()
    if load_assistant():
        evaluator = RAGEvaluator(assistant=get_assistant())

    try:
        report = evaluator.run_backtest(
            dataset_path=req.dataset_path,
            methods=req.methods,
            rerank_options=req.rerank_options,
            k=req.top_k,
        )
        evaluator.save_report(report, "data/eval_reports/latest.json")
        return {"success": True, "report": report}
    except Exception as e:
        logger.error("回测失败: %s", e)
        raise HTTPException(500, str(e))


@router.post("/backtest-async")
async def run_backtest_async(req: BacktestRequest, bg: BackgroundTasks):
    """后台运行回测"""
    if _backtest_status["running"]:
        return {"success": False, "message": "已有回测任务运行中"}

    def _task():
        _backtest_status["running"] = True
        _backtest_status["progress"] = 0
        _backtest_status["total"] = 0
        _backtest_status["phase"] = "loading"
        _backtest_status["result"] = None
        try:
            evaluator = RAGEvaluator()
            if load_assistant():
                evaluator = RAGEvaluator(assistant=get_assistant())

            def _on_progress(done, total, strategy):
                _backtest_status["phase"] = "running"
                _backtest_status["progress"] = done
                _backtest_status["total"] = total
                _backtest_status["current_strategy"] = strategy

            if any(req.rerank_options or []):
                _backtest_status["phase"] = "loading_rerank"
            report = evaluator.run_backtest(
                dataset_path=req.dataset_path,
                methods=req.methods,
                rerank_options=req.rerank_options,
                k=req.top_k,
                progress_callback=_on_progress,
            )
            evaluator.save_report(report, "data/eval_reports/latest.json")
            _backtest_status["result"] = report
        except Exception as e:
            _backtest_status["result"] = {"error": str(e)}
        finally:
            _backtest_status["running"] = False

    bg.add_task(_task)
    return {"success": True, "message": "回测任务已启动"}


@router.get("/backtest-status")
async def backtest_status():
    return _backtest_status


@router.get("/latest-report")
async def latest_report():
    from pathlib import Path
    import json
    path = Path("data/eval_reports/latest.json")
    if not path.exists():
        raise HTTPException(404, "暂无评测报告，请先运行回测")
    return json.loads(path.read_text(encoding="utf-8"))
