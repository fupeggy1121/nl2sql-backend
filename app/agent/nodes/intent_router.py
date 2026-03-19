"""
intent_router — 意图路由节点

分析用户输入，分类意图，决定后续走哪条分支。
支持多轮对话上下文：如果有 conversation_history，
会让 LLM 结合上下文理解追问意图。
"""

import logging
import time
from app.agent.state import AgentState
from app.agent.tools.intent_tools import classify_intent
from app.agent.trace import trace_step
from app.agent.cache import intent_cache

logger = logging.getLogger(__name__)

# 意图到 Agent 路由的映射
INTENT_ROUTE_MAP = {
    "direct_query": "query",
    "query_production": "query",
    "query_quality": "query",
    "query_equipment": "query",
    "generate_report": "query",
    "compare_analysis": "query",
    "chat": "chat",                    # Phase D: 路由到 rag_chat 节点
    "knowledge_qa": "chat",            # Phase D: 知识问答
    "explain": "chat",                 # Phase D: 解释说明类
    "write_action": "action",          # Phase E: 写操作 → action_executor
}


def intent_router_node(state: AgentState) -> dict:
    """
    意图路由节点 (Phase C 增强)。
    输入: user_input, resolved_input, is_followup, conversation_history, memory_context
    输出: intent, intent_data, start_time
    """
    # 快速路径: approved_sql 模式（前端直接提交已批准的 SQL 执行）
    # 跳过 LLM 意图分类，直接强制 intent = "query"
    if state.get("approved_sql"):
        _t0 = time.perf_counter()
        trace = list(state.get("pipeline_trace", []))
        # 保留前端传入的 query_type（来自上一轮 query 的意图识别结果），
        # 确保 result_analyzer 规则引擎能正确推荐图表类型（e.g. LIST→table）
        prior_query_type = (state.get("intent_data") or {}).get("query_type", "")
        trace_step(trace, "intent_router", _t0,
                   summary="approved_sql 模式: 跳过意图分类, 直接执行已批准的 SQL",
                   detail={"raw_intent": "direct_query", "route": "query",
                           "confidence": 1.0, "approved_sql_mode": True,
                           "preserved_query_type": prior_query_type})
        return {
            "intent": "query",
            "intent_data": {
                "intent": "direct_query",
                "confidence": 1.0,
                "entities": {},
                "query_type": prior_query_type,  # 传递给 result_analyzer
            },
            "start_time": time.time(),
            "pipeline_trace": trace,
        }

    user_input = state.get("user_input", "")
    resolved_input = state.get("resolved_input", "") or user_input
    is_followup = state.get("is_followup", False)
    conversation_history = state.get("conversation_history", [])
    memory_context = state.get("memory_context", {})

    logger.info(
        f"[intent_router] Processing: {user_input[:80]}... "
        f"(followup={is_followup})"
    )

    # Phase C: 如果是追问，使用消解后的输入
    effective_input = resolved_input if is_followup else user_input

    # 如果有对话历史，将上下文拼接到输入中
    if conversation_history:
        recent = conversation_history[-6:]
        context_parts = []
        for msg in recent:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:
                context_parts.append(f"[{role}]: {content}")
        if context_parts:
            context_str = "\n".join(context_parts)
            effective_input = f"对话上下文:\n{context_str}\n\n当前问题: {effective_input}"

    # ── B2: 意图缓存 (追问不使用缓存，避免上下文依赖) ──
    _cache_key = user_input  # 用原始输入做 key，避免上下文拼接干扰
    _t0 = time.perf_counter()
    _cache_hit = False

    if not is_followup:
        _cached = intent_cache.get(_cache_key)
        if _cached is not None:
            intent_data = _cached
            _cache_hit = True
            logger.info(f"[intent_router] Cache HIT for: {user_input[:60]}")

    if not _cache_hit:
        # 调用意图识别 Tool（LLM 或规则）
        intent_data = classify_intent.invoke({"user_input": effective_input})
        # 写入缓存（追问不缓存）
        if not is_followup:
            intent_cache.set(_cache_key, intent_data)

    # 映射意图到路由
    raw_intent = intent_data.get("intent", "direct_query")
    route = INTENT_ROUTE_MAP.get(raw_intent, "query")

    logger.info(
        f"[intent_router] Intent: {raw_intent} → route: {route}, "
        f"confidence: {intent_data.get('confidence', 0):.2f}, "
        f"cache={'HIT' if _cache_hit else 'MISS'}"
    )

    # P1: 读取新结构化字段
    query_type = intent_data.get("query_type", "LIST")
    target_class_hints = intent_data.get("target_class_hints", [])
    semantic_filters = intent_data.get("semantic_filters", [])

    # ── Pipeline Trace ──
    trace = list(state.get("pipeline_trace", []))
    trace_step(trace, "intent_router", _t0, summary=(
        f"意图: {raw_intent} → {route} [{query_type}]"
        f", 置信度: {intent_data.get('confidence', 0):.2f}"
        + (f", 类: {target_class_hints}" if target_class_hints else "")
        + (" [缓存]" if _cache_hit else "")
    ), detail={
        "raw_intent": raw_intent,
        "route": route,
        "confidence": intent_data.get("confidence", 0),
        "entities": intent_data.get("entities", {}),
        # P1: 新字段
        "query_type": query_type,
        "target_class_hints": target_class_hints,
        "semantic_filters": semantic_filters,
        "cache_hit": _cache_hit,
    })

    return {
        "intent": route,
        "intent_data": intent_data,
        "intent_slots": intent_data.get("intent_slots", {}),
        "start_time": time.time(),
        "pipeline_trace": trace,
    }
