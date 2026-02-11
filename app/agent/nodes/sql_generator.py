"""
sql_generator — SQL 生成节点

根据查询计划 + (可选) 错误上下文，调用 LLM 生成 SQL。
支持自我修正：如果 state 中有 sql_error，会注入错误信息让 LLM 修正。
"""

import logging
from app.agent.state import AgentState
from app.agent.tools.nl2sql_tools import generate_sql

logger = logging.getLogger(__name__)


def sql_generator_node(state: AgentState) -> dict:
    """
    SQL 生成节点。
    输入: user_input, query_plan, sql_error (可选), sql_retry_count (可选)
    输出: sql, sql_confidence, sql_retry_count
    """
    user_input = state.get("user_input", "")
    query_plan = state.get("query_plan", {})
    sql_error = state.get("sql_error", "")
    retry_count = state.get("sql_retry_count", 0)

    # 构建优化后的自然语言查询（结合 query_plan 的结构化信息）
    nl_query = _build_optimized_query(user_input, query_plan)

    # 如果是重试，构造错误上下文
    error_context = ""
    if sql_error and retry_count > 0:
        previous_sql = state.get("sql", "")
        error_context = (
            f"Previous SQL: {previous_sql}\n"
            f"Error: {sql_error}"
        )
        logger.info(
            f"[sql_generator] Retry #{retry_count}: fixing SQL error: "
            f"{sql_error[:100]}..."
        )

    # 调用 NL2SQL Tool
    sql = generate_sql.invoke({
        "natural_language": nl_query,
        "error_context": error_context,
    })

    # 更新重试计数（仅在重试时递增，首次生成不变）
    new_retry_count = retry_count + 1 if sql_error else 0

    if sql:
        logger.info(f"[sql_generator] Generated SQL: {sql[:100]}...")
        return {
            "sql": sql,
            "sql_confidence": 0.85 if not sql_error else 0.7,
            "sql_retry_count": new_retry_count,
            "sql_error": "",  # 清除上一次的错误
        }
    else:
        logger.warning("[sql_generator] Failed to generate SQL")
        return {
            "sql": "",
            "sql_confidence": 0.0,
            "sql_retry_count": new_retry_count,
            "error": "Failed to generate SQL from natural language input",
        }


def _build_optimized_query(user_input: str, query_plan: dict) -> str:
    """
    结合 query_plan 的结构化信息优化自然语言查询。
    如果 query_plan 中有明确的 table/metrics 信息，将其补充到查询中。
    """
    parts = [user_input]

    table = query_plan.get("table")
    if table:
        parts.append(f"(目标表: {table})")

    time_range = query_plan.get("time_range")
    if time_range:
        parts.append(f"(时间范围: {time_range})")

    limit = query_plan.get("limit")
    if limit:
        parts.append(f"(限制 {limit} 条)")

    return " ".join(parts)
