"""
method_selector 节点

两条路径 + 统一 ontology/mapping 层：

  ① Skill 路径  (有预定义指标 skill)
        LLM 语义匹配 skill → 读取方法论 + Mapping 物理信息 → SQL 编排

  ② 即席探索路径 (无匹配 skill)
        Ontology/Mapping 提供数据目录 → LLM CoT 推理 → 生成 SQL

  ③ 统计分析路径 (SPC / correlation / OEE 等)
        关键词快速匹配 / LLM 从方法库中选择

  两条路径共享 ontology+mapping 层和执行引擎。
"""

from __future__ import annotations

import json
import logging
import numbers
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from app.agents.analysis_agent.state import AnalysisState
from app.analytics.registry import list_methods

logger = logging.getLogger(__name__)

# ── 统计分析关键词快速映射（高置信度 → 无需 LLM）──────────────────────────────
_ANALYSIS_KEYWORD_MAP = {
    r"SPC|控制图|Cpk|Ppk|制程能力|control chart": "spc",
    r"相关性|相关系数|correlation|热力图": "correlation",
    r"ANOVA|方差分析|差异显著|t[-\s]?test|t检验|卡方|正态性": "hypothesis",
    r"帕累托|pareto|80/20|80%-20%\b": "pareto",
    r"回归|regression|线性分析|影响因素": "regression",
    r"预测|predict|forecast|random forest|随机森林": "prediction",
    r"异常检测|anomaly|outlier|离群|孤立|3[σσ]|三倍标准差": "anomaly",
    r"描述性统计|基础统计|descriptive stats": "descriptive",
    r"OEE|综合效率|设备效率": "oee_report",
}


def _quick_analysis_classify(user_input: str) -> str | None:
    """高置信度关键词匹配 → 统计分析方法名，或 None。"""
    for pattern, method in _ANALYSIS_KEYWORD_MAP.items():
        if re.search(pattern, user_input, re.IGNORECASE):
            return method
    return None


# ── LLM 语义路由器 ─────────────────────────────────────────────────────────────


def _llm_route(user_input: str) -> Dict[str, Any]:
    """
    中央语义路由器 — 用一次 LLM 调用决定走哪条处理路径。

    路由决策（path 字段）:
      "skill"     — 匹配到预定义指标 skill，携带 skill_name
      "adhoc"     — 即席探索查询，ontology/mapping 提供数据字典，LLM 生成 SQL
      "analysis"  — 统计分析方法（SPC/correlation/OEE 等），携带 method
      "out_of_scope" — 超出系统语义覆盖范围

    Returns: {"path": ..., "skill_name"?: ..., "method"?: ..., "reason": ...}
    """
    try:
        from app.agent.llm import get_llm
        from app.skills.loader import get_skill_loader

        loader = get_skill_loader()
        skills_text = "\n".join(
            f"  - {s.skill_name}: {', '.join(s.zh_names[:5])}"
            for s in loader.list_skills()
        )

        analysis_methods_text = "\n".join(
            f"  - {m['name']}: {m['description']}" for m in list_methods()
            if m["name"] not in ("metric_compute", "yield_report", "oee_report")
        )

        prompt = f"""你是一个半导体制造 MES 系统的查询路由器，负责将用户问题分发到正确的处理路径。

可用指标 Skill（精确计算，有预定义方法论）:
{skills_text}

统计分析方法（探索性数据分析）:
{analysis_methods_text}

系统覆盖的业务领域: 半导体晶圆生产 MES，包括良率、在制品、载具、批次、设备、工站等。

用户问题: "{user_input}"

请判断应走哪条路径，以 JSON 返回：
{{
  "path": "skill",
  "skill_name": "first_pass_yield",
  "reason": "用户查询一次良率，匹配 first_pass_yield skill"
}}
或
{{
  "path": "adhoc",
  "reason": "查询站点可用载具数量，需要即席 SQL 查询"
}}
或
{{
  "path": "analysis",
  "method": "spc",
  "reason": "用户要做 SPC 控制图分析"
}}
或
{{
  "path": "out_of_scope",
  "reason": "问题与 MES 系统无关"
}}

判断规则：
1. 如果问题明确提到 skill 列表中的指标名称或同义词 → skill
2. 如果问题是查询统计分析（SPC/相关性/回归等）→ analysis
3. 如果问题涉及 MES 业务数据查询但没有预定义 skill → adhoc
4. 如果完全与 MES 无关 → out_of_scope

只返回 JSON，不要其他内容。"""

        llm = get_llm()
        resp = llm.invoke(prompt)
        content = resp.content if hasattr(resp, "content") else str(resp)

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            path = data.get("path", "adhoc")
            if path not in ("skill", "adhoc", "analysis", "out_of_scope"):
                path = "adhoc"
            return {
                "path": path,
                "skill_name": data.get("skill_name"),
                "method": data.get("method"),
                "reason": data.get("reason", "LLM 路由"),
            }
    except Exception as e:
        logger.warning(f"[method_selector] _llm_route error: {e}")

    # 兜底：走即席路径
    return {"path": "adhoc", "reason": "路由失败，默认走即席路径"}


def _llm_gen_adhoc_sql(user_input: str) -> Optional[Dict[str, Any]]:
    """
    即席路径：LLM CoT 推理 + SQL 生成。

    LLM 接收:
      - 系统数据字典（ontology 物理表目录）
      - 预定义查询模板（query_patterns）
      - 业务值域（状态码枚举）
      - 用户问题

    LLM 先做思维链推理（涉及几个实体、数据量、是否复杂），
    然后生成可执行 SQL。

    Returns: {"sql": ..., "tables_used": [...], "cot_summary": ...}
             or None on failure
    """
    try:
        from app.agent.llm import get_llm
        from app.ontology.mapping import get_mapping

        mapping = get_mapping()
        table_catalog = mapping.build_table_catalog(max_tables=30)
        value_summary = mapping.build_value_summary(max_domains=8)

        today = datetime.now().date()
        fallback_start, fallback_end = _extract_date_range(user_input)

        prompt = f"""你是一个数据工程师，负责为半导体 MES 系统生成 SQL 查询。

## 数据字典（可用物理表）
{table_catalog}

## 业务值域（状态码）
{value_summary}

## 时间上下文
当前日期: {today}
请从用户问题中理解时间范围（"两个星期"=14天，"上个月"=上个日历月，"最近N周"=N×7天，"两周"=14天 等），
并在 SQL 的 WHERE 条件中直接写出正确的日期过滤（MySQL 语法，时间字段通常为 gmt_create）。
如果用户未明确指定时间，使用 fallback 范围: {fallback_start} 至 {fallback_end}。

## 用户问题
"{user_input}"

## 思考过程（请先分析，再生成 SQL）
1. 这个问题涉及哪些实体/表？
2. 需要 JOIN 吗？如果需要，通过哪个外键？
3. 过滤条件是什么（状态码用上面的值域）？
4. 是简单聚合还是复杂查询（窗口函数/子查询）？
5. 预期数据量大不大？

## 输出格式（JSON）
{{
  "cot_summary": "涉及 X 表，需要 JOIN Y 表，过滤条件 Z，简单 GROUP BY 聚合",
  "sql": "SELECT ... FROM ... WHERE ... LIMIT 10000",
  "tables_used": ["table1", "table2"],
  "approach": "sql_aggregate"
}}

注意：
- SQL 必须是 MySQL 语法，可以直接执行
- 时间字段通常是 gmt_create 或 gmt_update
- 加 LIMIT 防止大量数据返回（默认 10000 行）
- 只返回 JSON"""

        llm = get_llm()
        resp = llm.invoke(prompt)
        content = resp.content if hasattr(resp, "content") else str(resp)

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            sql = (data.get("sql") or "").strip()
            if sql:
                if not _has_date_filter(sql):
                    logger.warning(
                        "[method_selector] adhoc SQL has no date filter — "
                        f"injecting fallback range {fallback_start} ~ {fallback_end}"
                    )
                    fallback_clause = (
                        f" AND gmt_create >= '{fallback_start} 00:00:00'"
                        f" AND gmt_create <= '{fallback_end} 23:59:59'"
                    )
                    sql = re.sub(
                        r"(\bLIMIT\b)", fallback_clause + r" \1", sql, count=1, flags=re.IGNORECASE
                    ) if re.search(r'\bLIMIT\b', sql, re.IGNORECASE) else sql + fallback_clause
                return {
                    "sql": sql,
                    "tables_used": data.get("tables_used", []),
                    "cot_summary": data.get("cot_summary", ""),
                    "approach": data.get("approach", "sql"),
                }
    except Exception as e:
        logger.warning(f"[method_selector] _llm_gen_adhoc_sql error: {e}")

    return None


def _llm_analysis_classify(user_input: str) -> Tuple[str, str, Dict[str, Any]]:
    """
    统计分析路径：LLM 从分析方法库中选择方法并提取参数。
    返回 (method_name, reason, params_hint)。
    """
    try:
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

    user_input 可以是:
      - 用户自然语言（通过 zh_names 子串匹配）
      - metric_id 直接字符串（如 "first_pass_yield"，先精确匹配）

    Returns: (MetricDefinition, SkillDefinition, MetricComputer) or (None, None, None)
    """
    try:
        from app.ontology.mapping import get_mapping
        from app.skills.loader import get_skill_loader
        from app.analytics.registry import get_metric

        # 1. Ontology/Mapping 层：先尝试 metric_id 精确匹配，再做 zh_names 子串匹配
        mapping = get_mapping()
        metric_def = mapping.get_metric_by_id(user_input)   # 精确匹配 metric_id
        if not metric_def:
            metric_def = mapping.find_metric_by_name(user_input)  # zh_names 模糊匹配
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


# ── LLM 编排 SQL（skill 路径，替代确定性 _build_metric_sql）─────────────────

# 灰度开关：metric_id 在此集合内才走 LLM 路径，其余 fallback 到确定性生成
_LLM_SQL_ENABLED_METRICS: set = {
    "wafer_wip",          # sql_agg  — L1+L2 verified
    "rework_rate",        # python_compute — L1+L2+L3 verified
    "first_pass_yield",   # python_compute — L1+L2+L3 verified
    "final_yield",        # python_compute — L1+L2+L3 verified
}


def _llm_build_aggregate_sql(metric_def, skill, user_input: str) -> Optional[str]:
    """
    sql_aggregate 模式：LLM 读取 Skill 方法论 + Mapping 物理上下文，生成聚合 SQL。

    Prompt 结构与 _llm_build_detail_sql 完全独立，不出现"明细"/"不要 GROUP BY"等词。
    失败时返回 None，调用方 fallback 到 _build_metric_sql()。
    """
    try:
        from app.agent.llm import get_llm
        from app.ontology.mapping import get_mapping

        mapping = get_mapping()
        metric_context = mapping.build_metric_context(metric_def)
        value_summary = mapping.build_value_summary(max_domains=6)
        today = datetime.now().date()
        fallback_start, fallback_end = _extract_date_range(user_input)

        skill_block = ""
        if skill:
            skill_block = f"""## Skill 方法论
指标名称: {', '.join(skill.zh_names[:3])}
标准定义: {skill.standard_definition}
计算公式: {skill.formula}
支持粒度: {', '.join(skill.granularity)}

{skill.body}
"""

        prompt = f"""{skill_block}
{metric_context}

## 业务值域（状态码枚举）
{value_summary}

## 时间上下文
当前日期: {today}
请从用户问题中理解时间范围（"两个星期"=14天，"上个月"=上个日历月，"最近N周"=N×7天 等），
并在 SQL 的 WHERE 条件中直接写出正确的日期过滤（MySQL 语法，时间字段为 gmt_create 或 gmt_update）。
如果用户未明确提及时间，请使用 fallback 范围: {fallback_start} 至 {fallback_end}。

## 用户问题
"{user_input}"

## 任务
根据以上 Skill 方法论和数据物理结构，生成一条可执行的 MySQL 聚合查询 SQL。

要求：
- 使用聚合函数（COUNT / SUM / AVG）+ GROUP BY，返回统计结果
- 必须应用"自动过滤条件"中的所有 WHERE 条件
- 必须包含时间范围的 WHERE 过滤（根据上方"时间上下文"指引生成正确条件）
- 加 LIMIT 10000 防止数据量过大
- 完整、可直接执行的 MySQL 语法
- **严禁**使用"涉及的物理表"的关键列列表以外的列名，不要凭借 Skill 说明发明不存在的列

输出 JSON（只返回 JSON，不要任何解释）：
{{
  "sql": "SELECT ... FROM ... WHERE ... GROUP BY ... LIMIT 10000",
  "groupby_dims": ["col1", "col2"],
  "reason": "一句话说明为什么这样写"
}}"""

        llm = get_llm()
        resp = llm.invoke(prompt)
        content = resp.content if hasattr(resp, "content") else str(resp)

        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            sql = data.get("sql", "").strip()
            if sql:
                if not _has_date_filter(sql):
                    logger.warning(
                        f"[method_selector] LLM aggregate SQL for '{metric_def.metric_id}' "
                        f"has no date filter — injecting fallback range "
                        f"{fallback_start} ~ {fallback_end}"
                    )
                    fallback_clause = (
                        f" AND gmt_create >= '{fallback_start} 00:00:00'"
                        f" AND gmt_create <= '{fallback_end} 23:59:59'"
                    )
                    sql = re.sub(
                        r"(\bLIMIT\b)", fallback_clause + r" \1", sql, count=1, flags=re.IGNORECASE
                    ) if re.search(r'\bLIMIT\b', sql, re.IGNORECASE) else sql + fallback_clause
                logger.info(
                    f"[method_selector] LLM aggregate SQL for '{metric_def.metric_id}': "
                    f"dims={data.get('groupby_dims')}, reason={data.get('reason')}"
                )
                return sql
    except Exception as e:
        logger.warning(f"[method_selector] _llm_build_aggregate_sql error: {e}")
    return None


def _llm_build_detail_sql(metric_def, skill, user_input: str) -> Optional[str]:
    """
    python_compute 模式：LLM 生成明细查询 SQL（计算由 Python MetricComputer 执行）。

    Prompt 结构与 _llm_build_aggregate_sql 完全独立，不出现聚合/GROUP BY 相关词。
    失败时返回 None，调用方 fallback 到 _build_metric_sql()。
    """
    try:
        from app.agent.llm import get_llm
        from app.ontology.mapping import get_mapping

        mapping = get_mapping()
        metric_context = mapping.build_metric_context(metric_def)
        value_summary = mapping.build_value_summary(max_domains=6)
        today = datetime.now().date()
        fallback_start, fallback_end = _extract_date_range(user_input)

        skill_block = ""
        if skill:
            skill_block = f"""## Skill 方法论
指标名称: {', '.join(skill.zh_names[:3])}
标准定义: {skill.standard_definition}
计算公式: {skill.formula}

{skill.body}
"""

        # required_columns 硬约束：Python Computer 依赖的列，LLM 必须全部 SELECT
        req_cols_block = ""
        if skill and skill.required_columns:
            col_lines = []
            for col in skill.required_columns:
                if col == "rn":
                    order = skill.rn_order or "ASC"
                    col_lines.append(
                        f"  - rn   （必须用 ROW_NUMBER() OVER "
                        f"(PARTITION BY wafer_id, process_code ORDER BY gmt_create {order}) AS rn）"
                    )
                elif col == "report_date":
                    col_lines.append("  - report_date   （必须用 DATE(gmt_create) AS report_date）")
                else:
                    col_lines.append(f"  - {col}")
            req_cols_block = (
                "\n## Python Computer 必须列（SELECT 中必须包含，列名须完全一致）\n"
                + "\n".join(col_lines) + "\n"
            )

        prompt = f"""{skill_block}
{metric_context}
{req_cols_block}
## 业务值域（状态码枚举）
{value_summary}

## 时间上下文
当前日期: {today}
请从用户问题中理解时间范围（"两个星期"=14天，"上个月"=上个日历月，"最近N周"=N×7天 等），
并在 SQL 的 WHERE 条件中直接写出正确的日期过滤（MySQL 语法，时间字段为 gmt_create 或 gmt_update）。
如果用户未明确提及时间，请使用 fallback 范围: {fallback_start} 至 {fallback_end}。

## 用户问题
"{user_input}"

## 任务
根据以上 Skill 方法论和数据物理结构，生成明细查询 SQL。
后续 Python 程序将读取这些明细行并完成指标计算，SQL 不做指标聚合。

要求：
- SELECT 中必须包含"Python Computer 必须列"中的所有列（列名须与列表完全一致）
- 返回计算所需的原始明细行（行级数据）
- 必须应用"自动过滤条件"中的所有 WHERE 条件
- 时间范围过滤用 gmt_create BETWEEN 或 >= / <=
- 加 LIMIT 100000
- **严禁**使用"涉及的物理表"的关键列列表以外的列名，不要凭借 Skill 说明发明不存在的列

输出 JSON（只返回 JSON）：
{{
  "sql": "SELECT ... FROM ... WHERE ... LIMIT 100000",
  "key_columns": ["col1", "col2"],
  "reason": "一句话说明返回了哪些字段，用于什么计算"
}}"""

        llm = get_llm()
        resp = llm.invoke(prompt)
        content = resp.content if hasattr(resp, "content") else str(resp)

        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            sql = data.get("sql", "").strip()
            if sql:
                if not _has_date_filter(sql):
                    logger.warning(
                        f"[method_selector] LLM detail SQL for '{metric_def.metric_id}' "
                        f"has no date filter — injecting fallback range "
                        f"{fallback_start} ~ {fallback_end}"
                    )
                    fallback_clause = (
                        f" AND gmt_create >= '{fallback_start} 00:00:00'"
                        f" AND gmt_create <= '{fallback_end} 23:59:59'"
                    )
                    sql = re.sub(
                        r"(\bLIMIT\b)", fallback_clause + r" \1", sql, count=1, flags=re.IGNORECASE
                    ) if re.search(r'\bLIMIT\b', sql, re.IGNORECASE) else sql + fallback_clause
                logger.info(
                    f"[method_selector] LLM detail SQL for '{metric_def.metric_id}': "
                    f"cols={data.get('key_columns')}, reason={data.get('reason')}"
                )
                return sql
    except Exception as e:
        logger.warning(f"[method_selector] _llm_build_detail_sql error: {e}")
    return None


def _dispatch_metric_sql(metric_def, skill, user_input: str) -> str:
    """
    SQL 生成入口：根据 metric_id 灰度开关决定走 LLM 路径还是确定性路径。

    灰度策略（_LLM_SQL_ENABLED_METRICS）：
      - 在集合内 → 尝试 LLM 生成，失败则 fallback 到 _build_metric_sql()
      - 不在集合内 → 直接走确定性 _build_metric_sql()
    """
    if metric_def.metric_id in _LLM_SQL_ENABLED_METRICS:
        if metric_def.compute_mode == "sql_aggregate":
            llm_sql = _llm_build_aggregate_sql(metric_def, skill, user_input)
        else:
            llm_sql = _llm_build_detail_sql(metric_def, skill, user_input)

        if llm_sql:
            return llm_sql
        logger.warning(
            f"[method_selector] LLM SQL failed for '{metric_def.metric_id}', "
            "falling back to deterministic _build_metric_sql()"
        )

    return _build_metric_sql(metric_def, skill, user_input)


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

    四条路径，共享 ontology+mapping 层：

      ① Skill 路径  (LLM 语义匹配到预定义 skill)
            Mapping 物理信息 + Skill 方法论 → 确定性 SQL 编排 → Python metric_compute

      ② 即席探索路径 (无匹配 skill，但在 MES 领域内)
            Mapping 表目录 → LLM CoT 推理 + SQL 生成 → 直接返回数据

      ③ 统计分析路径 (SPC / correlation / OEE 等)
            关键词快速匹配 / LLM 从分析方法库选择 → AnalysisEngine 执行

      ④ 超出范围  → 返回提示

    输入: user_input
    输出: suggested_method, method_reason, method_params, data_source_config,
          skill_context, route_decision, adhoc_context
    """
    user_input = state.get("user_input", "")
    logger.info(f"[method_selector] input={user_input[:80]}...")

    data_source_config = state.get("data_source_config")
    skill_context: Dict[str, Any] | None = None
    adhoc_context: str | None = None
    params: Dict[str, Any] = {}
    method = ""
    reason = ""
    route_decision = "unknown"

    # ── 快速路径：统计分析关键词（高置信度，无需 LLM 路由）──
    fast_method = _quick_analysis_classify(user_input)

    # ── 主路由：LLM 语义路由 ──
    # 跳过条件：已有 data_source_config（前端显式传入），或已命中高置信度分析关键词
    if not data_source_config and not fast_method:
        route = _llm_route(user_input)
        route_path = route.get("path", "adhoc")
        route_reason = route.get("reason", "")
        logger.info(f"[method_selector] LLM route → path={route_path}, reason={route_reason}")

        # ── 路径①: Skill 路径 ──
        if route_path == "skill":
            skill_name = route.get("skill_name", "")
            # _resolve_metric_context 通过 skill_name 或用户输入做三层解析
            hint = skill_name or user_input
            metric_def, skill, computer = _resolve_metric_context(hint)

            if metric_def and metric_def.compute_mode == "python_compute" and computer:
                method = "metric_compute"
                skill_desc = skill.standard_definition if skill else metric_def.description
                reason = f"[Skill路径] '{metric_def.metric_id}' — {skill_desc}"
                route_decision = "skill"
                logger.info(f"[method_selector] skill → metric_compute ({metric_def.metric_id})")

                raw_sql = _dispatch_metric_sql(metric_def, skill, user_input)
                data_source_config = {"type": "sql", "sql": raw_sql, "limit": 100000}
                params = {"metric_name": metric_def.metric_id}

                if skill:
                    skill_context = {
                        "skill_name": skill.skill_name,
                        "compute_tool": skill.compute_tool,
                        "standard_definition": skill.standard_definition,
                        "formula": skill.formula,
                        "granularity": skill.granularity,
                        "body": skill.body,
                    }

            elif metric_def and metric_def.compute_mode == "sql_aggregate":
                method = "yield_report"
                skill_desc = skill.standard_definition if skill else metric_def.description
                reason = f"[Skill路径/聚合] '{metric_def.metric_id}'"
                route_decision = "skill"

                raw_sql = _dispatch_metric_sql(metric_def, skill, user_input)
                data_source_config = {"type": "sql", "sql": raw_sql, "limit": 10000}

                if skill:
                    skill_context = {
                        "skill_name": skill.skill_name,
                        "compute_tool": skill.compute_tool,
                        "standard_definition": skill.standard_definition,
                        "formula": skill.formula,
                        "granularity": skill.granularity,
                        "body": skill.body,
                    }
            else:
                # Skill 路由但没找到对应 metric_def → 降级到即席路径
                logger.warning(
                    f"[method_selector] skill route for '{skill_name}' but no metric_def found, "
                    "falling back to adhoc"
                )
                route_path = "adhoc"

        # ── 路径②: 即席探索路径 ──
        if route_path == "adhoc":
            route_decision = "adhoc"
            result = _llm_gen_adhoc_sql(user_input)
            if result and result.get("sql"):
                method = "adhoc_query"
                reason = f"[即席路径] {result.get('cot_summary', 'LLM 生成 SQL')}"
                adhoc_context = result.get("cot_summary", "")
                data_source_config = {
                    "type": "sql",
                    "sql": result["sql"],
                    "limit": 10000,
                    "tables_used": result.get("tables_used", []),
                }
                logger.info(
                    f"[method_selector] adhoc SQL generated, "
                    f"tables={result.get('tables_used')}"
                )
            else:
                # SQL 生成失败 → 兜底描述性统计
                method = "descriptive"
                reason = "[即席路径] SQL 生成失败，回退到描述性统计"
                data_source_config = {"type": "data", "data": state.get("raw_data") or []}

        # ── 路径③: LLM 选择统计分析方法 ──
        elif route_path == "analysis":
            route_decision = "analysis"
            suggested_method = route.get("method")
            if suggested_method:
                method = suggested_method
                reason = f"[统计分析] {route_reason}"
            else:
                method, reason, params = _llm_analysis_classify(user_input)
                route_decision = "analysis"

        # ── 路径④: 超出范围 ──
        elif route_path == "out_of_scope":
            route_decision = "out_of_scope"
            method = "out_of_scope"
            reason = f"[超出范围] {route_reason}"
            data_source_config = {"type": "data", "data": []}

    # ── 高置信度统计分析关键词命中（跳过 LLM 路由）──
    if fast_method and not method:
        method = fast_method
        reason = f"[快速匹配] 关键词命中 '{method}'"
        route_decision = "analysis"
        logger.info(f"[method_selector] fast keyword → {method}")

    # ── 最终兜底：如果所有路径都没设定 method ──
    if not method:
        method = "descriptive"
        reason = "默认描述性统计"
        route_decision = "fallback"

    # ── data_source_config 兜底构建（analysis 路径使用 raw_data 或预建 SQL）──
    if not data_source_config:
        if method == "yield_report":
            data_source_config = _build_yield_sql(user_input)
        elif method == "oee_report":
            data_source_config = _build_oee_sql(user_input)
        else:
            data_source_config = {"type": "data", "data": state.get("raw_data") or []}

    # ── value_column 自动推断（SPC / correlation / anomaly / descriptive）──
    if method in ("spc", "correlation", "anomaly", "descriptive") and not params.get("value_column"):
        raw_data = state.get("raw_data") or []
        if raw_data and isinstance(raw_data[0], dict):
            cols = list(raw_data[0].keys())

            def _is_numeric(v: Any) -> bool:
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

            _EXCLUDE = ("数量", "count", "个数", "编码", "编号", "_id", "code", "id")
            candidate_cols = [
                c for c in cols
                if _is_numeric(raw_data[0].get(c))
                and not any(exc in c.lower() for exc in _EXCLUDE)
            ]
            detected = None
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
            if detected is None:
                _MEASURE_KEYWORDS = ("均值", "平均值", "测量值", "量测值", "value", "avg", "mean")
                detected = next(
                    (c for c in candidate_cols
                     if any(kw in c.lower() for kw in _MEASURE_KEYWORDS)),
                    None,
                )
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
        "route_decision": route_decision,
        "adhoc_context": adhoc_context,
    }


# ── SQL 模板构建器 ────────────────────────────────────────────────────────────

def _normalize_cn_numerals(text: str) -> str:
    """
    Replace single-character Chinese digit words with ASCII digits.
    Covers the common range used in time expressions like "最近两个星期"、"最近三天"。
    十 is intentionally left out (not used in time span patterns we handle).
    """
    _TABLE = {"零": "0", "一": "1", "二": "2", "两": "2",
              "三": "3", "四": "4", "五": "5", "六": "6",
              "七": "7", "八": "8", "九": "9"}
    for cn, ar in _TABLE.items():
        text = text.replace(cn, ar)
    return text


def _has_date_filter(sql: str) -> bool:
    """
    检测 SQL 是否已包含日期/时间过滤条件（gmt_create / gmt_update / report_date）。
    用于判断 LLM 生成的 SQL 是否需要补充 fallback 时间范围。
    """
    patterns = [
        r"gmt_create\s*(>=|<=|BETWEEN|>|<|=)",
        r"gmt_update\s*(>=|<=|BETWEEN|>|<|=)",
        r"report_date\s*(>=|<=|BETWEEN|>|<|=)",
        r"DATE\s*\(\s*gmt_(create|update)\s*\)\s*(>=|<=|=|>|<)",
        r"gmt_(create|update)\s+BETWEEN",
        r"DATE_SUB\s*\(",
        r"INTERVAL\s+\d+\s+(DAY|WEEK|MONTH|YEAR)",
        r"CURDATE\s*\(\s*\)",
        r"NOW\s*\(\s*\)",
    ]
    for p in patterns:
        if re.search(p, sql, re.IGNORECASE):
            return True
    return False


def _extract_date_range(user_input: str) -> tuple[str, str]:
    """
    从用户输入中提取日期范围（正则 fallback）。
    支持: 今天/昨天/本周/上周/本月/上月/最近N天 + 具体日期（YYYY-MM-DD）。
    默认: 最近 7 天。

    此函数现为 **fallback**：LLM SQL 生成路径中，LLM 自己负责解析时间范围并写入 SQL；
    仅当 LLM 生成的 SQL 未含任何日期过滤条件时，才用本函数计算兜底范围注入。
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
    if re.search(r"上个?月|last\s*month", user_input, re.IGNORECASE):
        first_of_this = today.replace(day=1)
        last_of_prev = first_of_this - timedelta(days=1)
        start = last_of_prev.replace(day=1)
        return str(start), str(last_of_prev)

    # 「最近一周」/「过去一周」/「最近一个星期」/「过去一个星期」等文字形式
    if re.search(r"最近一周|过去一周|最近七天|过去七天|最近一个星期|过去一个星期", user_input, re.IGNORECASE):
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

    # 将中文数字字符转换为 ASCII 数字，使正则 \d+ 能匹配「最近两个星期」「最近三天」等
    user_input_norm = _normalize_cn_numerals(user_input)

    n_days_match = re.search(r"最近\s*(\d+)\s*天", user_input_norm)
    if n_days_match:
        n = int(n_days_match.group(1))
        return str(today - timedelta(days=n - 1)), str(today)

    # 「最近N周」/「最近N个星期」或「最近N个月」（数字形式）
    n_weeks_match = re.search(r"最近\s*(\d+)\s*(?:周|个星期)", user_input_norm)
    if n_weeks_match:
        n = int(n_weeks_match.group(1))
        return str(today - timedelta(days=n * 7 - 1)), str(today)

    n_months_match = re.search(r"最近\s*(\d+)\s*个?月", user_input_norm)
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

