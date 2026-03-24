"""
LangGraph Node 函数
每个 Node 是一个独立的处理步骤，接收 AgentState，返回局部更新。
"""

from app.agent.nodes.memory_loader import memory_loader_node
from app.agent.nodes.intent_router import intent_router_node
from app.agent.nodes.query_planner import query_planner_node
from app.agent.nodes.query_decomposer import query_decomposer_node
from app.agent.nodes.sql_generator import sql_generator_node
from app.agent.nodes.sql_validator import sql_validator_node
from app.agent.nodes.data_executor import data_executor_node
from app.agent.nodes.result_analyzer import result_analyzer_node
from app.agent.nodes.chart_generator import chart_generator_node
from app.agent.nodes.response_builder import response_builder_node
from app.agent.nodes.memory_saver import memory_saver_node
from app.agent.nodes.rag_chat import rag_chat_node     # Phase D 新增
from app.agent.nodes.semantic_resolver import semantic_resolver_node  # Phase 3: 本体引擎
from app.agent.nodes.action_executor import action_executor_node  # Phase E: 写操作执行
from app.agent.nodes.clarification_node import clarification_node  # Clarification: 澄清确认

__all__ = [
    "memory_loader_node",
    "intent_router_node",
    "semantic_resolver_node",
    "query_planner_node",
    "query_decomposer_node",
    "sql_generator_node",
    "sql_validator_node",
    "data_executor_node",
    "result_analyzer_node",
    "chart_generator_node",
    "response_builder_node",
    "memory_saver_node",
    "rag_chat_node",
    "action_executor_node",
    "clarification_node",
]
