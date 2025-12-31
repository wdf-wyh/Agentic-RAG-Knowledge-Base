#!/usr/bin/env python3
"""
RAG 知识库系统 - API 服务入口

启动方式:
    python run_api.py

或使用 uvicorn:
    uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
"""
import os
import sys

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    """启动 API 服务"""
    import uvicorn
    from src.api.app import app
    
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"
    
    print(f"🚀 启动 RAG 知识库 API 服务")
    print(f"   地址: http://{host}:{port}")
    print(f"   文档: http://{host}:{port}/docs")
    
    uvicorn.run(
        "src.api.app:app",
        host=host,
        port=port,
        reload=reload
    )


if __name__ == "__main__":
    main()
