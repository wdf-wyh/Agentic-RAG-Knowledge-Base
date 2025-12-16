#!/bin/bash

# RAG 知识库启动脚本

echo "================================"
echo "  RAG 知识库助手启动脚本"
echo "================================"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 检查必要的目录
if [ ! -d "documents" ]; then
    echo "📁 创建 documents 目录..."
    mkdir -p documents
fi

if [ ! -d "frontend" ]; then
    echo "❌ 错误: 未找到 frontend 目录"
    exit 1
fi

# 启动后端服务
echo ""
echo "🚀 启动后端服务..."
echo "后端将运行在: http://localhost:8000"
echo "API 文档: http://localhost:8000/docs"
echo ""

python app_api.py &
BACKEND_PID=$!

# 等待后端启动
sleep 3

# 启动前端应用
echo ""
echo "🎨 启动前端应用..."
echo "前端将运行在: http://localhost:5173"
echo ""

cd frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "================================"
echo "✓ 应用已启动!"
echo "================================"
echo ""
echo "📝 后端进程 ID: $BACKEND_PID"
echo "📝 前端进程 ID: $FRONTEND_PID"
echo ""
echo "💡 按 Ctrl+C 停止所有服务"
echo ""

# 等待用户中断
wait
