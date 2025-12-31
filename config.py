"""兼容层 - 保持向后兼容性"""
import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 从新位置导入并重新导出
from src.config.settings import Config

__all__ = ["Config"]
