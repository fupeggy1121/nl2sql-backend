"""
result_analyzer — 结果分析节点

分析查询结果的数据特征，推荐合适的图表类型。

优化策略:
  1. 先走规则引擎（0 LLM 调用，覆盖 90%+ 场景）
  2. 规则置信度不足时，fallback 到 LLM 推荐
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional

from app.agent.state import AgentState
from app.agent.trace import trace_step

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# 规则引擎
# ──────────────────────────────────────────────────────────
_TIME_COL_RE = re.compile(
    r"(date|time|day|month|year|week|dt|ts|timestamp|created|updated|_at)",
    re.IGNORECASE,
)
_NUMERIC_TYPES = (int, float)

_RATIO_KEYWORDS = re.compile(r"(率|占比|比例|比率|percent|ratio|rate)", re.IGNORECASE)
_BAR_KEYWORDS   = re.compile(r"(数量|总数|合计|统计|count|total|sum|avg|average)", re.IGNORECASE)
_PARETO_KEYWORDS = re.compile(r"(柏拉图|帕累托|pareto|不良|缺陷|异常|故障|返工)", re.IGNORECASE)


def _col_types(data: List[Dict[str, Any]]) -> Dict[str, str]:
    """粗略推断每列的类型：time / numeric / category"""
    if not data:
        return {}
    row = data[0]
    result: Dict[str, str] = {}
    for col, val in row.items():
        if _TIME_COL_RE.search(col):
            result[col] = "time"
        elif isinstance(val, _NUMERIC_TYPES):
            result[col] = "numeric"
        else:
            result[col] = "category"
    return result


def _rule_recommend_chart(
    data: List[Dict[str, Any]],
    sql: str,
    natural_language: str,
    query_type: str = "",
) -> Optional[Dict[str, Any]]:
    """
    规则引擎：根据结果集结构推断图表类型。
    优先使用 query_type（来自 intent_data），再按结构规则推断。
    返回 viz dict（confidence >= 0.75）或 None（需要 LLM fallback）。
    """
    if not data:
        return _make_viz("table", None, None, None, 0.9, "空数据集，使用表格")

    rows = len(data)
    col_types = _col_types(data)
    time_cols     = [c for c, t in col_types.items() if t == "time"]
    numeric_cols  = [c for c, t in col_types.items() if t == "numeric"]
    category_cols = [c for c, t in col_types.items() if t == "category"]
    total_cols    = len(col_types)

    qt = (query_type or "").upper()

    # ══ 优先级 0: 基于 query_type 的语义规则（最高优先级）══

    # LIST 查询 → 明细表格（无论列类型如何，明细列表应展示表格）
    if qt == "LIST":
        return _make_viz("table", None, None, None, 0.95, f"LIST 查询，展示明细表格 ({rows} 行)")

    # COUNT / AGGREGATE 且结果为单行单列数值 → 单值卡片
    if qt in ("COUNT", "AGGREGATE") and rows == 1 and total_cols == 1 and numeric_cols:
        col = numeric_cols[0]
        return _make_viz("card", None, col, None, 0.95, f"COUNT/单值聚合，使用单值卡片 ({col})")

    # COUNT 且结果为多行（分组统计）→ 柱状图
    if qt == "COUNT" and rows > 1 and category_cols and numeric_cols:
        cat_col = category_cols[0]
        num_col = numeric_cols[0]
        if _RATIO_KEYWORDS.search(natural_language):
            return _make_viz("pie", cat_col, num_col, None, 0.90, f"分组统计占比，使用饼图 ({cat_col})")
        return _make_viz("bar", cat_col, num_col, None, 0.90, f"分组统计，使用柱状图 ({cat_col} vs {num_col})")

    # TREND 查询 → 优先折线图（需有时间列）
    if qt == "TREND" and time_cols and numeric_cols:
        x = time_cols[0]
        y = numeric_cols[0]
        series = category_cols[0] if category_cols else None
        return _make_viz("line", x, y, series, 0.95, f"TREND 查询，使用折线图 ({x} vs {y})")

    # ══ 结构规则（无 query_type 或未命中语义规则时兜底）══

    # ── 规则 1: 单行单列数值 → 单值卡片
    if rows == 1 and total_cols == 1 and numeric_cols:
        col = numeric_cols[0]
        return _make_viz("card", None, col, None, 0.90, f"单行单列数值，使用单值卡片 ({col})")

    # ── 规则 1b: 单行多列 → 表格（KPI 横排）
    if rows == 1:
        return _make_viz("table", None, None, None, 0.85, "单行多列结果，使用表格/KPI展示")

    # ── 规则 2: 有时间列 + 数值列 → 折线图
    if time_cols and numeric_cols:
        x = time_cols[0]
        y = numeric_cols[0]
        series = category_cols[0] if category_cols else None
        return _make_viz("line", x, y, series, 0.88, f"时序数据 ({x} vs {y})，使用折线图")

    # ── 规则 3: 1 个分类列 + 1 个数值列，分类数 ≤ 8
    if len(category_cols) == 1 and len(numeric_cols) == 1:
        cat_col = category_cols[0]
        num_col = numeric_cols[0]
        if _PARETO_KEYWORDS.search(natural_language) and rows <= 30:
            return _make_viz("pareto", cat_col, num_col, None, 0.92,
                             f"不良/缺陷分析 ({cat_col})，使用柏拉图")
        distinct = len({row[cat_col] for row in data if cat_col in row})
        if distinct <= 8:
            # 占比/比率类 → 饼图；数量/合计类 → 柱状图
            if _RATIO_KEYWORDS.search(natural_language) or _RATIO_KEYWORDS.search(num_col):
                return _make_viz("pie", cat_col, num_col, None, 0.85, f"占比分布 ({cat_col})，使用饼图")
            return _make_viz("bar", cat_col, num_col, None, 0.82, f"分类对比 ({cat_col} vs {num_col})，使用柱状图")

    # ── 规则 3b: 2 个分类列 + 1 个数值列 → 分组柱状图（二维分组）
    if len(category_cols) >= 2 and len(numeric_cols) == 1:
        x_col = category_cols[0]
        series_col = category_cols[1]
        num_col = numeric_cols[0]
        return _make_viz("grouped_bar", x_col, num_col, series_col, 0.88,
                         f"两个分类维度 ({x_col} & {series_col})，使用分组柱状图")

    # ── 规则 4: 行数 > 20 且无时间列 → 先检查是否为明细数据
    if rows > 20 and not time_cols:
        # 如果分类列的唯一值 ≈ 行数（每行是独立记录），认为是明细数据 → 表格
        if category_cols:
            cat_col = category_cols[0]
            distinct = len({row[cat_col] for row in data if cat_col in row})
            if distinct > 15:
                return _make_viz("table", None, None, None, 0.80, f"数据量大且分类多 ({rows}行/{distinct}类)，使用表格")
        else:
            # 无分类列（全数值列）的大数据集 → 也用表格（明细列表）
            return _make_viz("table", None, None, None, 0.80, f"数据量大 ({rows}行)，无分类列，使用表格")

    # ── 规则 5: 多个数值列 + 分类列 → 柱状图
    if len(numeric_cols) >= 2 and category_cols:
        x = category_cols[0]
        y = numeric_cols[0]
        return _make_viz("bar", x, y, None, 0.78, f"多指标对比，使用柱状图")

    # ── 规则 6: 多行全数值列（如明细列表，status/id 均为 int）→ 表格
    if rows > 1 and numeric_cols and not category_cols and not time_cols:
        return _make_viz("table", None, None, None, 0.80, f"全数值列明细 ({rows}行/{total_cols}列)，使用表格")

    # ── 规则未覆盖 → 交给 LLM
    return None


def _make_viz(
    chart_type: str,
    x: Optional[str],
    y: Optional[str],
    series: Optional[str],
    confidence: float,
    reason: str,
) -> Dict[str, Any]:
    return {
        "type": chart_type,
        "title": "",
        "xAxisField": x,
        "yAxisField": y,
        "seriesField": series,
        "confidence": confidence,
        "reason": reason,
        "_source": "rule",
    }


# ──────────────────────────────────────────────────────────
# 节点主函数
# ──────────────────────────────────────────────────────────
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
                "_source": "rule",
            },
        }

    data = query_result.get("data", [])

    # ── 优先走规则引擎 ──
    query_type = intent_data.get("query_type", "")
    viz = _rule_recommend_chart(data, sql, user_input, query_type)
    source = "rule"

    if viz is None:
        # 规则无法覆盖，fallback 到 LLM
        logger.info("[result_analyzer] Rule engine undecided, falling back to LLM")
        try:
            from app.agent.tools.chart_tools import recommend_chart
            viz = recommend_chart.invoke({
                "sql": sql,
                "data": data,
                "natural_language": user_input,
                "intent_type": intent_data.get("intent", ""),
            })
            source = "llm"
        except Exception as e:
            logger.error(f"[result_analyzer] LLM fallback failed: {e}")
            viz = _make_viz("table", None, None, None, 0.5, f"Fallback error: {e}")

    chart_type = viz.get("type", "table")
    logger.info(
        f"[result_analyzer] Recommended: {chart_type} "
        f"(conf={viz.get('confidence', 0):.2f}, source={source})"
    )

    # ── Pipeline Trace ──
    trace = list(state.get("pipeline_trace", []))
    trace_step(trace, "result_analyzer", _t0, summary=(
        f"推荐图表: {chart_type} [{source}], 置信度: {viz.get('confidence', 0):.2f}"
    ), detail={
        "chart_type": chart_type,
        "x_axis": viz.get("xAxisField"),
        "y_axis": viz.get("yAxisField"),
        "confidence": viz.get("confidence", 0),
        "reason": viz.get("reason", ""),
        "source": source,
    })

    return {
        "chart_type": chart_type,
        "visualization": viz,
        "pipeline_trace": trace,
    }
