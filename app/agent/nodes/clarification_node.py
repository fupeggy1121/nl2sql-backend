"""
clarification_node — 澄清确认节点

当意图模糊（LLM 主动识别为 need_clarification 或置信度过低）时，
向用户返回一个反问，等待下一轮用户补充信息后继续正常流程。
不调用任何 LLM；所有信息来自 intent_data 中的 clarification_question 字段。
"""

import logging
import time
from app.agent.state import AgentState
from app.agent.trace import trace_step

logger = logging.getLogger(__name__)


def clarification_node(state: AgentState) -> dict:
    """
    澄清节点。
    输入:  intent_data（含 clarification_question）
    输出:  clarification_question, awaiting_clarification=True
    """
    _t0 = time.perf_counter()
    intent_data = state.get("intent_data", {})

    question = intent_data.get("clarification_question", "")
    if not question:
        # 兜底：LLM 没给出具体问题，给出通用提示
        question = "请描述一下您想查询的目标和条件，例如：查询对象（批次 / 设备 / 工序）、时间范围、具体筛选条件等。"

    logger.info(f"[clarification_node] Asking user: {question}")

    trace = list(state.get("pipeline_trace", []))
    trace_step(
        trace, "clarification_node", _t0,
        summary=f"意图模糊，需澄清：{question[:60]}",
        detail={
            "clarification_question": question,
            "original_confidence": intent_data.get("confidence", 0),
            "raw_intent": intent_data.get("intent", ""),
        },
    )

    return {
        "clarification_question": question,
        "awaiting_clarification": True,
        "pipeline_trace": trace,
    }
