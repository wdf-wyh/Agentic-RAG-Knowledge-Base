# Agentic RAG 知识库系统 (v3.0.0)

> **全自动知识资产管理 Agent** —— 基于 ReAct 架构的企业级 RAG 系统。

本项目是一个结合了 **RAG (检索增强生成)** 与 **Agentic (智能体)** 能力的现代化知识库系统。它不仅支持传统的问答，还能通过 ReAct 框架自主管理知识、联网搜索 (SearXNG) 并进行自我纠错。

## 🌟 核心特性

- **🤖 Agentic 架构**: 引入 ReAct 推理循环，支持自主规划、工具调用与反思。
- **🔍 混合检索**: 向量检索 (ChromaDB) + BM25 稀疏检索 + Cross-encoder 精排。
- **🌐 联网搜索**: 集成 SearXNG 隐私搜索引擎，支持实时信息获取。
- **🧠 多模型生态**: 无缝切换 OpenAI, Google Gemini, Ollama (本地私有模型)。
- **💻 全栈体验**: 
  - **Backend**: FastAPI 高性能异步接口
  - **Frontend**: Vue.js 3 + Vite 现代化界面
  - **CLI**: 开发者友好的命令行工具
- **📊 知识管理**: 支持 PDF/Markdown/Txt 等多格式自动处理与向量化。

## 📁 项目结构

```
RAG知识库/
├── src/
│   ├── agent/                 # 🆕 Agent 智能体核心 (ReAct)
│   ├── api/                   # FastAPI 接口层
│   ├── core/                  # RAG 核心 (向量库, 文档处理)
│   ├── services/              # 业务服务 (LLM 客户端)
│   ├── config/                # 系统配置
│   └── utils/                 # 通用工具
├── documents/                 # 知识库源文件
├── frontend/                  # Vue.js 前端应用
├── deploy/                    # 部署配置 (Docker/SearXNG)
├── docs/                      # 详细文档
└── vector_db/                 # 向量数据库持久化存储
```

## 🚀 快速开始

### 1. 环境准备

确保已安装 Python 3.10+ 和 Node.js。

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 配置 OPENAI_API_KEY 或 OLLAMA_URL
```

### 2. 启动服务 (推荐)

使用一键启动脚本：

```bash
bash start.sh
```

或者手动分别启动：

```bash
# 终端 1: 启动 API 服务
python app_api.py

# 终端 2: 启动前端界面
cd frontend
npm install
npm run dev
```

### 3. 可选：部署 SearXNG 搜索服务

如果不使用 Docker，Agent 将仅使用本地 RAG 检索。

```bash
docker-compose -f deploy/docker-compose.searxng.yml up -d
```

## 📖 核心文档

- [✨ 快速上手指南 (START_HERE.md)](START_HERE.md) - 首次使用必读
- [🧠 Agent 架构文档 (docs/AGENT_ARCHITECTURE.md)](docs/AGENT_ARCHITECTURE.md) - 理解系统原理
- [🌐 SearXNG 配置 (docs/SEARXNG_SETUP.md)](docs/SEARXNG_SETUP.md) - 联网搜索功能
- [📝 日志说明 (LOG_QUICK_GUIDE.md)](LOG_QUICK_GUIDE.md) - 排查问题

## 🛠️ API & SDK 使用

**Python SDK 示例:**

```python
from src.services.rag_assistant import RAGAssistant
from src.core.vector_store import VectorStore

# 初始化
assistant = RAGAssistant()

# 基础 RAG 问答
answer = assistant.query("DeepSeek 模型的特点是什么？")

# Agent 模式 (支持联网与推理)
# (需在配置中启用 agent_mode)
```

**REST API:**

- API 文档: `http://localhost:8000/docs`
- 前端地址: `http://localhost:5173`

## 🏷️ 版本历史

- **v3.0.0 (Current)**: 引入 Agentic ReAct 架构，集成 SearXNG，增强自主能力。
- **v2.0.0**: 企业级重构，模块化设计，FastAPI + Vue 前后端分离。
- **v1.0.0**: 基础 Streamlit RAG原型。

## 📄 许可证

MIT License

