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


def _skill_driven_classify(user_input: str):
    """
    技能驱动路由：通过 SkillLoader 将用户输入匹配到 compute_mode=python_compute 的技能。
    技能 .md 文件是业务定义和 raw_sql_template 的**单一来源**。

    Returns: (SkillDefinition, MetricComputer) or (None, None)
    """
    try:
        from app.skills.loader import get_skill_loader
        from app.analytics.registry import get_metric

        loader = get_skill_loader()
        skill = loader.find_by_zh_name(user_input)
        if skill and skill.compute_mode == "python_compute":
            computer = get_metric(skill.skill_name)
            if computer:
                logger.info(f"[method_selector] skill match: '{skill.skill_name}' via SkillLoader")
                return skill, computer
            else:
                logger.warning(
                    f"[method_selector] skill '{skill.skill_name}' has compute_mode=python_compute "
                    f"but no MetricComputer registered — check @register_metric decorator"
                )
    except Exception as e:
        logger.warning(f"[method_selector] SkillLoader error: {e}")

    return None, None


def method_selector_node(state: AnalysisState) -> dict:
    """
    节点：分析方法选择。

    路由优先级（由高到低）：
      1. SkillLoader 技能匹配 → python_compute 指标，SQL 来自 skill.md（单一来源）
      2. 关键词快速分类 → 非指标计算方法（SPC / OEE / yield_report 聚合视图等）
      3. LLM 分类 → 通用兜底

    输入: user_input
    输出: suggested_method, method_reason, method_params, data_source_config, skill_context
    """
    user_input = state.get("user_input", "")
    logger.info(f"[method_selector] input={user_input[:80]}...")

    data_source_config = state.get("data_source_config")
    skill_context: Dict[str, Any] | None = None
    params: Dict[str, Any] = {}
    method = ""
    reason = ""

    # ── 1. 技能驱动路由（优先）: SkillLoader 匹配 python_compute 技能 ──
    if not data_source_config:
        skill, computer = _skill_driven_classify(user_input)
        if skill and computer:
            method = "metric_compute"
            reason = f"技能匹配: '{skill.skill_name}' — {skill.standard_definition}"
            logger.info(f"[method_selector] skill-driven → metric_compute ({skill.skill_name})")

            # 提取时间范围 + 工站过滤
            start_date, end_date = _extract_date_range(user_input)
            station_clause = _extract_station_filter(user_input, alias="log")
            date_filter = (
                f"log.gmt_create >= '{start_date} 00:00:00' "
                f"AND log.gmt_create <= '{end_date} 23:59:59'"
            )

            # SQL 来自 skill.md（单一来源）
            where_parts = [f"AND {date_filter}"]
            sc = station_clause.replace("\n  AND ", "").strip() if station_clause else ""
            if sc:
                where_parts.append(f"AND {sc}")
            where_extra = "\n  ".join(where_parts)
            raw_sql = skill.raw_sql_template.format(WHERE_EXTRA=where_extra, LIMIT=100000)

            data_source_config = {"type": "sql", "sql": raw_sql, "limit": 100000}
            params = {"metric_name": skill.skill_name}

            # 技能业务上下文（供下游节点 / LLM 响应使用）
            skill_context = {
                "skill_name": skill.skill_name,
                "standard_definition": skill.standard_definition,
                "formula": skill.formula,
                "granularity": skill.granularity,
                "body": skill.body,
            }

    # ── 2. 关键词 + LLM 分类（技能未匹配时）──
    if not method:
        method = _quick_classify(user_input)
        if method:
            reason = f"关键词匹配: '{method}'"
            logger.info(f"[method_selector] keyword match → {method}")
        else:
            try:
                method, reason, params = _llm_classify(user_input)
                logger.info(f"[method_selector] LLM suggest → {method}")
            except Exception as e:
                logger.error(f"[method_selector] LLM error: {e}")
                method, reason, params = "descriptive", "默认使用描述性统计", {}

    # ── 3. yield_report → python_compute 兜底（SkillLoader 未覆盖的指标）──
    if method == "yield_report" and not data_source_config:
        _metric_name, _computer, _metric_def = _detect_python_compute_metric(user_input)
        if _metric_name and _computer:
            logger.info(f"[method_selector] ontology fallback: python_compute '{_metric_name}'")
            method = "metric_compute"
            reason = f"指标 '{_metric_name}' 使用 Python 计算模式（本体兜底）"
            start_date, end_date = _extract_date_range(user_input)
            station_clause = _extract_station_filter(user_input, alias="log")
            date_filter = (
                f"log.gmt_create >= '{start_date} 00:00:00' "
                f"AND log.gmt_create <= '{end_date} 23:59:59'"
            )

            raw_sql_template = _metric_def.raw_sql_template if _metric_def else None
            if raw_sql_template:
                where_parts = [f"AND {date_filter}"]
                sc = station_clause.replace("\n  AND ", "").strip() if station_clause else ""
                if sc:
                    where_parts.append(f"AND {sc}")
                where_extra = "\n  ".join(where_parts)
                raw_sql = raw_sql_template.format(WHERE_EXTRA=where_extra, LIMIT=100000)
                logger.info(f"[method_selector] SQL from ontology raw_sql_template for '{_metric_name}'")
            else:
                logger.warning(
                    f"[method_selector] '{_metric_name}' has no raw_sql_template in ontology or skill.md"
                )
                raw_sql = ""

            data_source_config = {"type": "sql", "sql": raw_sql, "limit": 100000}
            params = {**params, "metric_name": _metric_name}

    # ── 4. 其余 data_source_config 构建 ──
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
        "skill_context": skill_context,
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

    # 「最近一周」/「过去一周」等文字形式
    if re.search(r"最近一周|过去一周|最近七天|过去七天", user_input, re.IGNORECASE):
        return str(today - timedelta(days=6)), str(today)

    # 「最近一个月」 /「过去一个月」/「最近一月」等文字形式
    if re.search(r"最近一个月|过去一个月|最近一月|过去一月", user_input, re.IGNORECASE):
        return str(today - timedelta(days=29)), str(today)

    # 「最近三个月」/「最近半年」/「最近一年」
    if re.search(r"最近三个月|过去三个月|最近三月", user_input, re.IGNORECASE):
        return str(today - timedelta(days=89)), str(today)
    if re.search(r"最近半年|过去半年", user_input, re.IGNORECASE):
        return str(today - timedelta(days=179)), str(today)
    if re.search(r"最近一年|过去一年", user_input, re.IGNORECASE):
        return str(today - timedelta(days=364)), str(today)

    n_days_match = re.search(r"最近\s*(\d+)\s*天", user_input)
    if n_days_match:
        n = int(n_days_match.group(1))
        return str(today - timedelta(days=n - 1)), str(today)

    # 「最近N周」或「最近N个月」（数字形式）
    n_weeks_match = re.search(r"最近\s*(\d+)\s*周", user_input)
    if n_weeks_match:
        n = int(n_weeks_match.group(1))
        return str(today - timedelta(days=n * 7 - 1)), str(today)

    n_months_match = re.search(r"最近\s*(\d+)\s*个?月", user_input)
    if n_months_match:
        n = int(n_months_match.group(1))
        return str(today - timedelta(days=n * 30 - 1)), str(today)

    # 默认最近 7 天
    return str(today - timedelta(days=6)), str(today)


def _build_yield_sql(user_input: str) -> Dict[str, Any]:
    """
    构建良率报表数据查询 SQL。
    当用户询问「一次良率/FPY」或「综合良率/最终良率」时，
    优先使用 mapping_prod.json 中预构建的 CTE 模板，获得更准确的良率数据。
    否则退回旧的 CheckIn 聚合 SQL（input_wafers/ng_wafers 格式）。
    """
    start_date, end_date = _extract_date_range(user_input)

    # ── 判断是否需要使用新 CTE 模板 ──
    wants_fpy = bool(re.search(r"一次良率|首次合格率|直通率|FPY|first.pass", user_input, re.IGNORECASE))
    wants_final = bool(re.search(r"综合良率|最终良率|累计良率", user_input, re.IGNORECASE))
    use_dual_template = wants_fpy or wants_final or re.search(r"良率趋势|yield.*trend|trend.*yield", user_input, re.IGNORECASE)

    if use_dual_template:
        try:
            _sql = _build_dual_yield_cte_sql(user_input, start_date, end_date, wants_fpy, wants_final)
            logger.info(f"[method_selector] yield_report 使用 CTE 模板: fpy={wants_fpy}, final={wants_final}")
            return {"type": "sql", "sql": _sql, "limit": 10000}
        except Exception as e:
            logger.warning(f"[method_selector] CTE 模板构建失败，退回旧 SQL: {e}")

    # ── 旧格式：CheckIn 聚合（input_wafers/ng_wafers）──
    # 提取工站过滤
    station_clause = _extract_station_filter(user_input)
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
  AND ci.gmt_create <= '{end_date} 23:59:59'{station_clause}
GROUP BY DATE(ci.gmt_create), ci.process_code, ci.process_name,
         ci.product_code, ci.lot_code
ORDER BY report_date DESC, ci.process_code"""
    logger.info(f"[method_selector] yield_report SQL date range: {start_date} ~ {end_date}")
    return {"type": "sql", "sql": sql, "limit": 10000}


def _extract_station_filter(user_input: str, alias: str = "ci") -> str:
    """从用户输入中提取工站/工序过滤条件，返回 AND 子句（含前导换行+空格）。"""
    # 优先匹配：以字母开头的工站代码（如 POL、CMP、CVD 等），可跟可选中文描述
    # 允许前后有中英文引号（如 "POL抛光"工站 或 "CMP"工站）
    _QUOTE_L = r'[\u201c\u2018"\']'   # 左引号：" ' " '
    _QUOTE_R = r'[\u201d\u2019"\']*'  # 右引号（可选）
    _CODE    = r'([A-Za-z][A-Za-z0-9]{0,9}(?:\s*[\u4e00-\u9fa5]{0,6})?)'
    m = re.search(
        _QUOTE_L + r'\s*' + _CODE + r'\s*' + _QUOTE_R + r'\s*(?:工站|工序)'
        + r'|' + _CODE + r'\s*(?:工站|工序)',
        user_input
    )
    if m:
        name = (m.group(1) or m.group(2) or "").strip()
    else:
        # 退回：纯中文工站名（排除含时间/代词/通配词的匹配）
        m2 = re.search(r'([\u4e00-\u9fa5]{2,8})\s*(?:工站|工序)', user_input)
        if m2:
            cand = m2.group(1)
            _SKIP = ('今天', '昨天', '本周', '上周', '本月', '上月', '最近', '这周', '各', '所有', '全部', '每个', '每', '全',
                     '想看', '查询', '查看', '分析', '统计')
            if any(s in cand for s in _SKIP):
                return ""
            safe = cand.replace("'", "''")
            return f"\n  AND ({alias}.process_code = '{safe}' OR {alias}.process_name LIKE '%{safe}%')"
        return ""
    if not name:
        return ""
    safe = name.replace("'", "''")
    return f"\n  AND ({alias}.process_code = '{safe}' OR {alias}.process_name LIKE '%{safe}%')"


def _build_dual_yield_cte_sql(
    user_input: str, start_date: str, end_date: str,
    wants_fpy: bool, wants_final: bool,
) -> str:
    """
    使用 mapping_prod.json 中的 sql_template 构建双良率 CTE SQL，
    替换 {WHERE_EXTRA} 为真实日期+工站过滤条件。
    """
    import json as _json
    import os as _os
    _mapping_path = _os.path.join(
        _os.path.dirname(__file__), '..', '..', '..', 'ontology', 'data', 'mapping_prod.json'
    )
    with open(_os.path.normpath(_mapping_path)) as f:
        _map = _json.load(f)
    metrics = _map.get("metric_definitions", {})

    # 选择模板：如果明确要 FPY 用 first_pass_yield，否则用 final_yield（含综合良率）
    if wants_fpy and not wants_final:
        tmpl_key = "first_pass_yield"
    else:
        tmpl_key = "final_yield"

    tmpl = metrics.get(tmpl_key, {}).get("sql_template", "")
    if not tmpl:
        raise ValueError(f"sql_template not found for metric '{tmpl_key}'")

    # 构建 WHERE_EXTRA 条件
    conditions = [
        f"AND log.gmt_create >= '{start_date} 00:00:00'",
        f"AND log.gmt_create <= '{end_date} 23:59:59'",
    ]
    # 工站过滤
    station_cond = _extract_station_filter(user_input, alias="log")
    if station_cond:
        # strip leading whitespace/newline from _extract_station_filter output
        conditions.append(station_cond.strip())

    where_extra = "\n    ".join(conditions)
    sql = tmpl.replace("{WHERE_EXTRA}", where_extra)
    return sql.strip().rstrip(";")



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


# ── python_compute 指标检测 ────────────────────────────────────────────────────

def _detect_python_compute_metric(user_input: str):
    """
    检测用户查询是否匹配 compute_mode=python_compute 的指标。
    返回 (metric_name, MetricComputer, MetricDefinition) 或 (None, None, None)。

    MetricDefinition 一起返回，供调用方读取 raw_sql_template（ontology 层 SQL）。
    """
    try:
        from app.analytics.registry import get_metric
        from app.ontology.mapping import get_mapping

        mapping = get_mapping()  # 使用全局单例（而非每次实例化新的 MappingDictionary）
        metric_def = mapping.find_metric_by_name(user_input)
        if metric_def and metric_def.compute_mode == "python_compute":
            computer = get_metric(metric_def.metric_id)
            if computer:
                return metric_def.metric_id, computer, metric_def
            else:
                logger.warning(
                    f"[method_selector] metric '{metric_def.metric_id}' has "
                    f"compute_mode=python_compute but no computer registered in registry"
                )
    except Exception as e:
        logger.warning(f"[method_selector] _detect_python_compute_metric error: {e}")

    return None, None, None
