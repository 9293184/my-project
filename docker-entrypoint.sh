#!/bin/bash
set -e

echo "=========================================="
echo "AI 安全训练平台启动中..."
echo "=========================================="

# 启动 Ollama 服务
echo "启动 Ollama 服务..."
ollama serve &
OLLAMA_PID=$!

# 等待 Ollama 启动
sleep 5

# 检查是否需要拉取模型
if [ ! -z "$OLLAMA_MODEL" ]; then
    echo "拉取模型: $OLLAMA_MODEL"
    ollama pull $OLLAMA_MODEL
fi

# 启动后端服务
echo "启动后端服务..."
cd /app/backend
python app.py &
BACKEND_PID=$!

# 启动前端（如果存在）
if [ -d "/app/frontend" ]; then
    echo "启动前端服务..."
    cd /app/frontend
    if [ -f "package.json" ]; then
        npm install
        npm run dev &
        FRONTEND_PID=$!
    fi
fi

echo "=========================================="
echo "✓ 所有服务启动完成"
echo "=========================================="
echo "后端 API: http://localhost:8000"
echo "前端界面: http://localhost:5173"
echo "Ollama API: http://localhost:11434"
echo "=========================================="

# 等待所有进程
wait $OLLAMA_PID $BACKEND_PID $FRONTEND_PID
