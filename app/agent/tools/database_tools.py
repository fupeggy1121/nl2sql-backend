"""
Database Tools — 封装现有 QueryExecutor + SupabaseClient
"""

import logging
import datetime
import decimal
from typing import Optional, Any
from langchain_core.tools import tool
from app.services.query_executor import QueryExecutor
from app.services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

# 延迟初始化
_executor = None


def _get_executor() -> QueryExecutor:
    global _executor
    if _executor is None:
        _executor = QueryExecutor(supabase_client=get_supabase_client())
    return _executor


def _make_json_safe(value: Any) -> Any:
    """将 MySQL 返回的非 JSON 原生类型转换为可序列化类型。"""
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        # 整数型列（id, status 等）MySQL 有时以 Decimal 回传
        # 若无小数部分则转为 int，避免前端显示为 59.00
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except Exception:
            return value.hex()
    return value


def _sanitize_rows(rows: list) -> list:
    """对查询结果列表中每行每列执行 JSON 安全转换。"""
    return [
        {k: _make_json_safe(v) for k, v in row.items()}
        for row in rows
        if isinstance(row, dict)
    ]


@tool
def execute_query(sql: str) -> dict:
    """Execute a SQL query against the database.
    Returns dict with keys: success, data, rows_count, error."""
    try:
        executor = _get_executor()
        result = executor.execute_query(sql)

        if result and result.get("success"):
            data = _sanitize_rows(result.get("data", []))
            return {
                "success": True,
                "data": data,
                "rows_count": len(data) if isinstance(data, list) else 0,
                "source": result.get("source", "unknown"),
            }
        else:
            error_msg = result.get("error", "Unknown execution error") if result else "No result returned"
            return {
                "success": False,
                "data": [],
                "rows_count": 0,
                "error": str(error_msg),
            }
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        return {
            "success": False,
            "data": [],
            "rows_count": 0,
            "error": str(e),
        }
