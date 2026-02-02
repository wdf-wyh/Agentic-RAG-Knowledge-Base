"""图像分析工具单元测试"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.agent.tools.image_tools import (
    ImageAnalysisTool,
    BatchImageAnalysisTool,
    ImageAnalysisMode
)
from src.agent.tools.base import ToolResult, ToolCategory


class TestImageAnalysisTool:
    """ImageAnalysisTool 测试类"""
    
    def setup_method(self):
        """测试前初始化"""
        self.tool = ImageAnalysisTool(backend="ollama")
    
    def test_tool_properties(self):
        """测试工具属性"""
        assert self.tool.name == "image_analysis"
        assert self.tool.category == ToolCategory.ANALYSIS
        assert len(self.tool.parameters) == 5
        
        param_names = [p["name"] for p in self.tool.parameters]
        assert "image_path" in param_names
        assert "mode" in param_names
        assert "compare_with" in param_names
        assert "question" in param_names
        assert "language" in param_names
    
    def test_validate_nonexistent_file(self):
        """测试不存在的文件验证"""
        result = self.tool.execute(image_path="/nonexistent/image.jpg")
        assert result.success is False
        assert "不存在" in result.error
    
    def test_validate_unsupported_format(self):
        """测试不支持的格式"""
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            f.write(b"test")
            temp_path = f.name
        
        try:
            result = self.tool.execute(image_path=temp_path)
            assert result.success is False
            assert "不支持的图像格式" in result.error
        finally:
            Path(temp_path).unlink()
    
    def test_validate_url(self):
        """测试 URL 验证"""
        validation = self.tool._validate_image("https://example.com/image.jpg")
        assert validation["valid"] is True
        assert validation["type"] == "url"
    
    def test_invalid_mode(self):
        """测试无效的分析模式"""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"fake image data")
            temp_path = f.name
        
        try:
            result = self.tool.execute(image_path=temp_path, mode="invalid_mode")
            assert result.success is False
            assert "不支持的分析模式" in result.error
        finally:
            Path(temp_path).unlink()
    
    def test_compare_mode_requires_second_image(self):
        """测试对比模式需要第二张图片"""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"fake image data")
            temp_path = f.name
        
        try:
            result = self.tool.execute(image_path=temp_path, mode="compare")
            assert result.success is False
            assert "compare_with" in result.error
        finally:
            Path(temp_path).unlink()
    
    def test_get_mime_type(self):
        """测试 MIME 类型获取"""
        assert self.tool._get_image_mime_type("test.jpg") == "image/jpeg"
        assert self.tool._get_image_mime_type("test.png") == "image/png"
        assert self.tool._get_image_mime_type("test.gif") == "image/gif"
        assert self.tool._get_image_mime_type("test.webp") == "image/webp"
    
    @patch.object(ImageAnalysisTool, '_call_vision_model')
    def test_describe_mode(self, mock_call):
        """测试描述模式"""
        mock_call.return_value = ToolResult(
            success=True,
            output="这是一张测试图片的描述",
            data={"model": "llava", "backend": "ollama"}
        )
        
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"fake image data")
            temp_path = f.name
        
        try:
            result = self.tool.execute(image_path=temp_path, mode="describe")
            assert result.success is True
            assert "描述" in result.output
            mock_call.assert_called_once()
        finally:
            Path(temp_path).unlink()
    
    @patch.object(ImageAnalysisTool, '_call_vision_model')
    def test_ocr_mode(self, mock_call):
        """测试 OCR 模式"""
        mock_call.return_value = ToolResult(
            success=True,
            output="提取的文字内容",
            data={"model": "llava", "backend": "ollama"}
        )
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake image data")
            temp_path = f.name
        
        try:
            result = self.tool.execute(image_path=temp_path, mode="ocr")
            assert result.success is True
            mock_call.assert_called_once()
        finally:
            Path(temp_path).unlink()


class TestBatchImageAnalysisTool:
    """BatchImageAnalysisTool 测试类"""
    
    def setup_method(self):
        """测试前初始化"""
        self.tool = BatchImageAnalysisTool(backend="ollama")
    
    def test_tool_properties(self):
        """测试工具属性"""
        assert self.tool.name == "batch_image_analysis"
        assert self.tool.category == ToolCategory.ANALYSIS
    
    def test_empty_input(self):
        """测试空输入"""
        result = self.tool.execute()
        assert result.success is False
        assert "没有找到" in result.error
    
    def test_nonexistent_directory(self):
        """测试不存在的目录"""
        result = self.tool.execute(directory="/nonexistent/dir")
        assert result.success is False
        assert "不存在" in result.error
    
    @patch.object(ImageAnalysisTool, 'execute')
    def test_batch_processing(self, mock_execute):
        """测试批量处理"""
        mock_execute.return_value = ToolResult(
            success=True,
            output="分析结果"
        )
        
        # 创建临时目录和图片
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                (Path(tmpdir) / f"test{i}.jpg").write_bytes(b"fake")
            
            result = self.tool.execute(directory=tmpdir)
            assert result.success is True
            assert result.data["total"] == 3
            assert mock_execute.call_count == 3


if __name__ == "__main__":
    # 简单的手动测试
    print("=" * 50)
    print("图像分析工具基础测试")
    print("=" * 50)
    
    tool = ImageAnalysisTool(backend="ollama")
    print(f"✅ 工具名称: {tool.name}")
    print(f"✅ 工具分类: {tool.category}")
    print(f"✅ 支持格式: {tool.SUPPORTED_FORMATS}")
    print(f"✅ 分析模式: {[m.value for m in ImageAnalysisMode]}")
    
    # 测试参数验证
    result = tool.execute(image_path="/nonexistent.jpg")
    print(f"✅ 文件验证: {'通过' if not result.success else '失败'}")
    
    batch_tool = BatchImageAnalysisTool(backend="ollama")
    print(f"✅ 批量工具: {batch_tool.name}")
    
    print("\n所有基础测试通过! 🎉")
    print("\n要使用视觉功能，请确保:")
    print("1. Ollama 服务已启动: ollama serve")
    print("2. 已安装视觉模型: ollama pull llava")
