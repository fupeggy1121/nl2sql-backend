"""
LangGraph 工作流 — AI Agent 的核心决策引擎

构建一个有向图状态机，包含:
- 意图路由（条件分支）
- 查询流水线（intent → plan → sql → execute → analyze → chart → response）
- SQL 自我修正循环（执行失败 → 重新生成 → 最多重试 3 次）
"""

import logging
from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.nodes import (
    intent_router_node,
    query_planner_node,
    sql_generator_node,
    data_executor_node,
    result_analyzer_node,
    chart_generator_node,
    response_builder_node,
)

logger = logging.getLogger(__name__)

# ── 最大 SQL 重试次数 ──
MAX_SQL_RETRIES = 3


def _route_by_intent(state: AgentState) -> str:
    """条件边：根据意图路由到不同分支"""
    intent = state.get("intent", "query")
    if intent == "query":
        return "query_planner"
    elif intent == "chat":
        return "response_builder"  # Phase B 会添加 rag_chat 节点
    elif intent == "alert":
        return "response_builder"  # Phase 后续
    elif intent == "schedule":
        return "response_builder"  # Phase 后续
    else:
        return "query_planner"


def _route_after_execution(state: AgentState) -> str:
    """
    条件边：SQL 执行后的路由决策（自我修正循环的核心）

    - 执行成功 → result_analyzer（继续分析）
    - 执行失败 且 重试次数 < MAX → sql_generator（自我修正）
    - 执行失败 且 重试次数 >= MAX → response_builder（返回错误）
    """
    sql_error = state.get("sql_error", "")
    retry_count = state.get("sql_retry_count", 0)

    if not sql_error:
        # 执行成功
        return "result_analyzer"
    elif retry_count < MAX_SQL_RETRIES:
        # 失败但还有重试机会 → 自我修正
        logger.info(
            f"[graph] SQL execution failed (retry {retry_count}/{MAX_SQL_RETRIES}), "
            f"routing to sql_generator for self-correction"
        )
        return "sql_generator"
    else:
        # 重试次数用尽 → 返回错误
        logger.warning(
            f"[graph] SQL self-correction exhausted ({MAX_SQL_RETRIES} retries), "
            f"returning error response"
        )
        return "response_builder"


def build_agent_graph() -> StateGraph:
    """
    构建 LangGraph 工作流图。

    流程:
    intent_router → (条件分支)
      └─ query → query_planner → sql_generator → data_executor → (条件分支)
                                      ↑                            │
                                      └── 自我修正循环 ←───────────┘ (失败且 retry < 3)
                                                                   │
                                                                   ↓ (成功)
                                                           result_analyzer → chart_generator → response_builder → END
      └─ chat/alert/schedule → response_builder → END
    """
    graph = StateGraph(AgentState)

    # ── 注册所有节点 ──
    graph.add_node("intent_router", intent_router_node)
    graph.add_node("query_planner", query_planner_node)
    graph.add_node("sql_generator", sql_generator_node)
    graph.add_node("data_executor", data_executor_node)
    graph.add_node("result_analyzer", result_analyzer_node)
    graph.add_node("chart_generator", chart_generator_node)
    graph.add_node("response_builder", response_builder_node)

    # ── 入口 ──
    graph.set_entry_point("intent_router")

    # ── 条件边: 意图路由 ──
    graph.add_conditional_edges(
        "intent_router",
        _route_by_intent,
        {
            "query_planner": "query_planner",
            "response_builder": "response_builder",
        },
    )

    # ── 固定边: 查询流水线 ──
    graph.add_edge("query_planner", "sql_generator")
    graph.add_edge("sql_generator", "data_executor")

    # ── 条件边: 执行后路由（自我修正循环）──
    graph.add_conditional_edges(
        "data_executor",
        _route_after_execution,
        {
            "result_analyzer": "result_analyzer",
            "sql_generator": "sql_generator",      # 自我修正回环
            "response_builder": "response_builder",  # 重试用尽
        },
    )

    # ── 固定边: 分析 → 图表 → 响应 ──
    graph.add_edge("result_analyzer", "chart_generator")
    graph.add_edge("chart_generator", "response_builder")

    # ── 终止 ──
    graph.add_edge("response_builder", END)

    return graph


def compile_agent():
    """编译并返回可执行的 Agent 应用"""
    graph = build_agent_graph()
    agent_app = graph.compile()
    logger.info("[graph] Agent graph compiled successfully")
    return agent_app


# ── 全局单例 ──
_agent_app = None


def get_agent_app():
    """获取编译后的 Agent 应用（单例）"""
    global _agent_app
    if _agent_app is None:
        _agent_app = compile_agent()
    return _agent_app
