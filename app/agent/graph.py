"""
LangGraph 工作流 — AI Agent 的核心决策引擎 (Phase D RAG 增强版)

构建一个有向图状态机，包含:
- 对话记忆加载/保存（多轮对话支持）
- 意图路由（条件分支）
- 查询分解（复杂查询拆解为子步骤）
- SQL 预验证（执行前检查表/列名是否存在）
- SQL 自我修正循环（验证失败/执行失败 → 重新生成 → 最多重试 3 次）

Phase D 新增:
- rag_chat 节点: 基于 RAG 知识库的智能问答
- query_planner RAG 增强: 使用向量检索获取相关 schema
- sql_generator RAG 增强: 检索历史 SQL 作为 few-shot
"""

import logging
from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.nodes import (
    memory_loader_node,
    intent_router_node,
    semantic_resolver_node,   # Phase 3: 本体引擎
    query_planner_node,
    query_decomposer_node,
    sql_generator_node,
    sql_validator_node,
    data_executor_node,
    result_analyzer_node,
    chart_generator_node,
    response_builder_node,
    memory_saver_node,
    rag_chat_node,          # Phase D 新增
    action_executor_node,   # Phase E 新增
)

logger = logging.getLogger(__name__)

# ── 最大 SQL 重试次数 ──
MAX_SQL_RETRIES = 3


def _route_by_intent(state: AgentState) -> str:
    """条件边：根据意图路由到不同分支"""
    intent = state.get("intent", "query")
    if intent == "query":
        return "semantic_resolver"   # Phase 3: 先经语义解析
    elif intent == "chat":
        return "rag_chat"        # Phase D: 路由到 RAG 问答节点
    elif intent == "action":
        return "action_executor"  # Phase E: 写操作执行节点
    elif intent == "alert":
        return "response_builder"  # Phase 后续
    elif intent == "schedule":
        return "response_builder"  # Phase 后续
    else:
        return "semantic_resolver"   # Phase 3: 默认也经语义解析


def _route_after_execution(state: AgentState) -> str:
    """
    条件边：SQL 执行后的路由决策（自我修正循环的核心）

    - 执行成功 → result_analyzer（继续分析）
    - DB 连接类错误（db_error 有值）→ response_builder（不触发 LLM 重试）
    - SQL 逻辑类错误 且 重试次数 < MAX → sql_generator（自我修正）
    - SQL 逻辑类错误 且 重试次数 >= MAX → response_builder（返回错误）
    """
    db_error  = state.get("db_error", "")
    sql_error = state.get("sql_error", "")
    retry_count = state.get("sql_retry_count", 0)

    if not sql_error and not db_error:
        # 执行成功
        return "result_analyzer"

    if db_error:
        # 数据库连接/基础设施错误 —— 重新生成 SQL 无意义，直接返回错误
        logger.warning(
            f"[graph] DB connection error, skipping LLM retry → response_builder: {db_error[:80]}"
        )
        return "response_builder"

    if retry_count < MAX_SQL_RETRIES:
        # SQL 逻辑错误，还有重试机会 → 自我修正
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


def _route_after_validation(state: AgentState) -> str:
    """
    条件边：SQL 验证后的路由决策 (Phase B 新增)

    - 验证通过（无 sql_error）→ data_executor（执行）
    - 验证失败 且 重试次数 < MAX → sql_generator（自我修正，跳过执行）
    - 验证失败 且 重试次数 >= MAX → response_builder（返回错误）
    """
    sql_error = state.get("sql_error", "")
    retry_count = state.get("sql_retry_count", 0)

    if not sql_error:
        return "data_executor"
    elif retry_count < MAX_SQL_RETRIES:
        logger.info(
            f"[graph] SQL validation failed (retry {retry_count}/{MAX_SQL_RETRIES}), "
            f"routing to sql_generator for correction"
        )
        return "sql_generator"
    else:
        logger.warning(
            f"[graph] SQL validation exhausted ({MAX_SQL_RETRIES} retries), "
            f"returning error response"
        )
        return "response_builder"


def build_agent_graph() -> StateGraph:
    """
    构建 LangGraph 工作流图 (Phase 3: 语义引擎增强版)。

    流程:
    memory_loader → intent_router → (条件分支)
      └─ query → semantic_resolver(Phase3) → query_planner(+RAG) → query_decomposer → sql_generator(+语义上下文) → sql_validator → (条件分支)
                                                                  ↑                            │
                                                                  └── 验证修正 ←───────────────┘ (验证失败 + retry<3)
                                                                  ↑                            │
                                                                  │                            ↓ (验证通过)
                                                                  │                    data_executor → (条件分支)
                                                                  │                            │
                                                                  └── 执行修正 ←───────────────┘ (执行失败 + retry<3)
                                                                                               │
                                                                                               ↓ (成功)
                                                                                       result_analyzer → chart_generator → response_builder → memory_saver → END
      └─ chat → rag_chat → memory_saver → END
      └─ alert/schedule → response_builder → memory_saver → END
    """
    graph = StateGraph(AgentState)

    # ── 注册所有节点 ──
    graph.add_node("memory_loader", memory_loader_node)       # Phase C
    graph.add_node("intent_router", intent_router_node)
    graph.add_node("semantic_resolver", semantic_resolver_node)  # Phase 3: 本体引擎
    graph.add_node("query_planner", query_planner_node)
    graph.add_node("query_decomposer", query_decomposer_node)
    graph.add_node("sql_generator", sql_generator_node)
    graph.add_node("sql_validator", sql_validator_node)
    graph.add_node("data_executor", data_executor_node)
    graph.add_node("result_analyzer", result_analyzer_node)
    graph.add_node("chart_generator", chart_generator_node)
    graph.add_node("response_builder", response_builder_node)
    graph.add_node("memory_saver", memory_saver_node)         # Phase C
    graph.add_node("rag_chat", rag_chat_node)                 # Phase D 新增
    graph.add_node("action_executor", action_executor_node)   # Phase E 新增

    # ── 入口: memory_loader ──
    graph.set_entry_point("memory_loader")

    # ── 固定边: 记忆加载 → 意图路由 ──
    graph.add_edge("memory_loader", "intent_router")

    # ── 条件边: 意图路由 ──
    graph.add_conditional_edges(
        "intent_router",
        _route_by_intent,
        {
            "semantic_resolver": "semantic_resolver",  # Phase 3: query → 语义解析
            "rag_chat": "rag_chat",                 # Phase D: chat → rag_chat
            "action_executor": "action_executor",    # Phase E: write → action_executor
            "response_builder": "response_builder",
        },
    )

    # ── 固定边: 语义解析 → 查询规划（LLM 始终参与 SQL 生成，业务规则模板作为提示注入）──
    graph.add_edge("semantic_resolver", "query_planner")
    graph.add_edge("query_planner", "query_decomposer")
    graph.add_edge("query_decomposer", "sql_generator")
    graph.add_edge("sql_generator", "sql_validator")

    # ── 条件边: 验证后路由（Phase B）──
    graph.add_conditional_edges(
        "sql_validator",
        _route_after_validation,
        {
            "data_executor": "data_executor",
            "sql_generator": "sql_generator",       # 验证失败 → 修正
            "response_builder": "response_builder",  # 重试用尽
        },
    )

    # ── 条件边: 执行后路由（自我修正循环）──
    graph.add_conditional_edges(
        "data_executor",
        _route_after_execution,
        {
            "result_analyzer": "result_analyzer",
            "sql_generator": "sql_generator",       # 执行失败 → 修正
            "response_builder": "response_builder",  # 重试用尽
        },
    )

    # ── 固定边: 分析 → 图表 → 响应 → 记忆保存 ──
    graph.add_edge("result_analyzer", "chart_generator")
    graph.add_edge("chart_generator", "response_builder")
    graph.add_edge("response_builder", "memory_saver")

    # ── Phase D: rag_chat → memory_saver ──
    graph.add_edge("rag_chat", "memory_saver")

    # ── Phase E: action_executor → response_builder → memory_saver ──
    graph.add_edge("action_executor", "response_builder")

    # ── 终止 ──
    graph.add_edge("memory_saver", END)

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
