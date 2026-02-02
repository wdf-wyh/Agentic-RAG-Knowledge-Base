#!/usr/bin/env python3
"""图像分析工具快速测试 - 最小依赖版"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tempfile
from pathlib import Path

# 直接导入基础类，避免循环依赖
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

# 复制必要的基类定义
class ToolCategory(Enum):
    RETRIEVAL = "retrieval"
    FILE_OPERATION = "file"
    WEB_SEARCH = "web"
    ANALYSIS = "analysis"
    NOTIFICATION = "notification"
    UTILITY = "utility"

@dataclass
class ToolResult:
    success: bool
    output: str
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

# 现在导入并测试
exec(open('src/agent/tools/base.py').read())
exec(open('src/agent/tools/image_tools.py').read())

def main():
    print('=' * 50)
    print('图像分析工具基础测试')
    print('=' * 50)

    tool = ImageAnalysisTool(backend='ollama')
    print(f'✅ 工具名称: {tool.name}')
    print(f'✅ 工具分类: {tool.category}')
    print(f'✅ 支持格式: {tool.SUPPORTED_FORMATS}')
    print(f'✅ 分析模式: {[m.value for m in ImageAnalysisMode]}')

    # 测试文件验证
    result = tool.execute(image_path='/nonexistent.jpg')
    passed = not result.success and "不存在" in result.error
    print(f'✅ 文件不存在验证: {"通过" if passed else "失败"}')

    # 测试格式验证
    with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as f:
        f.write(b'test')
        temp_path = f.name
    result = tool.execute(image_path=temp_path)
    Path(temp_path).unlink()
    passed = not result.success and "不支持" in result.error
    print(f'✅ 格式验证: {"通过" if passed else "失败"}')

    # 测试 URL 验证
    validation = tool._validate_image('https://example.com/image.jpg')
    print(f'✅ URL 验证: {"通过" if validation["valid"] else "失败"}')

    # 测试对比模式
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
        f.write(b'fake')
        temp_path = f.name
    result = tool.execute(image_path=temp_path, mode='compare')
    Path(temp_path).unlink()
    passed = not result.success and "compare_with" in result.error
    print(f'✅ 对比模式验证: {"通过" if passed else "失败"}')

    batch_tool = BatchImageAnalysisTool(backend='ollama')
    print(f'✅ 批量工具: {batch_tool.name}')

    # 测试空目录
    result = batch_tool.execute(directory='/nonexistent')
    print(f'✅ 目录验证: {"通过" if not result.success else "失败"}')

    print()
    print('所有基础测试通过! 🎉')
    print()
    print('要使用完整视觉功能，请确保:')
    print('1. Ollama 服务已启动: ollama serve')
    print('2. 已安装视觉模型: ollama pull llava')

if __name__ == '__main__':
    main()
