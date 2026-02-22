"""
语义上下文构建器 (SemanticContextBuilder)

输入: 用户自然语言查询 + OntologyGraph + MappingDictionary
输出: SemanticContext — 包含匹配的逻辑类、物理表、JOIN路径、值过滤、业务规则

核心流程:
  1. 中文关键词 → 本体类/关系匹配
  2. 两两本体类之间的路径发现
  3. 路径上每跳关系 → 物理 JOIN 条件翻译
  4. 语义值映射 (如 "在制品" → WIP → sub_batches.status != 'completed')
  5. 业务规则匹配
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from app.ontology.loader import get_ontology
from app.ontology.mapping import (
    BusinessRule,
    JoinCondition,
    MappingDictionary,
    PhysicalTable,
    RecursiveMapping,
    RelationMapping,
    ValueMapping,
    get_mapping,
)
from app.ontology.model import OntologyClass, OntologyGraph

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------- #
# SemanticContext — 构建的最终输出
# --------------------------------------------------------------------- #

@dataclass
class MatchedClass:
    """一个被匹配到的逻辑类及其物理映射"""
    keyword: str                    # 触发匹配的原始关键词
    logic_class: str                # e.g. "semi:Wafer"
    label_cn: str                   # e.g. "晶圆"
    physical_table: Optional[str]   # e.g. "wafers", None if virtual
    primary_key: Optional[str]
    display_column: Optional[str]
    key_columns: List[str] = field(default_factory=list)
    virtual: bool = False


@dataclass
class ResolvedJoin:
    """一段物理 JOIN 路径"""
    logic_relation: str             # e.g. "semi:belongsToLot"
    strategy: str                   # ForeignKey / JoinTable / Indirect
    conditions: List[JoinCondition] = field(default_factory=list)
    bridge_table: Optional[str] = None
    order_by: Optional[str] = None
    note: Optional[str] = None


@dataclass
class ResolvedFilter:
    """一个语义值 → 物理过滤条件"""
    semantic_domain: str            # e.g. "semi:WaferState"
    semantic_value: str             # e.g. "WIP"
    description: str
    physical_condition: Optional[str] = None  # SQL WHERE 片段
    physical_values: Optional[List[str]] = None
    applies_to_table: Optional[str] = None
    applies_to_column: Optional[str] = None


@dataclass
class ResolvedRecursive:
    """递归追溯解析结果 — WITH RECURSIVE CTE 片段"""
    logic_relation: str             # e.g. "semi:hasParentLot"
    table: str                      # e.g. "batches"
    self_key: str
    parent_key: str
    max_depth: int
    cte_sql: str                    # 编译好的 WITH RECURSIVE SQL
    description: str = ""


@dataclass
class SemanticContext:
    """语义解析的最终上下文 — 传递给 SQL 编译器"""
    user_query: str
    matched_classes: List[MatchedClass] = field(default_factory=list)
    joins: List[ResolvedJoin] = field(default_factory=list)
    filters: List[ResolvedFilter] = field(default_factory=list)
    recursive: List[ResolvedRecursive] = field(default_factory=list)
    business_rules: List[BusinessRule] = field(default_factory=list)

    # 快捷属性
    @property
    def physical_tables(self) -> List[str]:
        """所有涉及的物理表名(去重)"""
        tables: Set[str] = set()
        for mc in self.matched_classes:
            if mc.physical_table:
                tables.add(mc.physical_table)
        for j in self.joins:
            for c in j.conditions:
                tables.add(c.from_table)
                tables.add(c.to_table)
            if j.bridge_table:
                tables.add(j.bridge_table)
        return sorted(tables)

    @property
    def schema_snippet(self) -> str:
        """生成精简的 schema 提示片段，供 LLM 或 SQL 编译器使用"""
        lines = []
        for mc in self.matched_classes:
            if mc.physical_table and mc.key_columns:
                cols = ", ".join(mc.key_columns)
                lines.append(f"-- {mc.label_cn}({mc.logic_class})")
                lines.append(f"TABLE {mc.physical_table} ({cols})")
        if self.joins:
            lines.append("")
            lines.append("-- JOIN conditions")
            for j in self.joins:
                for c in j.conditions:
                    lines.append(
                        f"  {c.from_table}.{c.from_key} = {c.to_table}.{c.to_key}"
                    )
        if self.filters:
            lines.append("")
            lines.append("-- Filters")
            for f in self.filters:
                if f.physical_condition:
                    lines.append(f"  WHERE {f.physical_condition}  -- {f.description}")
                elif f.physical_values:
                    vals = ", ".join(f"'{v}'" for v in f.physical_values)
                    lines.append(
                        f"  WHERE {f.applies_to_table}.{f.applies_to_column} IN ({vals})  -- {f.description}"
                    )
        if self.recursive:
            lines.append("")
            lines.append("-- Recursive CTE (batch/lot tree)")
            for r in self.recursive:
                lines.append(f"  -- {r.description}")
                lines.append(r.cte_sql)
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（便于注入 AgentState）"""
        return {
            "user_query": self.user_query,
            "matched_classes": [
                {
                    "keyword": mc.keyword,
                    "logic_class": mc.logic_class,
                    "label_cn": mc.label_cn,
                    "physical_table": mc.physical_table,
                    "primary_key": mc.primary_key,
                    "display_column": mc.display_column,
                    "key_columns": mc.key_columns,
                    "virtual": mc.virtual,
                }
                for mc in self.matched_classes
            ],
            "physical_tables": self.physical_tables,
            "joins": [
                {
                    "logic_relation": j.logic_relation,
                    "strategy": j.strategy,
                    "conditions": [
                        {"from": f"{c.from_table}.{c.from_key}",
                         "to": f"{c.to_table}.{c.to_key}"}
                        for c in j.conditions
                    ],
                    "bridge_table": j.bridge_table,
                }
                for j in self.joins
            ],
            "filters": [
                {
                    "semantic_domain": f.semantic_domain,
                    "semantic_value": f.semantic_value,
                    "description": f.description,
                    "physical_condition": f.physical_condition,
                    "physical_values": f.physical_values,
                    "applies_to_table": f.applies_to_table,
                    "applies_to_column": f.applies_to_column,
                }
                for f in self.filters
            ],
            "recursive": [
                {
                    "logic_relation": r.logic_relation,
                    "table": r.table,
                    "self_key": r.self_key,
                    "parent_key": r.parent_key,
                    "max_depth": r.max_depth,
                    "cte_sql": r.cte_sql,
                    "description": r.description,
                }
                for r in self.recursive
            ],
            "business_rules": [
                {"id": br.id, "name": br.name, "description": br.description}
                for br in self.business_rules
            ],
            "schema_snippet": self.schema_snippet,
        }


# --------------------------------------------------------------------- #
# Synonym dictionary: 常见简称/缩写 → 本体类 URI
# --------------------------------------------------------------------- #

_CLASS_SYNONYMS: Dict[str, str] = {
    # 中文简称
    "工站": "semi:ProcessStation",
    "工序": "semi:ProcessStation",
    "站点": "semi:ProcessStation",
    "批次": "semi:ProductionLot",
    "lot": "semi:ProductionLot",
    "batch": "semi:ProductionLot",
    "子批": "semi:Sublot",
    "sublot": "semi:Sublot",
    "晶圆": "semi:Wafer",
    "wafer": "semi:Wafer",
    "设备": "semi:Equipment",
    "机台": "semi:Equipment",
    "载具": "semi:Carrier",
    "花篮": "semi:Carrier",
    "carrier": "semi:Carrier",
    "产品": "semi:ProductModel",
    "product": "semi:ProductModel",
    "工单": "semi:ProductionOrder",
    "order": "semi:ProductionOrder",
    "路线": "semi:Route",
    "route": "semi:Route",
    "配方": "semi:Recipe",
    "recipe": "semi:Recipe",
    "物料": "semi:Material",
    "bom": "semi:BOM",
    "物料清单": "semi:BOM",
}


# --------------------------------------------------------------------- #
# Recursive / tree traversal trigger keywords
# --------------------------------------------------------------------- #

_RECURSIVE_KEYWORDS: Dict[str, str] = {
    "父批次": "semi:hasParentLot",
    "母批次": "semi:hasParentLot",
    "批次树": "semi:hasParentLot",
    "追溯": "semi:hasParentLot",
    "批次层级": "semi:hasParentLot",
    "parent lot": "semi:hasParentLot",
    "lot tree": "semi:hasParentLot",
}


# --------------------------------------------------------------------- #
# Keyword dictionary for value mapping triggers
# --------------------------------------------------------------------- #

# 中文关键词 → (语义域, 语义值)
_VALUE_KEYWORDS: Dict[str, Tuple[str, str]] = {
    # ── WaferState (sub_batches.status) ──
    "在制品": ("semi:WaferState", "WIP"),
    "wip": ("semi:WaferState", "WIP"),
    "在制": ("semi:WaferState", "WIP"),
    "已完成": ("semi:WaferState", "Completed"),
    "完工": ("semi:WaferState", "Completed"),
    "hold": ("semi:WaferState", "Hold"),
    "暂停": ("semi:WaferState", "Hold"),

    # ── CarrierStatus ──
    "污染": ("semi:CarrierStatus", "Contaminated"),
    "脏": ("semi:CarrierStatus", "Contaminated"),
    "清洁": ("semi:CarrierStatus", "Clean"),

    # ── EquipmentStatus (Phase 4) ──
    "运行中": ("semi:EquipmentStatus", "Running"),
    "running": ("semi:EquipmentStatus", "Running"),
    "空闲": ("semi:EquipmentStatus", "Idle"),
    "idle": ("semi:EquipmentStatus", "Idle"),
    "待机": ("semi:EquipmentStatus", "Idle"),
    "维护": ("semi:EquipmentStatus", "Maintenance"),
    "保养": ("semi:EquipmentStatus", "Maintenance"),
    "pm": ("semi:EquipmentStatus", "Maintenance"),
    "宕机": ("semi:EquipmentStatus", "Down"),
    "故障": ("semi:EquipmentStatus", "Down"),
    "down": ("semi:EquipmentStatus", "Down"),

    # ── OrderStatus (Phase 4) ──
    "工单进行中": ("semi:OrderStatus", "Active"),
    "工单完成": ("semi:OrderStatus", "Completed"),
    "工单取消": ("semi:OrderStatus", "Cancelled"),

    # ── OrderPriority (Phase 4) ──
    "紧急": ("semi:OrderPriority", "High"),
    "高优先级": ("semi:OrderPriority", "High"),
    "urgent": ("semi:OrderPriority", "High"),
    "中优先级": ("semi:OrderPriority", "Medium"),
    "低优先级": ("semi:OrderPriority", "Low"),

    # ── StationStatus (Phase 4) ──
    "工站停用": ("semi:StationStatus", "Inactive"),
    "工站维护": ("semi:StationStatus", "Maintenance"),

    # ── RouteStatus (Phase 4) ──
    "路线停用": ("semi:RouteStatus", "Inactive"),

    # ── ProductStatus (Phase 4) ──
    "停产": ("semi:ProductStatus", "Inactive"),
    "在产": ("semi:ProductStatus", "Active"),
}


# --------------------------------------------------------------------- #
# SemanticContextBuilder
# --------------------------------------------------------------------- #

class SemanticContextBuilder:
    """
    从用户查询构建 SemanticContext。

    使用方式:
        builder = SemanticContextBuilder()
        ctx = builder.build("各工站的在制品数量")
    """

    def __init__(
        self,
        ontology: Optional[OntologyGraph] = None,
        mapping: Optional[MappingDictionary] = None,
    ):
        self._ontology = ontology or get_ontology()
        self._mapping = mapping or get_mapping()

    # ----------------------------------------------------------------- #
    # 主入口
    # ----------------------------------------------------------------- #

    def build(self, user_query: str) -> SemanticContext:
        """
        完整构建流程:
          1. 提取关键词 → 匹配本体类
          2. 提取值关键词 → 值映射过滤
          3. 类间路径发现 → 物理 JOIN 翻译
          4. 业务规则匹配
        """
        ctx = SemanticContext(user_query=user_query)

        # Step 1: 匹配本体类
        matched = self._match_classes(user_query)
        ctx.matched_classes = matched
        logger.info(
            "Matched %d classes from query: %s",
            len(matched),
            [m.keyword for m in matched],
        )

        # Step 2: 值映射
        filters = self._match_values(user_query)
        ctx.filters = filters
        if filters:
            logger.info(
                "Matched %d value filters: %s",
                len(filters),
                [(f.semantic_domain, f.semantic_value) for f in filters],
            )

        # Step 2.5: 递归追溯检测
        recursive = self._match_recursive(user_query)
        ctx.recursive = recursive
        if recursive:
            logger.info(
                "Matched %d recursive patterns: %s",
                len(recursive),
                [r.logic_relation for r in recursive],
            )

        # Step 3: 路径发现 + JOIN 翻译
        joins = self._resolve_joins(matched)
        ctx.joins = joins
        if joins:
            logger.info("Resolved %d join paths", len(joins))

        # Step 4: 业务规则
        rules = self._match_business_rules(ctx.physical_tables)
        ctx.business_rules = rules

        return ctx

    # ----------------------------------------------------------------- #
    # Step 1: 关键词 → 本体类匹配
    # ----------------------------------------------------------------- #

    def _match_classes(self, query: str) -> List[MatchedClass]:
        """
        从查询中提取中文/英文关键词并匹配到本体类。

        策略:
          A. 映射字典的中文标签做精确子串匹配
          B. 同义词/缩写词典匹配
          C. OntologyGraph 的 label_index 做模糊匹配
          D. 正则分词后逐词查找
        """
        results: List[MatchedClass] = []
        seen_classes: Set[str] = set()
        query_lower = query.lower()

        # 策略A: 映射字典中文标签精确匹配（label_cn 是查询子串）
        for pt in self._mapping.list_all_tables():
            if pt.label_cn and pt.label_cn in query:
                if pt.logic_class not in seen_classes:
                    seen_classes.add(pt.logic_class)
                    results.append(self._to_matched_class(pt.label_cn, pt))

        # 策略B: 同义词/缩写匹配
        for keyword, logic_class in _CLASS_SYNONYMS.items():
            if keyword in query_lower and logic_class not in seen_classes:
                seen_classes.add(logic_class)
                pt = self._mapping.get_physical_table(logic_class)
                if pt:
                    results.append(self._to_matched_class(keyword, pt))
                else:
                    cls = self._ontology.get_class(logic_class)
                    label = cls.label if cls else ""
                    results.append(MatchedClass(
                        keyword=keyword,
                        logic_class=logic_class,
                        label_cn=label,
                        physical_table=None,
                        primary_key=None,
                        display_column=None,
                        virtual=True,
                    ))

        # 策略C: 扫描本体 label_index — 检查 index key 是否出现在查询中
        for label_key, uri in self._ontology._label_index.items():
            if len(label_key) >= 2 and label_key in query_lower:
                if uri in self._ontology.classes and uri not in seen_classes:
                    seen_classes.add(uri)
                    pt = self._mapping.get_physical_table(uri)
                    if pt:
                        results.append(self._to_matched_class(label_key, pt))
                    else:
                        cls = self._ontology.classes[uri]
                        results.append(MatchedClass(
                            keyword=label_key,
                            logic_class=uri,
                            label_cn=cls.label,
                            physical_table=None,
                            primary_key=None,
                            display_column=None,
                            virtual=True,
                        ))

        # 策略D: 正则分词后逐词查找（仍保留作为兜底）
        chinese_tokens = re.findall(r'[\u4e00-\u9fff]{2,}', query)
        english_tokens = re.findall(r'[a-zA-Z]{2,}', query.lower())
        all_tokens = chinese_tokens + english_tokens

        for token in all_tokens:
            cls = self._ontology.find_class_by_label(token)
            if cls and cls.uri not in seen_classes:
                seen_classes.add(cls.uri)
                pt = self._mapping.get_physical_table(cls.uri)
                if pt:
                    results.append(self._to_matched_class(token, pt))
                else:
                    results.append(MatchedClass(
                        keyword=token,
                        logic_class=cls.uri,
                        label_cn=cls.label,
                        physical_table=None,
                        primary_key=None,
                        display_column=None,
                        virtual=True,
                    ))

        return results

    def _to_matched_class(self, keyword: str, pt: PhysicalTable) -> MatchedClass:
        return MatchedClass(
            keyword=keyword,
            logic_class=pt.logic_class,
            label_cn=pt.label_cn,
            physical_table=pt.table_name,
            primary_key=pt.primary_key,
            display_column=pt.display_column,
            key_columns=pt.key_columns,
            virtual=pt.virtual,
        )

    # ----------------------------------------------------------------- #
    # Step 2: 值关键词 → 过滤条件
    # ----------------------------------------------------------------- #

    def _match_values(self, query: str) -> List[ResolvedFilter]:
        """从查询中识别语义值关键词并映射到物理过滤条件"""
        results: List[ResolvedFilter] = []
        seen_pairs: Set[Tuple[str, str]] = set()  # (domain, value) 去重
        query_lower = query.lower()

        for keyword, (domain, value) in _VALUE_KEYWORDS.items():
            if keyword in query_lower:
                pair = (domain, value)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                vm = self._mapping.map_value(domain, value)
                if vm:
                    results.append(ResolvedFilter(
                        semantic_domain=domain,
                        semantic_value=value,
                        description=vm.description,
                        physical_condition=vm.physical_condition,
                        physical_values=vm.physical_values,
                        applies_to_table=vm.applies_to_table,
                        applies_to_column=vm.applies_to_column,
                    ))
        return results

    # ----------------------------------------------------------------- #
    # Step 2.5: 递归追溯关键词 → CTE
    # ----------------------------------------------------------------- #

    def _match_recursive(self, query: str) -> List[ResolvedRecursive]:
        """检测查询中是否涉及递归追溯关键词，自动编译 CTE"""
        results: List[ResolvedRecursive] = []
        seen_relations: Set[str] = set()
        query_lower = query.lower()

        for keyword, relation in _RECURSIVE_KEYWORDS.items():
            if keyword in query_lower and relation not in seen_relations:
                seen_relations.add(relation)
                rec = self._mapping.get_recursive_mapping(relation)
                if rec is None:
                    continue

                # 编译 CTE
                cte_sql = self._mapping.compile_recursive_cte(
                    relation=relation,
                    anchor_condition=None,  # 默认查全部根节点
                    select_columns=None,
                    include_depth=True,
                )
                if cte_sql:
                    results.append(ResolvedRecursive(
                        logic_relation=relation,
                        table=rec.table,
                        self_key=rec.self_key,
                        parent_key=rec.parent_key,
                        max_depth=rec.max_depth,
                        cte_sql=cte_sql,
                        description=rec.description,
                    ))

        return results

    # ----------------------------------------------------------------- #
    # Step 3: 类间路径 → 物理 JOIN
    # ----------------------------------------------------------------- #

    def _resolve_joins(self, classes: List[MatchedClass]) -> List[ResolvedJoin]:
        """
        对匹配到的类两两做路径发现，然后将每一跳的本体关系翻译为物理 JOIN。
        """
        if len(classes) < 2:
            return []

        resolved: List[ResolvedJoin] = []
        seen_relations: Set[str] = set()

        # 取非虚拟类来做 JOIN
        physical_classes = [c for c in classes if not c.virtual and c.physical_table]
        if len(physical_classes) < 2:
            return []

        for i in range(len(physical_classes)):
            for j in range(i + 1, len(physical_classes)):
                source = physical_classes[i].logic_class
                target = physical_classes[j].logic_class
                path = self._ontology.find_path(source, target)
                if path is None:
                    continue

                for from_cls, rel_uri, to_cls in path:
                    # 处理反向边标记
                    actual_rel = rel_uri.lstrip("^")
                    if actual_rel in seen_relations:
                        continue
                    seen_relations.add(actual_rel)

                    rm = self._mapping.get_join_path(actual_rel)
                    if rm:
                        resolved.append(ResolvedJoin(
                            logic_relation=rm.logic_relation,
                            strategy=rm.strategy,
                            conditions=rm.join_conditions,
                            bridge_table=rm.bridge_table,
                            order_by=rm.order_by,
                            note=rm.note,
                        ))

        return resolved

    # ----------------------------------------------------------------- #
    # Step 4: 业务规则
    # ----------------------------------------------------------------- #

    def _match_business_rules(self, tables: List[str]) -> List[BusinessRule]:
        """根据涉及的物理表匹配业务规则"""
        if not tables:
            return []
        return self._mapping.get_business_rules(involved_tables=tables)


# --------------------------------------------------------------------- #
# Module-level convenience
# --------------------------------------------------------------------- #

def build_semantic_context(
    user_query: str,
    ontology: Optional[OntologyGraph] = None,
    mapping: Optional[MappingDictionary] = None,
) -> SemanticContext:
    """一行调用: 从自然语言 → SemanticContext"""
    builder = SemanticContextBuilder(ontology=ontology, mapping=mapping)
    return builder.build(user_query)
