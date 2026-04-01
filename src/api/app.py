"""FastAPI 应用工厂"""
import logging
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
    # 从环境变量读取允许的来源，默认仅允许本地开发
    allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,http://localhost:80").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in allowed_origins],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )
    
    # 注册路由
    app.include_router(router, prefix="/api")
    app.include_router(agent_router, prefix="/api")  # Agent 路由

    # 静态文件服务 - 生成的图片
    generated_images_dir = Path("output/generated_images")
    generated_images_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/api/generated-images", StaticFiles(directory=str(generated_images_dir)), name="generated_images")

    # 静态文件服务 - 生成的视频
    generated_videos_dir = Path("output/generated_videos")
    generated_videos_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/api/generated-videos", StaticFiles(directory=str(generated_videos_dir)), name="generated_videos")
    
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

    @app.get("/health")
    async def health_check():
        """Docker / 负载均衡健康检查端点"""
        return {"status": "ok"}

    return app


# 创建应用实例
app = create_app()
