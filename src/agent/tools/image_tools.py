"""图像分析工具 - 让 Agent 具备多模态视觉能力

支持功能：
- 图像描述: 自动生成图像内容描述
- OCR 提取: 从图像中提取文字
- 图表分析: 解析图表、流程图、架构图
- 文档理解: PDF/图片文档的智能解析
- 对比分析: 多图比较和差异分析
"""

import base64
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from enum import Enum
from urllib.parse import urlparse

import requests

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory
from src.config.settings import Config

logger = logging.getLogger(__name__)


class ImageAnalysisMode(Enum):
    """图像分析模式"""
    DESCRIBE = "describe"       # 图像描述
    OCR = "ocr"                 # OCR 文字提取
    CHART = "chart"             # 图表分析
    DOCUMENT = "document"       # 文档理解
    COMPARE = "compare"         # 对比分析


class ImageAnalysisTool(BaseTool):
    """图像分析工具
    
    集成多模态视觉模型，支持图像理解、分析和描述。
    
    支持的模型后端:
    - OpenAI: GPT-4V / GPT-4o
    - Google: Gemini Pro Vision
    - Anthropic: Claude 3 Vision
    - Ollama: LLaVA / BakLLaVA
    """
    
    # 支持的图像格式
    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    
    # 最大图像大小 (MB)
    MAX_IMAGE_SIZE_MB = 20
    
    def __init__(self, backend: str = "ollama"):
        """初始化图像分析工具
        
        Args:
            backend: 模型后端，可选 'openai', 'gemini', 'claude', 'ollama'
        """
        self._backend = backend
        self._config = Config()
        self._session = requests.Session()  # 复用 HTTP 连接
        self._session.timeout = 120
        super().__init__()
    
    def __del__(self):
        """析构函数：确保关闭 HTTP 会话"""
        if hasattr(self, '_session') and self._session:
            try:
                self._session.close()
            except Exception:
                pass
    
    @property
    def name(self) -> str:
        return "image_analysis"
    
    @property
    def description(self) -> str:
        return """分析图像内容，支持多种分析模式：
- describe: 生成图像内容的详细描述
- ocr: 从图像中提取文字内容
- chart: 解析图表、流程图、架构图的结构和数据
- document: 智能解析 PDF/图片文档
- compare: 对比多张图片的异同"""
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "image_path",
                "type": "string",
                "description": "图像文件路径（本地路径或 URL）",
                "required": True
            },
            {
                "name": "mode",
                "type": "string",
                "description": "分析模式: 'describe'(描述), 'ocr'(文字提取), 'chart'(图表解析), 'document'(文档理解), 'compare'(对比分析)，默认 'describe'",
                "required": False
            },
            {
                "name": "compare_with",
                "type": "string",
                "description": "对比分析时的第二张图片路径（仅 compare 模式需要）",
                "required": False
            },
            {
                "name": "question",
                "type": "string",
                "description": "针对图像的具体问题（可选，用于更精准的分析）",
                "required": False
            },
            {
                "name": "language",
                "type": "string",
                "description": "OCR 提取的目标语言，默认 'auto' 自动检测",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """执行图像分析"""
        image_path = kwargs.get("image_path")
        mode = kwargs.get("mode", "describe")
        compare_with = kwargs.get("compare_with")
        question = kwargs.get("question")
        language = kwargs.get("language", "auto")
        
        # 验证图像路径
        validation_result = self._validate_image(image_path)
        if not validation_result["valid"]:
            return ToolResult(
                success=False,
                output="",
                error=validation_result["error"]
            )
        
        # 根据模式执行不同的分析
        try:
            if mode == ImageAnalysisMode.DESCRIBE.value:
                return self._describe_image(image_path, question)
            elif mode == ImageAnalysisMode.OCR.value:
                return self._extract_text(image_path, language)
            elif mode == ImageAnalysisMode.CHART.value:
                return self._analyze_chart(image_path, question)
            elif mode == ImageAnalysisMode.DOCUMENT.value:
                return self._parse_document(image_path, question)
            elif mode == ImageAnalysisMode.COMPARE.value:
                if not compare_with:
                    return ToolResult(
                        success=False,
                        output="",
                        error="对比分析模式需要提供 compare_with 参数指定第二张图片"
                    )
                return self._compare_images(image_path, compare_with, question)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"不支持的分析模式: {mode}，可选: describe, ocr, chart, document, compare"
                )
        except Exception as e:
            logger.error(f"图像分析失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"图像分析失败: {str(e)}"
            )
    
    def _validate_image(self, image_path: str) -> Dict[str, Any]:
        """验证图像文件"""
        # 检查是否是 URL
        if image_path.startswith(('http://', 'https://')):
            return {"valid": True, "type": "url"}
        
        # 检查本地文件
        path = Path(image_path)
        
        if not path.exists():
            return {"valid": False, "error": f"图像文件不存在: {image_path}"}
        
        if not path.is_file():
            return {"valid": False, "error": f"路径不是文件: {image_path}"}
        
        # 检查文件格式
        if path.suffix.lower() not in self.SUPPORTED_FORMATS:
            return {
                "valid": False, 
                "error": f"不支持的图像格式: {path.suffix}，支持: {', '.join(self.SUPPORTED_FORMATS)}"
            }
        
        # 检查文件大小
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > self.MAX_IMAGE_SIZE_MB:
            return {
                "valid": False,
                "error": f"图像文件过大: {size_mb:.1f}MB，最大支持: {self.MAX_IMAGE_SIZE_MB}MB"
            }
        
        return {"valid": True, "type": "local", "size_mb": size_mb}
    
    def _load_image_base64(self, image_path: str) -> Optional[str]:
        """加载图像并转换为 base64"""
        try:
            if image_path.startswith(('http://', 'https://')):
                response = self._session.get(image_path, timeout=30)
                response.raise_for_status()
                return base64.b64encode(response.content).decode('utf-8')
            else:
                with open(image_path, 'rb') as f:
                    return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"加载图像失败: {e}")
            return None
    
    def _get_image_mime_type(self, image_path: str) -> str:
        """获取图像 MIME 类型"""
        # 处理 URL 中可能包含的查询参数
        if image_path.startswith(('http://', 'https://')):
            parsed = urlparse(image_path)
            path = parsed.path
        else:
            path = image_path
        
        ext = Path(path).suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp'
        }
        return mime_types.get(ext, 'image/jpeg')
    
    def _call_vision_model(self, image_path: str, prompt: str) -> ToolResult:
        """调用视觉模型 API"""
        image_base64 = self._load_image_base64(image_path)
        if not image_base64:
            return ToolResult(
                success=False,
                output="",
                error="无法加载图像文件"
            )
        
        mime_type = self._get_image_mime_type(image_path)
        
        # 根据后端调用不同的 API
        if self._backend == "ollama":
            return self._call_ollama_vision(image_base64, prompt)
        elif self._backend == "openai":
            return self._call_openai_vision(image_base64, mime_type, prompt)
        elif self._backend == "gemini":
            return self._call_gemini_vision(image_base64, mime_type, prompt)
        elif self._backend == "claude":
            return self._call_claude_vision(image_base64, mime_type, prompt)
        else:
            return ToolResult(
                success=False,
                output="",
                error=f"不支持的模型后端: {self._backend}"
            )
    
    def _call_ollama_vision(self, image_base64: str, prompt: str) -> ToolResult:
        """调用 Ollama 视觉模型 (LLaVA)"""
        try:
            ollama_url = getattr(self._config, 'OLLAMA_BASE_URL', 'http://localhost:11434')
            vision_model = getattr(self._config, 'OLLAMA_VISION_MODEL', 'llava')
            
            response = self._session.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": vision_model,
                    "prompt": prompt,
                    "images": [image_base64],
                    "stream": False
                },
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            return ToolResult(
                success=True,
                output=result.get("response", ""),
                metadata={"model": vision_model, "backend": "ollama"}
            )
        except Exception as e:
            logger.error(f"Ollama 视觉模型调用失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Ollama 视觉模型调用失败: {str(e)}"
            )
    
    def _call_openai_vision(self, image_base64: str, mime_type: str, prompt: str) -> ToolResult:
        """调用 OpenAI 视觉模型 (GPT-4V)"""
        try:
            api_key = getattr(self._config, 'OPENAI_API_KEY', None)
            if not api_key:
                return ToolResult(
                    success=False,
                    output="",
                    error="未配置 OPENAI_API_KEY"
                )
            
            vision_model = getattr(self._config, 'OPENAI_VISION_MODEL', 'gpt-4o')
            
            response = self._session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": vision_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{image_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    "max_tokens": 4096
                },
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            return ToolResult(
                success=True,
                output=content,
                metadata={"model": vision_model, "backend": "openai"}
            )
        except Exception as e:
            logger.error(f"OpenAI 视觉模型调用失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"OpenAI 视觉模型调用失败: {str(e)}"
            )
    
    def _call_gemini_vision(self, image_base64: str, mime_type: str, prompt: str) -> ToolResult:
        """调用 Google Gemini 视觉模型"""
        try:
            api_key = getattr(self._config, 'GOOGLE_API_KEY', None)
            if not api_key:
                return ToolResult(
                    success=False,
                    output="",
                    error="未配置 GOOGLE_API_KEY"
                )
            
            vision_model = getattr(self._config, 'GEMINI_VISION_MODEL', 'gemini-pro-vision')
            
            response = self._session.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{vision_model}:generateContent?key={api_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [
                        {
                            "parts": [
                                {"text": prompt},
                                {
                                    "inline_data": {
                                        "mime_type": mime_type,
                                        "data": image_base64
                                    }
                                }
                            ]
                        }
                    ]
                },
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["candidates"][0]["content"]["parts"][0]["text"]
            return ToolResult(
                success=True,
                output=content,
                metadata={"model": vision_model, "backend": "gemini"}
            )
        except Exception as e:
            logger.error(f"Gemini 视觉模型调用失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Gemini 视觉模型调用失败: {str(e)}"
            )
    
    def _call_claude_vision(self, image_base64: str, mime_type: str, prompt: str) -> ToolResult:
        """调用 Anthropic Claude 视觉模型"""
        try:
            api_key = getattr(self._config, 'ANTHROPIC_API_KEY', None)
            if not api_key:
                return ToolResult(
                    success=False,
                    output="",
                    error="未配置 ANTHROPIC_API_KEY"
                )
            
            vision_model = getattr(self._config, 'CLAUDE_VISION_MODEL', 'claude-3-5-sonnet-20241022')
            
            response = self._session.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": vision_model,
                    "max_tokens": 4096,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": mime_type,
                                        "data": image_base64
                                    }
                                },
                                {"type": "text", "text": prompt}
                            ]
                        }
                    ]
                },
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["content"][0]["text"]
            return ToolResult(
                success=True,
                output=content,
                metadata={"model": vision_model, "backend": "claude"}
            )
        except Exception as e:
            logger.error(f"Claude 视觉模型调用失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Claude 视觉模型调用失败: {str(e)}"
            )
    
    def _describe_image(self, image_path: str, question: str = None) -> ToolResult:
        """生成图像内容描述"""
        if question:
            prompt = f"""请仔细观察这张图片，并回答以下问题：
{question}

请提供详细且准确的回答。"""
        else:
            prompt = """请详细描述这张图片的内容，包括：
1. 图片中的主要对象和场景
2. 颜色、布局和构图特点
3. 图片传达的信息或氛围
4. 任何值得注意的细节

请用清晰、结构化的方式描述。"""
        
        result = self._call_vision_model(image_path, prompt)
        if result.success:
            result.metadata["mode"] = "describe"
            result.metadata["image_path"] = image_path
        return result
    
    def _extract_text(self, image_path: str, language: str = "auto") -> ToolResult:
        """从图像中提取文字 (OCR)"""
        lang_hint = "" if language == "auto" else f"（目标语言: {language}）"
        prompt = f"""请仔细识别并提取这张图片中的所有文字内容{lang_hint}。

要求：
1. 按照图片中的阅读顺序提取文字
2. 保持原有的格式和结构（如段落、列表等）
3. 如果有表格，请用 Markdown 表格格式呈现
4. 对于模糊或不确定的文字，用 [?] 标记
5. 如果图片中没有文字，请说明"图片中未检测到文字内容"

请直接输出提取的文字内容："""
        
        result = self._call_vision_model(image_path, prompt)
        if result.success:
            result.metadata["mode"] = "ocr"
            result.metadata["language"] = language
            result.metadata["image_path"] = image_path
        return result
    
    def _analyze_chart(self, image_path: str, question: str = None) -> ToolResult:
        """解析图表、流程图、架构图"""
        base_prompt = """请分析这张图表/图示，提供以下信息：

1. **图表类型**: 识别这是什么类型的图表（柱状图、折线图、饼图、流程图、架构图、思维导图等）

2. **主要内容**:
   - 如果是数据图表：提取关键数据点、趋势、对比关系
   - 如果是流程图：描述流程步骤和逻辑关系
   - 如果是架构图：说明各组件及其连接关系

3. **关键洞察**: 从图表中可以得出的主要结论或发现

4. **数据提取**: 如果可能，以结构化格式（如表格或列表）呈现图表中的数据"""
        
        if question:
            prompt = f"{base_prompt}\n\n5. **特定问题**: {question}"
        else:
            prompt = base_prompt
        
        result = self._call_vision_model(image_path, prompt)
        if result.success:
            result.metadata["mode"] = "chart"
            result.metadata["image_path"] = image_path
        return result
    
    def _parse_document(self, image_path: str, question: str = None) -> ToolResult:
        """智能解析 PDF/图片文档"""
        base_prompt = """请智能解析这份文档图片，提供以下内容：

1. **文档类型**: 识别文档类型（报告、表单、发票、合同、信件等）

2. **结构化信息提取**:
   - 标题和章节
   - 关键字段和值（如日期、金额、姓名等）
   - 表格数据（如有）
   - 列表内容

3. **完整文本内容**: 按原文档结构提取所有文字

4. **文档摘要**: 简要概括文档的主要内容和目的"""
        
        if question:
            prompt = f"{base_prompt}\n\n5. **特定查询**: {question}"
        else:
            prompt = base_prompt
        
        result = self._call_vision_model(image_path, prompt)
        if result.success:
            result.metadata["mode"] = "document"
            result.metadata["image_path"] = image_path
        return result
    
    def _compare_images(self, image_path1: str, image_path2: str, question: str = None) -> ToolResult:
        """对比分析两张图片"""
        # 加载两张图片
        image1_base64 = self._load_image_base64(image_path1)
        image2_base64 = self._load_image_base64(image_path2)
        
        if not image1_base64 or not image2_base64:
            return ToolResult(
                success=False,
                output="",
                error="无法加载对比图像"
            )
        
        base_prompt = """请对比分析这两张图片：

1. **相似之处**: 两张图片有哪些共同点？

2. **差异之处**: 两张图片的主要区别是什么？

3. **变化分析**: 如果这是同一对象的前后对比，发生了什么变化？

4. **详细对比**: 按不同维度（颜色、构图、内容、质量等）逐项对比"""
        
        if question:
            prompt = f"{base_prompt}\n\n5. **特定问题**: {question}"
        else:
            prompt = base_prompt
        
        # 对于对比分析，需要特殊处理（发送两张图片）
        # 这里使用 OpenAI 或 Claude 的多图能力
        if self._backend == "openai":
            return self._compare_with_openai(image1_base64, image2_base64, image_path1, image_path2, prompt)
        elif self._backend == "claude":
            return self._compare_with_claude(image1_base64, image2_base64, image_path1, image_path2, prompt)
        else:
            # 对于不支持多图的后端，分别分析后合并
            return self._compare_fallback(image_path1, image_path2, prompt)
    
    def _compare_with_openai(self, img1_b64: str, img2_b64: str, 
                              path1: str, path2: str, prompt: str) -> ToolResult:
        """使用 OpenAI 进行多图对比"""
        try:
            api_key = getattr(self._config, 'OPENAI_API_KEY', None)
            if not api_key:
                return ToolResult(success=False, output="", error="未配置 OPENAI_API_KEY")
            
            vision_model = getattr(self._config, 'OPENAI_VISION_MODEL', 'gpt-4o')
            mime1 = self._get_image_mime_type(path1)
            mime2 = self._get_image_mime_type(path2)
            
            response = self._session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": vision_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "第一张图片:"},
                                {"type": "image_url", "image_url": {"url": f"data:{mime1};base64,{img1_b64}"}},
                                {"type": "text", "text": "第二张图片:"},
                                {"type": "image_url", "image_url": {"url": f"data:{mime2};base64,{img2_b64}"}},
                                {"type": "text", "text": prompt}
                            ]
                        }
                    ],
                    "max_tokens": 4096
                },
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            return ToolResult(
                success=True,
                output=content,
                metadata={"model": vision_model, "backend": "openai", "mode": "compare", 
                         "image_path_1": path1, "image_path_2": path2}
            )
        except Exception as e:
            logger.error(f"OpenAI 多图对比失败: {e}")
            return ToolResult(success=False, output="", error=f"多图对比失败: {str(e)}")
    
    def _compare_with_claude(self, img1_b64: str, img2_b64: str,
                              path1: str, path2: str, prompt: str) -> ToolResult:
        """使用 Claude 进行多图对比"""
        try:
            api_key = getattr(self._config, 'ANTHROPIC_API_KEY', None)
            if not api_key:
                return ToolResult(success=False, output="", error="未配置 ANTHROPIC_API_KEY")
            
            vision_model = getattr(self._config, 'CLAUDE_VISION_MODEL', 'claude-3-5-sonnet-20241022')
            mime1 = self._get_image_mime_type(path1)
            mime2 = self._get_image_mime_type(path2)
            
            response = self._session.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": vision_model,
                    "max_tokens": 4096,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "第一张图片:"},
                                {"type": "image", "source": {"type": "base64", "media_type": mime1, "data": img1_b64}},
                                {"type": "text", "text": "第二张图片:"},
                                {"type": "image", "source": {"type": "base64", "media_type": mime2, "data": img2_b64}},
                                {"type": "text", "text": prompt}
                            ]
                        }
                    ]
                },
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["content"][0]["text"]
            return ToolResult(
                success=True,
                output=content,
                metadata={"model": vision_model, "backend": "claude", "mode": "compare",
                         "image_path_1": path1, "image_path_2": path2}
            )
        except Exception as e:
            logger.error(f"Claude 多图对比失败: {e}")
            return ToolResult(success=False, output="", error=f"多图对比失败: {str(e)}")
    
    def _compare_fallback(self, image_path1: str, image_path2: str, prompt: str) -> ToolResult:
        """回退方案：分别分析两张图片"""
        result1 = self._describe_image(image_path1)
        result2 = self._describe_image(image_path2)
        
        if not result1.success or not result2.success:
            return ToolResult(
                success=False,
                output="",
                error="无法分析对比图像"
            )
        
        combined_output = f"""## 图片1分析
{result1.output}

## 图片2分析
{result2.output}

---
*注意: 当前后端不支持多图同时对比，以上为分别分析的结果。建议使用 OpenAI 或 Claude 后端获得更好的对比分析效果。*"""
        
        return ToolResult(
            success=True,
            output=combined_output,
            metadata={"mode": "compare_fallback", "image_path_1": image_path1, "image_path_2": image_path2}
        )


class BatchImageAnalysisTool(BaseTool):
    """批量图像分析工具
    
    支持对多张图片进行批量处理
    """
    
    def __init__(self, backend: str = "ollama"):
        self._backend = backend
        self._image_tool = ImageAnalysisTool(backend=backend)
        super().__init__()
    
    @property
    def name(self) -> str:
        return "batch_image_analysis"
    
    @property
    def description(self) -> str:
        return "批量分析多张图片，支持对整个目录的图片进行统一处理"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "image_paths",
                "type": "array",
                "description": "图像文件路径列表",
                "required": False
            },
            {
                "name": "directory",
                "type": "string",
                "description": "包含图片的目录路径（与 image_paths 二选一）",
                "required": False
            },
            {
                "name": "mode",
                "type": "string",
                "description": "分析模式: 'describe', 'ocr', 'chart', 'document'",
                "required": False
            },
            {
                "name": "max_images",
                "type": "integer",
                "description": "最大处理图片数量，默认 10",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """执行批量图像分析"""
        image_paths = kwargs.get("image_paths", [])
        directory = kwargs.get("directory")
        mode = kwargs.get("mode", "describe")
        max_images = kwargs.get("max_images", 10)
        
        # 如果指定了目录，扫描目录中的图片
        if directory:
            dir_path = Path(directory)
            if not dir_path.exists() or not dir_path.is_dir():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"目录不存在: {directory}"
                )
            
            image_paths = []
            for ext in ImageAnalysisTool.SUPPORTED_FORMATS:
                image_paths.extend(str(p) for p in dir_path.glob(f"*{ext}"))
                image_paths.extend(str(p) for p in dir_path.glob(f"*{ext.upper()}"))
        
        if not image_paths:
            return ToolResult(
                success=False,
                output="",
                error="没有找到要分析的图片"
            )
        
        # 限制处理数量
        image_paths = image_paths[:max_images]
        
        results = []
        for i, path in enumerate(image_paths, 1):
            logger.info(f"正在分析图片 {i}/{len(image_paths)}: {path}")
            result = self._image_tool.execute(image_path=path, mode=mode)
            results.append({
                "path": path,
                "success": result.success,
                "output": result.output if result.success else result.error
            })
        
        # 汇总结果
        success_count = sum(1 for r in results if r["success"])
        output_parts = [f"## 批量分析结果 ({success_count}/{len(results)} 成功)\n"]
        
        for i, r in enumerate(results, 1):
            status = "✅" if r["success"] else "❌"
            output_parts.append(f"\n### {status} 图片 {i}: {Path(r['path']).name}\n")
            output_parts.append(r["output"])
        
        return ToolResult(
            success=success_count > 0,
            output="\n".join(output_parts),
            data={
                "total": len(results),
                "success_count": success_count,
                "failed_count": len(results) - success_count,
                "results": results
            }
        )
