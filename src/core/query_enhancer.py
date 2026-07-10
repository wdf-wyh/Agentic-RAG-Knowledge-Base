"""查询增强：HyDE 与规则改写"""
import logging
import re
from typing import Optional, List

from src.config.settings import Config

logger = logging.getLogger(__name__)


class QueryEnhancer:
    """查询改写与 HyDE 假设文档生成"""

    RULE_REWRITES = [
        (
            re.compile(r"(深度学习|deep learning).*(架构|architecture)", re.I),
            "CNN RNN Transformer GAN 神经网络架构",
        ),
        (
            re.compile(r"(主要|常见).*(架构|模型|网络)", re.I),
            "CNN RNN Transformer GAN LSTM",
        ),
    ]

    def rewrite(self, question: str) -> str:
        """规则化查询改写"""
        if not Config.ENABLE_QUERY_REWRITE:
            return question
        for pattern, replacement in self.RULE_REWRITES:
            if pattern.search(question):
                logger.debug("查询改写: %s -> %s", question, replacement)
                return replacement
        return question

    def generate_hyde_document(self, question: str, llm=None) -> Optional[str]:
        """HyDE: 生成假设性答案文档用于检索"""
        if not Config.ENABLE_HYDE:
            return None

        prompt = (
            "请根据以下问题，写一段可能出现在知识库中的参考答案（100字以内，只输出正文）：\n"
            f"问题：{question}"
        )

        try:
            if llm is not None:
                result = llm.invoke(prompt)
                text = result.content if hasattr(result, "content") else str(result)
                return text.strip()[:500]
        except Exception as e:
            logger.warning("HyDE 生成失败: %s", e)

        # 无 LLM 时的轻量回退：拼接问题关键词
        tokens = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", question)
        return " ".join(tokens[:20]) if tokens else None

    def enhance_queries(self, question: str, llm=None) -> List[str]:
        """返回用于检索的查询列表（原始 + 改写 + HyDE）"""
        queries = []
        base = self.rewrite(question)
        queries.append(base)

        if base != question:
            queries.append(question)

        hyde = self.generate_hyde_document(question, llm=llm)
        if hyde and hyde not in queries:
            queries.append(hyde)

        return queries
