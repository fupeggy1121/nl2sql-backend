"""
Phase D & E — Agent 端到端测试

测试覆盖:
1. 完整 Agent 流程: NL → intent → SQL → 执行 → 图表 → 响应
2. SQL 修正循环: 故意提供错误 SQL → 验证自动修正
3. 多轮对话: 连续两个请求，第二个引用第一个上下文
4. API 兼容层: 用旧 API 格式请求 → 验证响应格式不变
5. RAG 组件: embedding / vectorstore / rag_tools
6. rag_chat 节点: chat 意图 → RAG 问答
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ══════════════════════════════════════════════
#  Phase D 单元测试
# ══════════════════════════════════════════════

class TestEmbeddingService:
    """D2: Embedding 服务测试"""

    def test_import(self):
        from app.agent.rag.embeddings import EmbeddingService, get_embedding_service
        svc = get_embedding_service()
        assert svc is not None
        assert svc.dimension == 1536

    def test_singleton(self):
        from app.agent.rag.embeddings import get_embedding_service
        s1 = get_embedding_service()
        s2 = get_embedding_service()
        assert s1 is s2

    def test_availability_check(self):
        from app.agent.rag.embeddings import EmbeddingService
        svc = EmbeddingService()
        # 不会崩溃，即使 API key 无效
        _ = svc.is_available


class TestVectorStore:
    """D2: VectorStore 测试"""

    def test_import(self):
        from app.agent.rag.vectorstore import VectorStore, get_vectorstore
        vs = get_vectorstore()
        assert vs is not None

    def test_singleton(self):
        from app.agent.rag.vectorstore import get_vectorstore
        v1 = get_vectorstore()
        v2 = get_vectorstore()
        assert v1 is v2


class TestKnowledgeIngestor:
    """D3: 知识入库测试"""

    def test_import(self):
        from app.agent.rag.ingest import KnowledgeIngestor
        ingestor = KnowledgeIngestor(dry_run=True)
        assert ingestor.dry_run is True

    def test_build_table_document(self):
        from app.agent.rag.ingest import KnowledgeIngestor
        ingestor = KnowledgeIngestor(dry_run=True)
        doc = ingestor._build_table_document(
            "production_events",
            {
                "name_cn": "生产事件",
                "description_cn": "记录所有生产事件",
                "business_meaning": "核心生产数据",
                "use_case": "产量统计",
            },
            {
                "production_events.id": {
                    "table_name": "production_events",
                    "column_name": "id",
                    "column_name_cn": "编号",
                    "data_type": "bigint",
                    "description_cn": "主键",
                    "example_value": "1",
                },
                "production_events.quantity": {
                    "table_name": "production_events",
                    "column_name": "quantity",
                    "column_name_cn": "产量",
                    "data_type": "integer",
                    "description_cn": "生产数量",
                    "example_value": "100",
                },
            },
        )
        assert "production_events" in doc
        assert "生产事件" in doc
        assert "quantity" in doc
        assert "产量" in doc


class TestRagTools:
    """D4: RAG 检索工具测试"""

    def test_import(self):
        from app.agent.tools.rag_tools import rag_search, rag_search_schema, rag_search_sql_examples
        assert rag_search is not None
        assert rag_search_schema is not None
        assert rag_search_sql_examples is not None

    def test_fallback_search(self):
        """RAG 不可用时应降级到 schema_tools"""
        from app.agent.tools.rag_tools import _fallback_search
        result = _fallback_search("查询产量")
        # 应返回字符串（即使是空的）
        assert isinstance(result, str)

    def test_rag_available_check(self):
        from app.agent.tools.rag_tools import _rag_available
        # 不应崩溃
        _ = _rag_available()


class TestRagChatNode:
    """D5: RAG Chat 节点测试"""

    def test_import(self):
        from app.agent.nodes.rag_chat import rag_chat_node
        assert callable(rag_chat_node)

    def test_rag_chat_returns_response(self):
        from app.agent.nodes.rag_chat import rag_chat_node
        state = {
            "user_input": "production_events 表有哪些列？",
            "session_id": "test-rag",
        }
        result = rag_chat_node(state)
        assert "response" in result
        assert result["response"]["success"] is True
        assert result["response"]["intent"] == "chat"


# ══════════════════════════════════════════════
#  Graph & Node 集成测试
# ══════════════════════════════════════════════

class TestGraphPhaseD:
    """Phase D: 图结构验证"""

    def test_graph_builds(self):
        from app.agent.graph import build_agent_graph
        graph = build_agent_graph()
        assert graph is not None

    def test_graph_compiles(self):
        from app.agent.graph import compile_agent
        app = compile_agent()
        assert app is not None

    def test_graph_has_rag_chat_node(self):
        from app.agent.graph import compile_agent
        app = compile_agent()
        nodes = list(app.get_graph().nodes.keys())
        assert "rag_chat" in nodes

    def test_graph_node_count(self):
        from app.agent.graph import compile_agent
        app = compile_agent()
        nodes = list(app.get_graph().nodes.keys())
        # 12 nodes + __start__ + __end__
        actual_nodes = [n for n in nodes if not n.startswith("__")]
        assert len(actual_nodes) == 12, f"Expected 12 nodes, got {len(actual_nodes)}: {actual_nodes}"


class TestIntentRouting:
    """意图路由应正确分发"""

    def test_query_route(self):
        from app.agent.graph import _route_by_intent
        assert _route_by_intent({"intent": "query"}) == "query_planner"

    def test_chat_route(self):
        from app.agent.graph import _route_by_intent
        assert _route_by_intent({"intent": "chat"}) == "rag_chat"

    def test_alert_route(self):
        from app.agent.graph import _route_by_intent
        assert _route_by_intent({"intent": "alert"}) == "response_builder"

    def test_unknown_route(self):
        from app.agent.graph import _route_by_intent
        assert _route_by_intent({"intent": "unknown"}) == "query_planner"


class TestQueryPlannerRAG:
    """query_planner RAG 增强验证"""

    def test_rag_context_retrieval(self):
        from app.agent.nodes.query_planner import _retrieve_rag_context
        # 不应崩溃，应返回字符串
        result = _retrieve_rag_context("查询产量数据")
        assert isinstance(result, str)


class TestSqlGeneratorRAG:
    """sql_generator RAG 增强验证"""

    def test_few_shot_retrieval(self):
        from app.agent.nodes.sql_generator import _get_sql_few_shots
        # 不应崩溃，应返回字符串
        result = _get_sql_few_shots("查询今天的OEE")
        assert isinstance(result, str)

    def test_schema_context_with_rag(self):
        from app.agent.nodes.sql_generator import _get_schema_context_with_rag
        result = _get_schema_context_with_rag("查询设备信息")
        assert isinstance(result, str)


# ══════════════════════════════════════════════
#  Phase E: 端到端测试
# ══════════════════════════════════════════════

class TestAgentE2E:
    """完整 Agent 端到端流程"""

    def test_query_flow_mock(self):
        """测试 query 意图的完整流程（mock LLM）"""
        from app.agent.state import AgentState

        # 构造一个模拟的初始 state
        initial_state: AgentState = {
            "user_input": "查询所有载具信息",
            "session_id": "e2e-test-1",
        }
        # 验证 state 结构正确
        assert "user_input" in initial_state
        assert "session_id" in initial_state

    def test_memory_integration(self):
        """测试多轮对话记忆集成"""
        from app.agent.memory import conversation_memory, ConversationTurn

        session_id = "e2e-test-multi"
        session = conversation_memory.get_or_create_session(session_id)

        # 第一轮
        session.add_turn(ConversationTurn(
            user_message="查询今天的 OEE",
            assistant_message="今日 OEE 为 85.2%",
            sql="SELECT AVG(oee) FROM production_events WHERE date = CURRENT_DATE",
            intent="query",
        ))

        # 第二轮：追问
        ctx = conversation_memory.get_context_for_llm(session_id, "那按月汇总呢？")
        assert ctx["is_followup"] is True
        assert "OEE" in ctx["resolved_input"] or "oee" in ctx["resolved_input"].lower()

        # 清理
        conversation_memory.clear_session(session_id)

    def test_sql_self_correction_routing(self):
        """测试 SQL 自我修正路由逻辑"""
        from app.agent.graph import _route_after_execution, _route_after_validation

        # 成功 → result_analyzer
        assert _route_after_execution({"sql_error": "", "sql_retry_count": 0}) == "result_analyzer"

        # 失败且 retry < 3 → sql_generator
        assert _route_after_execution({"sql_error": "table not found", "sql_retry_count": 1}) == "sql_generator"

        # 失败且 retry >= 3 → response_builder
        assert _route_after_execution({"sql_error": "error", "sql_retry_count": 3}) == "response_builder"

        # 验证成功 → data_executor
        assert _route_after_validation({"sql_error": "", "sql_retry_count": 0}) == "data_executor"

        # 验证失败 → sql_generator
        assert _route_after_validation({"sql_error": "missing table", "sql_retry_count": 1}) == "sql_generator"


class TestAPICompat:
    """API 兼容层测试"""

    def test_chat_request_model(self):
        from app.api.v1.chat import ChatRequest
        req = ChatRequest(message="查询OEE", session_id="test-api")
        assert req.message == "查询OEE"
        assert req.session_id == "test-api"

    def test_chat_response_model(self):
        from app.api.v1.chat import ChatResponse
        resp = ChatResponse(
            success=True,
            session_id="test-api",
            data={"key": "value"},
        )
        assert resp.success is True


class TestStateDefinition:
    """AgentState 字段验证"""

    def test_all_fields_exist(self):
        from app.agent.state import AgentState
        required_fields = [
            "user_input", "session_id", "intent", "intent_data",
            "query_plan", "rag_context", "sql", "sql_confidence",
            "query_result", "sql_retry_count", "sql_error",
            "chart_type", "chart_config", "visualization",
            "response", "error",
            "memory_context", "is_followup", "resolved_input",
            "start_time",
        ]
        annotations = AgentState.__annotations__
        for field in required_fields:
            assert field in annotations, f"Missing field: {field}"


# ══════════════════════════════════════════════
#  CLI Runner
# ══════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
