#!/usr/bin/env bash
# watchdog.sh — NL2SQL 后端自动守护脚本
# 用法: bash watchdog.sh
# 服务崩溃后自动重启，并将日志写入 logs/backend.log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/backend.log"
PID_FILE="$LOG_DIR/backend.pid"
PYTHON="$SCRIPT_DIR/.venv/bin/python"
START_CMD="$PYTHON run.py"
RESTART_DELAY=3  # 崩溃后等待 N 秒再重启

mkdir -p "$LOG_DIR"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cleanup() {
  log "守护进程收到退出信号，停止后端..."
  if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    kill "$PID" 2>/dev/null && log "后端进程 $PID 已终止" || true
    rm -f "$PID_FILE"
  fi
  exit 0
}
trap cleanup SIGINT SIGTERM

log "========================================"
log "NL2SQL 后端守护进程启动"
log "RootDir : $SCRIPT_DIR"
log "Python  : $PYTHON"
log "LogFile : $LOG_FILE"
log "========================================"

while true; do
  log "启动后端服务..."
  cd "$SCRIPT_DIR"
  $START_CMD >> "$LOG_FILE" 2>&1 &
  BACKEND_PID=$!
  echo "$BACKEND_PID" > "$PID_FILE"
  log "后端进程已启动 (PID=$BACKEND_PID)"

  # 等待子进程退出
  if wait "$BACKEND_PID"; then
    EXIT_CODE=0
  else
    EXIT_CODE=$?
  fi

  log "后端进程退出 (PID=$BACKEND_PID, ExitCode=$EXIT_CODE)"
  rm -f "$PID_FILE"

  log "等待 ${RESTART_DELAY}s 后自动重启..."
  sleep "$RESTART_DELAY"
done
