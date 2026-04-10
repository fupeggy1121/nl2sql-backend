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
      multi_sql_merge : 同时提及 mapping_prod.json 中 estimated_rows:large 标记的 2+ 张大表
      sql_then_python  : 明确要求行列转置/透视表
    """
    import re

    text = user_input.lower()

    # ── 规则 1: 两张大表同时出现 → multi_sql_merge ──
    # 大表集合从 mapping_prod.json 的 estimated_rows:"large" 动态读取，
    # 并扩展到与大表直接 JOIN 且共享同一业务前缀的 via_table（如 batch_resume_log_detail）。
    try:
        from app.ontology.mapping import get_mapping
        _m = get_mapping()
        _large_tables: set[str] = {
            pt.table_name
            for pt in _m.list_physical_tables()
            if pt.estimated_rows == "large" and pt.table_name
        }
        # 扩展：把与大表 JOIN 且共享 resume 业务前缀的 via_table 也纳入大表集合
        _RESUME_PREFIX = "matrix_routerx_operation_lot_batch_resume"
        for _rel in _m.list_all_relations():
            for _jc in _rel.join_conditions:
                if _jc.from_table in _large_tables and _jc.to_table.startswith(_RESUME_PREFIX):
                    _large_tables.add(_jc.to_table)
                if _jc.to_table in _large_tables and _jc.from_table.startswith(_RESUME_PREFIX):
                    _large_tables.add(_jc.from_table)
    except Exception:
        _large_tables = set()

    matched_tables = [t for t in _large_tables if t.lower() in text]
    if len(matched_tables) >= 2:
        decomposed = _decompose_query_for_multi_sql(user_input, matched_tables)
        if decomposed:
            return decomposed
        # LLM 拆解失败时降级到空骨架（sql_generator 兜底）
        return {
            "mode": "multi_sql_merge",
            "sqls": [],
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

    # ── 规则 3: 跨数据源实体同时出现 → multi_source_compute ──
    # 检测用户是否同时提及属于不同 source_id 的实体（如 MES 产出 + 设备停机）
    try:
        from app.ontology.mapping import get_mapping
        from app.config.data_sources import DataSourceRegistry, DEFAULT_SOURCE_ID
        _m2 = get_mapping()
        _registry = DataSourceRegistry.get_instance()
        _source_ids_in_query: set[str] = set()
        for _pt in _m2.list_physical_tables():
            sid = _pt.source_id or DEFAULT_SOURCE_ID
            if _pt.table_name and _pt.table_name.lower() in text:
                _source_ids_in_query.add(sid)
            elif _pt.label_cn and _pt.label_cn in user_input:
                _source_ids_in_query.add(sid)
        if len(_source_ids_in_query) >= 2 and _registry.has("equip_mgmt"):
            return {
                "mode": "multi_source_compute",
                "source_ids": list(_source_ids_in_query),
                "sqls": [],
                "merges": [],
                "postprocess": [],
                "primary_result": "production",
                "_forced": True,
                "_trigger": "cross_source_entities",
            }
    except Exception:
        pass

    return None
    """从 SQL 中提取主表名"""
    import re
    m = re.search(r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql, re.IGNORECASE)
    return m.group(1) if m else ""


def _decompose_query_for_multi_sql(
    user_input: str,
    large_tables: "list[str]",
) -> "dict | None":
    """
    额外一次轻量 LLM 调用，把涉及多张大表的查询拆解为子查询描述列表。
    返回带 _decomposed=True 标记的骨架 ExecutionPlan（sql 字段为空，sql_generator 填充）。
    拆解失败（LLM 错误/JSON 解析失败）时返回 None，外层降级到空骨架。
    """
    import re as _re
    import json as _json
    from app.agent.tools.schema_tools import _get_schema_metadata

    # 查询两张大表的真实列名，注入 prompt 防止幻觉
    _meta = {}
    try:
        _meta = _get_schema_metadata().get("tables", {})
    except Exception:
        pass

    def _table_cols_text(table_name: str) -> str:
        cols = [c["name"] for c in _meta.get(table_name, {}).get("columns", [])]
        if cols:
            return f"    真实字段: {', '.join(cols[:20])}"
        return ""

    tables_text = "\n".join(
        f"  - {t}\n{_table_cols_text(t)}" for t in large_tables
    )
    prompt = f"""你是 SQL 查询拆解器。用户查询涉及以下大表，生产环境查询超时限制 30s，直接 JOIN 大表会触发全表扫描导致超时，必须拆分为独立子查询后在 Python 层合并：
{tables_text}

用户查询：{user_input}

⚠️ 重要约束：hint 字段里的字段名必须来自上方"真实字段"列表，严禁使用 lot_batch_id/product_code/process_time 等虚构列名。
将查询拆解为 2-3 个独立子查询，每个子查询只查一张大表（可关联其他小维度表）。
返回 JSON（仅 JSON，无其他内容）：
{{
  "sqls": [
    {{"id": "s1", "table": "表名", "purpose": "这步查什么", "hint": "需要哪些真实字段，过滤条件"}},
    {{"id": "s2", "table": "表名", "purpose": "这步查什么", "hint": "需要哪些真实字段，过滤条件"}}
  ],
  "merges": [
    {{"id": "m1", "left": "s1", "right": "s2", "on": ["关联键字段名（必须是真实存在的字段）"], "how": "inner"}}
  ],
  "primary_result": "m1"
}}"""

    try:
        from app.agent.llm import get_llm
        llm = get_llm()
        resp = llm.invoke(prompt)
        content = resp.content if hasattr(resp, "content") else str(resp)
        m = _re.search(r"\{.*\}", content, _re.DOTALL)
        if not m:
            logger.warning(f"[query_planner] _decompose_query_for_multi_sql: no JSON in response: {content[:120]!r}")
            return None
        decomposed = _json.loads(m.group())
        sqls = decomposed.get("sqls", [])
        if not sqls:
            logger.warning("[query_planner] _decompose_query_for_multi_sql: empty sqls list")
            return None
        plan = {
            "mode": "multi_sql_merge",
            "sqls": [
                {
                    "id": s["id"],
                    "sql": "",          # sql_generator 填充
                    "purpose": s.get("purpose", ""),
                    "hint": s.get("hint", ""),
                    "table": s.get("table", ""),
                    "depends_on": [],
                }
                for s in sqls
            ],
            "merges": decomposed.get("merges", []),
            "primary_result": decomposed.get("primary_result", "m1"),
            "_forced": True,
            "_trigger": "large_table_pair",
            "_decomposed": True,
        }
        logger.info(
            f"[query_planner] _decompose_query_for_multi_sql success: "
            f"{len(sqls)} sub-queries, merges={len(plan['merges'])}"
        )
        return plan
    except Exception as e:
        logger.warning(f"[query_planner] _decompose_query_for_multi_sql failed: {e}")
        return None


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
