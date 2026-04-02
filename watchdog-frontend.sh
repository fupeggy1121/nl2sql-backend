#!/usr/bin/env bash
# watchdog-frontend.sh — NL2SQL 前端自动守护脚本
# 用法: bash watchdog-frontend.sh
# 服务崩溃后自动重启，并将日志写入 logs/frontend.log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/frontend.log"
PID_FILE="$LOG_DIR/frontend.pid"
RESTART_DELAY=3  # 崩溃后等待 N 秒再重启

mkdir -p "$LOG_DIR"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cleanup() {
  log "守护进程收到退出信号，停止前端..."
  if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    # npm run dev 会派生子进程，用 pkill 整组终止
    kill "$PID" 2>/dev/null
    sleep 1
    pkill -f "vite" 2>/dev/null || true
    log "前端进程 $PID 已终止"
    rm -f "$PID_FILE"
  fi
  exit 0
}
trap cleanup SIGINT SIGTERM SIGHUP

log "========================================"
log "NL2SQL 前端守护进程启动"
log "FrontendDir: $FRONTEND_DIR"
log "LogFile    : $LOG_FILE"
log "========================================"

while true; do
  log "启动前端服务 (npm run dev)..."
  cd "$FRONTEND_DIR"

  npm run dev >> "$LOG_FILE" 2>&1 &
  FRONTEND_PID=$!
  echo "$FRONTEND_PID" > "$PID_FILE"
  log "前端进程已启动 (PID=$FRONTEND_PID)"

  if wait "$FRONTEND_PID"; then
    EXIT_CODE=0
  else
    EXIT_CODE=$?
  fi

  log "前端进程退出 (PID=$FRONTEND_PID, ExitCode=$EXIT_CODE)"
  rm -f "$PID_FILE"

  log "等待 ${RESTART_DELAY}s 后自动重启..."
  sleep "$RESTART_DELAY"
done
