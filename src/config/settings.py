"""配置管理模块"""
import os
from dotenv import load_dotenv
from typing import Optional
import pytz

# 加载环境变量
load_dotenv()

# 设置时区为中国
os.environ['TZ'] = 'Asia/Shanghai'
try:
    import time
    time.tzset()
except AttributeError:
    # Windows 不支持 tzset
    pass


class Settings:
    """环境设置类 - 用于不同环境的配置"""
    
    # 环境标识
    ENV = os.getenv("ENV", "development")
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"
    
    # 日志配置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")


class Config:
    """配置类 - 保持与原有 config.py 完全一致的功能"""
    
    # OpenAI 配置
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    
    # 支持多个模型提供者，例如 'openai'、'gemini' 或 'ollama'
    # 优先使用显式的 MODEL_PROVIDER；若未设置，则根据可用的 API key 自动检测
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
    OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
    # DeepSeek 配置
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com")
    # .strip()：移除字符串开头和结尾的空白字符（空格、制表符、换行符等）。
    # .lower()：将字符串转换为小写字母。  
    _raw_provider = os.getenv("MODEL_PROVIDER", "").strip().lower()
    if _raw_provider:
        MODEL_PROVIDER = _raw_provider
    else:
        # 自动检测可用的 API key，优先顺序：GEMINI -> DEEPSEEK -> OPENAI
        if GEMINI_API_KEY:
            MODEL_PROVIDER = "gemini"
        elif DEEPSEEK_API_KEY:
            MODEL_PROVIDER = "deepseek"
        elif OPENAI_API_KEY:
            MODEL_PROVIDER = "openai"
        else:
            MODEL_PROVIDER = "openai"
    
    # 模型配置
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
    
    # 向量数据库配置
    VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./vector_db")
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "600"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
    
    # 检索配置
    TOP_K = int(os.getenv("TOP_K", "2"))  # 从3改为2以加快检索速度
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "800"))  # 从1000改为800以加快生成
    # 最大距离阈值（Chroma 返回的是距离，值越小表示越相似）
    # 如果为 None 或空字符串则不启用阈值过滤
    # 默认不启用距离阈值（避免在未明确配置时误过滤结果）
    _raw_max_distance = os.getenv("MAX_DISTANCE", "").strip()
    try:
        MAX_DISTANCE = float(_raw_max_distance) if _raw_max_distance != "" else None
    except Exception:
        MAX_DISTANCE = None
    
    # 相似度得分阈值（0-1，值越高要求相似度越高）
    # 默认 0.2：只返回相似度 >= 0.2 的文档（从0.3降低到0.2以提高命中率）
    # 设置为 None 则禁用此过滤
    _raw_similarity_threshold = os.getenv("SIMILARITY_THRESHOLD", "0.2").strip()
    try:
        SIMILARITY_THRESHOLD = float(_raw_similarity_threshold) if _raw_similarity_threshold != "" else None
    except Exception:
        SIMILARITY_THRESHOLD = 0.2
    
    # RAG 性能优化配置
    RAG_FAST_MODE = os.getenv("RAG_FAST_MODE", "true").lower() == "true"

    # 检索增强配置
    DEFAULT_RETRIEVAL_METHOD = os.getenv("DEFAULT_RETRIEVAL_METHOD", "hybrid")  # vector | bm25 | hybrid
    ENABLE_RERANK = os.getenv("ENABLE_RERANK", "true").lower() == "true"
    RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
    ENABLE_HYDE = os.getenv("ENABLE_HYDE", "false").lower() == "true"
    ENABLE_QUERY_REWRITE = os.getenv("ENABLE_QUERY_REWRITE", "true").lower() == "true"
    ENABLE_GRAPH_RAG = os.getenv("ENABLE_GRAPH_RAG", "true").lower() == "true"

    # GraphRAG / 增量索引
    GRAPH_RAG_PATH = os.getenv("GRAPH_RAG_PATH", "./data/knowledge_graph.json")
    INDEX_MANIFEST_PATH = os.getenv("INDEX_MANIFEST_PATH", "./data/index_manifest.json")
    TRACE_STORAGE_PATH = os.getenv("TRACE_STORAGE_PATH", "./data/traces")
    AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_PATH", "./logs/audit/audit.jsonl")

    # JWT 鉴权
    ENABLE_AUTH = os.getenv("ENABLE_AUTH", "false").lower() == "true"
    JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    DEFAULT_TENANT_ID = os.getenv("DEFAULT_TENANT_ID", "default")
    ENABLE_SECURITY_GUARDRAILS = os.getenv("ENABLE_SECURITY_GUARDRAILS", "true").lower() == "true"
    MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "12000"))
    ENABLE_PII_REDACTION = os.getenv("ENABLE_PII_REDACTION", "true").lower() == "true"
    ENABLE_ABAC = os.getenv("ENABLE_ABAC", "true").lower() == "true"
    EVAL_MIN_HIT_RATE = float(os.getenv("EVAL_MIN_HIT_RATE", "0.6"))
    EVAL_MIN_GUARDRAIL_PASS_RATE = float(os.getenv("EVAL_MIN_GUARDRAIL_PASS_RATE", "1.0"))

    # OIDC / 企业 SSO
    ENABLE_OIDC = os.getenv("ENABLE_OIDC", "false").lower() == "true"
    OIDC_ISSUER = os.getenv("OIDC_ISSUER", "")
    OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "")
    OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "")
    OIDC_REDIRECT_URI = os.getenv("OIDC_REDIRECT_URI", "http://localhost:8000/api/auth/oidc/callback")
    OIDC_SCOPES = os.getenv("OIDC_SCOPES", "openid profile email")
    OIDC_ROLE_CLAIM = os.getenv("OIDC_ROLE_CLAIM", "roles")
    OIDC_TENANT_CLAIM = os.getenv("OIDC_TENANT_CLAIM", "tenant_id")
    OIDC_FRONTEND_CALLBACK_URL = os.getenv("OIDC_FRONTEND_CALLBACK_URL", "http://localhost:5173/")
    OIDC_ADMIN_ROLES = [role.strip() for role in os.getenv("OIDC_ADMIN_ROLES", "admin,Administrator").split(",") if role.strip()]
    OIDC_AUDITOR_ROLES = [role.strip() for role in os.getenv("OIDC_AUDITOR_ROLES", "auditor,Auditor").split(",") if role.strip()]

    # 成本 / 配额治理
    ENABLE_QUOTA_ENFORCEMENT = os.getenv("ENABLE_QUOTA_ENFORCEMENT", "false").lower() == "true"
    QUOTA_DAILY_QUERIES = int(os.getenv("QUOTA_DAILY_QUERIES", "1000"))
    QUOTA_DAILY_TOKENS = int(os.getenv("QUOTA_DAILY_TOKENS", "500000"))
    QUOTA_DAILY_COST_USD = float(os.getenv("QUOTA_DAILY_COST_USD", "20"))

    # 企业 Webhook
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
    WEBHOOK_EVENTS = os.getenv(
        "WEBHOOK_EVENTS",
        "auth.login,auth.oidc_login,query.blocked,quota.exceeded,query.completed,build.completed,retention.cleanup,compliance.exported",
    )
    WEBHOOK_TIMEOUT_SECONDS = float(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "5"))

    # 数据保留 / 合规导出
    ENABLE_DATA_RETENTION = os.getenv("ENABLE_DATA_RETENTION", "false").lower() == "true"
    DATA_RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "90"))
    
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
        elif cls.MODEL_PROVIDER == "deepseek":
            if not cls.DEEPSEEK_API_KEY:
                raise ValueError("DEEPSEEK_API_KEY 未设置，请在 .env 文件中配置")
        else:
            raise ValueError(f"不支持的 MODEL_PROVIDER: {cls.MODEL_PROVIDER}")
        return True
