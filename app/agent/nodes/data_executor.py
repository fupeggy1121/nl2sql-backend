"""
data_executor — 数据执行节点

执行 SQL 查询，处理结果。
如果执行失败，将错误信息写入 state，触发自我修正循环。
"""

import logging
import time
from app.agent.state import AgentState
from app.agent.tools.database_tools import execute_query
from app.agent.trace import trace_step
from app.agent.cache import result_cache

logger = logging.getLogger(__name__)


def data_executor_node(state: AgentState) -> dict:
    """
    数据执行节点。
    输入: sql
    输出: query_result, sql_error (如果失败)
    """
    _t0 = time.perf_counter()
    sql = state.get("sql", "")

    if not sql:
        logger.warning("[data_executor] No SQL to execute")
        return {
            "query_result": {
                "success": False,
                "data": [],
                "rows_count": 0,
                "error": "No SQL generated",
            },
            "sql_error": "No SQL was generated to execute",
        }

    logger.info(f"[data_executor] Executing: {sql[:100]}...")

    # ── B2: 查询结果缓存查找 (TTL 60s) ──
    _cache_result = result_cache.get(sql)
    if _cache_result is not None:
        logger.info(f"[data_executor] Cache HIT for SQL")
        data = _cache_result.get("data", [])
        rows = len(data) if isinstance(data, list) else 0
        trace = list(state.get("pipeline_trace", []))
        trace_step(trace, "data_executor", _t0, summary=(
            f"[缓存] 返回 {rows} 行数据"
        ), detail={
            "rows_count": rows,
            "columns": list(data[0].keys()) if data else [],
            "cache_hit": True,
        })
        return {
            "query_result": _cache_result,
            "sql_error": "",
            "pipeline_trace": trace,
        }

    # 调用数据库执行 Tool
    result = execute_query.invoke({"sql": sql})

    trace = list(state.get("pipeline_trace", []))

    if result.get("success"):
        data = result.get("data", [])
        rows = len(data) if isinstance(data, list) else 0
        logger.info(f"[data_executor] Success: {rows} rows")
        trace_step(trace, "data_executor", _t0, summary=(
            f"执行成功, 返回 {rows} 行数据"
        ), detail={
            "rows_count": rows,
            "columns": list(data[0].keys()) if data else [],
            "source": result.get("source", "unknown"),
        })
        _query_result = {
            "success": True,
            "data": data,
            "rows_count": rows,
            "sql": sql,
            "source": result.get("source", "unknown"),
        }
        # 写入结果缓存
        result_cache.set(sql, _query_result)
        return {
            "query_result": _query_result,
            "sql_error": "",  # 清除错误（成功了）
            "pipeline_trace": trace,
        }
    else:
        error_msg = result.get("error", "Unknown execution error")
        is_db_conn_err = result.get("db_connection_error", False)
        logger.warning(f"[data_executor] Failed ({'db_conn' if is_db_conn_err else 'sql'}): {error_msg}")
        trace_step(trace, "data_executor", _t0,
                   summary=f"{'DB连接错误' if is_db_conn_err else '执行失败'}: {error_msg[:60]}",
                   status="error",
                   detail={"error": error_msg, "sql": sql[:200], "db_connection_error": is_db_conn_err})
        result_payload = {
            "query_result": {
                "success": False,
                "data": [],
                "rows_count": 0,
                "sql": sql,
                "error": error_msg,
            },
            "pipeline_trace": trace,
        }
        if is_db_conn_err:
            # 连接类错误：写 db_error，不写 sql_error
            # → _route_after_execution 不会路由到 sql_generator，直接 response_builder
            result_payload["db_error"] = error_msg
            result_payload["sql_error"] = ""   # 清空，避免残留触发额外重试
        else:
            result_payload["sql_error"] = error_msg
        return result_payload
