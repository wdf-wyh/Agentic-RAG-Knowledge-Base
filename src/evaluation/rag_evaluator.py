"""RAG 评测与回测"""
import json
import logging
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.config.settings import Config
from src.core.hybrid_retriever import HybridRetriever
from src.core.vector_store import VectorStore
from src.services.rag_assistant import RAGAssistant

logger = logging.getLogger(__name__)


@dataclass
class EvalCase:
    question: str
    expected_keywords: List[str]
    expected_sources: List[str] = None
    ground_truth: str = ""

    def __post_init__(self):
        if self.expected_sources is None:
            self.expected_sources = []


@dataclass
class EvalResult:
    question: str
    method: str
    rerank: bool
    hit: bool
    recall_at_k: float
    mrr: float
    keyword_recall: float
    latency_ms: float
    retrieved_sources: List[str]
    top_preview: str = ""


class RAGEvaluator:
    """RAG 检索评测器"""

    def __init__(self, assistant: Optional[RAGAssistant] = None):
        self.assistant = assistant
        self.retriever: Optional[HybridRetriever] = None

    def _get_retriever(self) -> HybridRetriever:
        if self.retriever is None:
            vs = self.assistant.vector_store if self.assistant else VectorStore()
            if vs.vectorstore is None:
                vs.load_vectorstore()
            self.retriever = HybridRetriever(vs)
        return self.retriever

    def ensure_local_retriever(self) -> HybridRetriever:
        """使用本地轻量依赖初始化检索器，无需 API Key 或 .env 配置"""
        if self.retriever is not None:
            return self.retriever

        vs = self.assistant.vector_store if self.assistant else VectorStore()
        if vs.vectorstore is None:
            vs.load_vectorstore()
        if vs.vectorstore is None:
            from src.core.document_processor import DocumentProcessor
            chunks = DocumentProcessor().process_documents(Config.DOCUMENTS_PATH)
            if not chunks:
                raise ValueError("本地回测需要 documents/ 目录有文件")
            logger.info("未找到向量库，使用本地嵌入模型自动构建（首次较慢）...")
            vs.create_vectorstore(chunks)

        self.retriever = HybridRetriever(vs)
        return self.retriever

    @staticmethod
    def load_dataset(path: str) -> List[EvalCase]:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        cases = []
        for item in data:
            cases.append(EvalCase(
                question=item["question"],
                expected_keywords=item.get("expected_keywords", []),
                expected_sources=item.get("expected_sources", []),
                ground_truth=item.get("ground_truth", ""),
            ))
        return cases

    @staticmethod
    def _doc_text(doc) -> str:
        if hasattr(doc, "page_content"):
            return doc.page_content or ""
        if isinstance(doc, dict):
            return doc.get("page_content", "") or ""
        return str(doc)

    @staticmethod
    def _doc_source(doc) -> str:
        meta = getattr(doc, "metadata", {}) if hasattr(doc, "metadata") else (
            doc.get("metadata", {}) if isinstance(doc, dict) else {}
        )
        return meta.get("source", "") if isinstance(meta, dict) else ""

    def _keyword_recall(self, docs: List[Any], keywords: List[str]) -> float:
        if not keywords:
            return 1.0
        text = " ".join(self._doc_text(d) for d in docs).lower()
        hits = sum(1 for kw in keywords if kw.lower() in text)
        return hits / len(keywords)

    def _source_hit(self, docs: List[Any], expected_sources: List[str]) -> bool:
        if not expected_sources:
            return True
        retrieved = [self._doc_source(d) for d in docs]
        for exp in expected_sources:
            if any(exp in src for src in retrieved):
                return True
        return False

    def _mrr(self, docs: List[Any], keywords: List[str]) -> float:
        for i, doc in enumerate(docs):
            text = self._doc_text(doc).lower()
            if any(kw.lower() in text for kw in keywords):
                return 1.0 / (i + 1)
        return 0.0

    def evaluate_retrieval(
        self,
        case: EvalCase,
        method: str = "hybrid",
        rerank: bool = False,
        k: int = None,
    ) -> EvalResult:
        k = k or Config.TOP_K
        retriever = self._get_retriever()

        start = time.time()
        result = retriever.retrieve(
            case.question, k=k, method=method, rerank=rerank,
            use_hyde=False, rewrite_query=False,
            candidate_k=max(k * 2, 6),
        )
        docs = result["documents"]
        latency = (time.time() - start) * 1000

        kw_recall = self._keyword_recall(docs, case.expected_keywords)
        hit = self._source_hit(docs, case.expected_sources) and kw_recall >= 0.5
        mrr = self._mrr(docs, case.expected_keywords)

        return EvalResult(
            question=case.question,
            method=method,
            rerank=rerank,
            hit=hit,
            recall_at_k=kw_recall,
            mrr=mrr,
            keyword_recall=kw_recall,
            latency_ms=round(latency, 2),
            retrieved_sources=[self._doc_source(d) for d in docs],
            top_preview=self._doc_text(docs[0])[:150] if docs else "",
        )

    @staticmethod
    def _strategy_count(methods: List[str], rerank_options: List[bool]) -> int:
        count = 0
        for method in methods:
            for rerank in rerank_options:
                if rerank and method != "hybrid":
                    continue
                count += 1
        return count

    def _preload_rerank_if_needed(self, rerank_options: List[bool]):
        if not any(rerank_options):
            return
        from src.core.reranker import get_cross_encoder
        logger.info("预加载 Rerank 模型（首次运行需下载，请耐心等待）...")
        get_cross_encoder()
        logger.info("Rerank 模型已就绪")

    def _run_bm25_only_backtest(
        self,
        cases: List[EvalCase],
        methods: List[str],
        rerank_options: List[bool],
        k: int = None,
    ) -> Dict[str, Any]:
        """纯 BM25 降级回测（不依赖向量库与 sentence-transformers）"""
        from src.core.document_processor import DocumentProcessor
        from src.core.bm25_retriever import BM25Retriever

        chunks = DocumentProcessor().process_documents(Config.DOCUMENTS_PATH)
        if not chunks:
            raise ValueError("离线回测需要 documents/ 目录有文件")

        all_results: Dict[str, List[Dict]] = {}
        summary: Dict[str, Dict[str, float]] = {}

        for method in methods:
            for rerank in rerank_options:
                if rerank and method != "hybrid":
                    continue
                key = f"{method}{'+rerank' if rerank else ''}"
                results = []
                bm = BM25Retriever(chunks)
                for case in cases:
                    start = time.time()
                    docs = bm.retrieve(case.question, k=k or Config.TOP_K)
                    latency = (time.time() - start) * 1000
                    kw_recall = self._keyword_recall(docs, case.expected_keywords)
                    hit = self._source_hit(docs, case.expected_sources) and kw_recall >= 0.5
                    mrr = self._mrr(docs, case.expected_keywords)
                    results.append({
                        "question": case.question,
                        "method": method,
                        "rerank": rerank,
                        "hit": hit,
                        "recall_at_k": kw_recall,
                        "mrr": mrr,
                        "keyword_recall": kw_recall,
                        "latency_ms": round(latency, 2),
                        "retrieved_sources": [self._doc_source(d) for d in docs],
                    })
                all_results[key] = results
                summary[key] = {
                    "hit_rate": sum(1 for r in results if r["hit"]) / len(results),
                    "avg_recall_at_k": sum(r["recall_at_k"] for r in results) / len(results),
                    "avg_mrr": sum(r["mrr"] for r in results) / len(results),
                    "avg_latency_ms": sum(r["latency_ms"] for r in results) / len(results),
                    "total_cases": len(results),
                }

        best = max(summary, key=lambda k: summary[k]["hit_rate"]) if summary else None
        return {
            "summary": summary,
            "best_strategy": best,
            "results": all_results,
            "mode": "bm25_only",
        }

    def run_backtest(
        self,
        dataset_path: str,
        methods: Optional[List[str]] = None,
        rerank_options: Optional[List[bool]] = None,
        k: int = None,
        offline: bool = False,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """对比多种检索策略的回测"""
        cases = self.load_dataset(dataset_path)
        methods = methods or ["vector", "bm25", "hybrid"]
        rerank_options = rerank_options or [False, True]

        mode = "full" if self.assistant else "local"
        if offline or self.assistant is None:
            try:
                self.ensure_local_retriever()
                mode = "local"
            except Exception as e:
                logger.warning("本地检索器初始化失败，降级为纯 BM25: %s", e)
                partial = self._run_bm25_only_backtest(
                    cases,
                    methods=["bm25"],
                    rerank_options=[False],
                    k=k,
                )
                return {
                    "dataset": dataset_path,
                    "total_cases": len(cases),
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    **partial,
                }

        all_results: Dict[str, List[Dict]] = {}
        summary: Dict[str, Dict[str, float]] = {}
        strategy_count = self._strategy_count(methods, rerank_options)
        total_steps = strategy_count * len(cases)
        done = 0

        self._preload_rerank_if_needed(rerank_options)
        for method in methods:
            for rerank in rerank_options:
                if rerank and method != "hybrid":
                    continue
                key = f"{method}{'+rerank' if rerank else ''}"
                results = []
                for case in cases:
                    try:
                        r = self.evaluate_retrieval(case, method=method, rerank=rerank, k=k)
                        results.append(asdict(r))
                    except Exception as e:
                        results.append({
                            "question": case.question,
                            "method": method,
                            "rerank": rerank,
                            "error": str(e),
                        })
                    done += 1
                    if progress_callback:
                        progress_callback(done, total_steps, key)
                all_results[key] = results

                valid = [r for r in results if "error" not in r]
                if valid:
                    summary[key] = {
                        "hit_rate": sum(1 for r in valid if r["hit"]) / len(valid),
                        "avg_recall_at_k": sum(r["recall_at_k"] for r in valid) / len(valid),
                        "avg_mrr": sum(r["mrr"] for r in valid) / len(valid),
                        "avg_latency_ms": sum(r["latency_ms"] for r in valid) / len(valid),
                        "total_cases": len(valid),
                    }

        # 找最佳策略
        best = None
        best_score = -1
        for key, stats in summary.items():
            score = stats["hit_rate"] * 0.5 + stats["avg_mrr"] * 0.3 + stats["avg_recall_at_k"] * 0.2
            if score > best_score:
                best_score = score
                best = key

        return {
            "dataset": dataset_path,
            "total_cases": len(cases),
            "summary": summary,
            "best_strategy": best,
            "results": all_results,
            "mode": mode,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def save_report(self, report: Dict[str, Any], output_path: str):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
