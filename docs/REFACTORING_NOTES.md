# RAG 知识库项目重构说明

> 重构日期：2024年12月31日

## 📋 重构目标

将原有的扁平化项目结构整理为**企业级工程架构**，同时确保所有现有功能保持不变。

---

## 🏗️ 架构变化

### 重构前（扁平结构）

```
RAG知识库/
├── config.py              # 配置
├── document_processor.py  # 文档处理
├── vector_store.py        # 向量数据库
├── bm25_retriever.py      # BM25 检索
├── rag_assistant.py       # RAG 助手
├── ollama_client.py       # Ollama 客户端
├── app_api.py             # FastAPI API (600+ 行)
├── app.py                 # Streamlit Web
├── main.py                # CLI 入口
├── debug_*.py             # 调试脚本 (10+ 个)
├── test_*.py              # 测试脚本
└── ...其他临时文件
```

### 重构后（企业级结构）

```
RAG知识库/
├── src/                        # 🆕 核心源代码目录
│   ├── __init__.py
│   ├── config/                 # 配置模块
│   │   ├── __init__.py
│   │   └── settings.py         # Config + Settings 类
│   ├── core/                   # 核心业务逻辑
│   │   ├── __init__.py
│   │   ├── document_processor.py
│   │   ├── vector_store.py
│   │   └── bm25_retriever.py
│   ├── services/               # 服务层
│   │   ├── __init__.py
│   │   ├── rag_assistant.py
│   │   └── ollama_client.py
│   ├── api/                    # REST API 模块
│   │   ├── __init__.py
│   │   ├── app.py              # FastAPI 应用工厂
│   │   └── routes.py           # API 路由定义
│   ├── models/                 # 数据模型
│   │   ├── __init__.py
│   │   └── schemas.py          # Pydantic 模型
│   └── utils/                  # 工具函数
│       ├── __init__.py
│       └── logger.py
├── run_api.py                  # 🆕 API 服务入口
├── run_cli.py                  # 🆕 CLI 工具入口
├── run_web.py                  # 🆕 Web 界面入口
├── app.py                      # Streamlit (保持不变)
├── config.py                   # 兼容层 → src/config/
├── document_processor.py       # 兼容层 → src/core/
├── vector_store.py             # 兼容层 → src/core/
├── rag_assistant.py            # 兼容层 → src/services/
├── ...                         # 其他兼容层文件
├── frontend/                   # 前端代码 (保持不变)
├── documents/                  # 知识库文档
├── vector_db/                  # 向量数据库
└── archive_20251231_114936/    # 🆕 归档目录
    ├── debug_scripts/          # 调试脚本归档
    ├── old_version/            # 旧版本代码备份
    └── temp_files/             # 临时文件
```

---

## 📦 模块说明

### src/config/settings.py
- `Config` 类：保持原有配置逻辑不变
- `Settings` 类：新增环境设置（ENV、DEBUG、LOG_LEVEL）

### src/core/
- `DocumentProcessor`：文档加载、分割
- `VectorStore`：Chroma 向量数据库管理
- `BM25Retriever`：稀疏检索实现

### src/services/
- `RAGAssistant`：RAG 问答核心逻辑
- `ollama_client`：本地 Ollama 模型调用

### src/api/
- `app.py`：FastAPI 应用工厂，CORS 配置
- `routes.py`：API 路由（/status, /build, /query-stream 等）

### src/models/schemas.py
- `QueryRequest`、`QueryResponse`
- `BuildRequest`、`BuildResponse`
- `StatusResponse`、`BuildProgress`

---

## 🔄 兼容性设计

为确保现有代码不受影响，根目录保留了**兼容层文件**：

```python
# config.py (兼容层)
from src.config.settings import Config
__all__ = ["Config"]
```

这样，原有的导入方式仍然有效：
```python
# 旧方式（仍然可用）
from config import Config
from vector_store import VectorStore

# 新方式（推荐）
from src.config.settings import Config
from src.core.vector_store import VectorStore
```

---

## 🚀 启动方式

### API 服务
```bash
# 方式一：使用入口脚本
python run_api.py

# 方式二：使用 uvicorn
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

### Web 界面
```bash
python run_web.py
# 或
streamlit run app.py
```

### CLI 工具
```bash
# 构建知识库
python run_cli.py build --documents ./documents

# 查询
python run_cli.py query --question "你的问题"

# 交互式对话
python run_cli.py chat --provider ollama
```

---

## 🐛 修复的问题

### 1. 向量数据库加载失败
**问题**：构建知识库后查询报错 "向量数据库未加载"

**原因**：`/api/build` 接口构建完成后没有调用 `load_assistant()`

**修复**：在 `src/api/routes.py` 中添加：
```python
# 构建完成后立即重新加载
_assistant = None
load_assistant()  # ← 新增
```

### 2. MODEL_PROVIDER 配置错误
**问题**：`.env` 中 `MODEL_PROVIDER=openai` 但 `OPENAI_API_KEY` 为空

**修复**：将 `MODEL_PROVIDER` 改为 `ollama`

---

## 📁 归档内容

以下文件已移至 `archive_20251231_114936/`：

### debug_scripts/
- `debug_deep_learning.py`
- `debug_similarity_threshold.py`
- `analyze_parsing.py`
- `test_similarity_filter.py`
- `verify_fix.py`
- `final_test.py`
- ... 等 10+ 个调试脚本

### old_version/
- 原始的 `config.py`
- 原始的 `app_api.py` (600+ 行)
- 原始的 `main.py`
- 其他核心文件的原始版本

### temp_files/
- `curl_resp.json`
- 其他临时文件

---

## ✅ 验证清单

- [x] `from config import Config` 导入正常
- [x] `from src.config.settings import Config` 导入正常
- [x] API 服务启动正常 (`uvicorn src.api.app:app`)
- [x] 向量数据库加载成功
- [x] Streamlit Web 界面正常
- [x] 前端 Vue 应用正常
- [x] CLI 命令正常

---

## 📝 后续建议

1. **添加单元测试**：在 `tests/unit/` 目录添加各模块测试
2. **添加日志记录**：使用 `src/utils/logger.py` 替代 `print`
3. **Docker 化部署**：在 `deploy/` 目录添加 Dockerfile
4. **API 文档**：访问 `http://localhost:8000/docs` 查看自动生成的 OpenAPI 文档
