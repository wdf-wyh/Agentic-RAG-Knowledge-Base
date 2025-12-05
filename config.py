"""配置管理模块"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    """配置类"""
    
    # OpenAI 配置
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    
    # 支持多个模型提供者，例如 'openai' 或 'gemini'
    # 优先使用显式的 MODEL_PROVIDER；若未设置，则根据可用的 API key 自动检测
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    _raw_provider = os.getenv("MODEL_PROVIDER", "").strip().lower()
    if _raw_provider:
        MODEL_PROVIDER = _raw_provider
    else:
        if GEMINI_API_KEY:
            MODEL_PROVIDER = "gemini"
        else:
            MODEL_PROVIDER = "openai"
    
    # 模型配置
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
    
    # 向量数据库配置
    VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./vector_db")
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
    
    # 检索配置
    TOP_K = int(os.getenv("TOP_K", "3"))
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1000"))
    
    # 文档目录
    DOCUMENTS_PATH = "./documents"
    
    @classmethod
    def validate(cls):
        """验证配置"""
        if cls.MODEL_PROVIDER == "openai":
            if not cls.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY 未设置，请在 .env 文件中配置")
        elif cls.MODEL_PROVIDER == "gemini":
            if not cls.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY 未设置，请在 .env 文件中配置")
        else:
            raise ValueError(f"不支持的 MODEL_PROVIDER: {cls.MODEL_PROVIDER}")
        return True
