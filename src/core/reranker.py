"""Cross-Encoder 重排序模块"""
import logging
import threading
from typing import List, Any, Optional, Tuple, Callable

from src.config.settings import Config

logger = logging.getLogger(__name__)

_cross_encoder = None
_download_lock = threading.Lock()
_download_status = {
    "active": False,
    "model": "",
    "phase": "",  # downloading | loading | ready | idle
    "file": "",
    "downloaded_bytes": 0,
    "total_bytes": 0,
    "percent": 0.0,
    "message": "",
}
_progress_callbacks: List[Callable[[dict], None]] = []

try:
    from sentence_transformers import CrossEncoder
except Exception:
    CrossEncoder = None


def get_download_status() -> dict:
    """返回当前 Rerank 模型下载/加载进度快照。"""
    with _download_lock:
        return dict(_download_status)


def set_progress_callback(callback: Optional[Callable[[dict], None]]):
    """注册进度回调（传 None 清空）。评测任务用它把进度写入 API status。"""
    global _progress_callbacks
    with _download_lock:
        _progress_callbacks = [callback] if callback else []


def _emit_status(**kwargs):
    with _download_lock:
        _download_status.update(kwargs)
        snapshot = dict(_download_status)
        callbacks = list(_progress_callbacks)
    for cb in callbacks:
        try:
            cb(snapshot)
        except Exception:
            pass


def _format_bytes(n: Optional[float]) -> str:
    if n is None or n <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    size = float(n)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _make_progress_tqdm():
    """构造会回写全局下载进度的 tqdm 子类，供 snapshot_download 使用。"""
    from tqdm.auto import tqdm as std_tqdm

    class DownloadProgressTqdm(std_tqdm):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("disable", False)
            super().__init__(*args, **kwargs)
            self._sync_status()

        def update(self, n=1):
            super().update(n)
            self._sync_status()

        def close(self):
            self._sync_status()
            super().close()

        def _sync_status(self):
            total = float(self.total or 0)
            current = float(self.n or 0)
            # 多文件并行时优先展示已知总量更大的那一个（通常是 model.safetensors）
            with _download_lock:
                prev_total = float(_download_status.get("total_bytes") or 0)
                if total and prev_total and total < prev_total * 0.5 and current < prev_total:
                    return
            desc = (self.desc or "").strip()
            percent = round(current / total * 100, 1) if total > 0 else 0.0
            msg = (
                f"正在下载 {desc or _download_status.get('model')}: "
                f"{_format_bytes(current)}"
                + (f" / {_format_bytes(total)} ({percent}%)" if total > 0 else "")
            )
            _emit_status(
                active=True,
                phase="downloading",
                file=desc,
                downloaded_bytes=int(current),
                total_bytes=int(total) if total > 0 else 0,
                percent=percent,
                message=msg,
            )

    return DownloadProgressTqdm


def get_cross_encoder(model_name: Optional[str] = None):
    """获取单例 CrossEncoder 实例（首次会下载并上报进度）"""
    global _cross_encoder
    if CrossEncoder is None:
        raise ImportError("请安装 sentence-transformers: pip install sentence-transformers")

    model_name = model_name or Config.RERANK_MODEL
    if _cross_encoder is not None and getattr(_cross_encoder, "_model_name", None) == model_name:
        return _cross_encoder

    import os
    if not os.getenv("HF_ENDPOINT"):
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

    _emit_status(
        active=True,
        model=model_name,
        phase="downloading",
        file="",
        downloaded_bytes=0,
        total_bytes=0,
        percent=0.0,
        message=f"准备下载 Rerank 模型: {model_name}",
    )
    logger.info("加载 Reranker 模型: %s", model_name)

    local_path = model_name
    try:
        from huggingface_hub import snapshot_download

        local_path = snapshot_download(
            repo_id=model_name,
            tqdm_class=_make_progress_tqdm(),
        )
    except Exception as e:
        logger.warning("snapshot_download 进度跟踪失败，回退直接加载: %s", e)
        _emit_status(
            active=True,
            model=model_name,
            phase="downloading",
            message=f"正在拉取模型（无细粒度进度）: {model_name}",
        )

    _emit_status(
        active=True,
        model=model_name,
        phase="loading",
        percent=100.0 if _download_status.get("total_bytes") else _download_status.get("percent", 0),
        message=f"下载完成，正在加载到内存: {model_name}",
    )
    _cross_encoder = CrossEncoder(local_path)
    _cross_encoder._model_name = model_name

    _emit_status(
        active=False,
        model=model_name,
        phase="ready",
        percent=100.0,
        message=f"Rerank 模型已就绪: {model_name}",
    )
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
