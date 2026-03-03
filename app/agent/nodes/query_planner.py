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
        # 取第一个（主表）作为 query_plan.table
        query_plan["table"] = physical_tables[0]
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

    return {
        "query_plan": query_plan,
        "rag_context": rag_context,
        "pipeline_trace": trace,
    }


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
