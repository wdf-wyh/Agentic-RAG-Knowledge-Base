# 🎯 日志查看快速指南

## 📌 日志位置

```
logs/backend.log    ← 后端API日志（包含Agent、RAG检索、AI调用等）
logs/frontend.log   ← 前端日志（可选）
```

## 🚀 快速查看日志

### 方式1️⃣ - 使用日志查看工具（最简单）

```bash
python view_logs.py              # 查看所有日志（最后100行）
python view_logs.py backend      # 只看后端日志
python view_logs.py follow       # 实时跟踪日志（Ctrl+C停止）
```

### 方式2️⃣ - 命令行工具

```bash
cat logs/backend.log                    # 查看完整日志
tail -50 logs/backend.log               # 查看最后50行
tail -f logs/backend.log                # 实时跟踪日志
grep "DeepSeek\|Ollama" logs/backend.log  # 搜索特定内容
```

### 方式3️⃣ - VS Code编辑器

打开文件: `logs/backend.log`

---

## 📊 日志内容说明

### API请求日志示例

```
[Query Stream] 开始处理查询 - 问题: 今天广州天气？
[DeepSeek] 开始检索文档...
[DeepSeek] 检索到 5 个文档               ← 检索结果数量
[DeepSeek] 开始调用AI生成答案
[DeepSeek] AI调用完成 - 耗时: 2.34秒    ← AI响应时间
[DeepSeek] 完整流程完成 - 总耗时: 3.12秒 ← 总耗时
```

### Agent执行日志示例

```
[Agent] 开始执行 - 问题: ...
[Agent] 迭代 1 开始
[Agent] 调用LLM进行推理...
[Agent] LLM调用完成 - 耗时: 1.23秒
[Agent] 执行工具: rag_search               ← 使用的工具
[Agent] 工具执行完成 - 耗时: 0.45秒, 结果长度: 890
[Agent] 迭代 1 完成 - 耗时: 2.10秒
[Agent] 执行完成 - 总耗时: 2.10秒, 迭代次数: 1
```

---

## 🔍 常用查询命令

### 查看所有错误
```bash
grep "ERROR\|error\|Failed" logs/backend.log
```

### 查看所有Agent执行
```bash
grep "\[Agent\]" logs/backend.log
```

### 查看所有API请求
```bash
grep "\[Query\]\|\[DeepSeek\]\|\[Ollama\]" logs/backend.log
```

### 查看性能耗时
```bash
grep "耗时\|Total" logs/backend.log
```

### 统计日志行数
```bash
wc -l logs/backend.log
```

---

## ⚡ 性能分析

从日志提取耗时信息：

```bash
# 查看每个请求的总耗时
grep "完整流程完成" logs/backend.log

# 查看LLM调用耗时
grep "AI调用完成" logs/backend.log

# 查看工具执行耗时
grep "工具执行完成" logs/backend.log
```

---

## 🧹 清空日志

```bash
# 清空后端日志
> logs/backend.log

# 或使用
echo "" > logs/backend.log

# 只保留最近1000行
tail -1000 logs/backend.log > logs/backend.log.tmp
mv logs/backend.log.tmp logs/backend.log
```

---

## 📚 更多信息

详见: [docs/LOGGING.md](../docs/LOGGING.md)

---

✨ **提示**: 调试问题时，始终先查看日志文件了解详细的执行过程！
