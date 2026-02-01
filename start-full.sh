#!/bin/bash

# 🚀 NL2SQL 一键启动脚本
# 同时启动后端和 Cloudflare 隧道

set -e

PROJECT_DIR="/Users/fupeggy/NL2SQL"
VENV_DIR="$PROJECT_DIR/.venv"
LOG_DIR="$PROJECT_DIR/logs"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}🚀 NL2SQL 后端完整启动${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# 检查虚拟环境
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}❌ 虚拟环境不存在: $VENV_DIR${NC}"
    exit 1
fi

# 激活虚拟环境
echo -e "${YELLOW}📦 激活 Python 虚拟环境...${NC}"
source "$VENV_DIR/bin/activate"

# 检查后端进程
if lsof -i :8000 > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  端口 8000 已被占用${NC}"
    read -p "是否杀死现有进程? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        lsof -ti :8000 | xargs kill -9
        echo -e "${GREEN}✅ 已杀死旧进程${NC}"
    else
        echo -e "${RED}❌ 启动失败${NC}"
        exit 1
    fi
fi

# 启动后端
echo -e "${YELLOW}🔧 启动 Flask 后端...${NC}"
cd "$PROJECT_DIR"
nohup python run.py > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo -e "${GREEN}✅ 后端已启动 (PID: $BACKEND_PID)${NC}"
sleep 2

# 检查后端是否正常启动
if ! lsof -i :8000 > /dev/null 2>&1; then
    echo -e "${RED}❌ 后端启动失败${NC}"
    cat "$LOG_DIR/backend.log"
    exit 1
fi

echo -e "${GREEN}✅ 后端运行正常${NC}"
echo ""

# 启动 Cloudflare 隧道
echo -e "${YELLOW}🌉 启动 Cloudflare Tunnel...${NC}"
echo ""
cloudflared tunnel --url http://localhost:8000 2>&1 | tee "$LOG_DIR/tunnel.log" &
TUNNEL_PID=$!

echo ""
echo -e "${BLUE}================================${NC}"
echo -e "${GREEN}✅ 启动完成！${NC}"
echo -e "${BLUE}================================${NC}"
echo ""
echo -e "${YELLOW}📊 服务状态:${NC}"
echo "  后端进程 ID: $BACKEND_PID"
echo "  隧道进程 ID: $TUNNEL_PID"
echo ""
echo -e "${YELLOW}📝 日志文件:${NC}"
echo "  后端日志: $LOG_DIR/backend.log"
echo "  隧道日志: $LOG_DIR/tunnel.log"
echo ""
echo -e "${YELLOW}🌐 查看隧道 URL:${NC}"
echo "  grep 'trycloudflare.com' $LOG_DIR/tunnel.log"
echo ""
echo -e "${YELLOW}⏹️  停止服务:${NC}"
echo "  kill $BACKEND_PID $TUNNEL_PID"
echo ""
echo -e "${YELLOW}💡 提示:${NC}"
echo "  1. 查看隧道输出中的 URL"
echo "  2. 复制 URL 到前端配置中"
echo "  3. 刷新前端页面"
echo ""

# 等待隧道启动
sleep 5

# 显示隧道输出
echo -e "${YELLOW}🔗 隧道输出 (最后 10 行):${NC}"
tail -10 "$LOG_DIR/tunnel.log"

# 保持进程运行
wait
