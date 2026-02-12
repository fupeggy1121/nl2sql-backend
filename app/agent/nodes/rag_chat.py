"""
rag_chat — RAG 知识问答节点 (Phase D)

处理 chat 意图：基于 RAG 知识库回答用户关于数据库 schema、
业务规则、表结构等的问题，不需要执行 SQL。

位置: intent_router → (chat) → rag_chat → response_builder
"""

import logging
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


def rag_chat_node(state: AgentState) -> dict:
    """
    RAG 知识问答节点 (Phase D)。
    输入: user_input, resolved_input, is_followup, memory_context
    输出: response (直接构建聊天回复)
    """
    user_input = state.get("user_input", "")
    resolved_input = state.get("resolved_input", "") or user_input
    is_followup = state.get("is_followup", False)

    effective_input = resolved_input if is_followup else user_input

    logger.info(f"[rag_chat] Processing: {effective_input[:80]}...")

    # 尝试 RAG 检索
    answer = _generate_rag_answer(effective_input)

    if answer:
        response = {
            "success": True,
            "message": answer,
            "intent": "chat",
            "source": "rag",
        }
    else:
        response = {
            "success": True,
            "message": _generate_fallback_answer(effective_input),
            "intent": "chat",
            "source": "fallback",
        }

    logger.info(f"[rag_chat] Response generated ({len(response.get('message', ''))} chars)")
    return {"response": response}


def _generate_rag_answer(user_input: str) -> str:
    """
    使用 RAG 检索 + LLM 生成回答。
    """
    try:
        from app.agent.tools.rag_tools import rag_search, _rag_available

        if not _rag_available():
            return ""

        # 从知识库检索相关文档
        context = rag_search.invoke({
            "query": user_input,
            "doc_type": "",  # 搜索所有类型
            "top_k": 5,
        })

        if not context or len(context) < 20:
            return ""

        # 使用 LLM 基于检索到的上下文生成回答
        from app.agent.llm import get_agent_llm

        llm = get_agent_llm()
        prompt = (
            f"你是一个 MES（制造执行系统）的智能助手。\n"
            f"请根据以下知识库信息回答用户的问题。\n"
            f"如果知识库没有相关信息，请如实告诉用户。\n"
            f"回答要简洁专业，使用中文。\n\n"
            f"【知识库信息】\n{context}\n\n"
            f"【用户问题】\n{user_input}\n\n"
            f"【回答】"
        )

        response = llm.invoke(prompt)
        answer = response.content if hasattr(response, "content") else str(response)
        return answer.strip()

    except Exception as e:
        logger.error(f"[rag_chat] RAG answer generation failed: {e}")
        return ""


def _generate_fallback_answer(user_input: str) -> str:
    """
    RAG 不可用时的降级回答：
    使用 LLM 直接回答，但提醒可能不准确。
    """
    try:
        from app.agent.llm import get_agent_llm

        llm = get_agent_llm()
        prompt = (
            f"你是一个 MES（制造执行系统）的智能助手。\n"
            f"用户问了一个关于系统的问题，但你没有检索到相关知识。\n"
            f"请尽力回答，但如果不确定请告诉用户。\n\n"
            f"【用户问题】\n{user_input}\n\n"
            f"【回答】"
        )
        response = llm.invoke(prompt)
        answer = response.content if hasattr(response, "content") else str(response)
        return answer.strip()

    except Exception as e:
        logger.error(f"[rag_chat] Fallback answer failed: {e}")
        return (
            "抱歉，我暂时无法回答您的问题。\n"
            "您可以尝试提出具体的数据查询问题，例如：\n"
            "• 查询今天的 OEE\n"
            "• 各产线本月产量\n"
            "• A01 设备最近的报警记录"
        )
