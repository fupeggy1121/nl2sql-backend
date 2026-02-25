"""
POST /api/v1/chat — 新 Agent 对话接口 (Phase C 增强版)

这是 AI Agent 的主入口。接收自然语言输入，
经过 LangGraph 状态机处理后返回完整结果。

Phase C 新增:
- 服务端对话记忆管理（短期 + 长期）
- 自动指代消解（追问识别）
- 会话历史查询 / 清除接口
"""

import logging
import uuid
from typing import Optional, List, Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agent.graph import get_agent_app
from app.agent.memory import conversation_memory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Agent Chat"])


# ── 请求/响应模型 ──

class ChatRequest(BaseModel):
    """对话请求"""
    message: str = Field(..., description="用户自然语言输入")
    session_id: Optional[str] = Field(None, description="会话 ID，用于多轮对话")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        None, description="对话历史（可选，服务端会自动管理）"
    )


class ChatResponse(BaseModel):
    """对话响应"""
    success: bool
    session_id: str
    data: Dict[str, Any] = Field(default_factory=dict)
    conversation: Optional[Dict[str, Any]] = Field(
        None, description="对话上下文信息 (Phase C)"
    )


# ── 端点 ──

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    AI Agent 对话接口 (Phase C 增强版)。

    接收自然语言输入，经过 LangGraph 状态机处理：
    memory_loader → intent_router → query_planner → sql_generator
    → data_executor → result_analyzer → chart_generator
    → response_builder → memory_saver

    支持:
    - 多轮对话（服务端自动管理对话记忆）
    - 指代消解（"那上个月呢" → 自动补全上下文）
    - SQL 自我修正（最多 3 次重试）
    """
    session_id = req.session_id or str(uuid.uuid4())
    logger.info(f"[chat] session={session_id}, message={req.message[:80]}...")

    try:
        agent = get_agent_app()

        # 构建初始状态
        initial_state = {
            "user_input": req.message,
            "session_id": session_id,
            "conversation_history": req.conversation_history or [],
            "sql_retry_count": 0,
        }

        # 运行 Agent
        result = await agent.ainvoke(initial_state)

        # 提取最终响应
        response_data = result.get("response", {})

        # Phase C: 返回对话上下文信息
        conversation_info = {
            "session_id": session_id,
            "is_followup": result.get("is_followup", False),
            "turn_count": len(
                conversation_memory.get_or_create_session(session_id).turns
            ),
        }

        return ChatResponse(
            success=response_data.get("success", False),
            session_id=session_id,
            data=response_data,
            conversation=conversation_info,
        )

    except Exception as e:
        logger.error(f"[chat] Agent error: {e}", exc_info=True)
        return ChatResponse(
            success=False,
            session_id=session_id,
            data={"success": False, "error": str(e)},
        )


# ── Phase C: 会话管理端点 ──

@router.get("/sessions")
async def list_sessions(limit: int = 20):
    """列出最近活跃的会话"""
    sessions = conversation_memory.list_recent_sessions(limit=limit)
    return {"success": True, "sessions": sessions, "count": len(sessions)}


@router.get("/sessions/latest")
async def get_latest_session():
    """
    返回最近一条有效会话（前端打开页面时调用，复用已有会话避免重复创建）。
    - 有历史会话 → 返回 {found: true, session: {...}}
    - 没有任何会话 → 返回 {found: false, session: null}
    前端逻辑：found=true 时直接复用 session_id；found=false 时才新建。
    """
    latest = conversation_memory.get_latest_session()
    if latest:
        return {"success": True, "found": True, "session": latest}
    return {"success": True, "found": False, "session": None}


@router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    """获取指定会话的完整历史"""
    history = conversation_memory.get_session_history(session_id)
    return {
        "success": True,
        "session_id": session_id,
        "history": history,
        "turn_count": len(history),
    }


@router.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    """清除指定会话"""
    conversation_memory.clear_session(session_id)
    return {"success": True, "session_id": session_id, "message": "会话已清除"}
