"""单元测试：查询增强"""
from src.core.query_enhancer import QueryEnhancer


def test_rewrite_deep_learning():
    enhancer = QueryEnhancer()
    result = enhancer.rewrite("深度学习的主要架构有哪些？")
    assert "CNN" in result or "Transformer" in result


def test_enhance_queries_returns_list():
    enhancer = QueryEnhancer()
    queries = enhancer.enhance_queries("什么是 RAG？")
    assert isinstance(queries, list)
    assert len(queries) >= 1
