"""
Phase 3 测试: LangGraph 语义引擎集成

覆盖:
  - semantic_resolver 节点单元测试
  - AgentState.semantic_context 字段
  - Graph 拓扑验证（节点存在 + 边连接）
  - sql_generator 语义上下文注入辅助函数
  - 路由逻辑 (query → semantic_resolver)
"""

import json
import pytest

from app.ontology.loader import load_ontology
from app.ontology.mapping import load_mapping
from app.ontology.context_builder import build_semantic_context


# ================================================================== #
#  Fixtures
# ================================================================== #

@pytest.fixture(scope="module")
def ontology():
    return load_ontology(force_reload=True)


@pytest.fixture(scope="module")
def mapping():
    return load_mapping(force_reload=True)


# ================================================================== #
#  Part A: semantic_resolver_node 单元测试
# ================================================================== #

class TestSemanticResolverNode:
    """semantic_resolver 节点直接调用测试"""

    def test_basic_query(self):
        """基本查询应返回 semantic_context dict"""
        from app.agent.nodes.semantic_resolver import semantic_resolver_node

        state = {"user_input": "各工站的在制品数量"}
        result = semantic_resolver_node(state)

        assert "semantic_context" in result
        ctx = result["semantic_context"]
        assert isinstance(ctx, dict)

        # 应有 matched_classes
        assert len(ctx.get("matched_classes", [])) >= 1
        class_names = {c["logic_class"] for c in ctx["matched_classes"]}
        assert "semi:ProcessStation" in class_names

    def test_wip_filter_present(self):
        """WIP 查询应包含过滤条件"""
        from app.agent.nodes.semantic_resolver import semantic_resolver_node

        state = {"user_input": "在制品数量统计"}
        result = semantic_resolver_node(state)
        ctx = result["semantic_context"]

        filters = ctx.get("filters", [])
        wip = [f for f in filters if f.get("semantic_value") == "WIP"]
        assert len(wip) >= 1
        assert "completed" in wip[0].get("physical_condition", "")

    def test_multi_class_join(self):
        """多类查询应有 JOIN 路径"""
        from app.agent.nodes.semantic_resolver import semantic_resolver_node

        state = {"user_input": "查询晶圆所属批次"}
        result = semantic_resolver_node(state)
        ctx = result["semantic_context"]

        assert len(ctx.get("joins", [])) >= 1
        join_rels = {j["logic_relation"] for j in ctx["joins"]}
        assert "semi:belongsToLot" in join_rels

    def test_empty_input_graceful(self):
        """空输入不崩溃，返回空 dict"""
        from app.agent.nodes.semantic_resolver import semantic_resolver_node

        state = {"user_input": ""}
        result = semantic_resolver_node(state)
        assert result["semantic_context"] == {}

    def test_followup_uses_resolved_input(self):
        """追问时应使用 resolved_input"""
        from app.agent.nodes.semantic_resolver import semantic_resolver_node

        state = {
            "user_input": "那设备呢？",
            "resolved_input": "查询各工站的设备信息",
            "is_followup": True,
        }
        result = semantic_resolver_node(state)
        ctx = result["semantic_context"]
        class_names = {c["logic_class"] for c in ctx.get("matched_classes", [])}
        assert "semi:Equipment" in class_names

    def test_schema_snippet_in_output(self):
        """输出应包含 schema_snippet"""
        from app.agent.nodes.semantic_resolver import semantic_resolver_node

        state = {"user_input": "查询晶圆信息"}
        result = semantic_resolver_node(state)
        ctx = result["semantic_context"]
        assert "schema_snippet" in ctx
        assert "wafers" in ctx["schema_snippet"]

    def test_physical_tables_in_output(self):
        """输出应包含 physical_tables 列表"""
        from app.agent.nodes.semantic_resolver import semantic_resolver_node

        state = {"user_input": "产品的工艺路线"}
        result = semantic_resolver_node(state)
        ctx = result["semantic_context"]
        tables = ctx.get("physical_tables", [])
        assert "products" in tables
        assert "process_routes" in tables

    def test_serializable(self):
        """输出应可 JSON 序列化"""
        from app.agent.nodes.semantic_resolver import semantic_resolver_node

        state = {"user_input": "各工站的在制品数量"}
        result = semantic_resolver_node(state)
        json.dumps(result, ensure_ascii=False)  # 不应抛异常


# ================================================================== #
#  Part B: AgentState 字段
# ================================================================== #

class TestAgentState:

    def test_semantic_context_field_exists(self):
        """AgentState 应有 semantic_context 字段"""
        from app.agent.state import AgentState
        import typing

        hints = typing.get_type_hints(AgentState)
        assert "semantic_context" in hints


# ================================================================== #
#  Part C: Graph 拓扑验证
# ================================================================== #

class TestGraphTopology:
    """验证 LangGraph 图的结构"""

    def test_graph_builds(self):
        """图应能成功构建"""
        from app.agent.graph import build_agent_graph
        graph = build_agent_graph()
        assert graph is not None

    def test_semantic_resolver_node_registered(self):
        """semantic_resolver 节点应被注册"""
        from app.agent.graph import build_agent_graph
        graph = build_agent_graph()
        assert "semantic_resolver" in graph.nodes

    def test_all_13_nodes(self):
        """应有 13 个节点"""
        from app.agent.graph import build_agent_graph
        graph = build_agent_graph()
        expected = {
            "memory_loader", "intent_router", "semantic_resolver",
            "query_planner", "query_decomposer", "sql_generator",
            "sql_validator", "data_executor", "result_analyzer",
            "chart_generator", "response_builder", "memory_saver",
            "rag_chat",
        }
        assert set(graph.nodes.keys()) == expected

    def test_intent_routes_to_semantic_resolver(self):
        """query 意图应路由到 semantic_resolver"""
        from app.agent.graph import _route_by_intent
        state = {"intent": "query"}
        assert _route_by_intent(state) == "semantic_resolver"

    def test_default_routes_to_semantic_resolver(self):
        """未知意图也应路由到 semantic_resolver"""
        from app.agent.graph import _route_by_intent
        state = {"intent": "unknown"}
        assert _route_by_intent(state) == "semantic_resolver"

    def test_chat_routes_to_rag_chat(self):
        """chat 意图仍路由到 rag_chat（不变）"""
        from app.agent.graph import _route_by_intent
        state = {"intent": "chat"}
        assert _route_by_intent(state) == "rag_chat"


# ================================================================== #
#  Part D: sql_generator 辅助函数测试
# ================================================================== #

class TestSqlGeneratorHelpers:
    """测试 sql_generator 中新增的语义辅助函数"""

    def test_merge_semantic_schema(self):
        from app.agent.nodes.sql_generator import _merge_semantic_schema

        result = _merge_semantic_schema(
            "TABLE wafers (id, wafer_id_code, batch_id)",
            "Some RAG context"
        )
        assert "语义引擎推荐" in result
        assert "wafers" in result
        assert "补充 Schema" in result
        assert "Some RAG context" in result

    def test_merge_semantic_schema_no_rag(self):
        from app.agent.nodes.sql_generator import _merge_semantic_schema

        result = _merge_semantic_schema("TABLE wafers (id)", "")
        assert "语义引擎推荐" in result
        assert "补充 Schema" not in result

    def test_format_semantic_context_full(self):
        from app.agent.nodes.sql_generator import _format_semantic_context

        ctx_dict = {
            "matched_classes": [
                {"label_cn": "工艺站点", "physical_table": "stations"},
            ],
            "joins": [
                {"conditions": [{"from": "wafers.batch_id", "to": "batches.id"}]},
            ],
            "filters": [
                {
                    "description": "在制品",
                    "physical_condition": "sub_batches.status != 'completed'",
                    "physical_values": None,
                },
            ],
            "business_rules": [
                {"name": "WIP规则", "description": "统计sub_batches"},
            ],
        }
        result = _format_semantic_context(ctx_dict)
        assert "语义引擎分析结果" in result
        assert "工艺站点→stations" in result
        assert "wafers.batch_id" in result
        assert "在制品" in result
        assert "WIP规则" in result

    def test_format_semantic_context_empty(self):
        from app.agent.nodes.sql_generator import _format_semantic_context
        assert _format_semantic_context({}) == ""
        assert _format_semantic_context(None) == ""

    def test_format_semantic_context_values_only(self):
        from app.agent.nodes.sql_generator import _format_semantic_context

        ctx_dict = {
            "matched_classes": [],
            "filters": [
                {
                    "description": "清洁载具",
                    "physical_condition": None,
                    "physical_values": ["clean", "available"],
                    "applies_to_table": "carriers",
                    "applies_to_column": "status",
                },
            ],
        }
        result = _format_semantic_context(ctx_dict)
        assert "carriers.status IN" in result
        assert "'clean'" in result


# ================================================================== #
#  Part E: 端到端集成 (轻量 — 不调用 LLM)
# ================================================================== #

class TestEndToEnd:
    """验证 semantic_resolver 产出的 context 可被 sql_generator 消费"""

    def test_resolver_output_feeds_sql_generator(self):
        """resolver 输出应能被 _format_semantic_context 消费"""
        from app.agent.nodes.semantic_resolver import semantic_resolver_node
        from app.agent.nodes.sql_generator import _format_semantic_context

        state = {"user_input": "各工站的在制品数量"}
        resolver_output = semantic_resolver_node(state)
        ctx_dict = resolver_output["semantic_context"]

        formatted = _format_semantic_context(ctx_dict)
        assert "语义引擎分析结果" in formatted
        assert len(formatted) > 50

    def test_resolver_output_feeds_merge(self):
        """resolver 的 schema_snippet 应能被 _merge_semantic_schema 使用"""
        from app.agent.nodes.semantic_resolver import semantic_resolver_node
        from app.agent.nodes.sql_generator import _merge_semantic_schema

        state = {"user_input": "查询晶圆所属批次"}
        resolver_output = semantic_resolver_node(state)
        ctx_dict = resolver_output["semantic_context"]

        snippet = ctx_dict.get("schema_snippet", "")
        assert "wafers" in snippet

        merged = _merge_semantic_schema(snippet, "fallback schema")
        assert "语义引擎推荐" in merged
        assert "wafers" in merged
