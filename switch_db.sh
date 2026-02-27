#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# switch_db.sh — 切换数据库环境（test ↔ prod）
#
# 用法:
#   ./switch_db.sh test    # 切换到测试环境（Supabase）
#   ./switch_db.sh prod    # 切换到生产环境（自托管 PostgreSQL）
#   ./switch_db.sh status  # 查看当前环境
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ENV_FILE=".env"
TEST_ENV=".env.test"
PROD_ENV=".env.prod"
PYCACHE_DIR="app"

usage() {
    echo "用法: $0 [test|prod|status]"
    exit 1
}

show_status() {
    if [[ ! -f "$ENV_FILE" ]]; then
        echo "⚠️  .env 文件不存在"
        return
    fi
    backend=$(grep -E '^DB_BACKEND=' "$ENV_FILE" | cut -d= -f2 | tr -d '[:space:]' || echo "未设置")
    mapping=$(grep -E '^MAPPING_FILE=' "$ENV_FILE" | cut -d= -f2 | tr -d '[:space:]' || echo "未设置")
    echo "─────────────────────────────────"
    echo "  当前环境"
    echo "  DB_BACKEND   : $backend"
    echo "  MAPPING_FILE : $mapping"
    echo "─────────────────────────────────"
}

clear_pycache() {
    echo "🧹 清理 __pycache__ ..."
    find "$PYCACHE_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
}

case "${1:-}" in
    test)
        if [[ ! -f "$TEST_ENV" ]]; then
            echo "❌ 未找到 $TEST_ENV"
            exit 1
        fi
        cp "$TEST_ENV" "$ENV_FILE"
        clear_pycache
        echo "✅ 已切换到 测试环境（Supabase）"
        show_status
        ;;
    prod)
        if [[ ! -f "$PROD_ENV" ]]; then
            echo "❌ 未找到 $PROD_ENV"
            exit 1
        fi
        cp "$PROD_ENV" "$ENV_FILE"
        clear_pycache
        echo "✅ 已切换到 生产环境（self-hosted PostgreSQL）"
        show_status
        ;;
    status)
        show_status
        ;;
    *)
        usage
        ;;
esac
