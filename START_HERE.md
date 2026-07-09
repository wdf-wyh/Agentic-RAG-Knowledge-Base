# Start Here

如果你是第一次打开这个仓库，先看这份最短路径说明。

## 30 秒判断这个项目适不适合你

这个项目适合你，如果你想要：

- 搭一个可本地部署的 RAG 知识库
- 在现有工程上继续做 Agent、工具调用、多模型接入
- 优先支持中文知识库和团队内部使用场景

## 最短启动路径

### 1. 安装依赖

```bash
pip install -r requirements.txt
cd frontend
npm install
cd ..
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

然后至少配置一种模型：

- `DEEPSEEK_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- 或本地 `OLLAMA_API_URL`

### 3. 启动项目

#### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

#### macOS / Linux

```bash
bash start.sh
```

### 4. 打开页面

- Web UI: `http://localhost:5173`
- API Docs: `http://localhost:8000/docs`

## 第一次进来做什么

1. 在“设置”中选择模型提供者
2. 在“知识库”里上传文档
3. 点击“开始构建”
4. 回到首页直接使用示例问题体验

## 推荐继续读

- 想快速跑通：看 [QUICKSTART.md](QUICKSTART.md)
- 想看完整介绍：看 [README.md](README.md)
- 想了解架构：看 [docs/AGENT_ARCHITECTURE.md](docs/AGENT_ARCHITECTURE.md)
- 想优化性能：看 [docs/PERFORMANCE_OPTIMIZATION.md](docs/PERFORMANCE_OPTIMIZATION.md)
