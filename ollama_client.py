"""兼容层 - 保持向后兼容性"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.services.ollama_client import generate, OllamaError

__all__ = ["generate", "OllamaError"]
