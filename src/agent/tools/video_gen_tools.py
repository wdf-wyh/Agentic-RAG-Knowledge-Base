"""AI 视频生成工具 - 让 Agent 具备文生视频能力

支持后端：
- OpenAI Sora (通过 /v1/videos/generations API)
- 智谱 AI CogVideoX
- Stability AI (Stable Video)
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

# 生成视频的保存目录
VIDEO_OUTPUT_DIR = Path("output/generated_videos")
VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class VideoGenerationTool(BaseTool):
    """AI 视频生成工具

    根据文字描述生成视频，支持多种模型后端。
    """

    def __init__(self, backend: str = None):
        """初始化视频生成工具

        Args:
            backend: 模型后端，可选 'openai', 'zhipu', 'stability'
                     默认根据 Config 自动选择
        """
        self._backend = backend or self._auto_detect_backend()
        self._config = Config()
        self._session = requests.Session()
        self._session.timeout = 300  # 视频生成耗时更长
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
        return "video_generation"

    @property
    def description(self) -> str:
        return (
            "根据文字描述生成视频。适用场景：用户要求生成视频、创建动画、"
            "制作短片、生成视频片段等涉及视频创作的需求。"
            "输入 prompt（英文效果更佳）和可选的参数，返回生成的视频。"
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
                "description": "视频描述（prompt），尽量使用英文以获得更好效果。描述要具体、详细，包含动作和场景。",
                "required": True,
            },
            {
                "name": "duration",
                "type": "string",
                "description": "视频时长，可选: '5'(5秒,默认), '10'(10秒)",
                "required": False,
            },
            {
                "name": "size",
                "type": "string",
                "description": "视频尺寸，可选: '1080x1920'(竖版,默认), '1920x1080'(横版), '1080x1080'(方形)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> ToolResult:
        """执行视频生成"""
        prompt = kwargs.get("prompt", "").strip()
        if not prompt:
            return ToolResult(
                success=False,
                output="",
                error="prompt 不能为空，请提供视频描述",
            )

        duration = kwargs.get("duration", "5")
        size = kwargs.get("size", "1080x1920")

        # 安全检查
        if len(prompt) > 4000:
            return ToolResult(
                success=False,
                output="",
                error="prompt 过长（最大4000字符）",
            )

        try:
            if self._backend == "openai":
                return self._generate_openai(prompt, duration, size)
            elif self._backend == "gemini":
                return self._generate_gemini(prompt, duration, size)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"不支持的视频生成后端: {self._backend}",
                )
        except Exception as e:
            logger.error(f"视频生成失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"视频生成失败: {str(e)}",
            )

    def _save_video(self, video_bytes: bytes, ext: str = "mp4") -> str:
        """保存视频到本地并返回相对路径"""
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = VIDEO_OUTPUT_DIR / filename
        filepath.write_bytes(video_bytes)
        return str(filepath)

    def _generate_openai(self, prompt: str, duration: str, size: str) -> ToolResult:
        """使用 OpenAI Sora 生成视频"""
        api_key = Config.OPENAI_API_KEY
        if not api_key:
            return ToolResult(
                success=False,
                output="",
                error="未配置 OPENAI_API_KEY，无法使用 Sora 生成视频",
            )

        api_base = Config.OPENAI_API_BASE.rstrip("/")

        # 第一步：提交视频生成任务
        create_url = f"{api_base}/videos/generations"
        payload = {
            "model": "sora",
            "prompt": prompt,
            "size": size,
            "duration": int(duration),
            "n": 1,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        logger.info(f"[VideoGen] 调用 Sora, prompt: {prompt[:80]}...")

        # 提交生成任务
        response = self._session.post(
            create_url, headers=headers, json=payload, timeout=60,
        )
        response.raise_for_status()
        task_data = response.json()

        # 如果直接返回了视频数据（某些兼容API）
        if "data" in task_data and task_data["data"]:
            return self._process_openai_result(task_data, prompt, duration, size)

        # 如果返回的是任务ID（异步模式），需要轮询
        task_id = task_data.get("id")
        if not task_id:
            return ToolResult(
                success=False,
                output="",
                error="视频生成任务创建失败：未返回任务ID",
            )

        # 第二步：轮询任务状态
        poll_url = f"{api_base}/videos/generations/{task_id}"
        max_wait = 300  # 最长等待5分钟
        poll_interval = 5
        waited = 0

        while waited < max_wait:
            time.sleep(poll_interval)
            waited += poll_interval

            poll_response = self._session.get(poll_url, headers=headers, timeout=30)
            poll_response.raise_for_status()
            poll_data = poll_response.json()

            status = poll_data.get("status", "")
            if status == "completed":
                return self._process_openai_result(poll_data, prompt, duration, size)
            elif status in ("failed", "error"):
                error_msg = poll_data.get("error", {}).get("message", "未知错误")
                return ToolResult(
                    success=False,
                    output="",
                    error=f"视频生成失败: {error_msg}",
                )
            # 继续等待

        return ToolResult(
            success=False,
            output="",
            error="视频生成超时（已等待5分钟）",
        )

    def _process_openai_result(
        self, result_data: dict, prompt: str, duration: str, size: str
    ) -> ToolResult:
        """处理 OpenAI 返回的视频结果"""
        data_list = result_data.get("data", [])
        if not data_list:
            return ToolResult(
                success=False,
                output="",
                error="视频生成返回数据为空",
            )

        video_item = data_list[0]

        # 优先使用 URL 下载
        video_url = video_item.get("url", "")
        if video_url:
            try:
                dl_resp = self._session.get(video_url, timeout=120)
                dl_resp.raise_for_status()
                video_bytes = dl_resp.content
            except Exception as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"视频下载失败: {str(e)}",
                )
        elif video_item.get("b64_json"):
            video_bytes = base64.b64decode(video_item["b64_json"])
            video_url = ""
        else:
            return ToolResult(
                success=False,
                output="",
                error="视频生成返回数据中无有效内容",
            )

        filepath = self._save_video(video_bytes, "mp4")
        revised_prompt = video_item.get("revised_prompt", prompt)

        # 为前端生成可访问的 URL
        video_serve_url = f"/api/generated-videos/{Path(filepath).name}"

        return ToolResult(
            success=True,
            output=f"视频已生成并保存到 {filepath}",
            data={
                "video_url": video_serve_url,
                "filepath": filepath,
                "revised_prompt": revised_prompt,
                "model": "sora",
                "duration": duration,
                "size": size,
            },
            metadata={"backend": "openai", "model": "sora"},
        )

    def _generate_gemini(self, prompt: str, duration: str, size: str) -> ToolResult:
        """使用 Google Gemini Veo 生成视频"""
        api_key = Config.GEMINI_API_KEY
        if not api_key:
            return ToolResult(
                success=False,
                output="",
                error="未配置 GEMINI_API_KEY，无法使用 Veo 生成视频",
            )

        # Gemini Veo API
        generate_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"veo-2.0-generate-001:predictLongRunning?key={api_key}"
        )

        # 解析尺寸为宽高
        parts = size.split("x")
        width = int(parts[0]) if len(parts) == 2 else 1080
        height = int(parts[1]) if len(parts) == 2 else 1920

        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "sampleCount": 1,
                "durationSeconds": int(duration),
                "aspectRatio": f"{width}:{height}",
            },
        }

        logger.info(f"[VideoGen] 调用 Gemini Veo, prompt: {prompt[:80]}...")

        response = self._session.post(
            generate_url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        operation = response.json()

        # Veo 返回 long-running operation，需要轮询
        operation_name = operation.get("name", "")
        if not operation_name:
            return ToolResult(
                success=False,
                output="",
                error="Veo 视频生成任务创建失败",
            )

        poll_url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"{operation_name}?key={api_key}"
        )
        max_wait = 300
        poll_interval = 10
        waited = 0

        while waited < max_wait:
            time.sleep(poll_interval)
            waited += poll_interval

            poll_resp = self._session.get(poll_url, timeout=30)
            poll_resp.raise_for_status()
            poll_data = poll_resp.json()

            if poll_data.get("done"):
                result = poll_data.get("response", {})
                videos = result.get("generatedSamples", [])
                if not videos:
                    return ToolResult(
                        success=False,
                        output="",
                        error="Veo 返回数据中无视频",
                    )
                video_item = videos[0]
                video_b64 = video_item.get("video", {}).get("bytesBase64Encoded", "")
                if not video_b64:
                    return ToolResult(
                        success=False,
                        output="",
                        error="Veo 返回视频数据为空",
                    )
                video_bytes = base64.b64decode(video_b64)
                filepath = self._save_video(video_bytes, "mp4")
                video_serve_url = f"/api/generated-videos/{Path(filepath).name}"

                return ToolResult(
                    success=True,
                    output=f"视频已生成并保存到 {filepath}",
                    data={
                        "video_url": video_serve_url,
                        "filepath": filepath,
                        "revised_prompt": prompt,
                        "model": "veo-2.0",
                        "duration": duration,
                        "size": size,
                    },
                    metadata={"backend": "gemini", "model": "veo-2.0"},
                )

            error = poll_data.get("error")
            if error:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Veo 视频生成失败: {error.get('message', '未知错误')}",
                )

        return ToolResult(
            success=False,
            output="",
            error="Veo 视频生成超时（已等待5分钟）",
        )
