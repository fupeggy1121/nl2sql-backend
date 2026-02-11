"""
Database Tools — 封装现有 QueryExecutor + SupabaseClient
"""

import logging
from typing import Optional
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


@tool
def execute_query(sql: str) -> dict:
    """Execute a SQL query against the database.
    Returns dict with keys: success, data, rows_count, error."""
    try:
        executor = _get_executor()
        result = executor.execute_query(sql)

        if result and result.get("success"):
            data = result.get("data", [])
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
