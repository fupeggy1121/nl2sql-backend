"""
analysis_executor 节点

调用 AnalysisEngine 执行选定的分析方法。

metric_compute 路径使用 LLM 动态工具分发：
  1. 从 state 取 skill_context（含 compute_tool 提示 + body 方法论）
  2. 构建提示，列出 ToolRegistry 中所有工具的描述
  3. LLM 选择工具名 + group_by 参数（JSON 响应）
  4. 从 ComputeToolRegistry 查找工具并执行
  5. 降级策略: LLM 失败 → 用 skill.compute_tool 直接分发 → 用 metric_name 分发
"""

from __future__ import annotations

import inspect
import io
import json
import logging
import re
from typing import Any, Dict, List, Optional

import pandas as pd

from app.agents.analysis_agent.state import AnalysisState
from app.analytics.engine import AnalysisEngine
from app.analytics.metrics.base import MetricResult
from app.analytics.models import AnalysisResult
import app.analytics.methods  # noqa: F401 — 触发方法注册

logger = logging.getLogger(__name__)


# ── LLM 工具选择 ──────────────────────────────────────────────────────────────

_TOOL_SELECTION_SYSTEM = (
    "你是一个数据分析工具协调器。"
    "根据用户问题、指标说明和 DataFrame 的列名，选择最合适的计算工具，并确定分组维度。\n"
    "只返回 JSON，不要解释。格式:\n"
    '{"tool": "<tool_name>", "group_by": ["col1", "col2"], "reason": "<一句话理由>"}\n'
    "group_by 应来自 DataFrame 列中有业务意义的维度列（如 process_code / report_date / product_code）。"
    "如果不需要分组或无法确定，group_by 传 null。"
)


def _llm_select_tool(
    user_input: str,
    skill_context: Dict[str, Any],
    df_columns: List[str],
    tools_desc: str,
) -> Optional[Dict[str, Any]]:
    """
    调用 LLM 动态选择 compute tool + group_by。
    返回 {"tool": str, "group_by": list|None, "reason": str} 或 None（失败时）。
    """
    try:
        from app.services.llm_provider import get_llm_provider
        provider = get_llm_provider()

        skill_name = skill_context.get("skill_name", "")
        skill_def  = skill_context.get("standard_definition", "")
        skill_body = (skill_context.get("body") or "")[:800]   # 截断避免超 token

        prompt = (
            f"用户问题: {user_input}\n\n"
            f"指标: {skill_name}\n"
            f"定义: {skill_def}\n"
            f"方法论摘要:\n{skill_body}\n\n"
            f"DataFrame 列: {df_columns}\n\n"
            f"{tools_desc}\n\n"
            "请选择最合适的工具并给出 group_by 维度。返回 JSON："
        )
        raw = provider.generate(prompt, system_prompt=_TOOL_SELECTION_SYSTEM)
        # 提取 JSON（LLM 可能带代码块）
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            logger.warning(f"[analysis_executor] LLM tool selection: no JSON found in: {raw[:200]}")
            return None
        result = json.loads(m.group())
        tool_name = result.get("tool", "")
        if not tool_name:
            return None
        logger.info(f"[analysis_executor] LLM selected tool={tool_name}, reason={result.get('reason', '')}")
        return result
    except Exception as e:
        logger.warning(f"[analysis_executor] LLM tool selection failed: {e}")
        return None


def _run_compute_tool(tool_name: str, df: pd.DataFrame, group_by: Optional[List[str]]) -> Optional[MetricResult]:
    """Execute a named compute tool. Returns None if not found."""
    from app.analytics.tool_registry import get_compute_tool
    spec = get_compute_tool(tool_name)
    if spec is None:
        logger.warning(f"[analysis_executor] compute tool '{tool_name}' not found in registry")
        return None
    return spec.call(df, group_by=group_by)


def _metric_result_to_analysis_result(
    result: MetricResult,
    metric_name: str,
    group_by: Optional[List[str]],
    tool_name: str,
    llm_reason: str,
) -> AnalysisResult:
    """Convert MetricResult → AnalysisResult, including source code extraction."""
    try:
        from app.analytics.tool_registry import get_compute_tool
        spec = get_compute_tool(tool_name)
        computer = spec.computer if spec else None

        if computer:
            method_src = inspect.getsource(type(computer).compute)
            module = inspect.getmodule(type(computer))
            import_lines: list = []
            if module:
                try:
                    module_src = inspect.getsource(module)
                    import_lines = [
                        line for line in module_src.splitlines()
                        if (line.startswith("import ") or line.startswith("from "))
                        and not line.startswith("from __future__")
                    ]
                except Exception:
                    pass
            imports_block = "\n".join(import_lines) or "# (import 提取失败)"
            header = (
                f"# metric: {metric_name}  tool: {tool_name}\n"
                f"# group_by: {group_by or '自动推断'}\n"
                f"# LLM 选择理由: {llm_reason}\n\n"
                f"# --- imports ---\n{imports_block}\n\n"
                f"# --- compute() ---\n"
            )
            python_script = header + method_src
        else:
            python_script = None
    except Exception:
        python_script = None

    data = {
        "metric_name": result.metric_name,
        "value": result.value,
        "detail": result.detail,
    }
    if python_script:
        data["python_script"] = python_script

    return AnalysisResult(
        success=result.success,
        method="metric_compute",
        summary=result.summary,
        data=data,
        charts=result.charts,
        metadata={
            **result.metadata,
            "compute_mode": "python_compute",
            "metric_name": metric_name,
            "tool_name": tool_name,
            "llm_tool_reason": llm_reason,
            "python_script": python_script,
        },
        error=result.error,
    )


# ── 节点主函数 ─────────────────────────────────────────────────────────────────

def analysis_executor_node(state: AnalysisState) -> dict:
    """
    节点：分析执行。

    输入: dataframe_json, suggested_method, method_params, skill_context, user_input
    输出: analysis_success, analysis_summary, analysis_data, analysis_charts, analysis_error
    """
    method = state.get("suggested_method", "descriptive")
    params = state.get("method_params") or {}

    # metric_compute 需要原始数据（NULL 有业务含义，不能被预处理器 drop 掉）
    if method == "metric_compute":
        df_json = state.get("raw_dataframe_json") or state.get("dataframe_json", "{}")
    else:
        df_json = state.get("dataframe_json", "{}")

    if not df_json or df_json == "{}":
        return {
            "analysis_success": False,
            "analysis_summary": "",
            "analysis_data": {},
            "analysis_charts": [],
            "analysis_error": "数据为空，无法执行分析",
        }

    try:
        df = pd.read_json(io.StringIO(df_json), orient="records", convert_dates=False)
    except Exception as e:
        return {
            "analysis_success": False,
            "analysis_summary": "",
            "analysis_data": {},
            "analysis_charts": [],
            "analysis_error": f"DataFrame 反序列化失败: {e}",
        }

    logger.info(f"[analysis_executor] method={method}, shape={df.shape}")

    # ── metric_compute: LLM 动态工具分发 ──────────────────────────────────────
    if method == "metric_compute":
        from app.analytics.tool_registry import describe_all_tools, get_compute_tool

        skill_context: Dict[str, Any] = state.get("skill_context") or {}
        user_input: str = state.get("user_input") or ""
        metric_name: str = params.get("metric_name", "")
        df_columns: List[str] = list(df.columns)
        tools_desc = describe_all_tools()

        # ── 第一层: LLM 动态选择 ──
        llm_result = _llm_select_tool(user_input, skill_context, df_columns, tools_desc)
        llm_reason = ""
        metric_result: Optional[MetricResult] = None
        chosen_tool = ""

        if llm_result:
            chosen_tool = llm_result.get("tool", "")
            group_by    = llm_result.get("group_by") or None
            llm_reason  = llm_result.get("reason", "LLM 选择")
            metric_result = _run_compute_tool(chosen_tool, df, group_by)

        # ── 第二层降级: skill.compute_tool ──
        if metric_result is None:
            fallback_tool = skill_context.get("compute_tool", "")
            if fallback_tool:
                logger.info(f"[analysis_executor] LLM fallback → skill.compute_tool={fallback_tool}")
                chosen_tool = fallback_tool
                llm_reason  = "skill.compute_tool 降级"
                metric_result = _run_compute_tool(fallback_tool, df, group_by=None)

        # ── 第三层降级: registry metric_name ──
        if metric_result is None and metric_name:
            from app.analytics.registry import get_metric
            computer = get_metric(metric_name)
            if computer:
                logger.info(f"[analysis_executor] final fallback → metric_registry[{metric_name}]")
                chosen_tool = metric_name
                llm_reason  = "metric_registry 兜底"
                metric_result = computer.compute(df, group_by=None)

        if metric_result is None:
            return {
                "analysis_success": False,
                "analysis_summary": "",
                "analysis_data": {},
                "analysis_charts": [],
                "analysis_error": f"无法找到指标 '{metric_name}' 的计算工具",
            }

        result = _metric_result_to_analysis_result(
            metric_result, metric_name, llm_result.get("group_by") if llm_result else None,
            chosen_tool, llm_reason,
        )

    # ── 其他方法: 走原有 AnalysisEngine ──────────────────────────────────────
    else:
        result = AnalysisEngine.run(method, df, params)

    # 合并 metadata 中的附加字段（如 python_script）进入 analysis_data 顶层
    data = result.data or {}
    meta = result.metadata or {}
    if meta.get("python_script"):
        data = {**data, "python_script": meta["python_script"]}

    return {
        "analysis_success": result.success,
        "analysis_summary": result.summary or "",
        "analysis_data": data,
        "analysis_charts": result.charts or [],
        "analysis_error": result.error,
    }

