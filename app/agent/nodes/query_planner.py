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
    查询规划节点。
    输入: user_input, intent_data
    输出: query_plan
    """
    user_input = state.get("user_input", "")
    intent_data = state.get("intent_data", {})

    logger.info(f"[query_planner] Building plan for: {user_input[:60]}...")

    # 从意图识别结果中提取结构化参数
    entities = intent_data.get("entities", {})

    query_plan = {
        "natural_language": user_input,
        "intent_type": intent_data.get("intent", "direct_query"),
        "confidence": intent_data.get("confidence", 0.0),
        "table": entities.get("table"),
        "metrics": entities.get("metrics", []),
        "time_range": entities.get("timeRange"),
        "equipment": entities.get("equipment"),
        "product_line": entities.get("productLine"),
        "limit": entities.get("limit"),
        "filters": entities.get("filters", {}),
    }

    logger.info(f"[query_planner] Plan: table={query_plan['table']}, "
                f"metrics={query_plan['metrics']}")

    return {
        "query_plan": query_plan,
    }
