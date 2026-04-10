"""
POST /api/v1/chat — 新 Agent 对话接口 (Phase C 增强版)
POST /api/v1/chat/stream — SSE 流式追踪接口 (Phase 2)

这是 AI Agent 的主入口。接收自然语言输入，
经过 LangGraph 状态机处理后返回完整结果。

Phase C 新增:
- 服务端对话记忆管理（短期 + 长期）
- 自动指代消解（追问识别）
- 会话历史查询 / 清除接口

Phase 2 新增:
- /stream 端点：Server-Sent Events，每完成一个 pipeline 步骤即时推送
  格式: event: trace_step | event: done | event: error
"""

import asyncio
import json
import logging
import re
import uuid
from typing import Optional, List, Dict, Any, AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.memory import conversation_memory
from app.agents.supervisor import route_to_agent
from app.utils.stream_errors import format_exception_as_sse, stream_error_sse, StreamError

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
        # Phase 0: 通过 Supervisor 路由到对应 Agent
        # - query 意图 → 现有 Query Agent（零改动）
        # - analyze 意图 → Analysis Agent（Phase 3 完善）
        result = await route_to_agent(
            user_input=req.message,
            session_id=session_id,
            conversation_history=req.conversation_history or [],
        )

        # 提取最终响应
        response_data = result.get("response", {})
        # pipeline_trace is popped from response by supervisor and lives at result level
        pipeline_trace = result.get("pipeline_trace") or []
        if pipeline_trace:
            response_data["pipeline_trace"] = pipeline_trace

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


# ── Phase 2: SSE 流式 pipeline 追踪端点 ──

def _sse_event(event: str, data: Any) -> str:
    """格式化一条 SSE 消息，确保输出为有效 JSON（NaN/Infinity → null）。"""
    raw = json.dumps(data, ensure_ascii=False)
    # Python json.dumps emits NaN/Infinity for float('nan')/float('inf') which
    # is invalid JSON and causes JSON.parse to throw on the frontend.
    raw = re.sub(r':\s*NaN\b', ': null', raw)
    raw = re.sub(r':\s*-?Infinity\b', ': null', raw)
    return f"event: {event}\ndata: {raw}\n\n"


async def _stream_query_agent(
    user_input: str,
    session_id: str,
    conversation_history: list,
) -> AsyncGenerator[str, None]:
    """
    使用 LangGraph .stream() 逐节点实时推送 trace_step。

    架构：
    - 同步线程 (threading.Thread) 驱动 agent.stream()，每完成一个节点
      立即通过 asyncio.Queue 把新 trace step 发给 async 生成器
    - async 生成器从 queue 取事件，立即 yield SSE —— 真正的实时流
    - 不攒完再回放，不用 asyncio.to_thread 阻塞整个 await
    """
    import threading
    from app.agent.graph import get_agent_app

    agent = get_agent_app()
    initial_state = {
        "user_input": user_input,
        "session_id": session_id,
        "conversation_history": conversation_history,
        "sql_retry_count": 0,
    }

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _run_stream() -> None:
        """在独立线程中驱动 LangGraph .stream()，把每个新 trace step 推入 queue。"""
        last_trace_len = 0
        final_ns: Dict[str, Any] = {}
        try:
            for chunk in agent.stream(initial_state):
                for node_name, node_state in chunk.items():
                    if not isinstance(node_state, dict):
                        continue
                    trace = node_state.get("pipeline_trace") or []
                    new_steps = trace[last_trace_len:]
                    last_trace_len = len(trace)
                    for step in new_steps:
                        loop.call_soon_threadsafe(queue.put_nowait, ("step", step))
                    final_ns = node_state
            loop.call_soon_threadsafe(queue.put_nowait, ("done", final_ns))
        except Exception as exc:
            from app.utils.stream_errors import classify_exception as _cls
            loop.call_soon_threadsafe(queue.put_nowait, ("error", (str(exc), _cls(exc))))

    thread = threading.Thread(target=_run_stream, daemon=True)
    thread.start()

    # async 端从 queue 消费事件，立即 yield SSE
    while True:
        event_type, payload = await queue.get()
        if event_type == "step":
            yield _sse_event("trace_step", payload)
        elif event_type == "done":
            final_state = payload
            response_data = final_state.get("response", {})
            pipeline_trace = (
                final_state.get("pipeline_trace")
                or response_data.get("pipeline_trace")
                or []
            )
            if isinstance(response_data, dict):
                response_data = dict(response_data)
                response_data.pop("pipeline_trace", None)
            yield _sse_event("done", {
                "success": response_data.get("success", False),
                "session_id": session_id,
                "data": response_data,
                "pipeline_trace": pipeline_trace,
            })
            break
        elif event_type == "error":
            if isinstance(payload, tuple):
                raw_msg, error_type = payload
                yield stream_error_sse(error_type, detail=raw_msg)
            else:
                yield _sse_event("error", {"error": payload})
            break


async def _stream_via_invoke(
    user_input: str,
    session_id: str,
    conversation_history: list,
) -> AsyncGenerator[str, None]:
    """
    Analysis Agent / multi-skill 路由不支持逐节点流式，
    改为先 invoke 再逐步模拟推送已完成的 trace。
    """
    from app.agents.supervisor import route_to_agent

    try:
        result = await route_to_agent(user_input, session_id, conversation_history)
    except Exception as e:
        yield format_exception_as_sse(e)
        return

    response_data = result.get("response", {})
    pipeline_trace = result.get("pipeline_trace") or response_data.get("pipeline_trace") or []
    if isinstance(response_data, dict):
        response_data = dict(response_data)
        response_data.pop("pipeline_trace", None)

    # 逐步推出 trace（给前端 "动画" 效果）
    for step in pipeline_trace:
        yield _sse_event("trace_step", step)
        await asyncio.sleep(0.02)   # 20 ms 间隔，避免一次性刷全

    done_payload = {
        "success": response_data.get("success", False),
        "session_id": session_id,
        "data": response_data,
        "pipeline_trace": pipeline_trace,
    }
    yield _sse_event("done", done_payload)


async def _chat_sse_generator(
    user_input: str,
    session_id: str,
    conversation_history: list,
) -> AsyncGenerator[str, None]:
    """
    主 SSE 生成器：根据路由决策选择流式策略。
    - adhoc → Query Agent，逐节点流式
    - 其他  → supervisor invoke，完成后回放 trace
    """
    from app.agents.supervisor import route_request

    try:
        route_result = await route_request(user_input)
    except Exception:
        route_result = {"route": "adhoc"}

    route = route_result.get("route", "adhoc")

    if route == "adhoc":
        async for chunk in _stream_query_agent(user_input, session_id, conversation_history):
            yield chunk
    else:
        async for chunk in _stream_via_invoke(user_input, session_id, conversation_history):
            yield chunk


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    SSE 流式对话接口 (Phase 2)。

    与 POST /chat 接收相同请求体，但以 text/event-stream 格式流式返回。

    事件类型:
    - event: trace_step  → data: PipelineStep (每完成一个 pipeline 节点推送)
    - event: done        → data: {success, session_id, data, pipeline_trace}
    - event: error       → data: {error: str}

    前端应使用 fetch + ReadableStream（不使用 EventSource，因为请求体为 POST）。
    """
    session_id = req.session_id or str(uuid.uuid4())
    logger.info(f"[chat/stream] session={session_id}, message={req.message[:80]}...")

    return StreamingResponse(
        _chat_sse_generator(
            req.message,
            session_id,
            req.conversation_history or [],
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # 禁止 nginx 缓冲
        },
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
