"""
Analysis Agent — 5 节点 LangGraph 管道

节点顺序：
  method_selector → data_loader → preprocessor → analysis_executor → viz_generator

条件路由：
  - data_loader 失败 → 跳过 preprocessor + analysis_executor，直接 viz_generator
  - analysis_executor 失败 → 仍走 viz_generator（展示错误信息）
"""

from __future__ import annotations

import logging
from functools import lru_cache

from langgraph.graph import END, StateGraph

from app.agents.analysis_agent.nodes.analysis_executor import analysis_executor_node
from app.agents.analysis_agent.nodes.data_loader import data_loader_node
from app.agents.analysis_agent.nodes.method_selector import method_selector_node
from app.agents.analysis_agent.nodes.preprocessor import preprocessor_node
from app.agents.analysis_agent.nodes.viz_generator import viz_generator_node
from app.agents.analysis_agent.state import AnalysisState

logger = logging.getLogger(__name__)


def _route_after_load(state: AnalysisState) -> str:
    """数据加载失败时跳过预处理和执行，直接生成响应。"""
    if state.get("data_load_error"):
        logger.warning(f"[analysis_graph] data load error → skip to viz")
        return "viz_generator"
    return "preprocessor"


def build_analysis_graph() -> StateGraph:
    """构建 Analysis Agent 的 StateGraph。"""
    graph = StateGraph(AnalysisState)

    # 注册节点
    graph.add_node("method_selector", method_selector_node)
    graph.add_node("data_loader", data_loader_node)
    graph.add_node("preprocessor", preprocessor_node)
    graph.add_node("analysis_executor", analysis_executor_node)
    graph.add_node("viz_generator", viz_generator_node)

    # 入口
    graph.set_entry_point("method_selector")

    # 边
    graph.add_edge("method_selector", "data_loader")
    graph.add_conditional_edges(
        "data_loader",
        _route_after_load,
        {
            "preprocessor": "preprocessor",
            "viz_generator": "viz_generator",
        },
    )
    graph.add_edge("preprocessor", "analysis_executor")
    graph.add_edge("analysis_executor", "viz_generator")
    graph.add_edge("viz_generator", END)

    return graph


@lru_cache(maxsize=1)
def get_analysis_agent_app():
    """编译并缓存 Analysis Agent 应用（线程安全，单例）。"""
    graph = build_analysis_graph()
    app = graph.compile()
    logger.info("[analysis_agent] graph compiled: 5 nodes")
    return app
