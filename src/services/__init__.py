"""服务层模块"""
from src.services.rag_assistant import RAGAssistant
from src.services.ollama_client import generate as ollama_generate, OllamaError

__all__ = ["RAGAssistant", "ollama_generate", "OllamaError"]
