"""AI 图片生成工具 - 让 Agent 具备文生图能力

支持后端：
- OpenAI DALL-E 3 / DALL-E 2
- Google Gemini Imagen
- 本地 Stable Diffusion (ComfyUI / AUTOMATIC1111)
"""

import base64
import logging
import os
import uuid
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

import requests

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory
from src.config.settings import Config

logger = logging.getLogger(__name__)

# 生成图片的保存目录
IMAGE_OUTPUT_DIR = Path("output/generated_images")
IMAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class ImageGenerationTool(BaseTool):
    """AI 图片生成工具
    
    根据文字描述生成图片，支持多种模型后端。
    """

    def __init__(self, backend: str = None):
        """初始化图片生成工具
        
        Args:
            backend: 模型后端，可选 'openai', 'gemini', 'stability', 'local'
                     默认根据 Config 自动选择
        """
        self._backend = backend or self._auto_detect_backend()
        self._config = Config()
        self._session = requests.Session()
        self._session.timeout = 120
        super().__init__()

    def __del__(self):
        if hasattr(self, '_session') and self._session:
            try:
                self._session.close()
            except Exception:
                pass

    @staticmethod
    def _auto_detect_backend() -> str:
        """根据配置自动选择后端"""
        if Config.OPENAI_API_KEY:
            return "openai"
        if Config.GEMINI_API_KEY:
            return "gemini"
        return "openai"

    @property
    def name(self) -> str:
        return "image_generation"

    @property
    def description(self) -> str:
        return (
            "根据文字描述生成图片。适用场景：用户要求画画、生成图片、创建插图、"
            "设计海报、生成头像等涉及图像创作的需求。"
            "输入 prompt（英文效果更佳）和可选的尺寸参数，返回生成的图片。"
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "prompt",
                "type": "string",
                "description": "图片描述（prompt），尽量使用英文以获得更好效果。描述要具体、详细。",
                "required": True,
            },
            {
                "name": "size",
                "type": "string",
                "description": "图片尺寸，可选: '1024x1024'(默认), '1024x1792'(竖版), '1792x1024'(横版)",
                "required": False,
            },
            {
                "name": "style",
                "type": "string",
                "description": "风格，可选: 'vivid'(生动,默认), 'natural'(自然写实)",
                "required": False,
            },
            {
                "name": "quality",
                "type": "string",
                "description": "质量，可选: 'standard'(标准,默认), 'hd'(高清)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> ToolResult:
        """执行图片生成"""
        prompt = kwargs.get("prompt", "").strip()
        if not prompt:
            return ToolResult(
                success=False,
                output="",
                error="prompt 不能为空，请提供图片描述",
            )

        size = kwargs.get("size", "1024x1024")
        style = kwargs.get("style", "vivid")
        quality = kwargs.get("quality", "standard")

        # 安全检查 - 只做基本过滤，具体内容审核由 API 端完成
        if len(prompt) > 4000:
            return ToolResult(
                success=False,
                output="",
                error="prompt 过长（最大4000字符）",
            )

        try:
            if self._backend == "openai":
                return self._generate_openai(prompt, size, style, quality)
            elif self._backend == "gemini":
                return self._generate_gemini(prompt, size)
            elif self._backend == "local":
                return self._generate_local(prompt, size)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"不支持的图片生成后端: {self._backend}",
                )
        except Exception as e:
            logger.error(f"图片生成失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"图片生成失败: {str(e)}",
            )

    def _save_image(self, image_bytes: bytes, ext: str = "png") -> str:
        """保存图片到本地并返回相对路径"""
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = IMAGE_OUTPUT_DIR / filename
        filepath.write_bytes(image_bytes)
        # 返回相对于项目根目录的路径
        return str(filepath)

    def _generate_openai(
        self, prompt: str, size: str, style: str, quality: str
    ) -> ToolResult:
        """使用 OpenAI DALL-E 生成图片"""
        api_key = Config.OPENAI_API_KEY
        if not api_key:
            return ToolResult(
                success=False,
                output="",
                error="未配置 OPENAI_API_KEY，无法使用 DALL-E 生成图片",
            )

        api_base = Config.OPENAI_API_BASE.rstrip("/")
        url = f"{api_base}/images/generations"

        payload = {
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": size,
            "style": style,
            "quality": quality,
            "response_format": "b64_json",
        }

        logger.info(f"[ImageGen] 调用 DALL-E 3, prompt: {prompt[:80]}...")

        response = self._session.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        response.raise_for_status()

        result = response.json()
        image_data = result["data"][0]
        revised_prompt = image_data.get("revised_prompt", prompt)

        # 解码 base64 并保存
        image_bytes = base64.b64decode(image_data["b64_json"])
        filepath = self._save_image(image_bytes, "png")

        # 同时返回 base64 供前端直接展示
        image_b64_url = f"data:image/png;base64,{image_data['b64_json']}"

        return ToolResult(
            success=True,
            output=f"图片已生成并保存到 {filepath}",
            data={
                "image_url": image_b64_url,
                "filepath": filepath,
                "revised_prompt": revised_prompt,
                "model": "dall-e-3",
                "size": size,
            },
            metadata={"backend": "openai", "model": "dall-e-3"},
        )

    def _generate_gemini(self, prompt: str, size: str) -> ToolResult:
        """使用 Google Gemini Imagen 生成图片"""
        api_key = Config.GEMINI_API_KEY
        if not api_key:
            return ToolResult(
                success=False,
                output="",
                error="未配置 GEMINI_API_KEY，无法使用 Imagen 生成图片",
            )

        # Gemini Imagen API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={api_key}"

        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "sampleCount": 1,
            },
        }

        logger.info(f"[ImageGen] 调用 Gemini Imagen, prompt: {prompt[:80]}...")

        response = self._session.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        response.raise_for_status()

        result = response.json()
        predictions = result.get("predictions", [])
        if not predictions:
            return ToolResult(
                success=False,
                output="",
                error="Gemini Imagen 未返回图片结果",
            )

        image_b64 = predictions[0].get("bytesBase64Encoded", "")
        if not image_b64:
            return ToolResult(
                success=False,
                output="",
                error="Gemini Imagen 返回的图片数据为空",
            )

        image_bytes = base64.b64decode(image_b64)
        filepath = self._save_image(image_bytes, "png")
        image_b64_url = f"data:image/png;base64,{image_b64}"

        return ToolResult(
            success=True,
            output=f"图片已生成并保存到 {filepath}",
            data={
                "image_url": image_b64_url,
                "filepath": filepath,
                "revised_prompt": prompt,
                "model": "imagen-3.0",
                "size": size,
            },
            metadata={"backend": "gemini", "model": "imagen-3.0"},
        )

    def _generate_local(self, prompt: str, size: str) -> ToolResult:
        """调用本地 Stable Diffusion API (AUTOMATIC1111 WebUI)"""
        sd_url = os.getenv("SD_API_URL", "http://127.0.0.1:7860")

        # 解析尺寸
        try:
            w, h = size.split("x")
            width, height = int(w), int(h)
        except (ValueError, AttributeError):
            width, height = 1024, 1024

        payload = {
            "prompt": prompt,
            "negative_prompt": "low quality, blurry, distorted",
            "width": width,
            "height": height,
            "steps": 30,
            "cfg_scale": 7.0,
            "sampler_name": "DPM++ 2M Karras",
        }

        logger.info(f"[ImageGen] 调用本地 SD, prompt: {prompt[:80]}...")

        response = self._session.post(
            f"{sd_url}/sdapi/v1/txt2img",
            json=payload,
            timeout=300,
        )
        response.raise_for_status()

        result = response.json()
        images = result.get("images", [])
        if not images:
            return ToolResult(
                success=False,
                output="",
                error="本地 Stable Diffusion 未返回图片",
            )

        image_b64 = images[0]
        image_bytes = base64.b64decode(image_b64)
        filepath = self._save_image(image_bytes, "png")
        image_b64_url = f"data:image/png;base64,{image_b64}"

        return ToolResult(
            success=True,
            output=f"图片已生成并保存到 {filepath}",
            data={
                "image_url": image_b64_url,
                "filepath": filepath,
                "revised_prompt": prompt,
                "model": "stable-diffusion",
                "size": size,
            },
            metadata={"backend": "local", "model": "stable-diffusion"},
        )
