"""DeepSeek API 客户端（基于 API key 的调用示例）

此模块提供一个轻量级的 `generate` 函数，用于调用 DeepSeek 风格的 HTTP 接口。
如果你使用 `langchain_deepseek`，优先建议使用 LangChain 的集成；
此文件用于直接通过 HTTP/REST 调用 DeepSeek 服务的场景。
"""
import json
from typing import Optional, Iterator
import requests


class DeepSeekError(Exception):
    pass


def generate(
    model: str,
    prompt: str,
    max_tokens: int = 512,
    temperature: float = 0.7,
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    stream: bool = False,
):
    """调用 DeepSeek HTTP API 生成文本。

    Args:
        model: 模型名称（由 DeepSeek 提供的标识）
        prompt: 输入提示文本（字符串）
        max_tokens: 最大生成 token 数
        temperature: 采样温度
        api_url: DeepSeek API 根地址，例如 `https://api.deepseek.ai`，若为 None 则使用默认
        api_key: 用于认证的 API key（优先使用此参数，否则应从环境变量读取）
        stream: 是否以流式方式返回

    Returns:
        非流：返回生成文本（str）；流：返回一个迭代器（yield 分块字符串）
    """
    if api_url is None:
        api_url = "https://api.deepseek.ai"

    if not api_key:
        # 不直接导入 env 以保持函数纯粹性，调用方可传入或从配置中读取
        raise DeepSeekError("需要提供 api_key，或在配置中设置 DEEPSEEK_API_KEY")

    endpoint = api_url.rstrip("/") + "/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        # DeepSeek 可能支持更多参数：top_p、stop、presence_penalty 等，可按需扩展
    }

    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=120, stream=stream)
    except requests.RequestException as e:
        raise DeepSeekError(f"请求 DeepSeek API 失败: {e}")

    if resp.status_code != 200:
        text = resp.text if resp is not None else ""
        raise DeepSeekError(f"DeepSeek API 返回错误: {resp.status_code} {text}")

    if stream:
        return _stream_response(resp)
    else:
        return _parse_response(resp)


def _stream_response(resp) -> Iterator[str]:
    try:
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except Exception:
                # 非 JSON 行，直接返回原始文本行
                yield line
                continue
            # 常见字段：choices -> delta / content，或 response 字段
            if isinstance(chunk, dict):
                if "delta" in chunk:
                    # 支持类似 OpenAI streaming 的结构
                    content = chunk.get("delta", {}).get("content")
                    if content:
                        yield content
                elif "response" in chunk:
                    yield chunk.get("response", "")
                elif "choices" in chunk:
                    for c in chunk.get("choices", []):
                        txt = c.get("text") or c.get("message", {}).get("content")
                        if txt:
                            yield txt
                else:
                    # 未知 JSON 结构，返回字符串化内容
                    yield json.dumps(chunk)
    except requests.RequestException as e:
        raise DeepSeekError(f"读取流时发生错误: {e}")


def _parse_response(resp) -> str:
    try:
        data = resp.json()
    except Exception as e:
        raise DeepSeekError(f"解析 DeepSeek 响应失败: {e}")

    # 兼容多种返回格式
    if isinstance(data, dict):
        # OpenAI 风格 /choice-like
        if "choices" in data:
            choices = data.get("choices", [])
            if choices:
                first = choices[0]
                return first.get("text") or first.get("message", {}).get("content", "")
        if "response" in data:
            return data.get("response", "")

    # 回退：返回完整文本
    return str(data)
