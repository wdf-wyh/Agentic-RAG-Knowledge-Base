"""单元测试：RAG 评测"""
import json
from pathlib import Path

from src.evaluation.rag_evaluator import RAGEvaluator, EvalCase


def test_load_dataset():
    path = "data/demo_dataset/qa_pairs.json"
    cases = RAGEvaluator.load_dataset(path)
    assert len(cases) >= 5
    assert isinstance(cases[0], EvalCase)


def test_strategy_count():
    assert RAGEvaluator._strategy_count(["vector", "bm25", "hybrid"], [False, True]) == 4
    assert RAGEvaluator._strategy_count(["vector", "bm25", "hybrid"], [False]) == 3


def test_keyword_recall():
    evaluator = RAGEvaluator()

    class FakeDoc:
        def __init__(self, text):
            self.page_content = text
            self.metadata = {}

    docs = [FakeDoc("CNN RNN Transformer GAN 是深度学习主要架构")]
    recall = evaluator._keyword_recall(docs, ["CNN", "GAN", "BERT"])
    assert recall == 2 / 3
