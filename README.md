# RAG 知识库系统 v2.0

企业级 RAG (Retrieval-Augmented Generation) 知识库问答系统。

## 🌟 特性

- **多模型支持**: OpenAI、Gemini、Ollama (本地)
- **混合检索**: 向量检索 + BM25 稀疏检索
- **精排重排序**: Cross-encoder 精排优化
- **多种界面**: Web UI、REST API、CLI
- **企业级架构**: 模块化设计，易于扩展

## 📁 项目结构

```
RAG知识库/
├── src/                    # 核心源代码
│   ├── api/               # REST API 模块
│   │   ├── app.py         # FastAPI 应用
│   │   └── routes.py      # API 路由
│   ├── config/            # 配置管理
│   │   └── settings.py    # 配置类
│   ├── core/              # 核心业务逻辑
│   │   ├── document_processor.py  # 文档处理
│   │   ├── vector_store.py        # 向量数据库
│   │   └── bm25_retriever.py      # BM25 检索
│   ├── services/          # 服务层
│   │   ├── rag_assistant.py       # RAG 助手
│   │   └── ollama_client.py       # Ollama 客户端
│   ├── models/            # 数据模型
│   │   └── schemas.py     # Pydantic 模型
│   └── utils/             # 工具函数
│       └── logger.py      # 日志工具
├── frontend/              # 前端代码 (Vue.js)
├── documents/             # 知识库文档
├── vector_db/             # 向量数据库存储
├── tests/                 # 测试代码
├── app.py                 # Streamlit Web 界面
├── run_api.py             # API 服务入口
├── run_cli.py             # CLI 工具入口
├── run_web.py             # Web 界面入口
├── .env                   # 环境配置
└── requirements.txt       # 依赖列表
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
cp .env.example .env
```

主要配置项：
- `MODEL_PROVIDER`: 模型提供者 (openai/gemini/ollama)
- `OPENAI_API_KEY`: OpenAI API 密钥
- `OLLAMA_MODEL`: 本地 Ollama 模型名称

### 3. 构建知识库

```bash
# 方式一：CLI
python run_cli.py build --documents ./documents

# 方式二：Web 界面
python run_web.py
```

### 4. 启动服务

```bash
# 启动 REST API
python run_api.py

# 启动 Streamlit Web 界面
python run_web.py

# 启动前端开发服务器
cd frontend && npm run dev
```

## 📖 使用方式

### CLI 命令行

```bash
# 构建知识库
python run_cli.py build --documents ./documents

# 单次查询
python run_cli.py query --question "什么是机器学习？"

# 交互式对话
python run_cli.py chat

# 使用 Ollama 本地模型
python run_cli.py chat --provider ollama
```

### REST API

```bash
# 查询接口 (流式)
curl -X POST http://localhost:8000/api/query-stream \
  -H "Content-Type: application/json" \
  -d '{"question": "什么是机器学习？"}'

# 构建知识库
curl -X POST http://localhost:8000/api/build \
  -H "Content-Type: application/json" \
  -d '{"documents_path": "./documents"}'
```

### Python SDK

```python
from src.services.rag_assistant import RAGAssistant
from src.core.vector_store import VectorStore

# 初始化
vector_store = VectorStore()
vector_store.load_vectorstore()
assistant = RAGAssistant(vector_store=vector_store)
assistant.setup_qa_chain()

# 查询
result = assistant.query("什么是深度学习？")
print(result["answer"])
```

## ⚙️ 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `MODEL_PROVIDER` | 模型提供者 | openai |
| `OPENAI_API_KEY` | OpenAI API 密钥 | - |
| `OLLAMA_MODEL` | Ollama 模型名称 | gemma3:4b |
| `OLLAMA_API_URL` | Ollama API 地址 | http://localhost:11434 |
| `EMBEDDING_MODEL` | 嵌入模型 | text-embedding-3-small |
| `LLM_MODEL` | LLM 模型 | gpt-4o-mini |
| `VECTOR_DB_PATH` | 向量库路径 | ./vector_db |
| `CHUNK_SIZE` | 文档分块大小 | 500 |
| `TOP_K` | 检索结果数量 | 3 |
| `SIMILARITY_THRESHOLD` | 相似度阈值 | 0.3 |

## 🔧 开发指南

### 模块导入

```python
# 推荐方式（企业级）
from src.config.settings import Config
from src.core.document_processor import DocumentProcessor
from src.services.rag_assistant import RAGAssistant

# 兼容方式（向后兼容）
from config import Config
from document_processor import DocumentProcessor
from rag_assistant import RAGAssistant
```

### 运行测试

```bash
# 单元测试
pytest tests/unit/

# 集成测试
pytest tests/integration/
```

## 📝 更新日志

### v2.0.0 (2024-12-31)
- 重构为企业级架构
- 模块化 src/ 目录结构
- 分离 API、核心逻辑、服务层
- 添加多入口点支持
- 保持向后兼容性

### v1.0.0
- 初始版本
- 基础 RAG 功能
- Streamlit Web 界面
- CLI 工具

## 📄 许可证

MIT License

