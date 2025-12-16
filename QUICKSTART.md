# 🚀 快速启动指南

## 5 分钟快速开始

### 前置条件
- Python 3.8+
- Node.js 14+ 和 npm
- 已安装依赖

### 步骤 1: 启动后端服务

```bash
cd /Users/apple/Documents/AI/RAG知识库
python app_api.py
```

✅ 当看到以下信息时表示启动成功：
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

📖 API 文档可在以下地址访问：
- http://localhost:8000/docs (Swagger UI)
- http://localhost:8000/redoc (ReDoc)

---

### 步骤 2: 启动前端应用

**新开一个终端**，运行：

```bash
cd /Users/apple/Documents/AI/RAG知识库/frontend
npm run dev
```

✅ 当看到以下信息时表示启动成功：
```
  VITE v5.0.0  ready in XXX ms

  ➜  Local:   http://localhost:5173/
```

---

### 步骤 3: 打开应用

在浏览器中访问：
```
http://localhost:5173
```

🎉 应用已启动！

---

## 💡 第一次使用

### 1. 上传文档
1. 在左侧看到"📤 上传文档"区域
2. 点击或拖拽文件到上传区
3. 支持: `.md`, `.pdf`, `.docx`, `.txt`

### 2. 构建知识库
1. 点击"🏗️ 开始构建"按钮
2. 等待进度条完成
3. 状态栏显示"✓ 已加载"

### 3. 开始提问
1. 在下方输入框输入问题
2. 按 `Shift+Enter` 或点击"发送"
3. 观看 AI 逐字回答

### 4. 查看来源
- 每个回答下方有"参考来源"
- 点击展开查看文档片段

---

## ⚙️ 配置模型

### 打开设置
点击右上角的 ⚙️ 按钮

### 选择模型提供者

#### 1. 后端默认
- 使用 config.py 中的配置
- 需要在 .env 文件中设置 API 密钥

#### 2. OpenAI
- 需要有效的 API 密钥
- 检查 .env 文件中的 OPENAI_API_KEY

#### 3. Gemini
- 需要 Google API 密钥
- 检查 .env 文件中的 GEMINI_API_KEY

#### 4. Ollama（本地模型）
需要：
1. 安装 Ollama: https://ollama.ai
2. 运行本地模型：
   ```bash
   ollama pull gemma3:4b
   ollama serve  # 在另一个终端运行
   ```
3. 配置：
   - 模型名称: `gemma3:4b`
   - API URL: `http://localhost:11434`

---

## 🖼️ 高级功能

### 粘贴图片
1. 点击输入框旁的 📷 按钮，或
2. 直接粘贴图片到输入框（Ctrl+V）
3. 图片会显示在输入框上方
4. 点击 ✕ 可移除图片

### 实时进度显示
- 构建知识库时显示实时进度
- 显示已处理的文档块数量
- 进度条颜色随进度变化

### 流式响应
- 回答会逐字显示
- 实时看到 AI 生成内容
- 响应来源会自动更新

---

## 🐛 常见问题

### ❌ "无法连接到后端"
**解决方案:**
1. 确保后端运行在 http://localhost:8000
2. 检查防火墙设置
3. 查看浏览器开发者工具 (F12 -> Network)

### ❌ "向量库未加载"
**解决方案:**
1. 确保 documents/ 文件夹中有文档
2. 点击"开始构建"构建知识库
3. 等待进度条完成

### ❌ "Ollama 连接失败"
**解决方案:**
1. 确保 Ollama 已安装并运行
2. 检查 API URL 是否正确
3. 运行 `ollama serve` 在另一个终端

### ❌ "流式响应中断"
**解决方案:**
1. 刷新页面重新连接
2. 检查网络连接
3. 查看后端日志错误信息

---

## 📊 项目文件说明

```
RAG知识库/
├── app_api.py              ← 后端 API 服务
├── config.py               ← 配置文件（修改 API 密钥）
├── ollama_client.py        ← Ollama 本地模型支持
├── document_processor.py    ← 文档处理逻辑
├── vector_store.py         ← 向量数据库操作
├── rag_assistant.py        ← RAG 问答逻辑
│
├── frontend/               ← 前端应用
│   ├── src/
│   │   ├── App.vue         ← 主组件（大部分UI在这）
│   │   ├── styles.css      ← GPT 风格样式
│   │   └── main.js         ← 入口点
│   ├── package.json        ← npm 依赖
│   └── vite.config.js      ← 构建配置
│
├── documents/              ← 知识库文档（自动创建）
├── vector_db/              ← 向量数据库（自动创建）
│
├── .env                    ← 环境变量（需要创建）
├── README.md               ← 完整文档
├── start.sh                ← 启动脚本
└── CHECKLIST.md            ← 功能检验清单
```

---

## 🔑 配置 API 密钥

### 创建 .env 文件

在项目根目录创建 `.env` 文件：

```env
# OpenAI（可选）
OPENAI_API_KEY=sk-xxx...
OPENAI_API_BASE=https://api.openai.com/v1

# Gemini（可选）
GEMINI_API_KEY=AIza...

# Ollama（可选 - 本地使用无需密钥）
OLLAMA_API_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:4b

# 其他设置
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
MODEL_PROVIDER=openai
TOP_K=3
MAX_TOKENS=512
TEMPERATURE=0.7
```

---

## ✅ 验证安装

运行以下命令检查所有依赖都已安装：

```bash
# 检查 Python
python --version  # 应显示 3.8+

# 检查 Node.js
node --version    # 应显示 14+
npm --version     # 应显示 6+

# 检查后端依赖
python -c "import fastapi; import torch; print('✓ 后端依赖 OK')"

# 检查前端依赖
cd frontend && npm ls --depth=0
```

---

## 📱 快速快捷键

| 快捷键 | 功能 |
|--------|------|
| `Shift + Enter` | 发送消息 |
| `Ctrl/Cmd + K` | 清空聊天（可配置） |
| `F12` | 打开开发者工具 |

---

## 🎨 自定义主题

修改 `frontend/src/styles.css` 中的 CSS 变量：

```css
:root {
  --primary-color: #10a37f;      /* 主色调 */
  --bg-primary: #ffffff;         /* 背景色 */
  --text-primary: #0d0d0d;       /* 文字色 */
  /* ... 更多变量 */
}
```

---

## 📞 获取帮助

1. **查看完整文档**: `README.md`
2. **功能清单**: `CHECKLIST.md`
3. **实现总结**: `IMPLEMENTATION_SUMMARY.md`
4. **后端 API 文档**: http://localhost:8000/docs
5. **浏览器开发者工具**: F12

---

## 🎯 下一步

### 推荐操作
1. ✅ 上传一份示例文档到 documents/ 文件夹
2. ✅ 构建知识库
3. ✅ 提几个问题测试功能
4. ✅ 根据需要调整模型配置
5. ✅ 检查 CHECKLIST.md 完成功能验证

### 进阶配置
- 配置生产环境 CORS
- 添加用户认证
- 优化向量检索参数
- 自定义 UI 主题

---

**祝您使用愉快! 🎉**

有问题? 查看 README.md 的故障排查部分。
