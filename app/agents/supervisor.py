"""
Supervisor — Multi-Agent 顶层路由器

职责：
1. 对用户输入进行意图预分类
2. 路由到对应的子 Agent（query / analyze / report）
3. 统一响应格式返回

Phase 0: 仅支持 query 和 analyze 路由，analyze 暂返回提示。
现有 Query Agent 逻辑零改动，通过 import 委托调用。
"""

import asyncio
import json
import logging
import re
import time
from typing import Dict, Any, List, Literal

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

# ── 基线/写操作检测（无需 LLM，直接走 adhoc）──────────────────────────────────
_BASELINE_ACTION = re.compile(
    r"(设定|设置|添加|新增|修改|更新|删除|移除|取消).{0,20}(基线|预警|阈值|上限|下限|警戒)"
    r"|(基线|预警|阈值|上限|下限|警戒).{0,20}(设定|设置|添加|新增|修改|更新|删除|移除|取消)"
    r"|为.{0,30}(添加|设置).{0,20}(基线|预警|阈值|上限|下限)"
    r"|为.{0,30}(基线|预警|阈值|上限|下限)",
    re.IGNORECASE,
)

# ── 统计分析关键词（高置信度快速路径，无需 LLM）──────────────────────────────
_ANALYSIS_KEYWORDS = re.compile(
    r"SPC|控制图|Cpk|Ppk|相关性分析|回归分析|预测模型|异常检测|帕累托|"
    r"良率分析|趋势分析|方差分析|ANOVA|假设检验|t[\-\s]?test|卡方检验|"
    r"统计分析|数据分析|描述性统计|分布分析|散点图分析|热力图",
    re.IGNORECASE,
)

# ── 路由提示词：注入完整 skill 列表，让 LLM 做有依据的路由决策 ──────────────
_ROUTE_PROMPT = """\
你是一个半导体制造 MES 系统的路由决策器。根据用户问题，判断应走哪条处理路径。

## 可用指标 Skill（有预定义方法论，精确计算）
{skills_text}

## 统计分析方法（探索性数据分析）
{analysis_methods_text}

## 判断规则
1. 用户问题**明确提到 2 个或以上** skill 别名 → multi_skill（携带 skill_names 数组）
2. 用户问题**明确提到 1 个** skill 别名 → skill（携带 skill_name）
3. 需要统计分析（SPC/相关性/回归/预测/异常检测）→ analysis（携带 method）
4. 涉及 MES 业务数据但无预定义 skill（设备数量/批次号/载具/库存等普通查询）→ adhoc
5. 与 MES 系统无关 → out_of_scope

## 注意
- 规则1/2**优先级最高**：查询中出现 skill 别名直接走 skill 或 multi_skill，不受其他规则影响
- "趋势"、"对比"、"统计"、"按站点统计" 等词本身不足以改变路由，最终取决于是否提到了 skill 别名
- 普通计数句式（如"各工站有**多少个批次**在加工"、"有多少台设备"）→ adhoc（这类句式没有出现 skill 别名）
- 基线/预警/阈值的"设置/添加/删除"操作 → adhoc（不是指标查询）
- 英文查询适用同等规则

## 用户问题
"{user_input}"

## 返回格式（JSON，仅返回 JSON，不要其他内容）

单指标：
{{
  "path": "skill",
  "skill_name": "first_pass_yield",
  "reason": "用户查询一次良率，匹配 first_pass_yield skill"
}}

多指标对比：
{{
  "path": "multi_skill",
  "skill_names": ["rework_rate", "first_pass_yield"],
  "reason": "用户要求对比返工率和良率，匹配两个 skill"
}}"""


def _route_fallback(user_input: str) -> Dict[str, Any]:
    """LLM 不可用时的关键词兼底路由，直接查 skill zh_names 列表。"""
    if _BASELINE_ACTION.search(user_input):
        return {"route": "adhoc", "reason": "baseline config operation"}
    if _ANALYSIS_KEYWORDS.search(user_input):
        return {"route": "analyze", "reason": "statistical analysis keywords"}
    try:
        from app.skills.loader import get_skill_loader
        loader = get_skill_loader()
        matched_skills: List[str] = []
        for skill in loader.list_skills():
            for zh in skill.zh_names:
                if zh and zh in user_input:
                    if skill.skill_name not in matched_skills:
                        matched_skills.append(skill.skill_name)
                    break
        if len(matched_skills) >= 2:
            return {"route": "multi_skill", "skill_names": matched_skills, "reason": f"keyword fallback: {matched_skills}"}
        if len(matched_skills) == 1:
            return {"route": "skill", "skill_name": matched_skills[0], "reason": f"keyword fallback: {matched_skills[0]}"}
    except Exception:
        pass
    return {"route": "adhoc", "reason": "default fallback"}


async def route_request(user_input: str) -> Dict[str, Any]:
    """
    统一路由决策 — 一次 LLM 调用，注入完整 skill 列表。

    返回: {"route": "skill"/"adhoc"/"analyze", "skill_name"?: str, "method"?: str, "reason": str}

    设计哲学：
    - 路由质量取决于 skill 描述写得好不好，而不是关键词词表覆盖得全不全
    - 新增 skill 只需在 skills/metrics/ 添加 .md 文件，无需改任何路由代码
    - 两个 if 分支守卫全部消除，无人工仲裁
    """
    # ── 快速路径 1：写操作/基线配置 → adhoc（无需 LLM）──
    if _BASELINE_ACTION.search(user_input):
        logger.info("[supervisor] baseline/write operation → adhoc (fast path)")
        return {"route": "adhoc", "reason": "baseline/write operation detected"}

    # ── 快速路径 2：统计分析关键词 → analyze（无需 LLM）──
    if _ANALYSIS_KEYWORDS.search(user_input):
        logger.info("[supervisor] statistical analysis keywords → analyze (fast path)")
        return {"route": "analyze", "reason": "statistical analysis keywords detected"}

    # ── LLM 路由（携带完整 skill 列表）──
    try:
        from app.agent.llm import get_llm
        from app.skills.loader import get_skill_loader
        from app.analytics.registry import list_methods

        loader = get_skill_loader()
        # 注入所有 zh_names（不截断），给 LLM 完整的同义词覆盖
        skills_text = "\n".join(
            f"  - {s.skill_name}: {', '.join(s.zh_names)}"
            for s in loader.list_skills()
        )
        analysis_methods_text = "\n".join(
            f"  - {m['name']}: {m['description']}" for m in list_methods()
            if m["name"] not in ("metric_compute", "yield_report", "oee_report")
        )

        prompt = _ROUTE_PROMPT.format(
            skills_text=skills_text,
            analysis_methods_text=analysis_methods_text,
            user_input=user_input,
        )

        llm = get_llm()
        resp = await llm.ainvoke(prompt)
        content = resp.content if hasattr(resp, "content") else str(resp)

        match = re.search(r"\{.*?\}", content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            path = data.get("path", "adhoc")

            # ── multi_skill 路径 ──
            if path == "multi_skill":
                skill_names = data.get("skill_names") or []
                # 至少需要 2 个有效 skill；否则降级为单 skill 或 adhoc
                if len(skill_names) >= 2:
                    result = {
                        "route": "multi_skill",
                        "skill_names": skill_names,
                        "reason": data.get("reason", "LLM multi_skill route"),
                    }
                    logger.info(
                        f"[supervisor] LLM route → multi_skill"
                        f" skills={skill_names!r}  reason={result['reason']!r}"
                    )
                    return result
                elif len(skill_names) == 1:
                    path = "skill"
                    data["skill_name"] = skill_names[0]
                else:
                    path = "adhoc"

            if path not in ("skill", "adhoc", "analysis", "out_of_scope"):
                path = "adhoc"
            route = (
                "skill"   if path == "skill"     else
                "analyze" if path == "analysis"  else
                "adhoc"
            )
            result = {
                "route": route,
                "skill_name": data.get("skill_name"),
                "method": data.get("method"),
                "reason": data.get("reason", "LLM route"),
            }
            logger.info(
                f"[supervisor] LLM route → {route}"
                + (f" skill={result['skill_name']!r}" if route == "skill" else "")
                + f"  reason={result['reason']!r}"
            )
            return result
    except Exception as e:
        logger.warning(f"[supervisor] route_request LLM failed: {e}, falling back to keyword route")

    # ── 关键词兜底 ──
    result = _route_fallback(user_input)
    logger.info(f"[supervisor] keyword fallback → {result['route']}")
    return result



async def route_to_agent(
    user_input: str,
    session_id: str,
    conversation_history: list | None = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Supervisor 主入口 — 路由到子 Agent。

    返回格式与现有 chat 端点一致：
    {
        "response": {...},
        "is_followup": bool,
        "session_id": str,
        ...AgentState fields
    }
    """
    result = await route_request(user_input)
    route = result.get("route", "adhoc")
    skill_name = result.get("skill_name")
    skill_names = result.get("skill_names", [])
    logger.info(
        f"[supervisor] route={route}"
        + (f", skill={skill_name}" if skill_name else "")
        + (f", skills={skill_names}" if skill_names else "")
        + f", input={user_input[:60]}..."
    )

    if route == "multi_skill":
        return await _run_multi_skill_agent(
            user_input, session_id, conversation_history,
            skill_names=skill_names, **kwargs
        )
    elif route == "skill":
        return await _run_analysis_agent(
            user_input, session_id, conversation_history,
            pre_selected_skill=skill_name, **kwargs
        )
    elif route == "analyze":
        return await _run_analysis_with_data_pipeline(
            user_input, session_id, conversation_history, **kwargs
        )
    else:  # "adhoc"
        return await _run_query_agent(
            user_input, session_id, conversation_history, **kwargs
        )


async def _run_multi_skill_agent(
    user_input: str,
    session_id: str,
    conversation_history: list | None = None,
    skill_names: List[str] | None = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    并行执行多个 skill，将结果合并为一个对比分析回复。
    """
    skill_names = skill_names or []
    logger.info(f"[supervisor] → multi_skill_agent: {skill_names!r} for: {user_input[:60]}...")

    tasks = [
        _run_analysis_agent(
            user_input, session_id, conversation_history,
            pre_selected_skill=s, **kwargs
        )
        for s in skill_names
    ]
    results: List[Dict[str, Any]] = await asyncio.gather(*tasks, return_exceptions=True)

    # 过滤出成功的结果和失败结果
    ok_results = [r for r in results if isinstance(r, dict)]
    failed = [str(r) for r in results if isinstance(r, Exception)]
    if failed:
        logger.warning(f"[supervisor] multi_skill: {len(failed)} sub-skill(s) failed: {failed}")

    if not ok_results:
        return {
            "response": {"success": False, "answer": "多指标并行执行全部失败"},
            "is_followup": False,
            "session_id": session_id,
            "pipeline_trace": [],
        }

    return _merge_multi_skill_results(ok_results, skill_names, user_input, session_id)


def _merge_multi_skill_results(
    results: List[Dict[str, Any]],
    skill_names: List[str],
    user_input: str,
    session_id: str,
) -> Dict[str, Any]:
    """
    将多个 skill 的单独响应合并成一个结构化回复。

    answer: 拼接每个 skill 的答复，中间用策划线分隔
    charts: 合并删除重复（按 title 去重）
    analysis: 将各 skill 的 analysis 字段展开至以 skill_name 为键的字典中
    pipeline_trace: 各 skill trace 合并在一起，末尾追加 multi_skill_merge step
    """
    from app.agent.trace import trace_step

    _t0 = time.perf_counter()
    answers: List[str] = []
    all_charts: List[Dict] = []
    seen_chart_titles: set = set()
    merged_analysis: Dict[str, Any] = {}
    merged_trace: List[Dict] = []

    for i, (name, r) in enumerate(zip(skill_names, results)):
        resp = r.get("response", {})

        # answer
        answer_text = resp.get("answer", "")
        if answer_text:
            answers.append(f"### {name}\n{answer_text}")

        # charts
        for chart in resp.get("charts") or []:
            title = chart.get("title", f"chart_{i}")
            if title not in seen_chart_titles:
                seen_chart_titles.add(title)
                all_charts.append(chart)

        # analysis
        analysis = resp.get("analysis")
        if analysis:
            merged_analysis[name] = analysis

        # trace
        merged_trace.extend(r.get("pipeline_trace") or [])

    combined_answer = "\n\n---\n\n".join(answers)

    # 写入 multi_skill_merge trace step（供测试脚本检测路由类型）
    trace_step(
        merged_trace, "multi_skill_merge", _t0,
        summary=f"合并 {len(skill_names)} 个 skill 结果：{skill_names}",
        detail={
            "skill_names": skill_names,
            "skills_success": len(results),
            "total_charts": len(all_charts),
            "answer_len": len(combined_answer),
        },
    )

    response: Dict[str, Any] = {
        "success": True,
        "answer": combined_answer,
        "analysis": merged_analysis if merged_analysis else None,
        "charts": all_charts,
    }

    return {
        "response": response,
        "is_followup": False,
        "session_id": session_id,
        "pipeline_trace": merged_trace,
    }


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
    pre_selected_skill: str | None = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    良率 / OEE / WIP 报表路由：analysis_agent 直接走（method_selector 内有专属 SQL builder）。

    pre_selected_skill: 由 supervisor route_request() 预先确定的 skill 名称；
                        传入后 method_selector 跳过自身的 LLM 路由调用，减少一次 LLM RTT。
    """
    from app.agents.analysis_agent.graph import get_analysis_agent_app

    logger.info(
        f"[supervisor] → analysis_agent: {user_input[:60]}..."
        + (f"  pre_skill={pre_selected_skill!r}" if pre_selected_skill else "")
    )

    initial_state = {
        "user_input": user_input,
        "session_id": session_id,
    }
    if pre_selected_skill:
        initial_state["pre_selected_skill"] = pre_selected_skill

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
