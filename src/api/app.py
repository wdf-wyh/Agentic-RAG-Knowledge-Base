"""FastAPI 应用工厂"""
import logging
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.api.agent_routes import router as agent_router
from src.utils.logger import setup_logging


# 在应用启动时配置日志
def configure_logging():
    """配置全局日志"""
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    backend_log = str(log_dir / "backend.log")
    
    # 配置根logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 避免重复添加handler
    if not root_logger.handlers:
        # 控制台输出
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # 文件输出
        try:
            file_handler = logging.FileHandler(backend_log, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            print(f"✓ 日志系统已初始化，日志文件: {backend_log}")
        except Exception as e:
            print(f"⚠️ 无法创建日志文件: {e}")


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    # 配置日志系统
    configure_logging()
    
    app = FastAPI(
        title="Agentic RAG API",
        description="具备自主决策能力的 RAG 知识库系统 API - 支持多工具协调、自省反思、规划推理",
        version="3.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # 配置 CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    app.include_router(router, prefix="/api")
    app.include_router(agent_router, prefix="/api")  # Agent 路由
    
    @app.get("/")
    async def root():
        return {
            "name": "Agentic RAG System",
            "version": "3.0.0",
            "description": "具备自主决策能力的 RAG 知识库系统",
            "features": [
                "RAG 检索增强生成",
                "ReAct 推理框架",
                "多工具协调",
                "自省与反思",
                "网页搜索",
                "文件管理"
            ],
            "docs": "/docs"
        }
    
    return app


# 创建应用实例
app = create_app()
