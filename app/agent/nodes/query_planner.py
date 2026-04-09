"""
query_planner — 查询规划节点 (Phase D RAG 增强版)

"想清楚怎么查"而不是"去查"。
从意图识别结果提取结构化查询参数，为 SQL 生成做准备。

Phase D 新增:
- 使用 RAG 向量检索替代全量 schema 加载
- 检索相关表的 schema 上下文并注入 state
- 检索历史 SQL 案例作为 few-shot 参考
"""

import logging
import time
from app.agent.state import AgentState
from app.agent.trace import trace_step

logger = logging.getLogger(__name__)


def query_planner_node(state: AgentState) -> dict:
    """
    查询规划节点 (Phase C 增强)。
    输入: user_input, resolved_input, is_followup, intent_data, memory_context
    输出: query_plan
    """
    user_input = state.get("user_input", "")
    resolved_input = state.get("resolved_input", "") or user_input
    is_followup = state.get("is_followup", False)
    intent_data = state.get("intent_data", {})
    memory_context = state.get("memory_context", {})

    # Phase C: 追问时使用消解后的输入
    effective_input = resolved_input if is_followup else user_input

    _t0 = time.perf_counter()
    logger.info(
        f"[query_planner] Building plan for: {effective_input[:60]}... "
        f"(followup={is_followup})"
    )

    # 从意图识别结果中提取结构化参数
    entities = intent_data.get("entities", {})

    query_plan = {
        "natural_language": effective_input,
        "intent_type": intent_data.get("intent", "direct_query"),
        "confidence": intent_data.get("confidence", 0.0),
        "table": entities.get("table"),
        "metrics": entities.get("metrics", []),
        "time_range": entities.get("timeRange"),
        "equipment": entities.get("equipment"),
        "product_line": entities.get("productLine"),
        "limit": entities.get("limit"),
        "filters": entities.get("filters", {}),
        # P1: 结构化查询类型（LIST/COUNT/AGGREGATE/TREND）
        "query_type": intent_data.get("query_type", "LIST"),
        # P1: 语义过滤器（来自 intent_router 的 LLM 分析）
        "semantic_filters": intent_data.get("semantic_filters", []),
        # Phase C: 对话上下文
        "is_followup": is_followup,
        "conversation_context": memory_context.get("context_summary", ""),
    }

    # Phase 3: 优先用 semantic_resolver 已解析的物理表名覆盖 intent 中的原始文本实体
    # semantic_context.physical_tables = ["carrier"] 比 entities.table = "可用的片篮列" 更准确
    semantic_context = state.get("semantic_context", {})
    physical_tables = semantic_context.get("physical_tables", [])
    if physical_tables:
        # 如果 intent 提供了 target_class_hints，优先选择与 hint 类对应的物理表，
        # 避免因字母排序导致错误域表排在首位（如 material < warehouse_input_record_bill_detail）
        target_hints = intent_data.get("target_class_hints", [])
        selected_table = None
        if target_hints:
            try:
                from app.ontology.mapping import get_mapping
                mapping = get_mapping()
                for hint_class in target_hints:
                    pt = mapping.get_physical_table(hint_class)
                    if pt and pt.table_name and pt.table_name in physical_tables:
                        selected_table = pt.table_name
                        logger.info(
                            f"[query_planner] Hint-selected table: {selected_table} "
                            f"(via {hint_class})"
                        )
                        break
            except Exception as _hint_err:
                logger.debug(f"[query_planner] Hint table lookup failed: {_hint_err}")
        query_plan["table"] = selected_table or physical_tables[0]
        if len(physical_tables) > 1:
            query_plan["all_tables"] = physical_tables

    # Phase C: 追问时尝试从上轮继承缺失的表名
    if is_followup and not query_plan["table"]:
        last_ctx = memory_context.get("last_query_context", {})
        last_sql = last_ctx.get("last_sql", "")
        if last_sql:
            inferred_table = _extract_table_from_sql(last_sql)
            if inferred_table:
                query_plan["table"] = inferred_table
                logger.info(f"[query_planner] Inherited table from last query: {inferred_table}")

    # ── Slot Filling 补充: 用 intent_slots 填充 limit / metric / sort_order ──
    # intent_slots 由意图识别器的 LLM 槽填充产出，比 entities 更细粒度、更精确
    try:
        from app.models.intent_slots import IntentSlots
        _slots = IntentSlots.from_dict(intent_data.get("intent_slots", {}))
        # limit_n: Top N 查询，如 intent 没有提取到 limit 时使用槽值
        if _slots.limit_n and not query_plan.get("limit"):
            query_plan["limit"] = _slots.limit_n
            logger.info(f"[query_planner] Slot-filled limit: {_slots.limit_n}")
        # metric: 聚合指标，如 intent 没有提取到 metrics 时使用槽值
        if _slots.metric and not query_plan.get("metrics"):
            query_plan["metrics"] = [_slots.metric]
            logger.info(f"[query_planner] Slot-filled metric: {_slots.metric}")
        # sort_order: 排序方向
        if _slots.sort_order and not query_plan.get("sort_order"):
            query_plan["sort_order"] = _slots.sort_order
            logger.info(f"[query_planner] Slot-filled sort_order: {_slots.sort_order}")
        # dimension_by: GROUP BY 维度（便于 sql_generator 参考）
        if _slots.dimension_by and not query_plan.get("group_by"):
            query_plan["group_by"] = _slots.dimension_by
            logger.info(f"[query_planner] Slot-filled group_by: {_slots.dimension_by}")
    except Exception as _slot_err:
        logger.debug(f"[query_planner] intent_slots enrichment skipped: {_slot_err}")

    # 安全守卫：只有用户明确说出数量词时才保留 limit，否则一律清除 LLM 幻觉
    # LLM 对 carrier/lot 等宽泛查询经常臆造 limit，导致截断
    import re as _re_planner
    if query_plan.get("limit"):
        _has_explicit_limit = _re_planner.search(
            r'前\s*\d+|[Tt]op\s*\d+|限制\s*\d+|取\s*\d+\s*条|最多\s*\d+',
            effective_input
        )
        if not _has_explicit_limit:
            logger.info(
                f"[query_planner] No explicit limit keyword in input — "
                f"clearing hallucinated limit={query_plan['limit']}"
            )
            query_plan["limit"] = None

    logger.info(f"[query_planner] Plan: table={query_plan['table']}, "
                f"metrics={query_plan['metrics']}")

    # ── 快速路径: approved_sql 模式——sql_generator 直接使用已批准SQL，无需RAG上下文 ──
    if state.get("approved_sql") and not state.get("sql_error"):
        trace = list(state.get("pipeline_trace", []))
        trace_step(trace, "query_planner", _t0,
                   summary="approved_sql 模式: 跳过RAG检索，不需要查询规划",
                   detail={"approved_sql_mode": True, "skipped": True})
        return {"query_plan": query_plan, "rag_context": "", "pipeline_trace": trace}

    # ── Phase D: RAG 检索 schema 上下文 ──
    # 优先用物理表名 + 原始 NL 双路检索，提升命中率
    rag_query = effective_input
    if physical_tables:
        rag_query = " ".join(physical_tables) + " " + effective_input
    rag_context = _retrieve_rag_context(rag_query)

    # ── Pipeline Trace ──
    trace = list(state.get("pipeline_trace", []))
    resolved_table = query_plan.get("table") or "自动推断"
    raw_table = entities.get("table") or ""
    table_display = resolved_table if not raw_table or resolved_table == raw_table \
        else f"{resolved_table} (原始: {raw_table})"
    trace_step(trace, "query_planner", _t0, summary=(
        f"目标表: {table_display}, "
        f"指标: {query_plan['metrics'] or '无'}, "
        f"RAG上下文: {'有' if rag_context else '无'}"
    ), detail={
        "table": query_plan.get("table"),
        "raw_table_from_intent": raw_table or None,
        "physical_tables_from_ontology": physical_tables or None,
        "metrics": query_plan.get("metrics", []),
        "time_range": query_plan.get("time_range"),
        "filters": query_plan.get("filters", {}),
        "is_followup": is_followup,
        "rag_context_length": len(rag_context) if rag_context else 0,
    })

    # ── 第一层: 确定性执行模式预判 ──────────────────────────────────────────
    # 在 SQL 生成前锁定 mode，避免 LLM 在已知复杂场景下仍生成单条 JOIN SQL。
    # 只有当前不处于重试循环（即 sql_error 为空）且无 approved_sql 时才预判。
    forced_plan = None
    if not state.get("sql_error") and not state.get("approved_sql"):
        forced_plan = _detect_forced_execution_plan(effective_input)
        if forced_plan:
            logger.info(
                f"[query_planner] 强制执行模式: mode={forced_plan['mode']} "
                f"(trigger={forced_plan.get('_trigger', '?')})"
            )

    out: dict = {
        "query_plan": query_plan,
        "rag_context": rag_context,
        "pipeline_trace": trace,
    }
    if forced_plan is not None:
        out["execution_plan"] = forced_plan
    return out


def _detect_forced_execution_plan(user_input: str) -> "dict | None":
    """
    第一层决策：确定性关键词扫描，预判执行模式。
    命中则返回骨架 ExecutionPlan dict（含 _forced=True 标记）；未命中返回 None。

    触发规则：
      multi_sql_merge : 同时提及两张已知大表
      sql_then_python  : 明确要求行列转置/透视表
    """
    import re

    text = user_input.lower()

    # ── 规则 1: 两张 resume 大表同时出现 → multi_sql_merge ──
    LARGE_TABLE_A = "matrix_routerx_operation_lot_batch_resume_log_detail"
    LARGE_TABLE_B = "matrix_routerx_operation_lot_batch_resume_wafer_detail_log"
    if LARGE_TABLE_A.lower() in text and LARGE_TABLE_B.lower() in text:
        return {
            "mode": "multi_sql_merge",
            "sqls": [],   # sql_generator 负责填充
            "merges": [],
            "postprocess": [],
            "primary_result": "m1",
            "_forced": True,
            "_trigger": "large_table_pair",
        }

    # ── 规则 2: 透视表 / pivot 明确需求 → sql_then_python ──
    PIVOT_PATTERNS = [
        r"透视表",
        r"行\s*[=＝=]\s*\S+.*?列\s*[=＝=]",  # 行=工站，列=日期
        r"pivot",
        r"行列转[置换]",
        r"转[置换]为.{0,10}表",
        r"列[为是]\S+.{0,6}行[为是]\S+",
    ]
    for pat in PIVOT_PATTERNS:
        if re.search(pat, user_input, re.IGNORECASE):
            return {
                "mode": "sql_then_python",
                "sqls": [],
                "merges": [],
                "postprocess": [{"operation": "pivot", "params": {}}],
                "primary_result": "s1",
                "_forced": True,
                "_trigger": f"pivot_keyword:{pat[:20]}",
            }

    return None


def _extract_table_from_sql(sql: str) -> str:
    """从 SQL 中提取主表名"""
    import re
    m = re.search(r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql, re.IGNORECASE)
    return m.group(1) if m else ""


def _retrieve_rag_context(user_input: str) -> str:
    """
    Phase D: 使用 RAG 检索相关 schema 上下文。
    如果 RAG 不可用或超时（3s），降级到旧的关键词匹配。
    """
    import concurrent.futures

    def _do_rag():
        from app.agent.tools.rag_tools import rag_search, _rag_available
        if not _rag_available():
            return None
        return rag_search.invoke({
            "query": user_input,
            "doc_type": "schema",
            "top_k": 4,
        })

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_do_rag)
            try:
                context = fut.result(timeout=3.0)
                if context:
                    logger.info(f"[query_planner] RAG context retrieved ({len(context)} chars)")
                    return context
            except concurrent.futures.TimeoutError:
                logger.warning("[query_planner] RAG call timed out (3s), falling back to schema_tools")
            except Exception as e:
                logger.debug(f"[query_planner] RAG call failed: {e}")
    except Exception as e:
        logger.debug(f"[query_planner] RAG executor failed: {e}")

    # 降级到旧的 schema_tools
    try:
        from app.agent.tools.schema_tools import get_schema_context
        return get_schema_context.invoke({"user_input": user_input})
    except Exception as e:
        logger.debug(f"[query_planner] schema_tools fallback failed: {e}")
        return ""

    except Exception as e:
        logger.warning(f"[query_planner] RAG retrieval failed, using fallback: {e}")
        try:
            from app.agent.tools.schema_tools import get_schema_context
            return get_schema_context.invoke({"user_input": user_input})
        except Exception:
            return ""
