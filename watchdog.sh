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
RESTART_DELAY=3              # 崩溃后等待 N 秒再重启
BACKEND_PORT="${PORT:-8000}" # 与 run.py 保持一致
HEALTH_CHECK_INTERVAL=15     # 每 N 秒做一次 HTTP 健康检查
HEALTH_CHECK_TIMEOUT=3       # 单次健康检查超时秒数
HEALTH_CHECK_URL="http://127.0.0.1:${BACKEND_PORT}/docs"

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
trap cleanup SIGINT SIGTERM SIGHUP

log "========================================"
log "NL2SQL 后端守护进程启动"
log "RootDir : $SCRIPT_DIR"
log "Python  : $PYTHON"
log "LogFile : $LOG_FILE"
log "========================================"

# 杀掉占用端口的残留进程（防止端口冲突导致无限循环重启）
kill_port() {
  local port=$1
  local pids
  pids=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    log "端口 $port 被 PID($pids) 占用，强制清理..."
    echo "$pids" | xargs kill -9 2>/dev/null || true
    # 等待端口真正释放（最多 10s），避免 [Errno 48] Address already in use
    local waited=0
    while lsof -nP -iTCP:"$port" -sTCP:LISTEN -t &>/dev/null; do
      sleep 1
      waited=$((waited + 1))
      [[ $waited -ge 10 ]] && break
    done
    log "端口 $port 已释放（等待 ${waited}s）"
  fi
}

while true; do
  kill_port "$BACKEND_PORT"
  log "启动后端服务..."
  cd "$SCRIPT_DIR"
  $START_CMD >> "$LOG_FILE" 2>&1 &
  BACKEND_PID=$!
  echo "$BACKEND_PID" > "$PID_FILE"
  log "后端进程已启动 (PID=$BACKEND_PID)"

  # 后台健康检查：uvicorn reload 模式下 reloader 进程不会崩溃
  # 但 worker 子进程可能已死（HTTP 超时），需主动探测并杀掉僵死 reloader
  (
    sleep 20  # 等待初始启动完成
    while kill -0 "$BACKEND_PID" 2>/dev/null; do
      sleep "$HEALTH_CHECK_INTERVAL"
      if ! kill -0 "$BACKEND_PID" 2>/dev/null; then break; fi
      HTTP_CODE=$(curl -sm "$HEALTH_CHECK_TIMEOUT" -o /dev/null -w "%{http_code}" "$HEALTH_CHECK_URL" 2>/dev/null || echo "000")
      if [[ "$HTTP_CODE" == "000" ]]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 健康检查失败 (HTTP=$HTTP_CODE)，杀掉僵死 reloader PID=$BACKEND_PID" >> "$LOG_FILE"
        kill -9 "$BACKEND_PID" 2>/dev/null || true
        break
      fi
    done
  ) &
  HEALTH_PID=$!

  # 等待主进程退出
  if wait "$BACKEND_PID" 2>/dev/null; then
    EXIT_CODE=0
  else
    EXIT_CODE=$?
  fi

  # 清理健康检查子shell
  kill "$HEALTH_PID" 2>/dev/null || true

  log "后端进程退出 (PID=$BACKEND_PID, ExitCode=$EXIT_CODE)"
  rm -f "$PID_FILE"

  log "等待 ${RESTART_DELAY}s 后自动重启..."
  sleep "$RESTART_DELAY"
done
