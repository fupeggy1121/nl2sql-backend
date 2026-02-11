"""
POST /api/v1/chat — 新 Agent 对话接口

这是 AI Agent 的主入口。接收自然语言输入，
经过 LangGraph 状态机处理后返回完整结果。
"""

import logging
import uuid
from typing import Optional, List, Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agent.graph import get_agent_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Agent Chat"])


# ── 请求/响应模型 ──

class ChatRequest(BaseModel):
    """对话请求"""
    message: str = Field(..., description="用户自然语言输入")
    session_id: Optional[str] = Field(None, description="会话 ID，用于多轮对话")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        None, description="对话历史"
    )


class ChatResponse(BaseModel):
    """对话响应"""
    success: bool
    session_id: str
    data: Dict[str, Any] = Field(default_factory=dict)


# ── 端点 ──

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    AI Agent 对话接口。

    接收自然语言输入，经过 LangGraph 状态机处理：
    intent_router → query_planner → sql_generator → data_executor
    → result_analyzer → chart_generator → response_builder

    支持 SQL 自我修正（最多 3 次重试）。
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

        return ChatResponse(
            success=response_data.get("success", False),
            session_id=session_id,
            data=response_data,
        )

    except Exception as e:
        logger.error(f"[chat] Agent error: {e}", exc_info=True)
        return ChatResponse(
            success=False,
            session_id=session_id,
            data={"success": False, "error": str(e)},
        )
