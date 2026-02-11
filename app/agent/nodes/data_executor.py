"""
data_executor — 数据执行节点

执行 SQL 查询，处理结果。
如果执行失败，将错误信息写入 state，触发自我修正循环。
"""

import logging
from app.agent.state import AgentState
from app.agent.tools.database_tools import execute_query

logger = logging.getLogger(__name__)


def data_executor_node(state: AgentState) -> dict:
    """
    数据执行节点。
    输入: sql
    输出: query_result, sql_error (如果失败)
    """
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

    # 调用数据库执行 Tool
    result = execute_query.invoke({"sql": sql})

    if result.get("success"):
        data = result.get("data", [])
        logger.info(f"[data_executor] Success: {result.get('rows_count', 0)} rows")
        return {
            "query_result": {
                "success": True,
                "data": data,
                "rows_count": len(data) if isinstance(data, list) else 0,
                "sql": sql,
                "source": result.get("source", "unknown"),
            },
            "sql_error": "",  # 清除错误（成功了）
        }
    else:
        error_msg = result.get("error", "Unknown execution error")
        logger.warning(f"[data_executor] Failed: {error_msg}")
        return {
            "query_result": {
                "success": False,
                "data": [],
                "rows_count": 0,
                "sql": sql,
                "error": error_msg,
            },
            "sql_error": error_msg,
        }
