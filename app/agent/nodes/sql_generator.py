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
from app.agent.state import AgentState
from app.agent.tools.nl2sql_tools import generate_sql
from app.agent.tools.schema_tools import get_schema_context

logger = logging.getLogger(__name__)


def sql_generator_node(state: AgentState) -> dict:
    """
    SQL 生成节点 (Phase C 增强)。
    输入: user_input, resolved_input, is_followup, query_plan, memory_context,
          sql_error (可选), sql_retry_count (可选)
    输出: sql, sql_confidence, sql_retry_count, rag_context
    """
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
            previous_sql, sql_error, retry_count, schema_ctx
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

    # ── 5. 更新 state ──
    new_retry_count = retry_count + 1 if sql_error else 0

    # ── 5.5 安全处理：去除末尾分号 ──
    if sql:
        sql = sql.strip().rstrip(';').strip()

    if sql:
        # 置信度计算：首次高，重试递减
        confidence = 0.88 if not sql_error else max(0.5, 0.8 - retry_count * 0.1)
        logger.info(f"[sql_generator] Generated SQL: {sql[:100]}...")
        return {
            "sql": sql,
            "sql_confidence": confidence,
            "sql_retry_count": new_retry_count,
            "sql_error": "",  # 清除上一次的错误
            "rag_context": schema_ctx,
        }
    else:
        logger.warning("[sql_generator] Failed to generate SQL")
        return {
            "sql": "",
            "sql_confidence": 0.0,
            "sql_retry_count": new_retry_count,
            "error": "Failed to generate SQL from natural language input",
            "rag_context": schema_ctx,
        }


def _build_optimized_query(
    user_input: str, query_plan: dict, schema_ctx: str,
    few_shot_ctx: str = "", semantic_ctx: dict = None,
) -> str:
    """
    结合 query_plan 的结构化信息、Schema 上下文、语义上下文和 few-shot 案例优化自然语言查询。
    """
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
    previous_sql: str, error: str, retry_count: int, schema_ctx: str
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
        if rules:
            for r in rules:
                rule_lines.append(f"- {r.get('name', '')}: {r.get('description', '')}")
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
        f"  JOIN路径: wafers→batches(batch_id=id)→sub_batches(batch_id)→stations(current_station_id=id)\n"
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
    """
    try:
        from app.agent.tools.rag_tools import rag_search_schema, _rag_available

        if _rag_available():
            ctx = rag_search_schema.invoke({
                "query": user_input,
                "top_k": 4,
            })
            if ctx and len(ctx) > 20:
                logger.info(f"[sql_generator] Using RAG schema context ({len(ctx)} chars)")
                return ctx
    except Exception as e:
        logger.debug(f"[sql_generator] RAG schema lookup failed: {e}")

    # 降级
    return get_schema_context.invoke({"user_input": user_input})


def _get_sql_few_shots(user_input: str) -> str:
    """
    Phase D: 检索历史 SQL 案例作为 few-shot 参考。
    如果 RAG 不可用或无结果，返回空字符串。
    """
    try:
        from app.agent.tools.rag_tools import rag_search_sql_examples, _rag_available

        if _rag_available():
            examples = rag_search_sql_examples.invoke({
                "query": user_input,
                "top_k": 2,
            })
            if examples and "用户问题:" in examples:
                logger.info("[sql_generator] SQL few-shot examples retrieved")
                return examples
    except Exception as e:
        logger.debug(f"[sql_generator] SQL few-shot lookup failed: {e}")

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

    # JOIN 条件
    joins = semantic_ctx.get("joins", [])
    if joins:
        lines.append("关联路径:")
        for j in joins:
            for c in j.get("conditions", []):
                lines.append(f"  {c['from']} = {c['to']}")

    # 过滤条件
    filters = semantic_ctx.get("filters", [])
    if filters:
        lines.append("语义过滤:")
        for f in filters:
            cond = f.get("physical_condition")
            if cond:
                lines.append(f"  {f.get('description', '')}: {cond}")
            elif f.get("physical_values"):
                vals = ", ".join(f"'{v}'" for v in f["physical_values"])
                tbl = f.get("applies_to_table", "?")
                col = f.get("applies_to_column", "?")
                lines.append(f"  {f.get('description', '')}: {tbl}.{col} IN ({vals})")
            # COUNT 目标提醒 — 关键区分 WIP 统计对象
            ct_table = f.get("count_target_table")
            ct_col = f.get("count_target_column")
            if ct_table and ct_col:
                lines.append(
                    f"  ⚠ COUNT 统计对象: COUNT(DISTINCT {ct_table}.{ct_col})，不是 COUNT({f.get('applies_to_table', '?')}.id)（JOIN可能产生重复行，必须DISTINCT去重）"
                )

    # 业务规则
    rules = semantic_ctx.get("business_rules", [])
    if rules:
        lines.append("业务规则提醒:")
        for r in rules:
            lines.append(f"  ⚠ {r.get('name', '')}: {r.get('description', '')}")

    return "\n".join(lines) if len(lines) > 1 else ""
