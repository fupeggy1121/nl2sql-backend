"""
result_analyzer — 结果分析节点

分析查询结果的数据特征，推荐合适的图表类型。
"""

import logging
import time
from app.agent.state import AgentState
from app.agent.tools.chart_tools import recommend_chart
from app.agent.trace import trace_step

logger = logging.getLogger(__name__)


def result_analyzer_node(state: AgentState) -> dict:
    """
    结果分析节点。
    输入: sql, query_result, user_input, intent_data
    输出: chart_type, visualization
    """
    _t0 = time.perf_counter()
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

    # ── Pipeline Trace ──
    trace = list(state.get("pipeline_trace", []))
    trace_step(trace, "result_analyzer", _t0, summary=(
        f"推荐图表: {chart_type}, 置信度: {viz.get('confidence', 0):.2f}"
    ), detail={
        "chart_type": chart_type,
        "x_axis": viz.get("xAxisField"),
        "y_axis": viz.get("yAxisField"),
        "confidence": viz.get("confidence", 0),
        "reason": viz.get("reason", ""),
    })

    return {
        "chart_type": chart_type,
        "visualization": viz,
        "pipeline_trace": trace,
    }
