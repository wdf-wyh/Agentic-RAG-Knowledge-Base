#!/usr/bin/env python3
"""
RAG 知识库系统 - Streamlit Web 界面入口

启动方式:
    python run_web.py

或使用 streamlit:
    streamlit run app.py
"""
import os
import sys

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    """启动 Streamlit Web 界面"""
    import subprocess
    
    print("🚀 启动 RAG 知识库 Web 界面")
    subprocess.run(["streamlit", "run", "app.py"])


if __name__ == "__main__":
    main()
