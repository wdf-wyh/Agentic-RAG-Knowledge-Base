"""单元测试：GraphRAG"""
from src.core.graph_rag import KnowledgeGraph


def test_extract_entities():
    kg = KnowledgeGraph(graph_path="data/test_graph.json")
    entities = kg.extract_entities("CNN 是卷积神经网络，主要用于图像识别。", source="test.md")
    assert len(entities) >= 1


def test_build_and_query():
    kg = KnowledgeGraph(graph_path="data/test_graph.json")
    text = "RAG 系统使用 Transformer 架构实现检索增强生成。"
    kg.extract_entities(text, source="demo.md")
    kg.extract_relations(text, source="demo.md")
    ctx = kg.search_context("RAG")
    assert isinstance(ctx, str)
