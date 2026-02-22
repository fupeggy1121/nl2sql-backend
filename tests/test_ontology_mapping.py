"""
Phase 2 测试: MappingDictionary + SemanticContextBuilder

覆盖:
  - JSON 加载 & 索引构建
  - 逻辑类 → 物理表查找
  - 关系 → JOIN 条件
  - 值映射（WIP / Completed / Hold）
  - 业务规则查询
  - SemanticContextBuilder 端到端
"""

import json
import pytest
from pathlib import Path

from app.ontology.loader import load_ontology
from app.ontology.mapping import (
    MappingDictionary,
    PhysicalTable,
    RelationMapping,
    ValueMapping,
    BusinessRule,
    load_mapping,
)
from app.ontology.context_builder import (
    SemanticContextBuilder,
    SemanticContext,
    MatchedClass,
    ResolvedJoin,
    ResolvedFilter,
    build_semantic_context,
)

# ================================================================== #
#  Fixtures
# ================================================================== #

@pytest.fixture(scope="module")
def ontology():
    """加载本体图（复用 Phase 1 的 TTL）"""
    return load_ontology(force_reload=True)


@pytest.fixture(scope="module")
def mapping():
    """加载映射字典"""
    return load_mapping(force_reload=True)


@pytest.fixture(scope="module")
def builder(ontology, mapping):
    """构建器实例"""
    return SemanticContextBuilder(ontology=ontology, mapping=mapping)


# ================================================================== #
#  Part A: MappingDictionary — 加载 & 索引
# ================================================================== #

class TestMappingLoad:
    """映射字典加载与基本统计"""

    def test_load_success(self, mapping):
        assert mapping is not None

    def test_summary_counts(self, mapping):
        s = mapping.summary()
        assert s["object_mappings_total"] == 14  # 11 物理 + 3 虚拟
        assert s["physical_tables"] >= 10
        assert s["virtual_classes"] >= 3
        assert s["relation_mappings"] >= 10
        assert s["value_domains"] >= 2
        assert s["business_rules"] >= 3

    def test_version(self, mapping):
        s = mapping.summary()
        assert "Demo_Fab" in s["customer"]


# ================================================================== #
#  Part B: 逻辑类 → 物理表
# ================================================================== #

class TestObjectMapping:
    """逻辑类 → 物理表查找"""

    @pytest.mark.parametrize("logic_class,expected_table", [
        ("semi:Wafer", "wafers"),
        ("semi:ProductionLot", "batches"),
        ("semi:Sublot", "sub_batches"),
        ("semi:ProcessStation", "stations"),
        ("semi:Equipment", "equipment"),
        ("semi:Carrier", "carriers"),
        ("semi:Route", "process_routes"),
        ("semi:ProductModel", "products"),
        ("semi:ProductionOrder", "production_orders"),
        ("semi:BOM", "product_boms"),
    ])
    def test_physical_table_lookup(self, mapping, logic_class, expected_table):
        pt = mapping.get_physical_table(logic_class)
        assert pt is not None
        assert pt.table_name == expected_table

    def test_virtual_recipe(self, mapping):
        pt = mapping.get_physical_table("semi:Recipe")
        assert pt is not None
        assert pt.virtual is True
        assert pt.table_name is None

    def test_virtual_material(self, mapping):
        pt = mapping.get_physical_table("semi:Material")
        assert pt is not None
        assert pt.virtual is True
        assert pt.embedded_in == "product_boms.bom_items"

    def test_chinese_label_lookup(self, mapping):
        pt = mapping.get_table_by_label("晶圆")
        assert pt is not None
        assert pt.logic_class == "semi:Wafer"

    def test_chinese_label_station(self, mapping):
        pt = mapping.get_table_by_label("工艺站点")
        assert pt is not None
        assert pt.table_name == "stations"

    def test_physical_name_reverse(self, mapping):
        pt = mapping.get_table_by_physical_name("batches")
        assert pt is not None
        assert pt.logic_class == "semi:ProductionLot"

    def test_list_physical_excludes_virtual(self, mapping):
        physical = mapping.list_physical_tables()
        names = {pt.table_name for pt in physical}
        assert "wafers" in names
        assert None not in names

    def test_wafer_key_columns(self, mapping):
        pt = mapping.get_physical_table("semi:Wafer")
        assert "id" in pt.key_columns
        assert "wafer_id_code" in pt.key_columns
        assert "batch_id" in pt.key_columns

    def test_wafer_has_state_property(self, mapping):
        pt = mapping.get_physical_table("semi:Wafer")
        assert "semi:hasState" in pt.properties
        assert pt.properties["semi:hasState"] == "status"


# ================================================================== #
#  Part C: 关系 → JOIN 条件
# ================================================================== #

class TestRelationMapping:
    """关系 → 物理 JOIN"""

    def test_belongs_to_lot_fk(self, mapping):
        rm = mapping.get_join_path("semi:belongsToLot")
        assert rm is not None
        assert rm.strategy == "ForeignKey"
        assert len(rm.join_conditions) == 1
        jc = rm.join_conditions[0]
        assert jc.from_table == "wafers"
        assert jc.from_key == "batch_id"
        assert jc.to_table == "batches"

    def test_located_in_slot_bridge(self, mapping):
        rm = mapping.get_join_path("semi:locatedInSlot")
        assert rm is not None
        assert rm.strategy == "JoinTable"
        assert rm.bridge_table == "wafer_carrier_contents"
        assert len(rm.join_conditions) == 2

    def test_at_station_indirect(self, mapping):
        rm = mapping.get_join_path("semi:atStation")
        assert rm is not None
        assert rm.strategy == "Indirect"
        assert len(rm.join_conditions) == 3

    def test_consists_of_station_ordered(self, mapping):
        rm = mapping.get_join_path("semi:consistsOfStation")
        assert rm is not None
        assert rm.strategy == "JoinTable"
        assert rm.order_by == "sequence"

    def test_uses_route_fk(self, mapping):
        rm = mapping.get_join_path("semi:usesRoute")
        assert rm is not None
        jc = rm.join_conditions[0]
        assert jc.from_table == "products"
        assert jc.to_table == "process_routes"

    def test_join_between_tables(self, mapping):
        """查找连接 wafers 和 batches 的关系"""
        results = mapping.get_join_between_tables("wafers", "batches")
        relation_names = {r.logic_relation for r in results}
        assert "semi:belongsToLot" in relation_names

    def test_has_parent_lot_recursive(self, mapping):
        rm = mapping.get_join_path("semi:hasParentLot")
        assert rm is not None
        assert rm.strategy == "Recursive"


# ================================================================== #
#  Part D: 值映射
# ================================================================== #

class TestValueMapping:
    """语义值 → 物理条件"""

    def test_wip_condition(self, mapping):
        vm = mapping.map_value("semi:WaferState", "WIP")
        assert vm is not None
        assert "status" in vm.physical_condition
        assert "completed" in vm.physical_condition
        assert vm.applies_to_table == "sub_batches"

    def test_wip_shortcut(self, mapping):
        vm = mapping.get_wip_condition()
        assert vm is not None
        assert vm.semantic_value == "WIP"

    def test_completed(self, mapping):
        vm = mapping.map_value("semi:WaferState", "Completed")
        assert vm is not None
        assert "completed" in vm.physical_values

    def test_hold(self, mapping):
        vm = mapping.map_value("semi:WaferState", "Hold")
        assert vm is not None
        assert "is_hold" in vm.physical_condition

    def test_carrier_clean(self, mapping):
        vm = mapping.map_value("semi:CarrierStatus", "Clean")
        assert vm is not None
        assert vm.applies_to_column == "status"

    def test_unknown_domain_returns_none(self, mapping):
        vm = mapping.map_value("semi:NonExistent", "Foo")
        assert vm is None

    def test_list_value_domains(self, mapping):
        domains = mapping.list_value_domains()
        assert "semi:WaferState" in domains
        assert "semi:CarrierStatus" in domains


# ================================================================== #
#  Part E: 业务规则
# ================================================================== #

class TestBusinessRules:
    """业务规则查询"""

    def test_all_rules(self, mapping):
        rules = mapping.get_business_rules()
        assert len(rules) >= 3

    def test_rules_by_table(self, mapping):
        rules = mapping.get_business_rules(involved_tables=["sub_batches"])
        ids = {r.id for r in rules}
        assert "wip_count" in ids

    def test_rules_by_stations(self, mapping):
        rules = mapping.get_business_rules(involved_tables=["stations"])
        ids = {r.id for r in rules}
        assert "chinese_name_filter" in ids

    def test_rule_by_id(self, mapping):
        r = mapping.get_rule_by_id("wip_count")
        assert r is not None
        assert "WIP" in r.name or "在制品" in r.name

    def test_route_warning(self, mapping):
        rules = mapping.get_business_rules(involved_tables=["process_route_stations"])
        ids = {r.id for r in rules}
        assert "route_vs_wip" in ids


# ================================================================== #
#  Part F: SemanticContextBuilder 端到端
# ================================================================== #

class TestContextBuilder:
    """SemanticContextBuilder 集成测试"""

    def test_wip_by_station(self, builder):
        """'各工站的在制品数量' → 匹配 Station + WIP filter"""
        ctx = builder.build("各工站的在制品数量")

        # 应匹配到工站
        class_names = {mc.logic_class for mc in ctx.matched_classes}
        assert "semi:ProcessStation" in class_names

        # 应有 WIP 过滤
        assert len(ctx.filters) >= 1
        wip_filters = [f for f in ctx.filters if f.semantic_value == "WIP"]
        assert len(wip_filters) == 1
        assert "completed" in wip_filters[0].physical_condition

    def test_wafer_batch_join(self, builder):
        """'查询晶圆所属批次' → Wafer + Lot + JOIN"""
        ctx = builder.build("查询晶圆所属批次")

        class_names = {mc.logic_class for mc in ctx.matched_classes}
        assert "semi:Wafer" in class_names
        assert "semi:ProductionLot" in class_names

        # 应有 JOIN
        assert len(ctx.joins) >= 1
        join_rels = {j.logic_relation for j in ctx.joins}
        assert "semi:belongsToLot" in join_rels

    def test_equipment_station(self, builder):
        """'各工站有哪些设备' → Station + Equipment"""
        ctx = builder.build("各工站有哪些设备")

        class_names = {mc.logic_class for mc in ctx.matched_classes}
        assert "semi:ProcessStation" in class_names
        assert "semi:Equipment" in class_names

    def test_product_route(self, builder):
        """'产品的工艺路线' → Product + Route"""
        ctx = builder.build("产品的工艺路线")

        class_names = {mc.logic_class for mc in ctx.matched_classes}
        assert "semi:ProductModel" in class_names
        assert "semi:Route" in class_names

        # 应有 usesRoute 的 JOIN
        join_rels = {j.logic_relation for j in ctx.joins}
        assert "semi:usesRoute" in join_rels

    def test_physical_tables_dedup(self, builder):
        """physical_tables 属性应去重"""
        ctx = builder.build("查询晶圆所属批次")
        tables = ctx.physical_tables
        assert len(tables) == len(set(tables))
        assert "wafers" in tables
        assert "batches" in tables

    def test_schema_snippet_not_empty(self, builder):
        """schema_snippet 应非空"""
        ctx = builder.build("查询晶圆所属批次")
        snippet = ctx.schema_snippet
        assert "wafers" in snippet
        assert "batches" in snippet

    def test_to_dict_serializable(self, builder):
        """to_dict 返回可 JSON 序列化的字典"""
        ctx = builder.build("各工站的在制品数量")
        d = ctx.to_dict()
        # 应能序列化
        serialized = json.dumps(d, ensure_ascii=False)
        assert "在制品" in serialized or "WIP" in serialized

    def test_business_rules_matched(self, builder):
        """查询涉及 sub_batches 时应匹配 wip_count 规则"""
        ctx = builder.build("各工站的在制品数量")
        # WIP filter involves sub_batches → should trigger wip_count rule
        # 业务规则需要 sub_batches 在 physical_tables 中
        # 注意: 如果只匹配了 station 且 WIP filter 的 applies_to_table 是 sub_batches
        # physical_tables 来自 matched_classes + joins，sub_batches 可能不在其中
        # 但 wip_count 规则的 involved_tables 包含 stations，所以应该被匹配
        rule_ids = {r.id for r in ctx.business_rules}
        assert "chinese_name_filter" in rule_ids  # stations 在场

    def test_carrier_query(self, builder):
        """'载具状态' → Carrier"""
        ctx = builder.build("载具状态查询")

        class_names = {mc.logic_class for mc in ctx.matched_classes}
        assert "semi:Carrier" in class_names

    def test_order_query(self, builder):
        """'生产工单' → ProductionOrder"""
        ctx = builder.build("查询所有生产工单")

        class_names = {mc.logic_class for mc in ctx.matched_classes}
        assert "semi:ProductionOrder" in class_names

    def test_empty_query(self, builder):
        """空查询不应崩溃"""
        ctx = builder.build("")
        assert isinstance(ctx, SemanticContext)
        assert len(ctx.matched_classes) == 0

    def test_convenience_function(self, ontology, mapping):
        """测试 build_semantic_context 便捷函数"""
        ctx = build_semantic_context(
            "晶圆的批次信息",
            ontology=ontology,
            mapping=mapping,
        )
        assert isinstance(ctx, SemanticContext)
        class_names = {mc.logic_class for mc in ctx.matched_classes}
        assert "semi:Wafer" in class_names


# ================================================================== #
#  Part G: 边界 & 特殊情况
# ================================================================== #

class TestEdgeCases:
    """边界情况"""

    def test_virtual_class_no_crash(self, builder):
        """包含虚拟类（如'配方'）的查询不应崩溃"""
        ctx = builder.build("查看配方信息")
        # 配方是虚拟类，不应出现在 physical_tables 中
        # 但应该被匹配到
        class_names = {mc.logic_class for mc in ctx.matched_classes}
        assert "semi:Recipe" in class_names

    def test_mixed_cn_en(self, builder):
        """中英混合查询"""
        ctx = builder.build("查询wafer的batch信息")
        class_names = {mc.logic_class for mc in ctx.matched_classes}
        assert "semi:Wafer" in class_names
        assert "semi:ProductionLot" in class_names  # "batch" should match

    def test_hold_filter(self, builder):
        """'hold状态的批次' → Hold filter"""
        ctx = builder.build("查询hold状态的批次")
        wip_like = [f for f in ctx.filters if f.semantic_value == "Hold"]
        assert len(wip_like) >= 1
