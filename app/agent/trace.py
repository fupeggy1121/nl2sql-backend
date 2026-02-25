"""
trace — 管道追踪助手

为每个 Agent 节点记录执行步骤：
  - 节点名、耗时、输入摘要、输出摘要
  - 前端可以展开查看完整信息

使用方式:
    from app.agent.trace import trace_step
    trace = state.get("pipeline_trace", [])
    trace_step(trace, "intent_router", t0, summary="...", detail={...})
    return {..., "pipeline_trace": trace}
"""

import time
from typing import Any, Dict, List, Optional


def trace_step(
    trace: List[Dict[str, Any]],
    step_name: str,
    start_time: float,
    *,
    summary: str = "",
    detail: Optional[Dict[str, Any]] = None,
    status: str = "ok",
    llm_tokens: Optional[Dict[str, int]] = None,
) -> None:
    """
    向 trace 列表追加一条步骤记录（原地修改 trace）。

    参数:
        trace      : state["pipeline_trace"] 的引用
        step_name  : 节点名称（如 "intent_router"）
        start_time : time.perf_counter() 的起始值
        summary    : 一行中文摘要（显示在折叠标题中）
        detail     : 可展开查看的完整字典
        status     : "ok" | "warn" | "error"
        llm_tokens : LLM token 用量，如 {"input": 320, "output": 128, "total": 448}
    """
    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
    entry: Dict[str, Any] = {
        "step": step_name,
        "elapsed_ms": elapsed_ms,
        "summary": summary,
        "status": status,
    }
    if detail is not None:
        entry["detail"] = _safe_detail(detail)
    if llm_tokens:
        entry["llm_tokens"] = llm_tokens
    trace.append(entry)


def _safe_detail(obj: Any, depth: int = 0) -> Any:
    """递归清理 detail 中可能不可 JSON 序列化的内容"""
    if depth > 4:
        return str(obj)[:200]
    if isinstance(obj, dict):
        return {k: _safe_detail(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        items = [_safe_detail(i, depth + 1) for i in obj[:50]]
        if len(obj) > 50:
            items.append(f"... ({len(obj)} items total)")
        return items
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    return str(obj)[:200]
