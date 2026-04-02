"""
sql_generator — SQL 生成节点 (Phase D RAG 增强版)

根据查询计划 + Schema 上下文 + (可选) 错误上下文，调用 LLM 生成 SQL。

增强功能:
- 注入真实 Schema 上下文（RAG），减少幻觉表名/列名
- 支持多步查询分解的 sub_query 生成
- 自我修正模式：使用 ChatOpenAI 直接构建修正 prompt，包含错误类型分析

Phase D 新增:
- 优先使用 RAG 检索的 schema 上下文（由 query_planner 注入）
- 检索历史 SQL 案例作为 few-shot 参考
- 当 RAG 不可用时自动降级到 schema_tools
"""

import logging
import time as _time
from app.agent.state import AgentState
from app.agent.tools.nl2sql_tools import generate_sql
from app.agent.tools.schema_tools import get_schema_context
from app.agent.trace import trace_step

logger = logging.getLogger(__name__)


def sql_generator_node(state: AgentState) -> dict:
    """
    SQL 生成节点 (Phase C 增强)。
    输入: user_input, resolved_input, is_followup, query_plan, memory_context,
          sql_error (可选), sql_retry_count (可选)
    输出: sql, sql_confidence, sql_retry_count, rag_context
    """
    _t0 = _time.perf_counter()

    # 快速路径: approved_sql 模式（前端直接提交已批准的 SQL 执行）
    # 若无重试错误，跳过 LLM 生成，直接将 approved_sql 传递给下游节点
    _approved_sql = state.get("approved_sql", "")
    if _approved_sql and not state.get("sql_error"):
        trace = list(state.get("pipeline_trace", []))
        trace_step(trace, "sql_generator", _t0,
                   summary="approved_sql 模式: 使用前端提交的已批准 SQL，跳过 LLM 生成",
                   detail={"sql": _approved_sql[:200], "approved_sql_mode": True})
        return {
            "sql": _approved_sql,
            "sql_confidence": 1.0,
            "sql_retry_count": 0,
            "pipeline_trace": trace,
        }

    user_input = state.get("user_input", "")
    resolved_input = state.get("resolved_input", "") or user_input
    is_followup = state.get("is_followup", False)
    memory_context = state.get("memory_context", {})
    query_plan = state.get("query_plan", {})
    sql_error = state.get("sql_error", "")
    retry_count = state.get("sql_retry_count", 0)

    # Phase C: 追问时使用消解后的输入
    if is_followup:
        user_input = resolved_input

    # ── 0.5 快速路径: sql_template 模式（预构建模板，完全绕过 LLM）──
    # 暂时禁用：让 LLM 正常生成 SQL，sql_template 仅作为 prompt 参考注入。
    # 如需重新启用，取消下方注释并删除 `if False:` 行。
    # if not sql_error:
    #     semantic_ctx_early = state.get("semantic_context", {})
    #     _template_sql = _apply_metric_sql_template(
    #         semantic_ctx_early,
    #         state.get("query_plan", {}),
    #         user_input,
    #     )
    #     if _template_sql:
    #         trace = list(state.get("pipeline_trace", []))
    #         trace_step(trace, "sql_generator", _t0,
    #                    summary="sql_template 快速路径: 跳过 LLM，使用预构建模板",
    #                    detail={"sql": _template_sql[:300], "template_mode": True})
    #         return {
    #             "sql": _template_sql,
    #             "sql_confidence": 0.95,
    #             "sql_retry_count": 0,
    #             "sql_error": "",
    #             "pipeline_trace": trace,
    #         }

    # ── 1. 获取 Schema 上下文（优先使用语义引擎，降级 RAG → schema_tools）──
    semantic_ctx = state.get("semantic_context", {})
    schema_ctx = state.get("rag_context", "")
    if not schema_ctx:
        schema_ctx = _get_schema_context_with_rag(user_input)

    # Phase 3: 如果语义引擎产出了 schema_snippet，优先使用它（更精准）
    semantic_snippet = semantic_ctx.get("schema_snippet", "")
    if semantic_snippet:
        schema_ctx = _merge_semantic_schema(semantic_snippet, schema_ctx)

    # ── 1.5 Phase D: 检索 SQL few-shot 案例 ──
    few_shot_context = _get_sql_few_shots(user_input)

    # ── 2. 构建优化后的 NL 查询 ──
    nl_query = _build_optimized_query(
        user_input, query_plan, schema_ctx, few_shot_context, semantic_ctx
    )

    # ── 3. 自我修正模式 ──
    error_context = ""
    if sql_error and retry_count > 0:
        previous_sql = state.get("sql", "")
        error_context = _build_correction_context(
            previous_sql, sql_error, retry_count, schema_ctx, semantic_ctx
        )
        logger.info(
            f"[sql_generator] Self-correction #{retry_count}: "
            f"{sql_error[:120]}..."
        )

    # ── 4. 多步查询处理 ──
    if query_plan.get("is_multi_step") and not sql_error:
        sql = _generate_multi_step_sql(user_input, query_plan, schema_ctx, semantic_ctx)
    else:
        sql = generate_sql.invoke({
            "natural_language": nl_query,
            "error_context": error_context,
        })

    # ── 4.5 确定性表名修正（语义引擎物理表名强制替换）──
    # LLM 可能幻觉出英文翻译表名（如 stations / wafers / batches），
    # 但 semantic_ctx 已精确知道真实物理表名，故在此做确定性后处理。
    if sql and semantic_ctx:
        sql = _enforce_physical_table_names(sql, semantic_ctx)
    # ── 4.6 确定性 EmbeddedJSON 语法修正──
    # 如果 LLM 仍然生成了 CROSS JOIN <表名>(...) 而不是 CROSS JOIN JSON_TABLE(...)，在此修正
    if sql:
        sql = _fix_embedded_json_syntax(sql, semantic_ctx)
    # ── 4.7 object_csv 格式双格式兼容修正 ──
    # 对 {"id":"77,79,105"} 格式字段（如 equipment_group.equipments）的错误 JSON_TABLE 展开做确定性修正
    if sql:
        sql = _fix_object_csv_json_joins(sql)
    # ── 4.8 equipment_group_list 等值/JSON_CONTAINS JOIN 修正 ──
    # equipment_group_list 是标量整数数组，必须 JSON_TABLE 展开，不能等值JOIN 或 JSON_CONTAINS
    if sql:
        sql = _fix_equipment_group_list_join(sql)
    # 读取本次 LLM 调用的 token 用量
    from app.services.llm_provider import get_last_llm_usage
    llm_usage = get_last_llm_usage()

    # ── 5. 更新 state ──
    new_retry_count = retry_count + 1 if sql_error else 0

    # ── 5.5 安全处理：去除末尾分号 ──
    if sql:
        sql = sql.strip().rstrip(';').strip()

    # ── Pipeline Trace ──
    trace = list(state.get("pipeline_trace", []))

    if sql:
        # 置信度计算：首次高，重试递减
        confidence = 0.88 if not sql_error else max(0.5, 0.8 - retry_count * 0.1)
        logger.info(f"[sql_generator] Generated SQL: {sql[:100]}...")
        trace_step(trace, "sql_generator", _t0, summary=(
            f"生成SQL成功, 置信度: {confidence:.2f}"
            + (f", 重试#{new_retry_count}" if new_retry_count else "")
        ), detail={
            "sql": sql,
            "confidence": confidence,
            "retry_count": new_retry_count,
            "has_semantic_context": bool(semantic_ctx),
            "has_few_shot": bool(few_shot_context),
        }, llm_tokens={
            "input": llm_usage.get("input_tokens", 0),
            "output": llm_usage.get("output_tokens", 0),
            "total": llm_usage.get("total_tokens", 0),
        })
        return {
            "sql": sql,
            "sql_confidence": confidence,
            "sql_retry_count": new_retry_count,
            "sql_error": "",  # 清除上一次的错误
            "rag_context": schema_ctx,
            "pipeline_trace": trace,
        }
    else:
        logger.warning("[sql_generator] Failed to generate SQL")
        trace_step(trace, "sql_generator", _t0,
                   summary="SQL 生成失败", status="error")
        return {
            "sql": "",
            "sql_confidence": 0.0,
            "sql_retry_count": new_retry_count,
            "error": "Failed to generate SQL from natural language input",
            "rag_context": schema_ctx,
            "pipeline_trace": trace,
        }


def _apply_metric_sql_template(
    semantic_ctx: dict, query_plan: dict, user_input: str
) -> str:
    """
    当语义上下文中存在带 sql_template 的指标时，直接展开模板返回 SQL。
    用 query_plan 和用户输入推断 {WHERE_EXTRA} 条件，完全绕过 LLM。
    返回空字符串表示没有适用模板。
    """
    if not semantic_ctx:
        return ""
    metrics = semantic_ctx.get("metrics", [])
    template_metric = None
    for m in (metrics or []):
        if m.get("sql_template"):
            template_metric = m
            break
    if not template_metric:
        return ""

    template = template_metric["sql_template"]

    # ── 构建 WHERE_EXTRA 条件列表 ──
    conditions: list[str] = []

    # 1. 时间范围
    time_range = query_plan.get("time_range") or ""
    _time_map = {
        "today":        "AND DATE(log.gmt_create) = CURDATE()",
        "yesterday":    "AND DATE(log.gmt_create) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)",
        "last_week":    "AND log.gmt_create >= DATE_SUB(NOW(), INTERVAL 7 DAY)",
        "last_month":   "AND log.gmt_create >= DATE_SUB(NOW(), INTERVAL 30 DAY)",
        "last_30_days": "AND log.gmt_create >= DATE_SUB(NOW(), INTERVAL 30 DAY)",
        "last_7_days":  "AND log.gmt_create >= DATE_SUB(NOW(), INTERVAL 7 DAY)",
        "this_week":    "AND YEARWEEK(log.gmt_create, 1) = YEARWEEK(CURDATE(), 1)",
        "this_month":   "AND DATE_FORMAT(log.gmt_create, '%Y-%m') = DATE_FORMAT(CURDATE(), '%Y-%m')",
    }
    if time_range and time_range in _time_map:
        conditions.append(_time_map[time_range])
    elif time_range and time_range not in ("all", ""):
        # 尝试解析 "YYYY-MM-DD ~ YYYY-MM-DD" 格式
        import re as _re
        _range_m = _re.search(r'(\d{4}-\d{2}-\d{2})\s*[~～\-]+\s*(\d{4}-\d{2}-\d{2})', time_range)
        if _range_m:
            conditions.append(
                f"AND log.gmt_create BETWEEN '{_range_m.group(1)}' AND '{_range_m.group(2)} 23:59:59'"
            )

    # 2. 工站/工序过滤（process_code / process_name / station）
    import re as _re
    filters = query_plan.get("filters", {}) or {}
    if isinstance(filters, dict):
        process_code = filters.get("process_code") or filters.get("station")
        process_name = filters.get("process_name") or filters.get("station_name")
        product_code = filters.get("product_code")
        lot_code = filters.get("lot_code")
    else:
        process_code = process_name = product_code = lot_code = None

    # 也尝试从 query_plan 顶层提取
    if not process_code:
        process_code = query_plan.get("process_code") or query_plan.get("station")
    if not product_code:
        product_code = query_plan.get("product_code")

    # 最后从 user_input 正则提取（优先字母开头的工站代码，其次纯中文工站名）
    if not process_code and not process_name:
        # 优先: 字母开头的工站代码（如 POL、CMP），可跟可选中文
        # 允许前后有中英文引号（如 "POL抛光"工站 或 "CMP"工站）
        _QL = r'[\u201c\u2018"\']'
        _QR = r'[\u201d\u2019"\']*'
        _C  = r'([A-Za-z][A-Za-z0-9]{0,9}(?:\s*[\u4e00-\u9fa5]{0,6})?)'
        station_m = _re.search(
            _QL + r'\s*' + _C + r'\s*' + _QR + r'\s*(?:工站|工序)'
            + r'|' + _C + r'\s*(?:工站|工序)',
            user_input
        )
        if station_m:
            process_name = (station_m.group(1) or station_m.group(2) or "").strip()
        else:
            # 退回: 纯中文工站名（排除时间/代词/通配词）
            station_m2 = _re.search(r'([\u4e00-\u9fa5]{2,8})\s*(?:工站|工序)', user_input)
            if station_m2:
                cand = station_m2.group(1)
                _SKIP = ('今天', '昨天', '本周', '上周', '本月', '上月', '最近', '这周',
                         '各', '所有', '全部', '每个', '每', '想看', '查询', '查看', '分析', '统计')
                if not any(s in cand for s in _SKIP):
                    process_name = cand

    if process_code:
        # 精确匹配
        safe = process_code.replace("'", "''")
        conditions.append(f"AND log.process_code = '{safe}'")
    elif process_name:
        safe = process_name.replace("'", "''")
        conditions.append(f"AND log.process_name LIKE '%{safe}%'")

    if product_code:
        safe = str(product_code).replace("'", "''")
        conditions.append(f"AND log.product_code = '{safe}'")

    where_extra = "\n    ".join(conditions)
    sql = template.replace("{WHERE_EXTRA}", where_extra)
    sql = sql.strip().rstrip(";").strip()
    logger.info(f"[sql_generator] sql_template 快速路径: metric={template_metric.get('metric_id')}, conditions={conditions}")
    return sql


def _extract_mandatory_table_constraint(semantic_ctx: dict) -> str:
    """
    从语义上下文中提取物理表名，生成强制约束文本，放在 prompt 最前面。
    这确保 LLM 不会使用英文猜测名（如 stations），而使用真实物理表名。
    """
    if not semantic_ctx:
        return ""
    classes = semantic_ctx.get("matched_classes", [])
    if not classes:
        return ""
    lines = []
    for c in classes:
        if c.get("virtual"):
            continue
        keyword = c.get("keyword") or c.get("label_cn", "")
        physical = c.get("physical_table", "")
        if physical and keyword:
            lines.append(f"  - 「{keyword}」→ 物理表: {physical}")
    if not lines:
        return ""
    return (
        "【强制表名约束 - 最高优先级】\n"
        "语义引擎已识别以下真实物理表名，必须在 SQL 中直接使用，"
        "禁止使用英文翻译或猜测名称（如 stations, equipment 等）：\n"
        + "\n".join(lines)
        + "\n"
    )


def _enforce_physical_table_names(sql: str, semantic_ctx: dict) -> str:
    """
    确定性表名修正：利用语义引擎已解析的物理表名，修正 LLM 幻觉出的表名。

    原理：
    - LLM 常把「站点」翻译为 stations，把「晶圆」翻译为 wafers 等
    - semantic_ctx.matched_classes 已精确记录了应使用的物理表名
    - 只要 SQL 中出现了不属于真实物理表的名称，就用语义匹配的物理表替换

    在 generate_sql 之后、sql_validator 之前执行。
    """
    if not sql or not semantic_ctx:
        return sql

    import re

    # 1. 从 semantic_ctx 获取本次查询涉及的物理表（非虚拟类）
    classes = semantic_ctx.get("matched_classes", [])
    physical_tables_from_semantic = []   # 有序列表，用于多表场景按顺序对应
    for c in classes:
        if not c.get("virtual") and c.get("physical_table"):
            physical_tables_from_semantic.append(c["physical_table"])

    if not physical_tables_from_semantic:
        return sql

    # 2. 加载所有合法物理表名（用于判断 SQL 中哪些表名是非法的）
    try:
        from app.ontology.mapping import get_mapping
        all_valid_tables = {
            t.table_name.lower()
            for t in get_mapping().list_physical_tables()
            if t.table_name
        }
    except Exception:
        all_valid_tables = {t.lower() for t in physical_tables_from_semantic}

    # 注意：不从 Supabase annotation_metadata 补充白名单，因为它可能包含旧 demo 表（如 stations）导致 LLM 幻觉表名无法被纠正

    # 3. 提取 SQL 中 FROM / JOIN 后的表名
    token_pattern = re.compile(
        r'\b(FROM|JOIN)\s+([\w_]+)', re.IGNORECASE
    )
    replacements = {}   # bad_name -> good_name

    for m in token_pattern.finditer(sql):
        tbl = m.group(2)
        if tbl.lower() in all_valid_tables:
            continue  # 合法，跳过
        # 非法表名：在 semantic 物理表中找最佳替换
        if len(physical_tables_from_semantic) == 1:
            replacement = physical_tables_from_semantic[0]
        else:
            from difflib import SequenceMatcher
            replacement = max(
                physical_tables_from_semantic,
                key=lambda t: SequenceMatcher(None, tbl.lower(), t.lower()).ratio(),
            )
        replacements[tbl] = replacement

    if not replacements:
        corrected = sql
    else:
        corrected = sql
        for bad, good in replacements.items():
            corrected = re.sub(
                rf'\b{re.escape(bad)}\b', good, corrected, flags=re.IGNORECASE
            )
            logger.info(
                f"[sql_generator] 确定性表名修正: {bad!r} → {good!r} (语义引擎)"
            )

    return corrected


def _fix_embedded_json_syntax(sql: str, semantic_ctx: dict) -> str:
    """
    确定性修正：LLM 有时把 JSON_TABLE() 误写成 CROSS JOIN <物理表名>(...)。
    检测到「CROSS JOIN <已知物理表>(」或「JOIN <已知物理表>(」时，
    将 <物理表名> 替换为 JSON_TABLE，保留括号内的参数不变。
    """
    if not sql:
        return sql

    import re

    # 加载本次查询的物理表名集合（及全局合法表名）
    try:
        from app.ontology.mapping import get_mapping
        all_valid_tables = {
            t.table_name.lower()
            for t in get_mapping().list_physical_tables()
            if t.table_name
        }
    except Exception:
        all_valid_tables = set()

    # 补充 semantic_ctx 中的物理表
    if semantic_ctx:
        for c in semantic_ctx.get("matched_classes", []):
            if c.get("physical_table"):
                all_valid_tables.add(c["physical_table"].lower())

    if not all_valid_tables:
        return sql

    # 匹配: CROSS JOIN <tablename>( 或 JOIN <tablename>(
    # 其中 <tablename> 是已知物理表名（而非 JSON_TABLE 自身）
    pattern = re.compile(
        r'\b(CROSS\s+JOIN|JOIN)\s+([\w_]+)\s*\(',
        re.IGNORECASE,
    )

    def replacer(m: re.Match) -> str:
        join_kw = m.group(1)
        tbl = m.group(2)
        if tbl.lower() == 'json_table':
            return m.group(0)  # 已经正确，不替换
        if tbl.lower() in all_valid_tables:
            logger.warning(
                f"[sql_generator] EmbeddedJSON语法修正: "
                f"CROSS JOIN {tbl}( → CROSS JOIN JSON_TABLE("
            )
            return f"CROSS JOIN JSON_TABLE("
        return m.group(0)

    return pattern.sub(replacer, sql)


def _fix_equipment_group_list_join(sql: str) -> str:
    """
    确定性修正：equipment_group_list 是 JSON 整数数组（如 [1, 2]），
    必须用 JSON_TABLE 展开，而非等值 JOIN / JSON_CONTAINS。

    修正以下错误模式：
      ① JOIN equipment_group eg ON p.equipment_group_list = eg.id
      ② JOIN equipment_group eg ON JSON_CONTAINS(p.equipment_group_list, CAST(eg.id AS JSON)...)
    统一替换为：
      CROSS JOIN JSON_TABLE(p.equipment_group_list, '$[*]'
          COLUMNS (eg_id BIGINT PATH '$')) AS jt_eg
      INNER JOIN equipment_group eg ON eg.id = jt_eg.eg_id
    """
    if not sql or "equipment_group" not in sql.lower():
        return sql
    if "equipment_group_list" not in sql.lower():
        return sql

    import re

    # 提取 matrix_routerx_config_process 的别名
    from_alias_m = re.search(
        r'\bFROM\s+matrix_routerx_config_process\s+(\w+)',
        sql, re.IGNORECASE
    )
    p_alias = from_alias_m.group(1) if from_alias_m else "p"

    # 模式①: (LEFT|INNER|CROSS|) JOIN equipment_group <eg_alias> ON <any>.equipment_group_list = <eg_alias>.id
    pat_eq = re.compile(
        r'(?:LEFT\s+|INNER\s+|CROSS\s+)?JOIN\s+equipment_group\s+(\w+)\s+ON\s+'
        r'(?:\w+\.)?equipment_group_list\s*=\s*\w+\.id',
        re.IGNORECASE,
    )
    # 模式②: (LEFT|INNER|CROSS|) JOIN equipment_group <eg_alias> ON JSON_CONTAINS(... equipment_group_list ...)
    pat_jc = re.compile(
        r'(?:LEFT\s+|INNER\s+|CROSS\s+)?JOIN\s+equipment_group\s+(\w+)\s+ON\s+'
        r'JSON_CONTAINS\s*\([^)]*equipment_group_list[^)]*\)',
        re.IGNORECASE,
    )

    def _replacement(eg_alias: str) -> str:
        logger.warning(
            f"[sql_generator] equipment_group_list JOIN修正: "
            f"错误等值/JSON_CONTAINS → JSON_TABLE展开"
        )
        return (
            f"CROSS JOIN JSON_TABLE({p_alias}.equipment_group_list, '$[*]' "
            f"COLUMNS (eg_id BIGINT PATH '$')) AS jt_eg "
            f"INNER JOIN equipment_group {eg_alias} ON {eg_alias}.id = jt_eg.eg_id"
        )

    result = pat_eq.sub(lambda m: _replacement(m.group(1)), sql)
    result = pat_jc.sub(lambda m: _replacement(m.group(1)), result)
    return result


def _fix_object_csv_json_joins(sql: str) -> str:
    """
    双格式兼容修正（安全网）：当 LLM 仍然对 object_csv 格式的 JSON 字段
    （如 equipment_group.equipments，实际格式 {"id":"77,79,105"}）
    误用 JSON_TABLE($[*]) 展开时，确定性替换为正确的 FIND_IN_SET 写法。

    错误模式:
      CROSS JOIN JSON_TABLE(eg.equipments, '$[*]' COLUMNS (e_id BIGINT PATH '$')) AS jt_e
      INNER JOIN equipment e ON e.id = jt_e.e_id
    修正为:
      INNER JOIN equipment e
        ON FIND_IN_SET(CAST(e.id AS CHAR),
           JSON_UNQUOTE(JSON_EXTRACT(eg.equipments, '$.id'))) > 0
    """
    if not sql or "equipments" not in sql.lower():
        return sql

    import re

    # Step 1: 捕获并移除 CROSS JOIN JSON_TABLE(<eg_alias>.equipments, '$[*]'...) AS <jt_alias>
    jt_pattern = re.compile(
        r"CROSS\s+JOIN\s+JSON_TABLE\s*\(\s*(\w+)\.equipments\s*,"
        r"\s*[\'\"]?\$\[\*\][\'\"]?\s+COLUMNS\s*\([^)]+\)\s*\)\s+AS\s+(\w+)",
        re.IGNORECASE | re.DOTALL,
    )
    matches = list(jt_pattern.finditer(sql))
    if not matches:
        return sql

    eg_alias = matches[0].group(1)
    jt_alias = matches[0].group(2)
    sql_step1 = jt_pattern.sub("", sql)

    # Step 2: 将 INNER JOIN equipment <e_alias> ON <e_alias>.id = <jt_alias>.<col>
    #         替换为 FIND_IN_SET 写法
    ij_pattern = re.compile(
        r"INNER\s+JOIN\s+equipment\s+(\w+)\s+ON\s+\1\.id\s*=\s*"
        + re.escape(jt_alias) + r"\.\w+",
        re.IGNORECASE,
    )

    def _replace_ij(m: re.Match) -> str:
        e_alias = m.group(1)
        logger.warning(
            f"[sql_generator] object_csv双格式修正: "
            f"JSON_TABLE({eg_alias}.equipments,'$[*]') "
            f"→ FIND_IN_SET({e_alias}.id,...) > 0"
        )
        return (
            f"INNER JOIN equipment {e_alias} ON "
            f"FIND_IN_SET(CAST({e_alias}.id AS CHAR), "
            f"JSON_UNQUOTE(JSON_EXTRACT({eg_alias}.equipments, '$.id'))) > 0"
        )

    sql_step2 = ij_pattern.sub(_replace_ij, sql_step1)
    # 清理因移除 CROSS JOIN 行产生的多余空行
    sql_step2 = re.sub(r"\n(\s*\n){2,}", "\n\n", sql_step2)
    return sql_step2


def _build_optimized_query(
    user_input: str, query_plan: dict, schema_ctx: str,
    few_shot_ctx: str = "", semantic_ctx: dict = None,
) -> str:
    """
    结合 query_plan 的结构化信息、Schema 上下文、语义上下文和 few-shot 案例优化自然语言查询。
    """
    # 强制表名约束放在最前面，优先级最高
    mandatory_constraint = _extract_mandatory_table_constraint(semantic_ctx)
    if mandatory_constraint:
        parts = [mandatory_constraint, user_input]
    else:
        parts = [user_input]

    table = query_plan.get("table")
    if table:
        parts.append(f"(目标表: {table})")

    metrics = query_plan.get("metrics", [])
    if metrics:
        parts.append(f"(指标: {', '.join(metrics)})")

    time_range = query_plan.get("time_range")
    if time_range:
        parts.append(f"(时间范围: {time_range})")

    limit = query_plan.get("limit")
    if limit:
        parts.append(f"(限制 {limit} 条)")

    equipment = query_plan.get("equipment")
    if equipment:
        parts.append(f"(设备: {equipment})")

    # Phase 3: 注入语义引擎的结构化上下文
    if semantic_ctx:
        semantic_section = _format_semantic_context(semantic_ctx)
        if semantic_section:
            parts.append(f"\n\n{semantic_section}")

    # 注入 Schema 上下文
    if schema_ctx:
        parts.append(f"\n\n{schema_ctx}")

    # Phase D: 注入 few-shot SQL 案例
    if few_shot_ctx:
        parts.append(f"\n\n[参考 SQL 案例]\n{few_shot_ctx}")

    return " ".join(parts)


def _build_correction_context(
    previous_sql: str, error: str, retry_count: int, schema_ctx: str,
    semantic_ctx: dict = None,
) -> str:
    """
    构建智能错误修正上下文。

    根据错误类型提供不同的修正指导。
    """
    # 分析错误类型
    error_lower = error.lower()

    guidance = []

    if "not found" in error_lower or "does not exist" in error_lower:
        guidance.append("表名或列名不存在。请参照下方 Schema 使用正确的名称。")
        # 注入语义引擎的物理表名映射，帮助 LLM 修正
        mandatory = _extract_mandatory_table_constraint(semantic_ctx)
        if mandatory:
            guidance.append(mandatory)
    elif "validation" in error_lower:
        guidance.append("SQL 预验证失败。请参照 Schema 修正表名/列名。")
    elif "syntax" in error_lower:
        guidance.append("SQL 语法错误。请检查语法是否正确。")
    elif "permission" in error_lower or "denied" in error_lower:
        guidance.append("权限不足。请确保只使用 SELECT 查询。")
    elif "timeout" in error_lower:
        guidance.append("查询超时。请简化查询，添加 LIMIT 或减少数据量。")
    else:
        guidance.append("请分析错误原因并修正 SQL。")

    if retry_count >= 2:
        guidance.append(
            "这是最后一次重试机会！请使用最保守的查询方式，"
            "确保表名和列名完全匹配 Schema。"
        )

    return (
        f"Previous SQL:\n{previous_sql}\n\n"
        f"Error:\n{error}\n\n"
        f"修正指导: {' '.join(guidance)}\n\n"
        f"{schema_ctx}"
    )


def _generate_multi_step_sql(
    user_input: str, query_plan: dict, schema_ctx: str, semantic_ctx: dict = None,
) -> str:
    """
    为多步查询生成合并的 SQL。

    策略:
    1. 如果 sub_queries 可以用 CTE 合并 → 生成单个 CTE SQL
    2. 否则 → 生成第一个子查询的 SQL（后续子查询在 Phase C 实现）
    """
    sub_queries = query_plan.get("sub_queries", [])
    merge_strategy = query_plan.get("merge_strategy", "独立展示")

    if not sub_queries:
        # fallback: 正常生成
        return generate_sql.invoke({
            "natural_language": user_input,
            "error_context": "",
        })

    # 构建多步提示
    steps_desc = []
    for sq in sub_queries:
        step = sq.get("step", "?")
        desc = sq.get("description", "")
        hint = sq.get("sql_hint", "")
        steps_desc.append(f"  步骤{step}: {desc}" + (f" (提示: {hint})" if hint else ""))

    # Phase 3: 从语义引擎获取业务规则和过滤条件
    semantic_rules_section = ""
    if semantic_ctx:
        rules = semantic_ctx.get("business_rules", [])
        filters = semantic_ctx.get("filters", [])
        joins = semantic_ctx.get("joins", [])
        rule_lines = []
        if filters:
            for f in filters:
                cond = f.get("physical_condition") or ""
                desc = f.get("description", "")
                if cond:
                    rule_lines.append(f"- {desc}: {cond}")
                elif f.get("physical_values"):
                    vals = ", ".join(f"'{v}'" for v in f["physical_values"])
                    tbl = f.get("applies_to_table", "?")
                    col = f.get("applies_to_column", "?")
                    rule_lines.append(f"- {desc}: {tbl}.{col} IN ({vals})")
                else:
                    # 语义提示 — 物理枚举值尚未在 mapping 中配置
                    tbl = f.get("applies_to_table")
                    col = f.get("applies_to_column")
                    sv  = f.get("semantic_value")
                    if tbl and col and sv:
                        rule_lines.append(
                            f"- {desc or sv}: 必须对 {tbl}.{col} 加 WHERE 过滤，"
                            f"语义值为 '{sv}'（请根据实际枚举值填写正确的 WHERE 条件）"
                        )
        if rules:
            for r in rules:
                rule_lines.append(f"- {r.get('name', '')}: {r.get('description', '')}")
                if r.get("sql_example"):
                    rule_lines.append(f"  参考SQL模板: {r['sql_example']}")
        if joins:
            rule_lines.append("- JOIN 条件:")
            for j in joins:
                for c in j.get("conditions", []):
                    rule_lines.append(f"    {c['from']} = {c['to']}")
        if rule_lines:
            semantic_rules_section = "\\n".join(rule_lines)

    multi_prompt = (
        f"{user_input}\n\n"
        f"这是一个多维度查询，涉及以下方面:\n"
        f"{''.join(steps_desc)}\n"
        f"合并策略: {merge_strategy}\n\n"
        f"【强制 SQL 格式要求】\n"
        f"1. 禁止使用 WITH (CTE) 子句\n"
        f"2. 禁止使用关联子查询（SELECT 中嵌套 SELECT）\n"
        f"3. 必须使用 JOIN + WHERE ... IN (...) + GROUP BY 模式\n"
        f"4. 将所有维度合并为一个 SQL 查询，用 WHERE ... IN 筛选多个值\n"
        f"5. 不要在 SQL 末尾加分号\n"
        f"6. 中文名称匹配使用 name 列，不要用 code 列\n\n"
        f"【业务领域知识（来自语义引擎）】\n"
        f"- 在制品(WIP)数量 = COUNT(DISTINCT wafers.id) 晶圆实例数，不是 COUNT(sub_batches.id)！（batch→sub_batch一对多会导致wafer行重复，必须DISTINCT去重）\n"
        f"  WIP状态通过 sub_batches.status != 'completed' 过滤\n"
        f"  v2 JOIN路径(优先): wafers.sublot_id → sub_batches.id → stations(current_station_id=id)\n"
        f"  也可: wafers→batches(batch_id=id)→sub_batches(batch_id)→stations(current_station_id=id)\n"
        f"- wafers 表已包含 sublot_id, carrier_id, slot_number, wafer_type，直接外键关联\n"
        f"- process_route_stations 是工艺路线定义表，不含在制品数据\n"
    )

    if semantic_rules_section:
        multi_prompt += f"{semantic_rules_section}\n"

    multi_prompt += (
        f"\n【标准模板】\n"
        f"SELECT a.name AS 名称, COUNT(b.id) AS 数量\n"
        f"FROM 主表 a\n"
        f"LEFT JOIN 关联表 b ON a.id = b.外键\n"
        f"WHERE a.name IN ('值1', '值2', '值3')\n"
        f"GROUP BY a.name\n"
        f"ORDER BY a.name\n\n"
        f"{schema_ctx}"
    )

    logger.info(f"[sql_generator] Generating multi-step SQL: "
                f"{len(sub_queries)} steps, strategy={merge_strategy}")

    return generate_sql.invoke({
        "natural_language": multi_prompt,
        "error_context": "",
    })


# ══════════════════════════════════════════════
#  Phase D: RAG 辅助函数
# ══════════════════════════════════════════════

def _get_schema_context_with_rag(user_input: str) -> str:
    """
    获取 schema 上下文，优先使用 RAG，降级到 schema_tools。
    RAG 调用超时3秒则降级。
    """
    import concurrent.futures

    def _do_rag():
        from app.agent.tools.rag_tools import rag_search_schema, _rag_available
        if not _rag_available():
            return None
        return rag_search_schema.invoke({"query": user_input, "top_k": 4})

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_do_rag)
            try:
                ctx = fut.result(timeout=3.0)
                if ctx and len(ctx) > 20:
                    logger.info(f"[sql_generator] Using RAG schema context ({len(ctx)} chars)")
                    return ctx
            except concurrent.futures.TimeoutError:
                logger.warning("[sql_generator] RAG schema lookup timed out (3s), using schema_tools")
            except Exception as e:
                logger.debug(f"[sql_generator] RAG schema lookup failed: {e}")
    except Exception as e:
        logger.debug(f"[sql_generator] RAG executor failed: {e}")

    # 降级
    return get_schema_context.invoke({"user_input": user_input})


def _get_sql_few_shots(user_input: str) -> str:
    """
    Phase D: 检索历史 SQL 案例作为 few-shot 参考。
    如果 RAG 不可用或无结果或超时，返回空字符串。
    """
    import concurrent.futures

    def _do_rag():
        from app.agent.tools.rag_tools import rag_search_sql_examples, _rag_available
        if not _rag_available():
            return None
        return rag_search_sql_examples.invoke({"query": user_input, "top_k": 2})

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_do_rag)
            try:
                examples = fut.result(timeout=3.0)
                if examples and "用户问题:" in examples:
                    logger.info("[sql_generator] SQL few-shot examples retrieved")
                    return examples
            except concurrent.futures.TimeoutError:
                logger.debug("[sql_generator] SQL few-shot lookup timed out")
            except Exception as e:
                logger.debug(f"[sql_generator] SQL few-shot lookup failed: {e}")
    except Exception as e:
        logger.debug(f"[sql_generator] few-shot executor failed: {e}")

    return ""


# ══════════════════════════════════════════════
#  Phase 3: 语义引擎辅助函数
# ══════════════════════════════════════════════

def _merge_semantic_schema(semantic_snippet: str, rag_schema: str) -> str:
    """
    合并语义引擎的精准 schema 片段与 RAG/schema_tools 的通用 schema。
    语义引擎的片段放在最前面（最相关），RAG 作为补充。
    """
    parts = ["[语义引擎推荐 Schema（高优先级）]", semantic_snippet]
    if rag_schema:
        parts.append("")
        parts.append("[补充 Schema 上下文]")
        parts.append(rag_schema)
    return "\n".join(parts)


def _format_semantic_context(semantic_ctx: dict) -> str:
    """
    将 SemanticContext dict 格式化为 LLM 可读的文本段落。
    """
    if not semantic_ctx:
        return ""

    lines = ["[语义引擎分析结果]"]

    # 匹配的逻辑类
    classes = semantic_ctx.get("matched_classes", [])
    if classes:
        class_strs = [
            f"{c['label_cn']}→{c.get('physical_table', '虚拟')}"
            for c in classes
        ]
        lines.append(f"涉及实体: {', '.join(class_strs)}")
        # 同表多类 filter_condition — 必须加入 WHERE 子句，不可省略
        # 先按 (table, column) 分组，相同表+列的等值条件合并为 IN (...)
        import re as _re
        from collections import defaultdict as _defaultdict
        _fc_groups: dict = _defaultdict(list)  # (tbl, col) -> [(label_cn, raw_val)]
        _fc_others: list = []  # 无法解析为等值条件的，直接输出
        for c in classes:
            fc = c.get("filter_condition")
            tbl = c.get("physical_table")
            if not (fc and tbl):
                continue
            m = _re.match(r"^(\w+)\s*=\s*(\S+)$", fc.strip())
            if m:
                col, val = m.group(1), m.group(2)
                _fc_groups[(tbl, col)].append((c["label_cn"], val))
            else:
                _fc_others.append((c["label_cn"], tbl, fc))
        for (tbl, col), entries in _fc_groups.items():
            labels = "、".join(e[0] for e in entries)
            vals = ", ".join(e[1] for e in entries)
            if len(entries) == 1:
                cond = f"{col} = {vals}"
            else:
                cond = f"{col} IN ({vals})"
            lines.append(
                f"  ⚠ 【强制WHERE条件】{labels}({tbl}) 必须加 WHERE/AND {cond}"
                f"（同表多类区分，缺少此条件会把其他类型的行也查出来）"
            )
        for label_cn, tbl, fc in _fc_others:
            lines.append(
                f"  ⚠ 【强制WHERE条件】{label_cn}({tbl}) 必须加 WHERE/AND {fc}"
                f"（同表多类区分，缺少此条件会把其他类型的行也查出来）"
            )

    # JOIN 条件
    joins = semantic_ctx.get("joins", [])
    if joins:
        lines.append("关联路径:")
        for j in joins:
            strategy = j.get("strategy", "")
            for c in j.get("conditions", []):
                if strategy == "EmbeddedJSON":
                    # 不输出 表名.JSON列->>key 格式，避免 LLM 把表名当函数名
                    # 正: 'src_table.json_col' 中抽取表名和列名，key 单独列出
                    from_parts = c["from"].split(".")
                    src_table = from_parts[0] if from_parts else c["from"]
                    json_col_key = from_parts[1] if len(from_parts) > 1 else ""
                    to_parts = c["to"].split(".")
                    tgt_table = to_parts[0] if to_parts else c["to"]
                    tgt_col = to_parts[1] if len(to_parts) > 1 else "id"
                    # json_col_key 格式: processes->>id，分离列和key
                    if "->>'" in json_col_key:
                        json_col, json_key = json_col_key.split("->>'", 1)
                        json_key = json_key.rstrip("'")
                        is_scalar_array = False
                    elif "->>" in json_col_key:
                        json_col, json_key = json_col_key.split("->>")
                        is_scalar_array = False
                    else:
                        # 无 ->> 说明 from_key 就是列名本身，数组元素是标量整数（非对象）
                        json_col = json_col_key
                        json_key = "id"
                        is_scalar_array = True
                    lines.append(
                        f"  [EmbeddedJSON展开] 源表={src_table}, JSON列={json_col}, "
                        + (f"数组元素=整数ID, " if is_scalar_array else f"数组元素键={json_key}, ")
                        + f"关联目标={tgt_table}.{tgt_col}"
                    )
                    # ── 双格式兼容：detect object_csv 格式（note 中含 FIND_IN_SET 声明）──
                    _join_note = j.get("note", "")
                    if "FIND_IN_SET" in _join_note.upper():
                        # 该 JSON 字段实际是对象格式（如 {"id":"77,79,105"}），不是数组
                        lines.append(
                            f"  ⚠ 【重要 - 非数组格式】{json_col} 字段存储为 JSON 对象"
                            f"（如 {{\"id\":\"77,79,105\"}}），"
                            f"禁止使用 JSON_TABLE({src_table}别名.{json_col}, '$[*]')！"
                            f"必须用 FIND_IN_SET 写法："
                            f"INNER JOIN {tgt_table} {tgt_table[0]} "
                            f"ON FIND_IN_SET(CAST({tgt_table[0]}.{tgt_col} AS CHAR), "
                            f"JSON_UNQUOTE(JSON_EXTRACT({src_table}别名.{json_col}, '$.{json_key}'))) > 0"
                        )
                    elif is_scalar_array:
                        # 标量整数数组（如 [1,2]），每个元素直接是 ID，必须用 PATH '$'
                        lines.append(
                            f"  ⚠ 展开该 JSON 整数数组（元素直接是整数ID，如[1,2]）必须用 JSON_TABLE：\n"
                            f"  CROSS JOIN JSON_TABLE({src_table}别名.{json_col}, '$[*]' "
                            f"COLUMNS (eg_id BIGINT PATH '$')) AS jt_eg\n"
                            f"  INNER JOIN {tgt_table} ON {tgt_table}.{tgt_col} = jt_eg.eg_id\n"
                            f"  ⛔ 禁止写 {src_table}别名.{json_col} = {tgt_table}.{tgt_col} 等值JOIN！"
                            f"禁止使用 JSON_CONTAINS！"
                        )
                    else:
                        lines.append(
                            f"  ⚠ 展开该 JSON 数组必须用 MySQL 内置函数 JSON_TABLE（不是表名）："
                            f"CROSS JOIN JSON_TABLE({src_table}别名.{json_col}, '$[*]' "
                            f"COLUMNS (seq FOR ORDINALITY, {json_key} INT PATH '$.{json_key}')) AS jt "
                            f"INNER JOIN {tgt_table} ON {tgt_table}.{tgt_col} = jt.{json_key} ORDER BY jt.seq"
                        )
                else:
                    lines.append(f"  {c['from']} = {c['to']}")
            if j.get("note"):
                lines.append(f"  [{strategy}提示] {j['note']}")
            if not j.get("conditions") and j.get("note"):
                lines.append(f"  [{strategy}提示] {j['note']}")

    # 过滤条件
    filters = semantic_ctx.get("filters", [])
    if filters:
        lines.append("语义过滤:")
        for f in filters:
            cond = f.get("physical_condition")
            if cond:
                lines.append(
                    f"  ⚠ 【强制WHERE条件】 {f.get('description', '')}: "
                    f"必须在WHERE子句中直接使用 {cond}"
                )
            elif f.get("physical_values"):
                vals = ", ".join(f"'{v}'" for v in f["physical_values"])
                tbl = f.get("applies_to_table", "?")
                col = f.get("applies_to_column", "?")
                lines.append(f"  {f.get('description', '')}: {tbl}.{col} IN ({vals})")
            else:
                # 语义提示 — 物理枚举值尚未配置（TODO），给出语义线索供 LLM 参考
                tbl = f.get("applies_to_table")
                col = f.get("applies_to_column")
                sv  = f.get("semantic_value")
                if tbl and col and sv:
                    lines.append(
                        f"  ⚠ {f.get('description', sv)}: "
                        f"{tbl}.{col} 语义值 = '{sv}'（物理枚举待确认，必须加 WHERE 条件）"
                    )
            # COUNT 目标提醒 — 关键区分 WIP 统计对象
            ct_table = f.get("count_target_table")
            ct_col = f.get("count_target_column")
            if ct_table and ct_col:
                lines.append(
                    f"  ⚠ COUNT 统计对象: COUNT(DISTINCT {ct_table}.{ct_col})，不是 COUNT({f.get('applies_to_table', '?')}.id)（JOIN可能产生重复行，必须DISTINCT去重）"
                )

    # 指标定义（Phase 2: metric_definitions）
    metrics = semantic_ctx.get("metrics", [])
    if metrics:
        lines.append("【指标定义 — 必须按此公式生成SQL，禁止猜测计算方式】:")
        for m in metrics:
            compute_mode = m.get("compute_mode", "sql_aggregate")
            lines.append(f"  📊 {m.get('metric_id', '')}: {m.get('description', '')}")
            if compute_mode == "python_compute":
                # Python 计算模式 — SQL 只需取明细数据
                lines.append(f"    ℹ️ 【Python计算模式】此指标由Python计算引擎处理，SQL仅需获取明细数据（不需要 GROUP BY 聚合）。")
                if m.get('sql_template'):
                    lines.append(f"    参考明细SQL模板（CTE内的SELECT部分为所需明细字段）:")
                    lines.append(f"    ```sql")
                    lines.append(f"    {m['sql_template']}")
                    lines.append(f"    ```")
            elif m.get('sql_template'):
                # 有预构建 SQL 模板的复杂指标 — LLM 必须基于模板生成
                lines.append(f"    ⚠⚠ 【预构建SQL模板 — 必须使用此模板，仅替换 {{WHERE_EXTRA}} 占位符为用户条件】:")
                lines.append(f"    ```sql")
                lines.append(f"    {m['sql_template']}")
                lines.append(f"    ```")
                lines.append(f"    {{WHERE_EXTRA}} 占位符说明: 用户指定的过滤条件(如产品/时间/工站)以 AND ... 格式追加，无额外条件时替换为空字符串")
            else:
                lines.append(f"    公式: {m.get('formula', '')}")
                lines.append(f"    锚点表: {m.get('anchor_table', '')}")
                if m.get('join_path'):
                    lines.append(f"    JOIN路径: {m.get('join_path', '')}")
                if m.get('auto_filter'):
                    lines.append(f"    ⚠ 必含WHERE/AND条件: {m.get('auto_filter', '')}")
            if m.get('granularity'):
                gran = m['granularity']
                if isinstance(gran, list):
                    gran = ', '.join(gran)
                lines.append(f"    支持维度(GROUP BY): {gran}")

    # 业务规则
    rules = semantic_ctx.get("business_rules", [])
    if rules:
        lines.append("【业务规则约束 — 路径/过滤约束，不要照搬示例SQL】:")
        for r in rules:
            lines.append(f"  ⚠ {r.get('name', '')}: {r.get('description', '')}")
            if r.get("sql_example"):
                lines.append(
                    f"    ↳ 路径示例(仅供JOIN路径参考，必须根据实际查询的维度/指标重新组合，"
                    f"禁止直接复制此SQL):"
                )
                lines.append(f"    {r['sql_example']}")

    return "\n".join(lines) if len(lines) > 1 else ""
