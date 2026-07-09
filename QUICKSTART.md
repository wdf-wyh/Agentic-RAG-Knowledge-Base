# Quickstart

这份文档面向第一次接触本项目的用户，目标是在 5 到 10 分钟内跑起一个可用的 Agentic RAG 知识库。

## 你会得到什么

- 一个可上传文档的知识库界面
- 一个支持 `纯 RAG` 和 `智能模式` 的聊天工作台
- 一个可继续二次开发的 `FastAPI + Vue 3` 工程

## 方式一：本地开发

### 1. 准备环境

- Python `3.10+`
- Node.js `18+`
- 可选：`Ollama`

### 2. 安装依赖

```bash
pip install -r requirements.txt
cd frontend
npm install
cd ..
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

至少选择一种模型来源：

- `DeepSeek`: 填 `DEEPSEEK_API_KEY`
- `OpenAI`: 填 `OPENAI_API_KEY`
- `Gemini`: 填 `GEMINI_API_KEY`
- `Ollama`: 确保本地服务可访问，通常是 `http://localhost:11434`

### 4. 启动服务

#### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

或者双击 `start.bat`。

#### macOS / Linux

```bash
bash start.sh
```

#### 手动启动

```bash
# terminal 1
python run_api.py

# terminal 2
cd frontend
npm run dev
```

### 5. 打开页面

- 前端：`http://localhost:5173`
- API 文档：`http://localhost:8000/docs`

## 方式二：Docker Compose

适合想快速体验整套服务的场景。

```bash
cp .env.example .env
docker compose up -d --build
```

启动后访问：

- Web UI: `http://localhost`
- API Docs: `http://localhost:8000/docs`

查看日志：

```bash
docker compose logs -f
```

停止服务：

```bash
docker compose down
```

## 第一次进入后怎么用

1. 打开右上角“设置”，选择模型提供者
2. 点击“知识库”，上传文档
3. 点击“开始构建”
4. 回到主界面，用示例问题开始提问

## 推荐的第一批测试问题

- `请总结这份文档的核心内容，并列出 3 个关键结论。`
- `根据现有资料，帮我写一份新成员入门说明。`
- `这个项目支持哪些模型提供者？分别适合什么场景？`
- `如果我要内部部署，最小可行方案是什么？`

## 常见问题

### 1. 页面能打开，但回答失败

通常是模型没有配置好：

- DeepSeek / OpenAI / Gemini：检查 API Key
- Ollama：检查服务是否已启动

### 2. 提示“向量数据库未加载”

这是正常现象，说明还没完成知识库构建。先上传文档，再点击“开始构建”。

### 3. Docker 能跑，但智能模式联网搜索效果一般

默认搜索能力是可选增强。需要时再配置：

- `TAVILY_API_KEY`
- 或你自己的 SearXNG 服务

## 下一步建议

- 想了解架构：看 `docs/AGENT_ARCHITECTURE.md`
- 想优化速度：看 `docs/PERFORMANCE_OPTIMIZATION.md`
- 想排查日志：看 `LOG_QUICK_GUIDE.md`
