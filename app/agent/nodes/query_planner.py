"""
query_planner — 查询规划节点

"想清楚怎么查"而不是"去查"。
从意图识别结果提取结构化查询参数，为 SQL 生成做准备。
"""

import logging
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


def query_planner_node(state: AgentState) -> dict:
    """
    查询规划节点 (Phase C 增强)。
    输入: user_input, resolved_input, is_followup, intent_data, memory_context
    输出: query_plan
    """
    user_input = state.get("user_input", "")
    resolved_input = state.get("resolved_input", "") or user_input
    is_followup = state.get("is_followup", False)
    intent_data = state.get("intent_data", {})
    memory_context = state.get("memory_context", {})

    # Phase C: 追问时使用消解后的输入
    effective_input = resolved_input if is_followup else user_input

    logger.info(
        f"[query_planner] Building plan for: {effective_input[:60]}... "
        f"(followup={is_followup})"
    )

    # 从意图识别结果中提取结构化参数
    entities = intent_data.get("entities", {})

    query_plan = {
        "natural_language": effective_input,
        "intent_type": intent_data.get("intent", "direct_query"),
        "confidence": intent_data.get("confidence", 0.0),
        "table": entities.get("table"),
        "metrics": entities.get("metrics", []),
        "time_range": entities.get("timeRange"),
        "equipment": entities.get("equipment"),
        "product_line": entities.get("productLine"),
        "limit": entities.get("limit"),
        "filters": entities.get("filters", {}),
        # Phase C: 对话上下文
        "is_followup": is_followup,
        "conversation_context": memory_context.get("context_summary", ""),
    }

    # Phase C: 追问时尝试从上轮继承缺失的表名
    if is_followup and not query_plan["table"]:
        last_ctx = memory_context.get("last_query_context", {})
        last_sql = last_ctx.get("last_sql", "")
        if last_sql:
            inferred_table = _extract_table_from_sql(last_sql)
            if inferred_table:
                query_plan["table"] = inferred_table
                logger.info(f"[query_planner] Inherited table from last query: {inferred_table}")

    logger.info(f"[query_planner] Plan: table={query_plan['table']}, "
                f"metrics={query_plan['metrics']}")

    return {
        "query_plan": query_plan,
    }


def _extract_table_from_sql(sql: str) -> str:
    """从 SQL 中提取主表名"""
    import re
    m = re.search(r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql, re.IGNORECASE)
    return m.group(1) if m else ""
