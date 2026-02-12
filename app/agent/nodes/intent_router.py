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
}


def intent_router_node(state: AgentState) -> dict:
    """
    意图路由节点 (Phase C 增强)。
    输入: user_input, resolved_input, is_followup, conversation_history, memory_context
    输出: intent, intent_data, start_time
    """
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

    # 调用意图识别 Tool
    intent_data = classify_intent.invoke({"user_input": effective_input})

    # 映射意图到路由
    raw_intent = intent_data.get("intent", "direct_query")
    route = INTENT_ROUTE_MAP.get(raw_intent, "query")

    logger.info(
        f"[intent_router] Intent: {raw_intent} → route: {route}, "
        f"confidence: {intent_data.get('confidence', 0):.2f}"
    )

    return {
        "intent": route,
        "intent_data": intent_data,
        "start_time": time.time(),
    }
