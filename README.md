# RAG 知识库助手 📚

基于检索增强生成（RAG）技术的垂直领域知识库问答系统，支持多种文档格式，提供命令行和 Web 两种交互方式。

## ✨ 功能特点

- 🔍 **智能检索**: 基于向量相似度的语义检索
- 📄 **多格式支持**: PDF、TXT、DOCX、Markdown 等多种文档格式
- 🤖 **AI 回答**: 使用 GPT 模型生成准确、详细的答案
- 💬 **交互方式**: 支持命令行和 Web 界面两种交互方式
- 📊 **来源追溯**: 显示答案来源，确保可信度
- ⚡ **高效存储**: 使用 ChromaDB 向量数据库，支持持久化

## 🛠️ 技术栈

- **LangChain**: LLM 应用开发框架
- **OpenAI**: GPT 模型和 Embedding 模型
- **ChromaDB**: 向量数据库
- **Streamlit**: Web 界面框架
- **Python 3.8+**: 开发语言

## 📦 安装步骤

### 1. 克隆项目或创建目录

```bash
cd /Users/apple/Documents/AI/微调
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填写你的 API Key：

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_API_BASE=https://api.openai.com/v1
```

## 🚀 快速开始

### 准备文档

将你的文档放入 `documents` 目录：

```bash
mkdir -p documents
# 将 PDF、TXT、DOCX 等文件复制到 documents 目录
```

### 方式一：命令行使用

#### 1. 构建知识库

```bash
python main.py build --documents ./documents
```

#### 2. 单次查询

```bash
python main.py query --question "你的问题"
```

#### 3. 交互式对话

```bash
python main.py chat
```

### 方式二：Web 界面

启动 Streamlit 应用：

```bash
streamlit run app.py
```

然后在浏览器中访问 `http://localhost:8501`

## 📖 使用示例

### 命令行示例

```bash
# 构建知识库
python main.py build --documents ./documents

# 使用 OpenAI 查询（默认）
python main.py query --question "什么是机器学习？"

# 使用 Ollama 本地模型查询
python main.py query --question "什么是机器学习？" --provider ollama --ollama-model gemma3:4b

# 使用 Gemini 查询
python main.py query --question "什么是机器学习？" --provider gemini

# 启动对话模式（使用默认提供者）
python main.py chat

# 启动对话模式（使用 Ollama）
python main.py chat --provider ollama --ollama-model gemma3:4b
```

### Python 代码示例

```python
from config import Config
from document_processor import DocumentProcessor
from vector_store import VectorStore
from rag_assistant import RAGAssistant

# 1. 处理文档
processor = DocumentProcessor()
chunks = processor.process_documents("./documents")

# 2. 创建向量数据库
vector_store = VectorStore()
vector_store.create_vectorstore(chunks)

# 3. 创建 RAG 助手
assistant = RAGAssistant(vector_store=vector_store)

# 4. 查询
result = assistant.query("你的问题")
print(result["answer"])
```

## 📁 项目结构

```
.
├── README.md                 # 项目文档
├── requirements.txt          # 项目依赖
├── .env.example             # 环境变量示例
├── .gitignore               # Git 忽略文件
├── config.py                # 配置管理
├── document_processor.py    # 文档处理模块
├── vector_store.py          # 向量数据库模块
├── rag_assistant.py         # RAG 助手核心逻辑
├── main.py                  # 命令行入口
├── app.py                   # Web 界面入口
├── documents/               # 文档目录（需创建）
└── vector_db/               # 向量数据库（自动生成）
```

## ⚙️ 配置说明

在 `.env` 文件中可以配置以下参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | 必填 |
| `OPENAI_API_BASE` | API 基础 URL | https://api.openai.com/v1 |
| `EMBEDDING_MODEL` | Embedding 模型 | text-embedding-3-small |
| `LLM_MODEL` | LLM 模型 | gpt-4o-mini |
| `CHUNK_SIZE` | 文本分块大小 | 500 |
| `CHUNK_OVERLAP` | 分块重叠大小 | 50 |
| `TOP_K` | 检索文档数量 | 3 |
| `TEMPERATURE` | 生成温度 | 0.7 |
| `MAX_TOKENS` | 最大生成长度 | 1000 |

| `MODEL_PROVIDER` | 模型提供者，选择 `openai`、`gemini` 或 `ollama` | openai |
| `GEMINI_API_KEY` | Google Gemini (或其他 Gemini 兼容服务) 的 API Key | 可选，若使用 `gemini` 必填 |
| `OLLAMA_MODEL` | Ollama 本地模型名称 | gemma3:4b |
| `OLLAMA_API_URL` | Ollama API 地址 | http://localhost:11434 |

## 🎯 应用场景

- 📚 **企业知识库**: 内部文档问答系统
- 📖 **技术文档助手**: 快速查找技术文档内容
- 🏥 **医疗知识库**: 医疗文献检索和问答
- ⚖️ **法律咨询**: 法律条文检索和解读
- 🎓 **教育辅助**: 课程资料问答系统

## 🔧 自定义提示词

可以在创建助手时自定义提示词模板：

```python
custom_prompt = """你是一个专业的{领域}专家。

上下文信息:
{context}

问题: {question}

请给出专业的回答。
"""

assistant = RAGAssistant()
assistant.setup_qa_chain(prompt_template=custom_prompt)
```

## 🚧 常见问题

### 1. 导入错误

确保已安装所有依赖：
```bash
pip install -r requirements.txt
```

### 2. API 密钥错误

检查 `.env` 文件中的 `OPENAI_API_KEY` 是否正确设置。

### 3. 向量数据库未找到

首次使用需要先运行 `python main.py build` 构建知识库。

### 4. 文档加载失败

确保文档格式正确，支持的格式：PDF、TXT、DOCX、MD

## 📝 开发计划

- [ ] 支持更多文档格式（HTML、CSV、Excel）
- [ ] 添加对话历史记忆功能
- [ ] 支持多语言
- [ ] 添加用户认证
- [ ] 支持文档在线上传
- [ ] 优化检索算法
- [ ] 添加评估指标

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题，请提交 Issue。

---

⭐ 如果这个项目对你有帮助，请给个星标！
