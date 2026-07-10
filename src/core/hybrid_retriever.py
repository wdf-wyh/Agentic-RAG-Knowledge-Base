"""统一混合检索管线：Vector + BM25 + Rerank + HyDE"""
import logging
import time
from typing import List, Any, Optional, Dict

from langchain_core.documents import Document

from src.config.settings import Config
from src.core.bm25_retriever import BM25Retriever
from src.core.query_enhancer import QueryEnhancer
from src.core.reranker import rerank_documents
from src.core.vector_store import VectorStore

logger = logging.getLogger(__name__)


class HybridRetriever:
    """混合检索器"""

    def __init__(self, vector_store: VectorStore, llm=None):
        self.vector_store = vector_store
        self.enhancer = QueryEnhancer()
        self.llm = llm
        self._chunks_cache: Optional[List[Any]] = None
        self._bm25_retriever: Optional[BM25Retriever] = None

    def _doc_key(self, doc: Any) -> str:
        meta = getattr(doc, "metadata", None) if hasattr(doc, "metadata") else (
            doc.get("metadata") if isinstance(doc, dict) else None
        )
        if isinstance(meta, dict):
            cid = meta.get("chunk_id") or meta.get("id")
            if cid:
                return str(cid)
        text = getattr(doc, "page_content", None) if hasattr(doc, "page_content") else (
            doc.get("page_content") if isinstance(doc, dict) else str(doc)
        )
        return (text or "").strip()[:200]

    def _get_all_chunks(self) -> List[Any]:
        if self._chunks_cache is not None:
            return self._chunks_cache

        chunks = None
        try:
            if self.vector_store.vectorstore and hasattr(self.vector_store.vectorstore, "get"):
                raw = self.vector_store.vectorstore.get()
                if raw and raw.get("documents"):
                    documents_list = raw.get("documents", [])
                    metadatas_list = raw.get("metadatas", [])
                    chunks = [
                        Document(
                            page_content=documents_list[i],
                            metadata=metadatas_list[i] if i < len(metadatas_list) else {},
                        )
                        for i in range(len(documents_list))
                    ]
        except Exception as e:
            logger.debug("从 vectorstore 获取 chunks 失败: %s", e)

        if chunks is None:
            try:
                from src.core.document_processor import DocumentProcessor
                dp = DocumentProcessor()
                chunks = dp.process_documents(Config.DOCUMENTS_PATH)
            except Exception:
                chunks = []

        self._chunks_cache = chunks or []
        self._bm25_retriever = None
        return self._chunks_cache

    def _get_bm25(self) -> Optional[BM25Retriever]:
        chunks = self._get_all_chunks()
        if not chunks:
            return None
        if self._bm25_retriever is None:
            self._bm25_retriever = BM25Retriever(chunks)
        return self._bm25_retriever

    def invalidate_cache(self):
        self._chunks_cache = None
        self._bm25_retriever = None

    def retrieve(
        self,
        query: str,
        k: Optional[int] = None,
        method: str = "hybrid",
        rerank: Optional[bool] = None,
        use_hyde: Optional[bool] = None,
        rewrite_query: Optional[bool] = None,
        candidate_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        """执行检索并返回文档与元信息"""
        start = time.time()
        k = k or Config.TOP_K
        method = method or Config.DEFAULT_RETRIEVAL_METHOD
        rerank = Config.ENABLE_RERANK if rerank is None else rerank

        rewrite_query = Config.ENABLE_QUERY_REWRITE if rewrite_query is None else rewrite_query
        queries = [query]
        if use_hyde is not False and Config.ENABLE_HYDE:
            queries = self.enhancer.enhance_queries(query, llm=self.llm)
        elif rewrite_query:
            rewritten = self.enhancer.rewrite(query)
            if rewritten != query:
                queries = [rewritten, query]

        all_candidates: List[Any] = []
        seen = set()

        cand_k = candidate_k or max(20, k * 3)

        for q in queries:
            batch = self._retrieve_single(q, k=cand_k, method=method)
            for doc in batch:
                key = self._doc_key(doc)
                if key and key not in seen:
                    seen.add(key)
                    all_candidates.append(doc)

        if rerank and all_candidates:
            try:
                docs = rerank_documents(query, all_candidates, top_k=k)
            except Exception as e:
                logger.warning("Rerank 失败，回退到混合排序: %s", e)
                docs = all_candidates[:k]
        else:
            docs = all_candidates[:k]

        elapsed_ms = (time.time() - start) * 1000
        return {
            "documents": docs,
            "meta": {
                "method": method,
                "rerank": rerank,
                "queries_used": queries,
                "candidate_count": len(all_candidates),
                "returned": len(docs),
                "latency_ms": round(elapsed_ms, 2),
            },
        }

    def _retrieve_single(self, query: str, k: int, method: str) -> List[Any]:
        similarity_threshold = getattr(Config, "SIMILARITY_THRESHOLD", None)

        if method == "vector":
            if similarity_threshold is not None:
                try:
                    pairs = self.vector_store.similarity_search_with_score_filter(
                        query, k=k, similarity_threshold=similarity_threshold
                    )
                    return [doc for doc, _ in pairs]
                except Exception:
                    pass
            return self.vector_store.similarity_search(query, k=k)

        if method == "bm25":
            bm25 = self._get_bm25()
            if bm25 is None:
                return []
            return bm25.retrieve(query, k=k)

        # hybrid
        vec_docs = self.vector_store.similarity_search(query, k=k)
        bm25 = self._get_bm25()
        if bm25 is None:
            return vec_docs

        bm_docs = bm25.retrieve(query, k=k)
        merged = []
        seen = set()
        for doc in bm_docs + vec_docs:
            key = self._doc_key(doc)
            if key and key not in seen:
                seen.add(key)
                merged.append(doc)
        return merged
