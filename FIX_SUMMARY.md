# 修复总结：AI 回复显示问题

## 问题描述
- ✗ 页面只显示**参考来源**，没有显示 AI 的回复内容
- 用户选择了 Ollama 模型配置，但前端无法显示生成的答案

## 根本原因分析

### 问题1：`ollama_client.py` 中的生成器陷阱
**文件**: [ollama_client.py](ollama_client.py)

原始代码在 `generate()` 函数中混合了 `yield` 语句（用于流式）和 `return` 语句（用于非流式）：

```python
def generate(..., stream: bool = False):
    if stream:
        # 流式分支
        yield chunk  # ← 这里有 yield
        return result
    else:
        # 非流式分支
        return response_text  # ← 应该返回字符串
```

**问题**: Python 会将任何包含 `yield` 的函数标记为**生成器函数**，即使 `yield` 只在某个分支中。这意味着：
- 即使 `stream=False`，函数也会返回**生成器对象**而不是**字符串**
- 这导致 `app_api.py` 中的 `ollama_result` 是生成器而非字符串

### 问题2：`app_api.py` 中的字符迭代问题
**文件**: [app_api.py](app_api.py#L249-L261)

当 `ollama_result` 是生成器对象时：
```python
for char in ollama_result:  # 迭代生成器对象
    yield f"data: {json.dumps({'type': 'content', 'data': char})}\n\n"
```

生成器对象无法像字符串一样被逐字符迭代，导致不发送任何内容。

## 解决方案

### 修复：分离流和非流处理
将 `generate()` 函数拆分为三个函数：

1. **`generate()` - 主入口**：根据 `stream` 参数选择调用哪个函数
```python
def generate(..., stream: bool = False):
    if stream:
        return _generate_stream(resp)
    else:
        return _generate_non_stream(resp)
```

2. **`_generate_stream()` - 流式处理**：生成器函数，用 `yield` 返回数据块
```python
def _generate_stream(resp):
    for line in resp.iter_lines():
        if "response" in chunk:
            yield chunk["response"]
```

3. **`_generate_non_stream()` - 非流式处理**：普通函数，返回完整字符串
```python
def _generate_non_stream(resp) -> str:
    data = resp.json()
    # ... 处理逻辑 ...
    return response_text  # 返回字符串
```

### 修改的文件

#### [ollama_client.py](ollama_client.py)
- ✅ 拆分流和非流处理逻辑到独立函数
- ✅ 确保 `_generate_non_stream()` 总是返回字符串
- ✅ `_generate_stream()` 返回生成器

#### [app_api.py](app_api.py#L249-L261)
- ✅ 简化 Ollama 结果处理（无需额外类型检查）
- ✅ 确保 `ollama_result` 是字符串，可以逐字符发送

## 验证

运行以下命令验证修复：

```bash
# 测试 ollama_client 返回类型
python test_mock.py

# 运行前端并在配置中选择 Ollama
# 提交问题后应该能看到 AI 的回复
```

## 预期结果

修复后：
- ✅ API `/api/query-stream` 端点发送正确的 SSE 数据
- ✅ 前端接收到 `content` 类型的数据流
- ✅ AI 回复逐字显示在聊天界面
- ✅ 同时显示参考来源

## 技术细节

### SSE 数据流示例

修复前（无内容）：
```
data: {"type": "sources", "data": [...]}

data: {"type": "done"}
```

修复后（完整流）：
```
data: {"type": "sources", "data": [...]}

data: {"type": "content", "data": "这"}
data: {"type": "content", "data": "是"}
data: {"type": "content", "data": "A"}
...
data: {"type": "done"}
```

## 总结

| 方面 | 修复前 | 修复后 |
|------|--------|--------|
| `ollama_generate()` 返回类型 | 生成器对象 | 字符串 |
| 前端接收内容 | ✗ 无 | ✅ 完整回复 |
| 显示结果 | 仅参考来源 | 参考来源 + AI 回复 |
