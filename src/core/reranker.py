"""Cross-Encoder 重排序模块"""
import logging
from typing import List, Any, Optional, Tuple

from src.config.settings import Config

logger = logging.getLogger(__name__)

_cross_encoder = None

try:
    from sentence_transformers import CrossEncoder
except Exception:
    CrossEncoder = None


def get_cross_encoder(model_name: Optional[str] = None):
    """获取单例 CrossEncoder 实例"""
    global _cross_encoder
    if CrossEncoder is None:
        raise ImportError("请安装 sentence-transformers: pip install sentence-transformers")

    model_name = model_name or Config.RERANK_MODEL
    if _cross_encoder is None or getattr(_cross_encoder, "_model_name", None) != model_name:
        import os
        if not os.getenv("HF_ENDPOINT"):
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        logger.info("加载 Reranker 模型: %s", model_name)
        _cross_encoder = CrossEncoder(model_name)
        _cross_encoder._model_name = model_name
    return _cross_encoder


def rerank_documents(
    query: str,
    candidates: List[Any],
    top_k: Optional[int] = None,
    model_name: Optional[str] = None,
    return_scores: bool = False,
) -> List[Any]:
    """使用 Cross-Encoder 对候选文档重排序"""
    if not candidates:
        return []

    top_k = top_k or Config.TOP_K
    model = get_cross_encoder(model_name)

    pairs = []
    for doc in candidates:
        if hasattr(doc, "page_content"):
            text = doc.page_content or ""
        elif isinstance(doc, dict):
            text = doc.get("page_content") or doc.get("content") or ""
        else:
            text = str(doc)
        pairs.append((query, text))

    scores = model.predict(pairs)
    ranked: List[Tuple[float, Any]] = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)

    if return_scores:
        return [(doc, float(score)) for score, doc in ranked[:top_k]]
    return [doc for _, doc in ranked[:top_k]]
