"""兼容层 - 保持向后兼容性

旧的 app_api.py 入口，重定向到新的 API 模块
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.api.app import app

# 为了兼容旧的启动方式
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=8000, reload=True)
