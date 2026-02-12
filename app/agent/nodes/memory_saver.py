"""
memory_saver — 对话记忆保存节点 (Phase C)

图的最后一个节点 (response_builder → memory_saver → END)。
将本轮对话保存到 ConversationMemory:
  - 用户输入
  - 系统回复摘要
  - 生成的 SQL
  - 查询结果摘要
  - 意图类型
"""

import logging
from app.agent.state import AgentState
from app.agent.memory import conversation_memory

logger = logging.getLogger(__name__)


def memory_saver_node(state: AgentState) -> dict:
    """
    对话记忆保存节点。
    输入: session_id, user_input, response, sql, intent
    输出: (不修改 state，纯副作用)
    """
    session_id = state.get("session_id", "")
    if not session_id:
        return {}

    user_input = state.get("user_input", "")
    response = state.get("response", {})
    sql = state.get("sql", "")
    intent = state.get("intent", "")

    # 提取回复摘要
    assistant_message = _extract_assistant_message(response)
    query_result_summary = _extract_result_summary(response)

    # 保存到记忆
    conversation_memory.save_turn(
        session_id=session_id,
        user_message=user_input,
        assistant_message=assistant_message,
        sql=sql,
        query_result_summary=query_result_summary,
        intent=intent,
    )

    logger.info(
        f"[memory_saver] Saved turn for session={session_id}, "
        f"intent={intent}, sql_len={len(sql)}"
    )

    return {}


def _extract_assistant_message(response: dict) -> str:
    """从 response 中提取用于保存的回复文本"""
    if not response:
        return ""

    # 错误响应
    if not response.get("success"):
        return f"[错误] {response.get('error', '未知错误')}"

    # 查询结果
    qr = response.get("query_result", {})
    if qr:
        summary = qr.get("summary", "")
        rows = qr.get("rows_count", 0)
        return summary or f"查询返回 {rows} 条记录"

    # 聊天响应
    msg = response.get("message", "")
    if msg:
        return msg

    return "已处理"


def _extract_result_summary(response: dict) -> str:
    """提取查询结果的简短摘要 (用于上下文注入)"""
    if not response:
        return ""

    qr = response.get("query_result", {})
    if not qr:
        return ""

    data = qr.get("data", [])
    rows = qr.get("rows_count", 0)
    sql = qr.get("sql", "")

    parts = []
    if rows:
        parts.append(f"{rows}条记录")
    if data and isinstance(data, list) and len(data) > 0:
        cols = list(data[0].keys()) if isinstance(data[0], dict) else []
        if cols:
            parts.append(f"列: {', '.join(cols[:5])}")
        # 首行摘要
        if isinstance(data[0], dict):
            first_row = {k: str(v)[:30] for k, v in list(data[0].items())[:3]}
            parts.append(f"首行: {first_row}")

    return "; ".join(parts) if parts else ""
