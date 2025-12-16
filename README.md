# RAG 知识库助手 📚

一个现代化的 AI 知识库问答系统，基于检索增强生成（RAG）技术，提供类似 ChatGPT 官网的用户体验。

## ✨ 新增功能

- 📤 **文件上传与管理**: 支持拖拽或点击上传文件到服务器
- 🏗️ **进度展示**: 实时显示知识库构建进度，包括已处理文档数量
- 💬 **流式输出**: 支持流式响应，实时显示 AI 生成内容
- 🎨 **GPT 风格界面**: 现代化的深色/浅色主题设计
- ⚙️ **抽屉式配置**: 模型配置以弹框抽屉形式展现
- 🖼️ **图片支持**: 支持粘贴或上传图片到输入框
- 💾 **本地存储**: 模型配置自动保存到浏览器本地存储

## 🛠️ 技术栈

### 后端
- **FastAPI**: 高性能 Web 框架
- **LangChain**: LLM 应用开发框架
- **ChromaDB**: 向量数据库
- **Ollama**: 本地 LLM 支持
- **OpenAI/Gemini**: 云端 LLM 支持

### 前端
- **Vue 3**: 渐进式 JavaScript 框架
- **Element Plus**: 企业级 UI 组件库
- **Axios**: HTTP 客户端
- **Vite**: 下一代构建工具

## 📦 项目结构

```
RAG知识库/
├── frontend/                 # 前端 Vue 项目
│   ├── src/
│   │   ├── App.vue          # 主应用组件
│   │   ├── main.js          # 入口文件
│   │   ├── styles.css       # 全局样式（GPT风格）
│   ├── package.json
│   └── vite.config.js
├── app_api.py               # FastAPI 应用
├── config.py                # 配置文件
├── rag_assistant.py         # RAG 助手逻辑
├── document_processor.py    # 文档处理
├── vector_store.py          # 向量数据库
├── ollama_client.py         # Ollama 本地模型
├── documents/               # 知识库文档目录
├── vector_db/               # 向量数据库存储
└── requirements.txt         # Python 依赖

```

## 🚀 快速开始

### 1. 安装依赖

#### 后端
```bash
pip install -r requirements.txt
```

#### 前端
```bash
cd frontend
npm install
```

### 2. 配置环境变量

创建 `.env` 文件并配置：

```env
# OpenAI 配置（可选）
OPENAI_API_KEY=your_key_here
OPENAI_API_BASE=https://api.openai.com/v1

# Gemini 配置（可选）
GEMINI_API_KEY=your_key_here

# Ollama 配置（可选 - 本地LLM）
OLLAMA_API_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:4b

# 向量模型配置
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

# 其他配置
MODEL_PROVIDER=openai  # 可选：openai, gemini, ollama
TOP_K=3  # 检索文档数
MAX_TOKENS=512  # 生成最大token数
TEMPERATURE=0.7  # 温度参数
```

### 3. 运行后端服务

```bash
python app_api.py
```

后端会在 `http://localhost:8000` 启动

### 4. 运行前端应用

```bash
cd frontend
npm run dev
```

前端会在 `http://localhost:5173` 启动

## 📖 使用说明

### 上传知识库文档

1. **点击上传区域** 或 **拖拽文件** 到上传区
2. 支持的格式：`.md`, `.pdf`, `.docx`, `.txt`
3. 已上传的文件会显示在列表中

### 构建知识库

1. 点击"开始构建"按钮
2. 系统会扫描 `documents/` 文件夹中的所有文档
3. 实时显示处理进度和已处理的文档块数量
4. 构建完成后状态栏会显示"✓ 已加载"

### 配置模型

1. 点击右上角的设置按钮（⚙️）
2. 在抽屉面板中选择模型提供者：
   - **后端默认**: 使用配置文件中的默认设置
   - **OpenAI**: 使用 OpenAI 的 GPT 模型
   - **Gemini**: 使用 Google Gemini 模型
   - **Ollama**: 使用本地运行的模型
3. 对于 Ollama，需要输入模型名称和 API URL
4. 配置会自动保存到浏览器

### 提问和对话

1. 在输入框中输入问题
2. 支持的交互方式：
   - 按 **Shift+Enter** 发送
   - 点击"发送"按钮发送
3. 支持**粘贴或上传图片** - 点击图片按钮
4. 流式响应会逐字显示，提供流畅的用户体验
5. 点击"参考来源"可以查看答案基于的文档片段

## 🔧 API 端点

### 文件上传
```
POST /api/upload
- 参数: 文件二进制数据
- 返回: { success, filename, size, path }
```

### 知识库构建
```
POST /api/build-start
- 返回: { success, message }

GET /api/build-progress
- 返回: { processing, progress, total, current_file, status }
```

### 查询（流式）
```
POST /api/query-stream
- 参数: { question, provider, ollama_model, ollama_api_url }
- 返回: Server-Sent Events (SSE) 流
  - type: 'sources' - 参考来源
  - type: 'content' - 内容流
  - type: 'done' - 完成标记
  - type: 'error' - 错误信息
```

### 查询（非流式）
```
POST /api/query
- 参数: { question, provider, ollama_model, ollama_api_url }
- 返回: { question, answer, sources }
```

### 状态查询
```
GET /api/status
- 返回: { vector_store_loaded }
```

## 🌟 界面特性

### GPT 风格设计
- 清爽的白色背景，符合现代审美
- 绿色（#10a37f）作为主色调
- 流畅的动画和过渡效果
- 响应式布局，支持不同屏幕尺寸

### 消息交互
- **用户消息**: 右对齐，绿色渐变背景，圆角气泡
- **助手消息**: 左对齐，浅灰色背景
- **逐字动画**: 模拟实时输入的流畅感
- **光标效果**: 闪烁光标提示输入中

### 进度显示
- 知识库构建进度条，动态颜色变化
- 实时显示处理进度百分比
- 当前处理文件名显示

## ⌨️ 快捷键

- **Shift + Enter**: 发送消息
- **Ctrl/Cmd + K**: 清空聊天（可自定义）

## 🔐 安全建议

1. **API 密钥**: 不要在前端代码中存储敏感密钥
2. **CORS**: 生产环境应配置适当的 CORS 策略
3. **文件上传**: 实施文件类型和大小限制
4. **请求限制**: 建议使用速率限制防止滥用

## 🐛 故障排查

### 连接错误
- 确保后端服务运行在 `http://localhost:8000`
- 检查防火墙设置
- 查看浏览器开发者工具的网络标签

### 流式响应中断
- 检查网络连接
- 查看后端日志获取详细错误信息
- 尝试刷新页面重新连接

### 知识库构建失败
- 检查 `documents/` 文件夹是否存在
- 确认文件格式正确（.md, .pdf, .docx, .txt）
- 查看后端控制台的错误信息

### 模型响应缓慢
- 对于 OpenAI/Gemini：检查 API 额度和网络连接
- 对于 Ollama：确保本地模型已加载，检查系统资源

## 📝 配置选项详解

### Config.py 主要参数

```python
# 模型配置
MODEL_PROVIDER = "openai"  # 默认模型提供者
EMBEDDING_MODEL = "..."    # 向量模型路径
TOP_K = 3                  # 检索文档数

# OpenAI 配置
OPENAI_API_KEY = "..."
OPENAI_API_BASE = "..."

# Ollama 配置
OLLAMA_MODEL = "gemma3:4b"
OLLAMA_API_URL = "http://localhost:11434"

# 生成参数
MAX_TOKENS = 512
TEMPERATURE = 0.7
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🙏 致谢

- LangChain 社区
- ChromaDB 团队
- Element Plus 组件库
- Ollama 项目

---

**更新日期**: 2024年12月
**版本**: 2.0.0

