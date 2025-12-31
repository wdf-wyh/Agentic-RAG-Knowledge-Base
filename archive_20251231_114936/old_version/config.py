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
    
    # 支持多个模型提供者，例如 'openai'、'gemini' 或 'ollama'
    # 优先使用显式的 MODEL_PROVIDER；若未设置，则根据可用的 API key 自动检测
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
    OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
    # .strip()：移除字符串开头和结尾的空白字符（空格、制表符、换行符等）。
    # .lower()：将字符串转换为小写字母。  
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
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "600"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
    
    # 检索配置
    TOP_K = int(os.getenv("TOP_K", "3"))
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1000"))
    # 最大距离阈值（Chroma 返回的是距离，值越小表示越相似）
    # 如果为 None 或空字符串则不启用阈值过滤
    # 默认不启用距离阈值（避免在未明确配置时误过滤结果）
    _raw_max_distance = os.getenv("MAX_DISTANCE", "").strip()
    try:
        MAX_DISTANCE = float(_raw_max_distance) if _raw_max_distance != "" else None
    except Exception:
        MAX_DISTANCE = None
    
    # 相似度得分阈值（0-1，值越高要求相似度越高）
    # 默认 0.3：只返回相似度 >= 0.3 的文档
    # 设置为 None 则禁用此过滤
    _raw_similarity_threshold = os.getenv("SIMILARITY_THRESHOLD", "0.3").strip()
    try:
        SIMILARITY_THRESHOLD = float(_raw_similarity_threshold) if _raw_similarity_threshold != "" else None
    except Exception:
        SIMILARITY_THRESHOLD = 0.3
    
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
        elif cls.MODEL_PROVIDER == "ollama":
            # Ollama 不需要 API key，但可以验证模型名称
            if not cls.OLLAMA_MODEL:
                raise ValueError("OLLAMA_MODEL 未设置，请在 .env 文件中配置")
        else:
            raise ValueError(f"不支持的 MODEL_PROVIDER: {cls.MODEL_PROVIDER}")
        return True
