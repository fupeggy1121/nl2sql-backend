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

    # ── 1. 获取 Schema 上下文（优先使用 RAG，降级为 schema_tools）──
    schema_ctx = state.get("rag_context", "")
    if not schema_ctx:
        schema_ctx = _get_schema_context_with_rag(user_input)

    # ── 1.5 Phase D: 检索 SQL few-shot 案例 ──
    few_shot_context = _get_sql_few_shots(user_input)

    # ── 2. 构建优化后的 NL 查询 ──
    nl_query = _build_optimized_query(user_input, query_plan, schema_ctx, few_shot_context)

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
        sql = _generate_multi_step_sql(user_input, query_plan, schema_ctx)
    else:
        sql = generate_sql.invoke({
            "natural_language": nl_query,
            "error_context": error_context,
        })

    # ── 5. 更新 state ──
    new_retry_count = retry_count + 1 if sql_error else 0

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
    user_input: str, query_plan: dict, schema_ctx: str, few_shot_ctx: str = "",
) -> str:
    """
    结合 query_plan 的结构化信息、Schema 上下文和 few-shot 案例优化自然语言查询。
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
    user_input: str, query_plan: dict, schema_ctx: str
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

    multi_prompt = (
        f"{user_input}\n\n"
        f"这是一个复杂查询，需要以下步骤:\n"
        f"{''.join(steps_desc)}\n"
        f"合并策略: {merge_strategy}\n\n"
        f"请尽量使用 CTE (WITH 子句) 或子查询将多步合并为一个 SQL。\n"
        f"如果无法合并，优先生成最核心的查询。\n\n"
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
