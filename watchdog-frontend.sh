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
RESTART_DELAY=3              # 崩溃后等待 N 秒再重启
FRONTEND_PORT=5173           # Vite 默认端口
MAX_FAILS_BEFORE_REINSTALL=3 # 连续失败 N 次后自动执行 npm install
QUICK_FAIL_THRESHOLD=10      # 进程存活 < N 秒视为快速失败
fail_count=0

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

# 杀掉占用端口的残留进程
kill_port() {
  local port=$1
  local pids
  pids=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    log "端口 $port 被 PID($pids) 占用，强制清理..."
    echo "$pids" | xargs kill -9 2>/dev/null || true
    sleep 1
  fi
}

while true; do
  kill_port "$FRONTEND_PORT"
  log "启动前端服务 (npm run dev)..."
  cd "$FRONTEND_DIR"

  START_TIME=$(date +%s)
  npm run dev >> "$LOG_FILE" 2>&1 &
  FRONTEND_PID=$!
  echo "$FRONTEND_PID" > "$PID_FILE"
  log "前端进程已启动 (PID=$FRONTEND_PID)"

  if wait "$FRONTEND_PID"; then
    EXIT_CODE=0
  else
    EXIT_CODE=$?
  fi

  END_TIME=$(date +%s)
  UPTIME=$(( END_TIME - START_TIME ))
  log "前端进程退出 (PID=$FRONTEND_PID, ExitCode=$EXIT_CODE, 运行时长=${UPTIME}s)"
  rm -f "$PID_FILE"

  # 判断是否属于快速失败（依赖损坏等启动期崩溃）
  if (( UPTIME < QUICK_FAIL_THRESHOLD )); then
    (( fail_count++ )) || true
    log "连续快速失败次数: $fail_count / $MAX_FAILS_BEFORE_REINSTALL"
    if (( fail_count >= MAX_FAILS_BEFORE_REINSTALL )); then
      log "触发自愈：清理 node_modules 并重新执行 npm install..."
      rm -rf "$FRONTEND_DIR/node_modules" "$FRONTEND_DIR/package-lock.json"
      npm install --prefix "$FRONTEND_DIR" >> "$LOG_FILE" 2>&1 \
        && log "npm install 完成，重置失败计数" \
        || log "npm install 失败，下次继续重试"
      fail_count=0
    fi
  else
    # 正常运行超过阈值，重置失败计数
    fail_count=0
  fi

  log "等待 ${RESTART_DELAY}s 后自动重启..."
  sleep "$RESTART_DELAY"
done
