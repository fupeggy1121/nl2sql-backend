#!/bin/bash
# 安全重启 backend，防止旧进程残留导致测试环境污染
set -e

cd "$(dirname "$0")/.."

echo "==> 停止旧 backend 进程..."
pkill -f "python run.py" 2>/dev/null || true
pkill -f "\.venv.*run\.py" 2>/dev/null || true
sleep 2

# 彻底清理端口 8000 上的残留进程
PIDS=$(lsof -ti:8000 2>/dev/null) || true
if [ -n "$PIDS" ]; then
    echo "==> 强制清理端口 8000 上的进程: $PIDS"
    echo "$PIDS" | xargs kill -9 2>/dev/null || true
    sleep 1
fi

echo "==> 启动新 backend (no-reload)..."
# 使用 ENV=production 禁用 watchfiles 热重载，防止干扰测试环境
nohup env ENV=production .venv/bin/python run.py > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo "    Backend PID=$BACKEND_PID"

echo "==> 等待启动 (8s)..."
sleep 8

echo "==> 健康检查..."
curl -s http://localhost:8000/health | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    status = d.get('status', 'unknown')
    print(f'    status: {status}')
    sys.exit(0 if status == 'healthy' else 1)
except Exception as e:
    print(f'    health check failed: {e}')
    sys.exit(1)
"
