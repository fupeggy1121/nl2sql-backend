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

        # ── Pipeline Trace ──
        trace = list(state.get("pipeline_trace", []))
        trace_step(trace, "semantic_resolver", t0, summary=(
            f"匹配 {n_classes} 个本体类, {n_joins} 个JOIN, "
            f"{n_filters} 个过滤条件, 物理表: {tables}"
        ), detail={
            "matched_classes": ctx_dict.get("matched_classes", []),
            "joins": ctx_dict.get("joins", []),
            "filters": ctx_dict.get("filters", []),
            "business_rules": ctx_dict.get("business_rules", []),
            "physical_tables": tables,
        })

        return {"semantic_context": ctx_dict, "pipeline_trace": trace}

    except Exception as e:
        logger.error(f"[semantic_resolver] Failed: {e}", exc_info=True)
        # Graceful fallback — 不阻塞后续节点
        trace = list(state.get("pipeline_trace", []))
        trace_step(trace, "semantic_resolver", t0, summary=f"语义解析失败: {e}", status="error")
        return {"semantic_context": {}, "pipeline_trace": trace}
