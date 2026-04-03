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


# ── 三层解析: ontology → mapping → skill ──────────────────────────────────────


def _resolve_metric_context(user_input: str):
    """
    三层协同解析：
      1. Ontology/Mapping 层 → MetricDefinition（物理表、JOIN 路径、过滤条件）
      2. Skill 层 → SkillDefinition（计算方法论：公式、业务定义、注意事项）
      3. Registry → MetricComputer（Python 计算实例）

    三层各司其职，互不越界：
      - Mapping 不存公式/SQL 模板
      - Skill 不存物理表名/JOIN 路径

    Returns: (MetricDefinition, SkillDefinition, MetricComputer) or (None, None, None)
    """
    try:
        from app.ontology.mapping import get_mapping
        from app.skills.loader import get_skill_loader
        from app.analytics.registry import get_metric

        # 1. Ontology/Mapping 层：语义解析 → 物理数据源定位
        mapping = get_mapping()
        metric_def = mapping.find_metric_by_name(user_input)
        if not metric_def:
            return None, None, None

        metric_id = metric_def.metric_id

        # 2. Skill 层：计算方法论加载
        loader = get_skill_loader()
        skill = loader.get_skill(metric_id)
        # 也尝试 zh_names 匹配（覆盖 skill_name 与 metric_id 不同的场景）
        if not skill:
            skill = loader.find_by_zh_name(user_input)

        # 3. Registry: MetricComputer（仅 python_compute 有）
        computer = None
        if metric_def.compute_mode == "python_compute":
            computer = get_metric(metric_id)
            if not computer:
                logger.warning(
                    f"[method_selector] metric '{metric_id}' is python_compute "
                    f"but no MetricComputer registered"
                )

        logger.info(
            f"[method_selector] resolved: metric={metric_id}, "
            f"skill={'✓' if skill else '✗'}, computer={'✓' if computer else '✗'}"
        )
        return metric_def, skill, computer

    except Exception as e:
        logger.warning(f"[method_selector] _resolve_metric_context error: {e}")
        return None, None, None


def _build_metric_sql(metric_def, skill, user_input: str) -> str:
    """
    从 Mapping 物理信息 + Skill 方法论 编排 SQL。

    Mapping 提供:
      - anchor_table, join_path, auto_filter（物理层）
    Skill 提供:
      - formula, body（计算逻辑描述，LLM 可用）
    本函数根据 metric_def.join_path 解析表结构，组装 SELECT + JOIN + WHERE。
    """
    start_date, end_date = _extract_date_range(user_input)

    # 解析 join_path 字符串获取表别名
    # 格式: "table_a → table_b(fk_col) → table_c(fk_col)"
    join_path_str = metric_def.join_path or ""
    anchor = metric_def.anchor_table

    # 根据 metric_id 选择合适的 SQL 构建策略
    # 不同指标需要从不同维度取数据 — 由 skill.formula 中的语义指导
    alias_map = _parse_join_path_aliases(join_path_str, anchor)
    log_alias = alias_map.get(anchor, "log")

    # 时间过滤
    date_filter = (
        f"{log_alias}.gmt_create >= '{start_date} 00:00:00' "
        f"AND {log_alias}.gmt_create <= '{end_date} 23:59:59'"
    )
    station_clause = _extract_station_filter(user_input, alias=log_alias)

    # auto_filter（来自 Mapping — 物理层条件）
    auto_filter = metric_def.auto_filter or ""

    # 组装 WHERE
    where_parts = []
    if auto_filter:
        # auto_filter 已含表名限定，需加别名
        af = auto_filter
        for table, alias in alias_map.items():
            af = af.replace(f"{table}.", f"{alias}.")
        # 如果没有表限定，给裸列名加 log_alias 前缀
        if "." not in af:
            # 匹配 col = val, col != val, col IS NULL 等模式
            af = re.sub(
                r'\b([a-z_][a-z0-9_]*)\s*(=|!=|<>|>=|<=|>|<|IS\s)',
                lambda m: f"{log_alias}.{m.group(1)} {m.group(2)}",
                af
            )
        where_parts.append(af)
    where_parts.append(date_filter)
    sc = station_clause.replace("\n  AND ", "").strip() if station_clause else ""
    if sc:
        where_parts.append(sc)

    where_clause = "\n  AND ".join(where_parts)

    # 组装 JOIN
    join_clause = _build_join_clause(join_path_str, alias_map)

    # 根据指标类型构建 SELECT
    # skill.formula 描述了计算逻辑 — 这里根据 compute_mode 决定取明细还是聚合
    if metric_def.compute_mode == "python_compute":
        # 明细数据：Python 侧计算，SQL 只取原始行
        select_cols = _infer_detail_columns(metric_def, skill, alias_map)
        sql = f"""SELECT {select_cols}
FROM {anchor} {log_alias}
{join_clause}WHERE {where_clause}
LIMIT 100000"""
    else:
        # sql_aggregate: SQL 侧直接聚合
        select_cols = _infer_aggregate_columns(metric_def, skill, alias_map)
        sql = f"""SELECT {select_cols}
FROM {anchor} {log_alias}
{join_clause}WHERE {where_clause}"""

    return sql


def _parse_join_path_aliases(join_path_str: str, anchor: str) -> Dict[str, str]:
    """
    解析 join_path 字符串，为每张表分配短别名。

    Input: "table_a → table_b(fk) → table_c(fk)"
    Output: {"table_a": "log", "table_b": "d", "table_c": "wdl"}
    """
    aliases: Dict[str, str] = {}
    if not join_path_str:
        aliases[anchor] = "log"
        return aliases

    # 按 → 分割
    parts = [p.strip() for p in join_path_str.replace("→", "→").split("→")]
    _alias_pool = ["log", "d", "wdl", "t4", "t5", "t6"]
    for i, part in enumerate(parts):
        # 提取表名（去除括号内的 FK 信息）
        table_name = re.sub(r'\(.*?\)', '', part).strip()
        if not table_name:
            continue
        if i < len(_alias_pool):
            aliases[table_name] = _alias_pool[i]

    # 确保 anchor 有别名
    if anchor not in aliases:
        aliases[anchor] = "log"

    return aliases


def _build_join_clause(join_path_str: str, alias_map: Dict[str, str]) -> str:
    """
    从 join_path 字符串构建 JOIN 子句。

    Input: "table_a → table_b(fk1) → table_c(fk2)"
    Output:
        JOIN table_b d ON d.fk1 = log.id
        JOIN table_c wdl ON wdl.fk2 = d.id
    """
    if not join_path_str:
        return ""

    parts = [p.strip() for p in join_path_str.replace("→", "→").split("→")]
    if len(parts) < 2:
        return ""

    tables_ordered = list(alias_map.keys())
    lines = []
    for i in range(1, len(parts)):
        part = parts[i].strip()
        # 提取表名和 FK
        m = re.match(r'([^\(]+)\(([^\)]+)\)', part)
        if m:
            table_name = m.group(1).strip()
            fk_col = m.group(2).strip()
        else:
            table_name = part.strip()
            fk_col = "id"

        alias = alias_map.get(table_name, f"t{i}")
        # 前一张表
        prev_table = tables_ordered[i - 1] if i - 1 < len(tables_ordered) else ""
        prev_alias = alias_map.get(prev_table, "log")

        lines.append(f"JOIN {table_name} {alias}\n     ON {alias}.{fk_col} = {prev_alias}.id")

    return "\n".join(lines) + "\n" if lines else ""


def _infer_detail_columns(metric_def, skill, alias_map: Dict[str, str]) -> str:
    """
    根据指标语义推断明细查询需要的列。

    对于 python_compute 指标，SQL 只取原始明细行，具体计算由 Python MetricComputer 执行。
    列推断基于 skill.formula 中引用的字段语义。
    """
    tables = list(alias_map.keys())
    log_alias = alias_map.get(metric_def.anchor_table, "log")

    # 基础列（所有指标都需要）
    cols = [f"{log_alias}.process_code", f"{log_alias}.product_code",
            f"DATE({log_alias}.gmt_create) AS report_date"]

    formula = (skill.formula if skill else "").lower()

    # 根据 formula 语义推断需要的明细列
    if "wafer_id" in formula or "wafer" in (metric_def.description or "").lower():
        # 需要 wafer 级别明细
        wdl_alias = alias_map.get(tables[-1], "wdl") if len(tables) > 1 else log_alias
        cols.insert(0, f"{wdl_alias}.wafer_id")
        if "wafer_type" in formula:
            cols.append(f"{wdl_alias}.wafer_type")
        if "ng_code" in formula:
            cols.append(f"{wdl_alias}.ng_code")

    # ROW_NUMBER 窗口函数（ASC=首次, DESC=末次）
    if "rn=" in formula or "row_number" in formula.lower():
        wdl_alias = alias_map.get(tables[-1], "wdl") if len(tables) > 1 else log_alias
        order_dir = "DESC" if "desc" in formula else "ASC"
        cols.append(
            f"ROW_NUMBER() OVER (\n"
            f"           PARTITION BY {wdl_alias}.wafer_id, {log_alias}.process_code\n"
            f"           ORDER BY {log_alias}.gmt_create {order_dir}\n"
            f"         ) AS rn"
        )

    return ",\n       ".join(cols)


def _infer_aggregate_columns(metric_def, skill, alias_map: Dict[str, str]) -> str:
    """
    根据指标语义推断聚合查询列（sql_aggregate 模式）。
    """
    log_alias = alias_map.get(metric_def.anchor_table, "log")
    formula = skill.formula if skill else ""

    # 默认按 process_code 和 日期 分组
    cols = [f"{log_alias}.process_code", f"DATE({log_alias}.gmt_create) AS report_date"]

    # 主聚合表达式
    if formula:
        cols.append(f"{formula} AS metric_value")
    else:
        cols.append(f"COUNT(*) AS metric_value")

    return ",\n       ".join(cols)


def method_selector_node(state: AnalysisState) -> dict:
    """
    节点：分析方法选择。

    信息流（三层各司其职，LLM 做编排）:
      1. Ontology/Mapping: 语义解析 → MetricDefinition（表名、JOIN、过滤条件）
      2. Skill: 计算方法论 → SkillDefinition（公式、业务定义、注意事项）
      3. LLM 综合两层信息 → 编排 SQL + Python 计算方案
      4. 关键词/LLM 兜底：非指标类分析（SPC/OEE 等）

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

    # ── 1. 三层协同: Ontology(Mapping) + Skill + Registry ──
    if not data_source_config:
        metric_def, skill, computer = _resolve_metric_context(user_input)

        if metric_def and metric_def.compute_mode == "python_compute" and computer:
            # python_compute: Mapping 提供物理信息，Skill 提供方法论，Python 执行计算
            method = "metric_compute"
            skill_desc = skill.standard_definition if skill else metric_def.description
            reason = f"三层解析: '{metric_def.metric_id}' — {skill_desc}"
            logger.info(
                f"[method_selector] ontology+skill → metric_compute ({metric_def.metric_id})"
            )

            # SQL 由 Mapping 物理信息 + Skill 方法论 编排
            raw_sql = _build_metric_sql(metric_def, skill, user_input)
            data_source_config = {"type": "sql", "sql": raw_sql, "limit": 100000}
            params = {"metric_name": metric_def.metric_id}

            # Skill 业务上下文（供下游节点 / LLM 响应使用）
            if skill:
                skill_context = {
                    "skill_name": skill.skill_name,
                    "standard_definition": skill.standard_definition,
                    "formula": skill.formula,
                    "granularity": skill.granularity,
                    "body": skill.body,
                }

        elif metric_def and metric_def.compute_mode == "sql_aggregate":
            # sql_aggregate: Mapping + Skill 编排出聚合 SQL
            method = "yield_report"  # 保持兼容
            skill_desc = skill.standard_definition if skill else metric_def.description
            reason = f"三层解析(聚合): '{metric_def.metric_id}' — {skill_desc}"
            logger.info(
                f"[method_selector] ontology+skill → sql_aggregate ({metric_def.metric_id})"
            )

            raw_sql = _build_metric_sql(metric_def, skill, user_input)
            data_source_config = {"type": "sql", "sql": raw_sql, "limit": 10000}

            if skill:
                skill_context = {
                    "skill_name": skill.skill_name,
                    "standard_definition": skill.standard_definition,
                    "formula": skill.formula,
                    "granularity": skill.granularity,
                    "body": skill.body,
                }

    # ── 2. 关键词 + LLM 分类（三层未匹配时）──
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

    # ── 3. 其余 data_source_config 构建 ──
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
    构建良率报表数据查询 SQL（兜底路径）。

    仅在三层解析未匹配到指标时使用 — CheckIn 聚合 SQL（input_wafers/ng_wafers 格式）。
    Python 指标（FPY/FinalYield/ReworkRate）应通过 _resolve_metric_context → metric_compute 路由。
    """
    start_date, end_date = _extract_date_range(user_input)

    # CheckIn 聚合（input_wafers/ng_wafers）
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

