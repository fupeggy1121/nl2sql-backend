"""
semantic_resolver — 语义解析节点 (Phase 3: 本体引擎集成)

在 intent_router → query_planner 之间插入，职责：
  1. 从用户输入提取关键词 → 匹配本体类
  2. 发现类间路径 → 翻译为物理 JOIN 条件
  3. 识别语义值 → 映射为 SQL 过滤条件
  4. 匹配业务规则
  5. 将 SemanticContext 注入 AgentState.semantic_context

设计原则：
  - 纯 Python 确定性规则引擎，0 LLM 调用
  - 快速（< 5ms）、稳定、可测试
  - 失败时 graceful fallback：写入空 {} 而不阻塞流程
"""

import logging
import time
from typing import Dict, Any

from app.agent.state import AgentState
from app.agent.trace import trace_step
from app.agent.cache import semantic_cache

logger = logging.getLogger(__name__)


def semantic_resolver_node(state: AgentState) -> Dict[str, Any]:
    """
    语义解析节点。

    输入: user_input, resolved_input, is_followup
    输出: semantic_context (dict)
    """
    user_input = state.get("user_input", "")
    resolved_input = state.get("resolved_input", "") or user_input
    is_followup = state.get("is_followup", False)

    # 追问时使用消解后的输入
    effective_input = resolved_input if is_followup else user_input

    if not effective_input:
        logger.warning("[semantic_resolver] Empty input, skipping")
        return {"semantic_context": {}}

    # ── B2: 语义缓存查找（追问不使用缓存，避免上下文依赖）──
    _cache_key = effective_input
    _cache_hit = False
    if not is_followup:
        _cached_ctx = semantic_cache.get(_cache_key)
        if _cached_ctx is not None:
            _cache_hit = True
            logger.info(f"[semantic_resolver] Cache HIT for: {effective_input[:60]}")
            # 构建返回：不需要 trace，直接返回缓存值
            trace = list(state.get("pipeline_trace", []))
            t0_cache = time.perf_counter()
            trace_step(trace, "semantic_resolver", t0_cache, summary=(
                f"[缓存] " + _cached_ctx.get("_summary", "")
            ), detail={
                "cache_hit": True,
                "matched_classes": _cached_ctx.get("matched_classes", []),
                "physical_tables": _cached_ctx.get("physical_tables", []),
                "business_rules": _cached_ctx.get("business_rules", []),
            })
            extra: Dict[str, Any] = {}
            if _cached_ctx.get("_fast_path"):
                extra["sql"] = _cached_ctx["_fast_sql"]
                extra["fast_path"] = True
                extra["fast_sql_source"] = _cached_ctx.get("_fast_sql_source", "business_rule")
            return {"semantic_context": _cached_ctx, "pipeline_trace": trace, **extra}

    try:
        t0 = time.perf_counter()

        from app.ontology.context_builder import build_semantic_context

        ctx = build_semantic_context(effective_input)
        ctx_dict = ctx.to_dict()

        elapsed_ms = (time.perf_counter() - t0) * 1000
        n_classes = len(ctx.matched_classes)
        n_joins = len(ctx.joins)
        n_filters = len(ctx.filters)
        n_rules = len(ctx.business_rules)
        tables = ctx.physical_tables

        logger.info(
            f"[semantic_resolver] Resolved in {elapsed_ms:.1f}ms — "
            f"classes={n_classes}, joins={n_joins}, filters={n_filters}, "
            f"rules={n_rules}, tables={tables}"
        )

        # ── B1: Fast Path 检测 — 业务规则自带 SQL 模板 ──
        fast_path = False
        fast_sql = ""
        fast_sql_source = ""
        for rule in ctx.business_rules:
            if rule.physical_sql_template:
                fast_path = True
                fast_sql = rule.physical_sql_template
                fast_sql_source = f"business_rule:{rule.id}"
                logger.info(
                    f"[semantic_resolver] Fast Path activated by rule '{rule.id}': "
                    f"{fast_sql[:60]}..."
                )
                break  # 取第一个匹配规则

        # ── Pipeline Trace ──
        trace = list(state.get("pipeline_trace", []))
        fast_note = " [★快速通道]" if fast_path else ""
        trace_step(trace, "semantic_resolver", t0, summary=(
            f"匹配 {n_classes} 个本体类, {n_joins} 个JOIN, "
            f"{n_filters} 个过滤条件, 物理表: {tables}{fast_note}"
        ), detail={
            "matched_classes": ctx_dict.get("matched_classes", []),
            "joins": ctx_dict.get("joins", []),
            "filters": ctx_dict.get("filters", []),
            "business_rules": ctx_dict.get("business_rules", []),
            "physical_tables": tables,
            "fast_path": fast_path,
            **({"+fast_sql_source": fast_sql_source} if fast_path else {}),
        })

        # ── B2: 写入语义缓存（追问不缓存）──
        # 将 fast_path 信息一并存进缓存，方便缓存命中时知道是否快速通道
        if not is_followup:
            _summary = (
                f"匹配 {n_classes} 个本体类, {n_joins} 个JOIN, "
                f"{n_filters} 个过滤条件, 物理表: {tables}{fast_note}"
            )
            ctx_dict["_summary"] = _summary
            ctx_dict["_fast_path"] = fast_path
            ctx_dict["_fast_sql"] = fast_sql
            ctx_dict["_fast_sql_source"] = fast_sql_source
            semantic_cache.set(_cache_key, ctx_dict)

        result: Dict[str, Any] = {"semantic_context": ctx_dict, "pipeline_trace": trace}
        if fast_path:
            result["sql"] = fast_sql
            result["fast_path"] = True
            result["fast_sql_source"] = fast_sql_source
        return result

    except Exception as e:
        logger.error(f"[semantic_resolver] Failed: {e}", exc_info=True)
        # Graceful fallback — 不阻塞后续节点
        trace = list(state.get("pipeline_trace", []))
        trace_step(trace, "semantic_resolver", t0, summary=f"语义解析失败: {e}", status="error")
        return {"semantic_context": {}, "pipeline_trace": trace}
