"""
chart_generator — 图表配置生成节点

根据推荐的图表类型和数据，生成 ECharts option JSON 配置。
前端拿到 JSON 直接 chart.setOption(config) 即可渲染。
"""

import logging
import time
from app.agent.state import AgentState
from app.agent.trace import trace_step

logger = logging.getLogger(__name__)


def chart_generator_node(state: AgentState) -> dict:
    """
    图表配置生成节点。
    输入: chart_type, visualization, query_result
    输出: chart_config
    
    当前阶段（Phase A）：直接透传 visualization 信息。
    后续阶段可以在这里生成完整的 ECharts option JSON。
    """
    _t0 = time.perf_counter()
    chart_type = state.get("chart_type", "table")
    visualization = state.get("visualization", {})
    query_result = state.get("query_result", {})

    data = query_result.get("data", [])
    if not data:
        return {"chart_config": None}

    # Phase A: 透传 visualization 信息，前端使用现有逻辑渲染
    # 后续 Phase 可以在此生成完整 ECharts option JSON
    chart_config = {
        "chart_type": chart_type,
        "visualization": visualization,
        "data_summary": {
            "rows": len(data),
            "columns": list(data[0].keys()) if data else [],
        },
    }

    logger.info(f"[chart_generator] Config generated for type={chart_type}")

    # ── Pipeline Trace ──
    trace = list(state.get("pipeline_trace", []))
    trace_step(trace, "chart_generator", _t0, summary=(
        f"生成 {chart_type} 图表配置, {len(data)} 行数据"
    ), detail={
        "chart_type": chart_type,
        "rows": len(data),
        "columns": list(data[0].keys()) if data else [],
    })

    return {"chart_config": chart_config, "pipeline_trace": trace}
