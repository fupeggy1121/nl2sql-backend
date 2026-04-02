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

# ── 分析意图关键词（仅用作 fallback / 快速路径辅助） ──
_ANALYSIS_KEYWORDS = re.compile(
    r"SPC|控制图|Cpk|Ppk|相关性分析|回归分析|预测模型|异常检测|帕累托|"
    r"良率分析|趋势分析|方差分析|ANOVA|假设检验|t[\-\s]?test|卡方检验|"
    r"统计分析|数据分析|描述性统计|分布分析|散点图分析|热力图",
    re.IGNORECASE,
)

# ── 报表类关键词（仅用作 fallback） ──
_REPORT_KEYWORDS = re.compile(
    r"良率报表|良率分析|yield.*report|合格率报表|不良率.*报表|工站良率|站点良率|"
    r"一次良率|首次合格率|直通率|FPY|first.pass.yield|"
    r"综合良率|最终良率|累计良率|final.yield|overall.yield|"
    r"返工率|重工率|rework.rate|"
    r"OEE|oee|综合效率|设备效率|设备综合|可用率.*性能|日报|周报|月报|"
    r"良率.*趋势|趋势.*良率|不良.*分析|NG.*分析|ng.*分析",
    re.IGNORECASE,
)

# ── LLM 分类提示词 ──
_INTENT_CLASSIFY_PROMPT = """\
你是一个工业 MES 系统的智能路由器，需要将用户输入分类到三种处理管道之一。

## 三种管道定义

**query**（普通查询管道）：
- 普通数据查询、统计、筛选（NL2SQL）
- 基线/预警/阈值的设定、修改、删除操作（如"为一次良率添加基线下限85%"、"设置良率预警阈值"）
- 写操作（进站/出站/拆批等）
- 问答、解释说明

**report**（分析报表管道）：
- 计算/展示良率指标：一次良率(FPY)、综合良率、返工率
- 计算/展示 OEE（综合设备效率）
- 以上指标的趋势、对比、汇总报表

**analyze**（统计分析管道）：
- SPC、控制图、Cpk/Ppk 等过程能力分析
- 相关性分析、回归分析、异常检测、帕累托分析
- 需要对原始数据做统计建模的场景

## 判断规则
- 如果句子中**既有良率/OEE关键词，又有 基线/预警/阈值/上限/下限/设定/添加/修改/删除 等操作动词**，归为 **query**（基线设定，不是计算报表）
- 如果是"统计/计算/显示"某指标的数值，归为 **report** 或 **analyze**（按指标类型判断）
- 如果是"设置/添加/修改/删除"某配置，归为 **query**

## 用户输入
"{user_input}"

## 返回格式（JSON，仅返回 JSON，不要其他内容）
{{
  "intent": "query" | "report" | "analyze",
  "confidence": 0.0-1.0,
  "reason": "一句话说明理由"
}}"""


def _keyword_fallback(user_input: str) -> Literal["query", "analyze", "report"]:
    """关键词 fallback：仅在 LLM 不可用时使用。"""
    # 基线/预警操作词优先
    baseline_action = re.search(
        r"(设定|设置|添加|新增|修改|更新|删除|移除|取消).{0,20}(基线|预警|阈值|上限|下限|警戒)"
        r"|(基线|预警|阈值|上限|下限|警戒).{0,20}(设定|设置|添加|新增|修改|更新|删除|移除|取消)"
        r"|为.{0,30}(添加|设置).{0,20}(基线|预警|阈值|上限|下限)"
        r"|为.{0,30}(基线|预警|阈值|上限|下限)",
        user_input, re.IGNORECASE
    )
    if baseline_action:
        return "query"
    if _REPORT_KEYWORDS.search(user_input):
        return "report"
    if _ANALYSIS_KEYWORDS.search(user_input):
        return "analyze"
    return "query"


async def classify_agent_intent(user_input: str) -> Literal["query", "analyze", "report"]:
    """
    顶层意图分类 — LLM 优先，关键词 fallback。

    策略：
    1. 尝试调用 LLM，让其在 query/report/analyze 三类中做判断（带 CoT reason）
    2. LLM 置信度 >= 0.75 时采用 LLM 结果
    3. LLM 失败或置信度不足时，退化到关键词规则 fallback
    """
    # ── LLM 分类 ──
    try:
        import json as _json
        from app.agent.llm import get_llm

        llm = get_llm()
        prompt = _INTENT_CLASSIFY_PROMPT.format(user_input=user_input)
        resp = await llm.ainvoke(prompt)
        content = resp.content if hasattr(resp, "content") else str(resp)

        # 提取 JSON
        match = re.search(r"\{[^{}]+\}", content, re.DOTALL)
        if match:
            data = _json.loads(match.group())
            intent = data.get("intent", "").lower().strip()
            confidence = float(data.get("confidence", 0))
            reason = data.get("reason", "")

            if intent in ("query", "report", "analyze") and confidence >= 0.75:
                logger.info(
                    f"[supervisor] LLM classify → {intent} "
                    f"(conf={confidence:.2f}) reason={reason!r}"
                )
                return intent  # type: ignore[return-value]
            else:
                logger.info(
                    f"[supervisor] LLM low-conf ({confidence:.2f}) → fallback. "
                    f"raw={intent!r} reason={reason!r}"
                )
    except Exception as e:
        logger.warning(f"[supervisor] LLM classify failed: {e}, fallback to keyword rules")

    # ── 关键词 fallback ──
    result = _keyword_fallback(user_input)
    logger.info(f"[supervisor] keyword fallback → {result}")
    return result



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
    intent = await classify_agent_intent(user_input)
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
