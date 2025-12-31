"""轻量 BM25 检索器，基于 rank_bm25 实现稀疏检索"""
from typing import List, Any
from rank_bm25 import BM25Okapi
import re
try:
    import jieba
except Exception:
    jieba = None


def tokenize(text: str):
    if not text:
        return []
    text = str(text)
    # 优先使用 jieba（中文），否则使用简单正则分割
    if jieba is not None:
        tokens = [t.strip().lower() for t in jieba.cut(text) if t.strip()]
        return tokens
    parts = re.split(r"[^\u4e00-\u9fffA-Za-z0-9]+", text)
    return [p.lower() for p in parts if p]


class BM25Retriever:
    def __init__(self, documents: List[Any]):
        """初始化 BM25 检索器。

        documents: 文档对象列表，需包含 page_content 属性或作为 dict 的 page_content
        """
        # 确保内部使用 list，并且 corpus 与 docs 索引对齐
        self.docs = list(documents)
        self.corpus = []
        cleaned_docs = []
        for d in self.docs:
            if hasattr(d, 'page_content'):
                txt = getattr(d, 'page_content', '') or ''
            elif isinstance(d, dict):
                txt = d.get('page_content') or d.get('content') or ''
            else:
                txt = str(d) or ''
            txt = txt.strip()
            if not txt:
                # 跳过空文档
                continue
            self.corpus.append(txt)
            cleaned_docs.append(d)

        # 更新 docs 与 corpus 为清理后的对齐列表
        self.docs = cleaned_docs
        tokenized = [tokenize(t) for t in self.corpus]
        self.bm25 = BM25Okapi(tokenized)

    def retrieve(self, query: str, k: int = 5) -> List[Any]:
        qtok = tokenize(query)
        scores = self.bm25.get_scores(qtok)
        ranked_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        results = []
        for i in ranked_idx:
            try:
                results.append(self.docs[i])
            except Exception:
                # 保护性回退：如果索引失败，跳过
                continue
        return results
