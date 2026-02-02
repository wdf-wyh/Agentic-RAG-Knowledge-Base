"""Ollama 本地模型客户端"""
import requests
import json
from typing import Optional, Iterator


class OllamaError(Exception):
    """Ollama 相关错误"""
    pass


def generate(
    model: str,
    prompt: str,
    max_tokens: int = 256,
    temperature: float = 0.7,
    api_url: Optional[str] = None,
    stream: bool = False,
):
    """调用本地 Ollama HTTP API 进行文本生成。

    Args:
        model: Ollama 模型名称，例如 'gemma3:4b'。
        prompt: 输入提示文本。
        max_tokens: 最大生成 token 数。
        temperature: 温度参数。
        api_url: 可选的 Ollama 服务地址，默认 `http://localhost:11434`。
        stream: 是否使用流式输出。

    Returns:
        生成的文本字符串或流迭代器。
    """
    if api_url is None:
        api_url = "http://localhost:11434"

    endpoint = f"{api_url}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": stream,
    }

    # 对于 LLM 生成，需要更长的超时时间
    # 流式请求使用连接超时和读取超时的元组
    timeout = (10, 120) if stream else 120

    try:
        resp = requests.post(endpoint, json=payload, timeout=timeout, stream=stream)
    except requests.RequestException as e:
        raise OllamaError(f"请求 Ollama API 失败: {e}")

    if resp.status_code != 200:
        raise OllamaError(f"Ollama API 返回错误: {resp.status_code} {resp.text}")

    if stream:
        return _generate_stream(resp)
    else:
        return _generate_non_stream(resp)


def _generate_stream(resp):
    """处理流式响应"""
    try:
        for line in resp.iter_lines():
            if line:
                chunk = json.loads(line)
                if "response" in chunk:
                    yield chunk["response"]
    except json.JSONDecodeError as e:
        raise OllamaError(f"解析 Ollama 响应失败: {e}")


def _generate_non_stream(resp) -> str:
    """处理非流式响应，返回完整字符串"""
    try:
        data = resp.json()
        if "response" in data:
            response_text = data.get("response", "")
            if isinstance(response_text, str):
                # 尝试从响应中解析 JSON 格式的答案
                response_text = response_text.strip()
                try:
                    # 如果响应包含 JSON 格式，尝试提取
                    if '{' in response_text and '"answer"' in response_text:
                        # 找到第一个 { 和最后一个 }
                        start_idx = response_text.find('{')
                        end_idx = response_text.rfind('}')
                        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                            json_str = response_text[start_idx:end_idx+1]
                            parsed = json.loads(json_str)
                            if isinstance(parsed, dict) and "answer" in parsed:
                                answer = parsed["answer"].strip()
                                # 清理答案中可能的多余空格和格式符号
                                answer = answer.replace('\n', ' ').strip()
                                return answer
                except (json.JSONDecodeError, ValueError, KeyError):
                    # 如果不是有效的 JSON，直接返回原文本
                    pass
                return response_text
        else:
            # 备用方案：如果没有 'response' 字段，尝试其他常见字段
            if isinstance(data, dict):
                for field in ["answer", "text", "result", "content"]:
                    if field in data and isinstance(data[field], str):
                        field_text = data[field].strip()
                        return field_text
            # 最后的备用：返回整个响应的字符串化版本
            return str(data).strip()
            
    except json.JSONDecodeError as e:
        raise OllamaError(f"解析 Ollama 响应失败: {e}")
