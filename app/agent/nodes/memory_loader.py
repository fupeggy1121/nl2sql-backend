"""
memory_loader — 对话记忆加载节点 (Phase C)

图入口的第一个节点。在意图路由之前执行:
1. 从 ConversationMemory 加载会话上下文
2. 判断是否为追问 (指代查询)
3. 执行指代消解，将上下文注入到 state

位置: memory_loader → intent_router → ...
"""

import logging
from app.agent.state import AgentState
from app.agent.memory import conversation_memory

logger = logging.getLogger(__name__)


def memory_loader_node(state: AgentState) -> dict:
    """
    对话记忆加载节点。
    输入: user_input, session_id, conversation_history (可选，来自客户端)
    输出: memory_context, is_followup, resolved_input, conversation_history
    """
    user_input = state.get("user_input", "")
    session_id = state.get("session_id", "")
    client_history = state.get("conversation_history", [])

    if not session_id:
        logger.debug("[memory_loader] No session_id, skipping memory")
        return {
            "memory_context": {},
            "is_followup": False,
            "resolved_input": user_input,
        }

    # ── 1. 获取或创建会话 ──
    session = conversation_memory.get_or_create_session(session_id)

    # ── 2. 如果客户端传了 conversation_history 但本地为空，同步到内存 ──
    if client_history and not session.turns:
        _sync_client_history(session, client_history)

    # ── 3. 获取 LLM 上下文 ──
    ctx = conversation_memory.get_context_for_llm(session_id, user_input)

    is_followup = ctx["is_followup"]
    resolved_input = ctx["resolved_input"]

    # ── 4. 合并消息列表: 服务端记忆 > 客户端传入 ──
    if session.turns:
        merged_history = ctx["recent_messages"]
    else:
        merged_history = client_history or []

    logger.info(
        f"[memory_loader] session={session_id}, "
        f"turns={len(session.turns)}, "
        f"is_followup={is_followup}, "
        f"history_msgs={len(merged_history)}"
    )

    return {
        "memory_context": ctx,
        "is_followup": is_followup,
        "resolved_input": resolved_input if is_followup else user_input,
        "conversation_history": merged_history,
    }


def _sync_client_history(session, client_history: list):
    """将客户端传来的历史同步到 SessionMemory"""
    from app.agent.memory import ConversationTurn
    i = 0
    while i < len(client_history):
        msg = client_history[i]
        if msg.get("role") == "user":
            user_msg = msg.get("content", "")
            assistant_msg = ""
            # 看下一条是否为 assistant
            if i + 1 < len(client_history) and client_history[i + 1].get("role") == "assistant":
                assistant_msg = client_history[i + 1].get("content", "")
                i += 1
            session.add_turn(ConversationTurn(
                user_message=user_msg,
                assistant_message=assistant_msg,
            ))
        i += 1
