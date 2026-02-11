"""
result_analyzer — 结果分析节点

分析查询结果的数据特征，推荐合适的图表类型。
"""

import logging
from app.agent.state import AgentState
from app.agent.tools.chart_tools import recommend_chart

logger = logging.getLogger(__name__)


def result_analyzer_node(state: AgentState) -> dict:
    """
    结果分析节点。
    输入: sql, query_result, user_input, intent_data
    输出: chart_type, visualization
    """
    query_result = state.get("query_result", {})
    sql = state.get("sql", "")
    user_input = state.get("user_input", "")
    intent_data = state.get("intent_data", {})

    if not query_result.get("success"):
        logger.info("[result_analyzer] No successful data to analyze")
        return {
            "chart_type": "table",
            "visualization": {
                "type": "table",
                "title": "",
                "xAxisField": None,
                "yAxisField": None,
                "seriesField": None,
                "confidence": 0.0,
                "reason": "Query failed, defaulting to table",
            },
        }

    data = query_result.get("data", [])

    # 调用图表推荐 Tool
    viz = recommend_chart.invoke({
        "sql": sql,
        "data": data,
        "natural_language": user_input,
        "intent_type": intent_data.get("intent", ""),
    })

    chart_type = viz.get("type", "table")
    logger.info(f"[result_analyzer] Recommended: {chart_type} (conf={viz.get('confidence', 0):.2f})")

    return {
        "chart_type": chart_type,
        "visualization": viz,
    }
