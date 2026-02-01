#!/bin/bash

# NL2SQL 后端 - Cloudflare Tunnel 启动脚本
# 用于将本地后端暴露到公网

echo "🚀 NL2SQL 后端隧道启动脚本"
echo "================================"

# 检查后端是否运行
if ! lsof -i :8000 > /dev/null; then
    echo "⚠️  后端未运行，正在启动..."
    cd /Users/fupeggy/NL2SQL
    source .venv/bin/activate
    python run.py &
    BACKEND_PID=$!
    echo "✅ 后端启动成功 (PID: $BACKEND_PID)"
    sleep 3
else
    echo "✅ 后端已在运行"
fi

echo ""
echo "🌉 启动 Cloudflare Tunnel..."
echo "================================"

# 启动 Cloudflare Tunnel
cloudflared tunnel --url http://localhost:8000

echo ""
echo "按 Ctrl+C 停止隧道"
