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

# ── 分析意图转原始数据查询 ──
_ANALYSIS_VERBS = re.compile(r'^(分析|统计|评估|计算|对比)\s*')
_ANALYSIS_SUFFIX = re.compile(
    r'[，,]\s*(计算|分析|统计|评估)\s*(Cpk|Ppk|SPC|控制图|过程能力|制程能力|cp|ppk)[^，,]*',
    re.IGNORECASE,
)
_ANALYSIS_SUBJECT_SUFFIX = re.compile(r'的(制程能力|过程能力|品质能力|能力指数|统计特性|控制图)[^，,]*')


def _reformat_for_data_fetch(analysis_input: str) -> str:
    """
    将分析类查询转换为取原始数据查询，供两阶段管道的 Stage 1 使用。

    例: "分析晶圆厚度测量值的制程能力，计算 Cpk"
      → "查询晶圆厚度测量值的原始测量记录数据"
    """
    q = _ANALYSIS_VERBS.sub('', analysis_input)           # 去前置分析动词
    q = _ANALYSIS_SUFFIX.sub('', q)                       # 去末尾的 "计算 Cpk" 等
    q = _ANALYSIS_SUBJECT_SUFFIX.sub('', q)               # 去 "的制程能力" 等后缀
    q = q.strip().rstrip('，, ')
    if q and not q.startswith('查询'):
        q = f"查询{q}的原始测量记录数据"
    return q or analysis_input

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
    r"一次良率|首次合格率|直通率|FPY|first.pass.yield|"
    r"综合良率|最终良率|累计良率|final.yield|overall.yield|"
    r"返工率|重工率|rework.rate|"
    r"OEE|oee|综合效率|设备效率|设备综合|可用率.*性能|日报|周报|月报|"
    r"良率.*趋势|趋势.*良率|不良.*分析|NG.*分析|ng.*分析",
    re.IGNORECASE,
)


def classify_agent_intent(user_input: str) -> Literal["query", "analyze", "report"]:
    """
    顶层意图预分类 — 决定路由到哪个子 Agent。

    当前策略: 关键词匹配。Phase 3 可升级为 LLM 分类。
    优先级: report > analyze > query

    路由规则:
    - "report"  → _run_analysis_agent()              （良率/OEE 报表，有专属 SQL builder）
    - "analyze" → _run_analysis_with_data_pipeline() （SPC/相关性等，先 query_agent 取数）
    - "query"   → _run_query_agent()                 （普通查询）
    """
    if _REPORT_KEYWORDS.search(user_input):
        return "report"   # 良率/OEE 报表 → analysis_agent 直接走（method_selector 内有专属 SQL builder）
    if _ANALYSIS_KEYWORDS.search(user_input):
        return "analyze"  # SPC/相关性等 → 两阶段管道（先 query_agent 取数，再 analysis_agent 分析）
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
        return await _run_analysis_with_data_pipeline(
            user_input, session_id, conversation_history, **kwargs
        )
    elif intent == "report":
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


async def _run_analysis_with_data_pipeline(
    user_input: str,
    session_id: str,
    conversation_history: list | None = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    两阶段分析管道（SPC / 相关性 / 异常检测 / 描述性统计等）:

    Stage 1 — query_agent 利用完整本体语义生成并执行 SQL，获取原始 DataFrame
    Stage 2 — analysis_agent 对原始数据执行统计分析并生成报告

    优势：数据来源由本体语义自动解析，无需硬编码 SQL 模板。
    """
    from app.agents.analysis_agent.graph import get_analysis_agent_app

    # ── Stage 1: query_agent 取原始数据 ──
    # 将分析型查询转换为原始数据查询，避免 query_agent 预聚合导致数据量不足
    data_query = _reformat_for_data_fetch(user_input)
    logger.info(
        f"[supervisor] two-stage pipeline → Stage 1: query_agent"
        f"\n  original: {user_input[:80]}"
        f"\n  data_query: {data_query[:80]}"
    )
    query_state = await _run_query_agent(
        data_query, session_id, conversation_history, **kwargs
    )
    query_result = query_state.get("query_result") or {}
    raw_data: list = query_result.get("data") or []
    logger.info(f"[supervisor] two-stage → Stage 1 done: {len(raw_data)} rows retrieved")

    # ── Stage 2: analysis_agent 接收 raw_data ──
    logger.info(f"[supervisor] two-stage → Stage 2: analysis_agent")
    initial_state = {
        "user_input": user_input,
        "session_id": session_id,
        "raw_data": raw_data,
    }

    final_state: Dict[str, Any] = {}
    try:
        agent = get_analysis_agent_app()
        final_state = await agent.ainvoke(initial_state)
        response = final_state.get("response") or {
            "success": False,
            "answer": "分析 Agent 未返回结果",
        }
    except Exception as e:
        logger.error(f"[supervisor] analysis_agent error: {e}", exc_info=True)
        response = {"success": False, "answer": f"分析 Agent 执行出错: {e}"}

    pipeline_trace = (
        response.pop("pipeline_trace", None)
        or final_state.get("pipeline_trace")
        or []
    )
    return {
        "response": response,
        "is_followup": False,
        "session_id": session_id,
        "pipeline_trace": pipeline_trace,
    }


async def _run_analysis_agent(
    user_input: str,
    session_id: str,
    conversation_history: list | None = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    良率 / OEE 报表路由：analysis_agent 直接走（method_selector 内有专属 SQL builder）。

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
