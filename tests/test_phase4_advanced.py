"""
Phase 4 测试: 高级特性 — 值映射增强 + 递归追溯 CTE + 血缘可视化 API

覆盖:
  Part A: 值映射增强 — 新增域 (EquipmentStatus, OrderStatus, etc.)
  Part B: 递归追溯 — RecursiveMapping 解析 + CTE 编译
  Part C: 血缘可视化 — Ontology API 端点
  Part D: 上下文构建器递归检测
"""

import pytest
from pathlib import Path

from app.ontology.loader import load_ontology
from app.ontology.mapping import (
    MappingDictionary,
    RecursiveMapping,
    load_mapping,
)
from app.ontology.context_builder import (
    SemanticContextBuilder,
    SemanticContext,
    ResolvedRecursive,
    ResolvedFilter,
    build_semantic_context,
)


# ================================================================== #
#  Fixtures
# ================================================================== #

@pytest.fixture(scope="module")
def ontology():
    return load_ontology(force_reload=True)


@pytest.fixture(scope="module")
def mapping():
    return load_mapping(force_reload=True)


@pytest.fixture(scope="module")
def builder(ontology, mapping):
    return SemanticContextBuilder(ontology=ontology, mapping=mapping)


# ================================================================== #
#  Part A: 值映射增强
# ================================================================== #

class TestValueMappingEnhanced:
    """新增值域的正确解析"""

    def test_equipment_status_running(self, mapping):
        vm = mapping.map_value("semi:EquipmentStatus", "Running")
        assert vm is not None
        assert vm.applies_to_table == "equipment"
        assert "running" in vm.physical_values

    def test_equipment_status_down(self, mapping):
        vm = mapping.map_value("semi:EquipmentStatus", "Down")
        assert vm is not None
        assert "down" in vm.physical_values
        assert "fault" in vm.physical_values

    def test_equipment_status_maintenance(self, mapping):
        vm = mapping.map_value("semi:EquipmentStatus", "Maintenance")
        assert vm is not None
        assert "pm" in vm.physical_values

    def test_order_status_active(self, mapping):
        vm = mapping.map_value("semi:OrderStatus", "Active")
        assert vm is not None
        assert vm.applies_to_table == "production_orders"

    def test_order_status_cancelled(self, mapping):
        vm = mapping.map_value("semi:OrderStatus", "Cancelled")
        assert vm is not None
        assert "cancelled" in vm.physical_values

    def test_order_priority_high(self, mapping):
        vm = mapping.map_value("semi:OrderPriority", "High")
        assert vm is not None
        assert vm.applies_to_column == "priority"
        assert "urgent" in vm.physical_values

    def test_order_priority_low(self, mapping):
        vm = mapping.map_value("semi:OrderPriority", "Low")
        assert vm is not None
        assert "low" in vm.physical_values

    def test_station_status_active(self, mapping):
        vm = mapping.map_value("semi:StationStatus", "Active")
        assert vm is not None
        assert vm.applies_to_table == "stations"

    def test_route_status_active(self, mapping):
        vm = mapping.map_value("semi:RouteStatus", "Active")
        assert vm is not None
        assert "released" in vm.physical_values

    def test_product_status_inactive(self, mapping):
        vm = mapping.map_value("semi:ProductStatus", "Inactive")
        assert vm is not None
        assert "discontinued" in vm.physical_values

    def test_value_domains_count(self, mapping):
        domains = mapping.list_value_domains()
        # 3 old + 6 new = 9
        assert len(domains) >= 9

    def test_original_wip_still_works(self, mapping):
        """确保原有值映射未被破坏"""
        vm = mapping.map_value("semi:WaferState", "WIP")
        assert vm is not None
        assert "sub_batches.status != 'completed'" in vm.physical_condition

    def test_original_carrier_still_works(self, mapping):
        vm = mapping.map_value("semi:CarrierStatus", "Contaminated")
        assert vm is not None
        assert "dirty" in vm.physical_values


class TestValueKeywordsEnhanced:
    """新增关键词在 context_builder 中的触发"""

    def test_equipment_down_keyword(self, builder):
        ctx = builder.build("宕机的设备有哪些")
        down_filters = [f for f in ctx.filters if f.semantic_value == "Down"]
        assert len(down_filters) >= 1
        assert down_filters[0].semantic_domain == "semi:EquipmentStatus"

    def test_equipment_idle_keyword(self, builder):
        ctx = builder.build("空闲设备数量")
        idle_filters = [f for f in ctx.filters if f.semantic_value == "Idle"]
        assert len(idle_filters) >= 1

    def test_urgent_order_keyword(self, builder):
        ctx = builder.build("紧急工单列表")
        high_filters = [f for f in ctx.filters if f.semantic_value == "High"]
        assert len(high_filters) >= 1
        assert high_filters[0].semantic_domain == "semi:OrderPriority"

    def test_product_discontinued_keyword(self, builder):
        ctx = builder.build("停产产品")
        inactive_filters = [f for f in ctx.filters if f.semantic_value == "Inactive"
                           and f.semantic_domain == "semi:ProductStatus"]
        assert len(inactive_filters) >= 1

    def test_pm_maintenance_keyword(self, builder):
        ctx = builder.build("pm状态的设备")
        maint_filters = [f for f in ctx.filters if f.semantic_value == "Maintenance"]
        assert len(maint_filters) >= 1


# ================================================================== #
#  Part B: 递归追溯 CTE
# ================================================================== #

class TestRecursiveMapping:
    """递归关系解析"""

    def test_recursive_mapping_parsed(self, mapping):
        rec = mapping.get_recursive_mapping("semi:hasParentLot")
        assert rec is not None
        assert isinstance(rec, RecursiveMapping)
        assert rec.table == "batches"
        assert rec.self_key == "id"
        assert rec.parent_key == "parent_batch_id"
        assert rec.max_depth == 20

    def test_recursive_mapping_not_found(self, mapping):
        assert mapping.get_recursive_mapping("semi:belongsToLot") is None

    def test_list_recursive_relations(self, mapping):
        recs = mapping.list_recursive_relations()
        assert len(recs) >= 1
        names = [r.logic_relation for r in recs]
        assert "semi:hasParentLot" in names

    def test_summary_includes_recursive(self, mapping):
        s = mapping.summary()
        assert "recursive_relations" in s
        assert s["recursive_relations"] >= 1


class TestCTECompiler:
    """WITH RECURSIVE CTE 编译"""

    def test_compile_default(self, mapping):
        cte = mapping.compile_recursive_cte("semi:hasParentLot")
        assert cte is not None
        assert "WITH RECURSIVE" in cte
        assert "lot_tree" in cte
        assert "parent_batch_id" in cte
        assert "lvl" in cte
        assert "UNION ALL" in cte

    def test_compile_with_anchor(self, mapping):
        cte = mapping.compile_recursive_cte(
            "semi:hasParentLot",
            anchor_condition="batch_code = 'B001'",
        )
        assert cte is not None
        assert "batch_code = 'B001'" in cte
        assert "parent_batch_id IS NULL" not in cte

    def test_compile_custom_alias(self, mapping):
        cte = mapping.compile_recursive_cte(
            "semi:hasParentLot",
            cte_alias="batch_hierarchy",
        )
        assert "batch_hierarchy" in cte
        assert "lot_tree" not in cte

    def test_compile_no_depth(self, mapping):
        cte = mapping.compile_recursive_cte(
            "semi:hasParentLot",
            include_depth=False,
        )
        assert "lvl" not in cte

    def test_compile_with_columns(self, mapping):
        cte = mapping.compile_recursive_cte(
            "semi:hasParentLot",
            select_columns=["id", "batch_code", "parent_batch_id"],
        )
        assert "t.id" in cte
        assert "t.batch_code" in cte

    def test_compile_nonexistent_returns_none(self, mapping):
        result = mapping.compile_recursive_cte("semi:nonExistent")
        assert result is None


# ================================================================== #
#  Part C: 上下文构建器递归检测
# ================================================================== #

class TestContextBuilderRecursive:
    """context_builder 的递归追溯检测"""

    def test_parent_lot_keyword(self, builder):
        ctx = builder.build("查询某批次的父批次追溯链")
        assert len(ctx.recursive) >= 1
        rec = ctx.recursive[0]
        assert rec.logic_relation == "semi:hasParentLot"
        assert "WITH RECURSIVE" in rec.cte_sql

    def test_lot_tree_keyword(self, builder):
        ctx = builder.build("显示批次树结构")
        assert len(ctx.recursive) >= 1

    def test_traceability_keyword(self, builder):
        ctx = builder.build("追溯批次B001的完整层级")
        assert len(ctx.recursive) >= 1

    def test_no_recursive_for_normal_query(self, builder):
        ctx = builder.build("各工站的在制品数量")
        assert len(ctx.recursive) == 0

    def test_recursive_in_to_dict(self, builder):
        ctx = builder.build("批次层级追溯")
        d = ctx.to_dict()
        assert "recursive" in d
        assert len(d["recursive"]) >= 1
        assert "cte_sql" in d["recursive"][0]

    def test_recursive_in_schema_snippet(self, builder):
        ctx = builder.build("查询父批次")
        snippet = ctx.schema_snippet
        assert "WITH RECURSIVE" in snippet


# ================================================================== #
#  Part D: 血缘可视化 API (单元测试, 不启动服务器)
# ================================================================== #

class TestOntologyAPIHelpers:
    """直接测试 API 辅助函数"""

    def test_normalize_uri_plain(self):
        from app.api.v1.ontology import _normalize_uri
        assert _normalize_uri("Wafer") == "semi:Wafer"
        assert _normalize_uri("semi:Wafer") == "semi:Wafer"

    def test_path_to_hops(self):
        from app.api.v1.ontology import _path_to_hops, LineageHop
        path = [
            ("semi:Wafer", "semi:belongsToLot", "semi:ProductionLot"),
            ("semi:ProductionLot", "^semi:containsSublot", "semi:Sublot"),
        ]
        hops = _path_to_hops(path)
        assert len(hops) == 2
        assert hops[0].from_class == "semi:Wafer"
        assert hops[0].is_reverse is False
        assert hops[1].is_reverse is True
        assert hops[1].relation == "semi:containsSublot"


class TestOntologyAPIEndpoints:
    """使用 TestClient 测试 API 端点"""

    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from app.api.v1.ontology import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)
        return TestClient(test_app)

    def test_summary(self, client):
        resp = client.get("/api/v1/ontology/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "ontology" in data
        assert "mapping" in data
        assert data["ontology"]["classes"] >= 10
        assert data["mapping"]["value_domains"] >= 9

    def test_list_classes(self, client):
        resp = client.get("/api/v1/ontology/classes")
        assert resp.status_code == 200
        classes = resp.json()
        assert len(classes) >= 14
        logic_classes = [c["logic_class"] for c in classes]
        assert "semi:Wafer" in logic_classes

    def test_lineage_wafer_to_order(self, client):
        resp = client.get("/api/v1/ontology/lineage?source=Wafer&target=ProductionOrder")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "semi:Wafer"
        assert data["target"] == "semi:ProductionOrder"
        assert len(data["ontology_path"]) >= 1
        assert len(data["physical_joins"]) >= 1

    def test_lineage_not_found(self, client):
        resp = client.get("/api/v1/ontology/lineage?source=Wafer&target=NotExist")
        assert resp.status_code == 404

    def test_resolve_query(self, client):
        resp = client.post("/api/v1/ontology/resolve", json={"query": "各工站的在制品数量"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        ctx = data["context"]
        assert len(ctx["matched_classes"]) >= 1
        assert len(ctx["filters"]) >= 1

    def test_resolve_with_recursive(self, client):
        resp = client.post("/api/v1/ontology/resolve", json={"query": "追溯批次B001的父批次"})
        assert resp.status_code == 200
        ctx = resp.json()["context"]
        assert len(ctx["recursive"]) >= 1

    def test_recursive_endpoint(self, client):
        resp = client.get("/api/v1/ontology/recursive?relation=semi:hasParentLot")
        assert resp.status_code == 200
        data = resp.json()
        assert "cte_sql" in data
        assert "WITH RECURSIVE" in data["cte_sql"]

    def test_recursive_with_anchor(self, client):
        resp = client.get(
            "/api/v1/ontology/recursive",
            params={"relation": "semi:hasParentLot", "anchor": "batch_code = 'B001'"},
        )
        assert resp.status_code == 200
        assert "batch_code = 'B001'" in resp.json()["cte_sql"]

    def test_recursive_not_found(self, client):
        resp = client.get("/api/v1/ontology/recursive?relation=semi:belongsToLot")
        assert resp.status_code == 404

    def test_values_endpoint(self, client):
        resp = client.get("/api/v1/ontology/values")
        assert resp.status_code == 200
        data = resp.json()
        assert data["domains_count"] >= 9
        assert "semi:EquipmentStatus" in data["domains"]
        assert "semi:OrderPriority" in data["domains"]

    def test_reload_endpoint(self, client):
        resp = client.post("/api/v1/ontology/reload")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["ontology"]["classes"] >= 10
        assert data["mapping"]["value_domains"] >= 9


# ================================================================== #
#  Part E: 新业务规则
# ================================================================== #

class TestNewBusinessRules:
    """Phase 4 新增业务规则"""

    def test_equipment_utilization_rule(self, mapping):
        rules = mapping.get_business_rules(involved_tables=["equipment"])
        rule_ids = [r.id for r in rules]
        assert "equipment_utilization" in rule_ids

    def test_order_priority_rule(self, mapping):
        rules = mapping.get_business_rules(involved_tables=["production_orders"])
        rule_ids = [r.id for r in rules]
        assert "order_priority_filter" in rule_ids

    def test_recursive_parent_lot_rule(self, mapping):
        rules = mapping.get_business_rules(involved_tables=["batches"])
        rule_ids = [r.id for r in rules]
        assert "recursive_parent_lot" in rule_ids

    def test_total_business_rules(self, mapping):
        all_rules = mapping.get_business_rules()
        assert len(all_rules) >= 7  # 4 original + 3 new
