"""
response_builder — 响应构建节点

所有分支的汇聚点。组装完整的 API 响应。
"""

import logging
import time
from datetime import datetime
from app.agent.state import AgentState
from app.agent.trace import trace_step

logger = logging.getLogger(__name__)


def response_builder_node(state: AgentState) -> dict:
    """
    响应构建节点。
    输入: 所有 state 字段
    输出: response (最终 API 响应)
    """
    _t0 = time.perf_counter()
    intent = state.get("intent", "query")
    error = state.get("error", "")
    query_result = state.get("query_result", {})
    visualization = state.get("visualization")
    sql = state.get("sql", "")
    user_input = state.get("user_input", "")
    intent_data = state.get("intent_data", {})
    start_time = state.get("start_time", time.time())

    # 计算耗时
    elapsed_ms = (time.time() - start_time) * 1000

    # 构建响应
    if error and not query_result.get("success"):
        # ── 全局错误 ──
        response = {
            "success": False,
            "error": error,
            "query_time_ms": round(elapsed_ms, 1),
        }
    elif intent == "query":
        # ── 数据查询响应 ──
        data = query_result.get("data", [])
        rows_count = query_result.get("rows_count", len(data) if isinstance(data, list) else 0)
        retry_count = state.get("sql_retry_count", 0)

        # 生成摘要
        summary = _generate_summary(user_input, data, rows_count)

        # 构建查询计划
        plan_info = {
            "query_intent": intent_data,
            "generated_sql": sql,
            "sql_confidence": state.get("sql_confidence", 0.0),
            "explanation": f"根据您的查询生成了 SQL 并执行",
        }

        # 如果有自我修正历史，记录到响应中
        if retry_count > 0:
            plan_info["self_correction"] = {
                "retries": retry_count,
                "note": f"SQL 经过 {retry_count} 次自我修正后成功执行"
                        if query_result.get("success")
                        else f"SQL 修正 {retry_count} 次仍然失败",
            }

        # 如果有查询分解信息，记录
        decomposition = state.get("query_plan", {}).get("decomposition")
        if decomposition:
            plan_info["decomposition"] = {
                "strategy": decomposition.get("strategy", ""),
                "steps": len(decomposition.get("sub_queries", [])),
                "merge_strategy": decomposition.get("merge_strategy", ""),
            }

        response = {
            "success": True,
            "query_plan": plan_info,
            "query_result": {
                "success": True,
                "data": data,
                "rows_count": rows_count,
                "sql": sql,
                "summary": summary,
                "visualization_type": state.get("chart_type", "table"),
                "actions": ["export", "refresh"],
                "query_time_ms": round(elapsed_ms, 1),
                "generated_at": datetime.now().isoformat(),
            },
            "visualization": visualization,
        }
    elif intent == "action":
        # ── 写操作执行响应 (Phase E) ──
        action_result = state.get("action_result", {})
        action_error = state.get("action_error", "")
        if action_error:
            response = {
                "success": False,
                "type": "action",
                "error": action_error,
                "message": action_error,
                "query_time_ms": round(elapsed_ms, 1),
            }
        else:
            # 优先使用 action_executor 已组装好的 response，补充耗时字段
            pre_built = state.get("response", {})
            response = {
                "success": True,
                "type": "action",
                "message": pre_built.get("message", "✅ 操作执行成功"),
                "action": pre_built.get("action", action_result.get("eventType", "")),
                "data": action_result,
                "query_time_ms": round(elapsed_ms, 1),
            }
    elif intent == "clarification":
        # ── 澄清反问响应 ──
        question = state.get("clarification_question", "")
        response = {
            "success": True,
            "type": "clarification",
            "clarification_question": question,
            "message": question,
            "query_time_ms": round(elapsed_ms, 1),
        }
    else:
        # ── 其他意图（chat/alert/schedule）暂返回占位 ──
        response = {
            "success": True,
            "message": "该功能正在开发中",
            "intent": intent,
        }

    logger.info(
        f"[response_builder] Built response: success={response.get('success')}, "
        f"elapsed={elapsed_ms:.0f}ms"
    )

    # ── Pipeline Trace: 汇总并写入响应 ──
    trace = list(state.get("pipeline_trace", []))
    trace_step(trace, "response_builder", _t0, summary=(
        f"构建响应完成, 总耗时: {elapsed_ms:.0f}ms"
    ))
    response["pipeline_trace"] = trace

    return {"response": response}


def _generate_summary(user_input: str, data: list, rows_count: int) -> str:
    """生成简短的查询结果摘要"""
    if not data:
        return "查询未返回数据"
    if rows_count == 1 and len(data[0]) == 1:
        # 单值结果
        val = list(data[0].values())[0]
        return f"查询结果: {val}"
    return f"查询返回 {rows_count} 条记录"
