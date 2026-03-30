"""
method_selector 节点

利用 LLM + 本体元数据自动识别用户意图，推荐合适的分析方法，
并构建 data_source_config 和 method_params。
"""

from __future__ import annotations

import json
import logging
import numbers
import re
from datetime import datetime, timedelta
from typing import Any, Dict

from app.agents.analysis_agent.state import AnalysisState
from app.analytics.registry import list_methods

logger = logging.getLogger(__name__)

# ── 关键词 → 方法名 快速映射（无需 LLM）──
_KEYWORD_MAP = {
    r"SPC|控制图|Cpk|Ppk|制程能力|control chart": "spc",
    r"相关性|相关系数|correlation|热力图": "correlation",
    r"ANOVA|方差分析|差异显著|t[-\s]?test|t检验|卡方|正态性": "hypothesis",
    r"帕累托|pareto|80/20|80%-20%": "pareto",
    r"回归|regression|线性分析|影响因素": "regression",
    r"预测|predict|forecast|分类|random forest|随机森林": "prediction",
    r"异常|anomaly|outlier|离群|孤立|3[σσ]|三倍标准差": "anomaly",
    r"描述性|分布|基础统计|均值|方差|直方图|descriptive": "descriptive",
    # ── 报表类（须在通用分析关键词之前匹配，防止被"预测"等截获） ──
    r"OEE|oee|综合效率|设备效率|可用率.*性能|availability.*performance": "oee_report",
    r"良率报表|良率分析|yield.*report|合格率报表|pass.*rate.*report|不良率.*报表|工站良率|站点良率": "yield_report",
    r"良率|yield rate|合格率|pass rate|不良率|ng.*rate|报表" : "yield_report",
}


def _quick_classify(user_input: str) -> str | None:
    """关键词快速分类，返回方法名或 None（须走 LLM）。"""
    for pattern, method in _KEYWORD_MAP.items():
        if re.search(pattern, user_input, re.IGNORECASE):
            return method
    return None


def _llm_classify(user_input: str) -> tuple[str, str, Dict[str, Any]]:
    """
    使用 LLM 从自然语言中提取分析意图。
    返回 (method_name, reason, params_hint)。
    """
    from app.agent.llm import get_llm

    available = [f"  - {m['name']}: {m['description']}" for m in list_methods()]
    methods_text = "\n".join(available)

    prompt = f"""你是一个数据分析专家，根据用户需求选择最合适的分析方法，并提取关键参数。

可用分析方法：
{methods_text}

用户需求："{user_input}"

请以 JSON 格式返回，示例：
{{
  "method": "spc",
  "reason": "用户提到控制图分析，SPC 最合适",
  "params": {{
    "value_column": "measurement_value",
    "usl": 10.5,
    "lsl": 9.5
  }}
}}

仅返回 JSON，不要其他内容。"""

    llm = get_llm()
    resp = llm.invoke(prompt)
    content = resp.content if hasattr(resp, "content") else str(resp)

    try:
        # 提取 JSON 块
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return (
                data.get("method", "descriptive"),
                data.get("reason", "LLM 推荐"),
                data.get("params", {}),
            )
    except Exception as e:
        logger.warning(f"[method_selector] LLM JSON parse error: {e}")

    return "descriptive", "默认使用描述性统计", {}


def method_selector_node(state: AnalysisState) -> dict:
    """
    节点：分析方法选择。

    输入: user_input
    输出: suggested_method, method_reason, method_params, data_source_config
    """
    user_input = state.get("user_input", "")
    logger.info(f"[method_selector] input={user_input[:80]}...")

    # 1. 尝试关键词快速分类
    method = _quick_classify(user_input)
    if method:
        reason = f"关键词匹配: '{method}'"
        params: Dict[str, Any] = {}
        logger.info(f"[method_selector] keyword match → {method}")
    else:
        # 2. 回退到 LLM
        try:
            method, reason, params = _llm_classify(user_input)
            logger.info(f"[method_selector] LLM suggest → {method}")
        except Exception as e:
            logger.error(f"[method_selector] LLM error: {e}")
            method, reason, params = "descriptive", "默认使用描述性统计", {}

    # 3. 构造 data_source_config（如果 state 中尚未有）
    data_source_config = state.get("data_source_config")
    if not data_source_config:
        if method == "yield_report":
            data_source_config = _build_yield_sql(user_input)
        elif method == "oee_report":
            data_source_config = _build_oee_sql(user_input)
        else:
            data_source_config = {
                "type": "data",
                "data": state.get("raw_data") or [],
            }

    # 4. 若方法需要 value_column 且尚未指定，从 raw_data 列名 + 用户输入关键词自动推断
    if method in ("spc", "correlation", "anomaly", "descriptive") and not params.get("value_column"):
        raw_data = state.get("raw_data") or []
        if raw_data and isinstance(raw_data[0], dict):
            cols = list(raw_data[0].keys())

            def _is_numeric(v: Any) -> bool:
                """判断值是否为数值（含数值字符串，如 varchar 存储的测量值）。"""
                if v is None:
                    return False
                if isinstance(v, numbers.Number) and not isinstance(v, bool):
                    return True
                if isinstance(v, str):
                    try:
                        float(v)
                        return True
                    except (ValueError, TypeError):
                        return False
                return False

            # 排除计数/编码类列
            _EXCLUDE = ("数量", "count", "个数", "编码", "编号", "_id", "code", "id")
            candidate_cols = [
                c for c in cols
                if _is_numeric(raw_data[0].get(c))
                and not any(exc in c.lower() for exc in _EXCLUDE)
            ]
            detected = None
            # 优先：从用户输入中提取量纲关键词（厚度、宽度、电阻等），匹配含该词且含"值/均"的列
            dim_match = re.search(
                r"(厚度|宽度|深度|高度|长度|电阻|张力|压力|温度|湿度|粗糙度|应力"
                r"|thickness|width|depth|height|resistance|pressure|temp)",
                user_input, re.IGNORECASE,
            )
            if dim_match:
                dim = dim_match.group(1)
                detected = next(
                    (c for c in candidate_cols
                     if dim in c and any(kw in c for kw in ("值", "均", "value", "avg", "mean"))),
                    None,
                ) or next((c for c in candidate_cols if dim in c), None)
            # 退回：第一个含 "值"/"均"/"value" 关键词的数值列
            if detected is None:
                _MEASURE_KEYWORDS = ("均值", "平均值", "测量值", "量测值", "value", "avg", "mean")
                detected = next(
                    (c for c in candidate_cols
                     if any(kw in c.lower() for kw in _MEASURE_KEYWORDS)),
                    None,
                )
            # 最后退回：第一个候选数值列
            if detected is None:
                detected = candidate_cols[0] if candidate_cols else None
            if detected:
                params = {**params, "value_column": detected}
                logger.info(f"[method_selector] auto-detected value_column='{detected}'")

    return {
        "suggested_method": method,
        "method_reason": reason,
        "method_params": params,
        "data_source_config": data_source_config,
    }


# ── SQL 模板构建器 ────────────────────────────────────────────────────────────

def _extract_date_range(user_input: str) -> tuple[str, str]:
    """
    从用户输入中提取日期范围。
    支持: 今天/昨天/本周/上周/本月/上月/最近N天 + 具体日期（YYYY-MM-DD）。
    默认: 最近 7 天。
    """
    today = datetime.now().date()

    # 具体日期范围
    date_range = re.search(r"(\d{4}-\d{2}-\d{2})\s*[到至~]\s*(\d{4}-\d{2}-\d{2})", user_input)
    if date_range:
        return date_range.group(1), date_range.group(2)

    single_date = re.search(r"(\d{4}-\d{2}-\d{2})", user_input)
    if single_date:
        d = single_date.group(1)
        return d, d

    if re.search(r"今天|today", user_input, re.IGNORECASE):
        return str(today), str(today)
    if re.search(r"昨天|yesterday", user_input, re.IGNORECASE):
        d = today - timedelta(days=1)
        return str(d), str(d)
    if re.search(r"本周|this\s*week", user_input, re.IGNORECASE):
        start = today - timedelta(days=today.weekday())
        return str(start), str(today)
    if re.search(r"上周|last\s*week", user_input, re.IGNORECASE):
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return str(start), str(end)
    if re.search(r"本月|this\s*month", user_input, re.IGNORECASE):
        start = today.replace(day=1)
        return str(start), str(today)
    if re.search(r"上月|last\s*month", user_input, re.IGNORECASE):
        first_of_this = today.replace(day=1)
        last_of_prev = first_of_this - timedelta(days=1)
        start = last_of_prev.replace(day=1)
        return str(start), str(last_of_prev)

    n_days_match = re.search(r"最近\s*(\d+)\s*天", user_input)
    if n_days_match:
        n = int(n_days_match.group(1))
        return str(today - timedelta(days=n - 1)), str(today)

    # 默认最近 7 天
    return str(today - timedelta(days=6)), str(today)


def _build_yield_sql(user_input: str) -> Dict[str, Any]:
    """构建良率报表数据查询 SQL。"""
    start_date, end_date = _extract_date_range(user_input)
    sql = f"""SELECT
    DATE(ci.gmt_create)                                                   AS report_date,
    ci.process_code,
    ci.process_name,
    ci.product_code,
    ci.lot_code,
    COALESCE(SUM(d.wafer_num), 0)                                         AS input_wafers,
    COUNT(DISTINCT CASE
        WHEN wdl.ng_code IS NOT NULL AND wdl.ng_code <> ''
        THEN wdl.wafer_id END)                                            AS ng_wafers
FROM matrix_routerx_operation_lot_batch_resume_log ci
LEFT JOIN matrix_routerx_operation_lot_batch_resume_log_detail d
       ON d.batch_resume_log_id = ci.id
LEFT JOIN matrix_routerx_operation_lot_batch_resume_wafer_detail_log wdl
       ON wdl.batch_resume_detail_log_id = d.id
WHERE ci.operation_type = 8
  AND (ci.deleted = 0 OR ci.deleted IS NULL)
  AND ci.gmt_create >= '{start_date} 00:00:00'
  AND ci.gmt_create <= '{end_date} 23:59:59'
GROUP BY DATE(ci.gmt_create), ci.process_code, ci.process_name,
         ci.product_code, ci.lot_code
ORDER BY report_date DESC, ci.process_code"""
    logger.info(f"[method_selector] yield_report SQL date range: {start_date} ~ {end_date}")
    return {"type": "sql", "sql": sql, "limit": 10000}


def _build_oee_sql(user_input: str) -> Dict[str, Any]:
    """构建 OEE 日报数据查询 SQL。"""
    start_date, end_date = _extract_date_range(user_input)
    sql = f"""SELECT
    e.operation_type,
    e.lot_code,
    e.process_code,
    e.process_name,
    e.product_code,
    JSON_UNQUOTE(JSON_EXTRACT(e.extra, '$.equipment_id'))   AS eqp_id,
    JSON_UNQUOTE(JSON_EXTRACT(e.extra, '$.equipment_name')) AS eqp_name,
    e.gmt_create                                            AS event_time,
    COALESCE(d.wafer_num, 0)                               AS wafer_num
FROM matrix_routerx_operation_lot_batch_resume_log e
LEFT JOIN matrix_routerx_operation_lot_batch_resume_log_detail d
       ON d.batch_resume_log_id = e.id
WHERE e.operation_type IN (8, 9)
  AND (e.deleted = 0 OR e.deleted IS NULL)
  AND e.gmt_create >= '{start_date} 00:00:00'
  AND e.gmt_create <= '{end_date} 23:59:59'
ORDER BY e.lot_code, e.process_code, e.gmt_create"""
    logger.info(f"[method_selector] oee_report SQL date range: {start_date} ~ {end_date}")
    return {"type": "sql", "sql": sql, "limit": 20000}
