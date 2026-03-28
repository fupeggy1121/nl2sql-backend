"""
Supervisor — Multi-Agent 顶层路由器

职责：
1. 对用户输入进行意图预分类
2. 路由到对应的子 Agent（query / analyze / report）
3. 统一响应格式返回

Phase 0: 仅支持 query 和 analyze 路由，analyze 暂返回提示。
现有 Query Agent 逻辑零改动，通过 import 委托调用。
"""

import logging
import re
from typing import Dict, Any, Literal

logger = logging.getLogger(__name__)

# ── 分析意图关键词 ──
_ANALYSIS_KEYWORDS = re.compile(
    r"SPC|控制图|Cpk|Ppk|相关性分析|回归分析|预测模型|异常检测|帕累托|"
    r"良率分析|趋势分析|方差分析|ANOVA|假设检验|t[\-\s]?test|卡方检验|"
    r"统计分析|数据分析|描述性统计|分布分析|散点图分析|热力图",
    re.IGNORECASE,
)

# ── 报表类意图关键词（良率报表、OEE 日报等须走 analysis_agent） ──
_REPORT_KEYWORDS = re.compile(
    r"良率报表|良率分析|yield.*report|合格率报表|不良率.*报表|工站良率|站点良率|"
    r"OEE|oee|综合效率|设备效率|设备综合|可用率.*性能|日报|周报|月报|"
    r"良率.*趋势|趋势.*良率|不良.*分析|NG.*分析|ng.*分析",
    re.IGNORECASE,
)


def classify_agent_intent(user_input: str) -> Literal["query", "analyze", "report"]:
    """
    顶层意图预分类 — 决定路由到哪个子 Agent。

    当前策略: 关键词匹配。Phase 3 可升级为 LLM 分类。
    优先级: report > analyze > query
    """
    if _REPORT_KEYWORDS.search(user_input):
        return "analyze"  # 报表走 analysis_agent（内部由 method_selector 选 yield_report/oee_report）
    if _ANALYSIS_KEYWORDS.search(user_input):
        return "analyze"
    return "query"


async def route_to_agent(
    user_input: str,
    session_id: str,
    conversation_history: list | None = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Supervisor 主入口 — 分类意图并路由到子 Agent。

    返回格式与现有 chat 端点一致：
    {
        "response": {...},
        "is_followup": bool,
        "session_id": str,
        ...AgentState fields
    }
    """
    intent = classify_agent_intent(user_input)
    logger.info(f"[supervisor] intent={intent}, input={user_input[:60]}...")

    if intent == "query":
        return await _run_query_agent(
            user_input, session_id, conversation_history, **kwargs
        )
    elif intent == "analyze":
        return await _run_analysis_agent(
            user_input, session_id, conversation_history, **kwargs
        )
    else:
        return await _run_query_agent(
            user_input, session_id, conversation_history, **kwargs
        )


async def _run_query_agent(
    user_input: str,
    session_id: str,
    conversation_history: list | None = None,
    **kwargs,
) -> Dict[str, Any]:
    """委托给现有 Query Agent（app/agent/graph.py），零改动。"""
    from app.agent.graph import get_agent_app

    agent = get_agent_app()
    initial_state = {
        "user_input": user_input,
        "session_id": session_id,
        "conversation_history": conversation_history or [],
        "sql_retry_count": 0,
        **kwargs,
    }
    return await agent.ainvoke(initial_state)


async def _run_analysis_agent(
    user_input: str,
    session_id: str,
    conversation_history: list | None = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    路由到 Analysis Agent (Phase 3 实装)。

    委托给 app/agents/analysis_agent/graph.py 的独立 LangGraph。
    """
    from app.agents.analysis_agent.graph import get_analysis_agent_app

    logger.info(f"[supervisor] → analysis_agent: {user_input[:60]}...")

    initial_state = {
        "user_input": user_input,
        "session_id": session_id,
    }

    try:
        agent = get_analysis_agent_app()
        final_state = await agent.ainvoke(initial_state)
        response = final_state.get("response") or {
            "success": False,
            "answer": "分析 Agent 未返回结果",
        }
    except Exception as e:
        logger.error(f"[supervisor] analysis_agent error: {e}", exc_info=True)
        response = {
            "success": False,
            "answer": f"分析 Agent 执行出错: {e}",
        }

    # 透传 pipeline_trace（analysis_agent 在 viz_generator 中组装）
    pipeline_trace = response.pop("pipeline_trace", None) or final_state.get("pipeline_trace") or []

    return {
        "response": response,
        "is_followup": False,
        "session_id": session_id,
        "pipeline_trace": pipeline_trace,
    }
