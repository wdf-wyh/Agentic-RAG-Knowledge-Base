"""兼容层 - 保持向后兼容性"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.bm25_retriever import BM25Retriever, tokenize

__all__ = ["BM25Retriever", "tokenize"]
