#!/usr/bin/env python3
"""
RAG 知识库系统 - 命令行主程序

兼容旧的 main.py 入口，重定向到新的 CLI 模块  
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入并运行新的 CLI
from run_cli import main

if __name__ == "__main__":
    main()
