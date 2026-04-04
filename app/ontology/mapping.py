"""
映射字典模块 (MappingDictionary)

加载 mapping_demo_fab.json，提供：
  - 逻辑类 → 物理表/主键/列 的正向查找
  - 关系 → 物理 JOIN 条件的翻译
  - 语义值 → 物理 SQL 条件的转换
  - 业务规则查询
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.ontology.config import ONTOLOGY_DATA_DIR, SEMI_NS

# --------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------- #

@dataclass
class PhysicalTable:
    """一个本体类对应的物理表描述"""
    logic_class: str          # e.g. "semi:Wafer"
    table_name: Optional[str] # None when virtual
    primary_key: Optional[str]
    label_cn: str
    display_column: Optional[str]
    key_columns: List[str] = field(default_factory=list)
    properties: Dict[str, Optional[str]] = field(default_factory=dict)
    virtual: bool = False
    virtual_kind: Optional[str] = None
    embedded_in: Optional[str] = None
    filter_condition: Optional[str] = None  # 同表多类区分条件，e.g. "parent_id != 0"
    time_column: Optional[str] = None        # 时间锚点列，有此字段的实体为时间过滤主表
    subclass_of: Optional[str] = None        # 父类 logic_class，用于关系匹配时的父类权限上卷
    note: Optional[str] = None


@dataclass
class JoinCondition:
    """一条 JOIN 路径"""
    from_table: str
    from_key: str
    to_table: str
    to_key: str
    filter_condition: Optional[str] = None   # JOIN 涉及的行级过滤条件，e.g. "JSON_EXTRACT(extra,'$.isSource')=false"


@dataclass
class RelationMapping:
    """一条本体关系 → 物理 JOIN 映射"""
    logic_relation: str          # e.g. "semi:belongsToLot"
    description: str
    strategy: str                # ForeignKey / JoinTable / Indirect / Recursive / Denormalized
    # OWL TTL 中对应 ObjectProperty 的 rdfs:domain / rdfs:range（语义节点，用于 NetworkX 图）
    domain_class: Optional[str] = None  # e.g. "semi:Wafer"
    range_class: Optional[object] = None  # str 或 List[str]（owl:unionOf 时为列表）
    join_conditions: List[JoinCondition] = field(default_factory=list)
    bridge_table: Optional[str] = None
    order_by: Optional[str] = None
    note: Optional[str] = None
    # 意图感知路径过滤：路径发现时只在意图相关的关系子图上做 BFS
    # applicable_intents: 允许此关系参与路径的意图标签列表（空列表=全允许）
    # forbidden_intents:  禁止此关系参与路径的意图标签列表
    applicable_intents: List[str] = field(default_factory=list)
    forbidden_intents: List[str] = field(default_factory=list)
    # 适用的 EventRecord 子类列表（空列表=全部适用）
    # 当同名 relation 对不同事件类型有不同物理路径时，用此字段区分各条目
    # e.g. semi:producesLot 对 SplitEventRecord 走 _wafer_detail_log.extra，对 AccumulateEventRecord 走 _detail.extra
    applicable_record_types: List[str] = field(default_factory=list)

@dataclass
class RecursiveMapping:
    """递归自关联描述（如 hasParentLot）"""
    logic_relation: str       # e.g. "semi:hasParentLot"
    table: str                # e.g. "batches"
    self_key: str             # e.g. "id"
    parent_key: str           # e.g. "parent_batch_id"
    max_depth: int = 20
    description: str = ""
    # OWL TTL 语义锚定（同 RelationMapping）
    domain_class: Optional[str] = None
    range_class: Optional[object] = None
    note: Optional[str] = None

@dataclass
class ValueMapping:
    """语义值 → 物理值条件"""
    semantic_value: str
    name: str = ""          # 短中文标签，用于 UI 显示，e.g. "批次进站"
    description: str = ""
    physical_values: Optional[List[str]] = None
    physical_condition: Optional[str] = None
    applies_to_table: Optional[str] = None
    applies_to_column: Optional[str] = None
    count_target_table: Optional[str] = None   # COUNT 的目标表 (e.g. "wafers")
    count_target_column: Optional[str] = None  # COUNT 的目标列 (e.g. "id")
    join_path: Optional[str] = None            # JOIN 路径描述
    is_terminal: bool = False                  # Phase 1: 是否为终态（完结/作废等）
    nl_triggers: List[str] = field(default_factory=list)  # Phase 1: 自然语言触发词
    note: Optional[str] = None


@dataclass
class BusinessRule:
    """业务规则"""
    id: str
    name: str
    description: str
    semantic_pattern: Optional[str] = None
    physical_sql_template: Optional[str] = None
    involved_tables: List[str] = field(default_factory=list)
    involved_relations: List[str] = field(default_factory=list)
    applies_to: List[str] = field(default_factory=list)
    warning_tables: List[str] = field(default_factory=list)
    # Fast Path 触发条件：用户查询必须包含其中至少一个关键词才激活该规则的 SQL 模板
    trigger_keywords: List[str] = field(default_factory=list)


@dataclass
class QueryPattern:
    """即席查询模板 — 来自 mapping JSON 的 query_patterns 节。

    代表一类频繁出现的业务查询，通过 nl_triggers 匹配用户意图，
    直接返回 sql_template（填入 param_bindings 后可执行）。
    """
    intent: str
    label_cn: str
    nl_triggers: List[str]
    sql_template: str
    param_bindings: Dict[str, str] = field(default_factory=dict)
    tables: List[str] = field(default_factory=list)
    note: Optional[str] = None


# --------------------------------------------------------------------- #
# MappingDictionary
# --------------------------------------------------------------------- #


# Runtime mode override，由前端「切换库」按钮写入，优先级高于 env var
# 值: "prod" | "demo" | None（None = 由 env var / auto-detect 决定）
_RUNTIME_MODE_OVERRIDE: Optional[str] = None

_PROD_FILE  = "mapping_prod.json"
_DEMO_FILE  = "mapping_demo_fab.json"


def _resolve_mapping_file() -> Path:
    """解析应使用的映射文件路径。

    优先级:
      1. 运行时 override（前端切换按钮写入）：prod | demo
      2. 环境变量 MAPPING_FILE — 绝对路径或相对于 ontology/data/ 的文件名
         例: MAPPING_FILE=mapping_prod.json
      3. mapping_prod.json（若文件存在则自动选用）
      4. mapping_demo_fab.json（兜底）
    """
    import logging
    log = logging.getLogger(__name__)

    if _RUNTIME_MODE_OVERRIDE == "prod":
        return ONTOLOGY_DATA_DIR / _PROD_FILE
    if _RUNTIME_MODE_OVERRIDE == "demo":
        return ONTOLOGY_DATA_DIR / _DEMO_FILE

    env_val = os.getenv("MAPPING_FILE", "").strip()
    if env_val:
        p = Path(env_val)
        if not p.is_absolute():
            p = ONTOLOGY_DATA_DIR / p
        if p.exists():
            log.info("[mapping] Using MAPPING_FILE env: %s", p)
            return p
        log.warning("[mapping] MAPPING_FILE=%s not found, falling back", env_val)

    prod = ONTOLOGY_DATA_DIR / _PROD_FILE
    if prod.exists():
        log.info("[mapping] Auto-selected mapping_prod.json")
        return prod
    return ONTOLOGY_DATA_DIR / _DEMO_FILE


def set_mapping_mode(mode: str) -> Path:
    """切换运行时映射模式。

    Args:
        mode: "prod" | "demo" | "auto" (auto = 清除 override，回归 env/auto-detect)

    Returns:
        切换后实际使用的文件路径
    """
    global _RUNTIME_MODE_OVERRIDE, _MAPPING_FILE, _cached_mapping
    import logging
    log = logging.getLogger(__name__)

    if mode == "auto":
        _RUNTIME_MODE_OVERRIDE = None
    elif mode in ("prod", "demo"):
        _RUNTIME_MODE_OVERRIDE = mode
    else:
        raise ValueError(f"Invalid mode: {mode!r}. Use 'prod', 'demo', or 'auto'.")

    _MAPPING_FILE = _resolve_mapping_file()
    _cached_mapping = None          # 强制下次访问时重载
    log.info("[mapping] Mode switched to '%s', file: %s", mode, _MAPPING_FILE)
    return _MAPPING_FILE


def get_current_mode() -> dict:
    """返回当前映射模式信息。"""
    file = _resolve_mapping_file()
    if _RUNTIME_MODE_OVERRIDE:
        source = f"runtime_override({_RUNTIME_MODE_OVERRIDE})"
    elif os.getenv("MAPPING_FILE", "").strip():
        source = "env_var(MAPPING_FILE)"
    else:
        source = "auto_detect"

    name = file.name
    if name == _PROD_FILE:
        mode = "prod"
    elif name == _DEMO_FILE:
        mode = "demo"
    else:
        mode = "custom"

    return {
        "mode": mode,
        "source": source,
        "file": name,
        "runtime_override": _RUNTIME_MODE_OVERRIDE,
        "env_mapping_file": os.getenv("MAPPING_FILE", ""),
    }


_MAPPING_FILE = _resolve_mapping_file()

_cached_mapping: Optional["MappingDictionary"] = None


class MappingDictionary:
    """
    映射字典 — 将本体层概念映射到物理数据库层。

    提供四大核心能力：
      1. get_physical_table(logic_class)  — 逻辑类 → 物理表
      2. get_join_path(relation)           — 关系 → JOIN 条件链
      3. map_value(domain, value)          — 语义值 → SQL 条件
      4. get_business_rules(context)       — 上下文相关业务规则
    """

    def __init__(self, mapping_file: Optional[Path] = None):
        self._file = mapping_file or _MAPPING_FILE
        self._raw: Dict[str, Any] = {}

        # 索引结构
        self._table_by_class: Dict[str, PhysicalTable] = {}          # "semi:Wafer" → PhysicalTable (最后一条，向后兼容)
        self._tables_by_class_all: Dict[str, List[PhysicalTable]] = {}  # "semi:Equipment" → [PhysicalTable, ...] (全部)
        self._table_by_label: Dict[str, PhysicalTable] = {}          # "晶圆" → PhysicalTable
        self._table_by_physical: Dict[str, PhysicalTable] = {}       # "wafers" → PhysicalTable
        self._relation_map: Dict[str, RelationMapping] = {}          # "semi:belongsToLot" → RelationMapping
        self._relation_map_list: List[RelationMapping] = []           # 全部条目（含同名多 domain 覆盖项）
        self._recursive_map: Dict[str, RecursiveMapping] = {}        # "semi:hasParentLot" → RecursiveMapping
        self._value_map: Dict[str, Dict[str, ValueMapping]] = {}     # "semi:WaferState" -> {"WIP": ValueMapping}
        self._business_rules: List[BusinessRule] = []
        self._query_patterns: List[QueryPattern] = []               # 即席查询模板列表

        self._load()

    # ----------------------------------------------------------------- #
    # Loading
    # ----------------------------------------------------------------- #

    def _load(self) -> None:
        with open(self._file, "r", encoding="utf-8") as f:
            self._raw = json.load(f)

        self._parse_object_mappings(self._raw.get("object_mappings", []))
        self._parse_relation_mappings(self._raw.get("relation_mappings", []))
        self._parse_value_mappings(self._raw.get("value_mappings", {}))
        self._parse_business_rules(self._raw.get("business_rules", []))
        self._parse_query_patterns(self._raw.get("query_patterns", []))

    def _parse_object_mappings(self, items: List[Dict]) -> None:
        for item in items:
            pt = PhysicalTable(
                logic_class=item["logic_class"],
                table_name=item.get("physical_table"),
                primary_key=item.get("primary_key"),
                label_cn=item.get("label_cn", ""),
                display_column=item.get("display_column"),
                key_columns=item.get("key_columns", []),
                properties=item.get("properties", {}),
                virtual=item.get("virtual", False),
                virtual_kind=item.get("virtual_kind"),
                embedded_in=item.get("embedded_in"),
                filter_condition=item.get("filter_condition"),
                time_column=item.get("time_column"),
                subclass_of=item.get("subclass_of"),
                note=item.get("note"),
            )
            self._table_by_class[pt.logic_class] = pt
            # 全量多表索引（每个本体类可能对应多张物理表）
            self._tables_by_class_all.setdefault(pt.logic_class, []).append(pt)
            if pt.label_cn:
                self._table_by_label[pt.label_cn] = pt
            if pt.table_name:
                self._table_by_physical[pt.table_name] = pt

    def _parse_relation_mappings(self, items: List[Dict]) -> None:
        for item in items:
            strategy = item.get("strategy", "ForeignKey")
            jl = item.get("join_logic", {})
            conditions: List[JoinCondition] = []
            bridge: Optional[str] = None
            order_by: Optional[str] = None

            if strategy == "ForeignKey":
                conditions.append(JoinCondition(
                    from_table=jl["source_table"],
                    from_key=jl["source_key"],
                    to_table=jl["target_table"],
                    to_key=jl["target_key"],
                    filter_condition=jl.get("filter_condition"),
                ))
            elif strategy == "JoinTable":
                bridge = jl.get("bridge_table")
                order_by = jl.get("order_by")
                # bridge → source
                conditions.append(JoinCondition(
                    from_table=jl.get("source_table", ""),
                    from_key=jl.get("source_pk", "id"),
                    to_table=bridge or "",
                    to_key=jl.get("source_key", ""),
                ))
                # bridge → target
                conditions.append(JoinCondition(
                    from_table=bridge or "",
                    from_key=jl.get("target_key", ""),
                    to_table=jl.get("target_table", ""),
                    to_key=jl.get("target_pk", "id"),
                ))
            elif strategy == "Indirect":
                for step in jl.get("path", []):
                    conditions.append(JoinCondition(
                        from_table=step["from_table"],
                        from_key=step["from_key"],
                        to_table=step["to_table"],
                        to_key=step["to_key"],
                    ))
            elif strategy == "JoinVia":
                source_table = jl.get("source_table", "")
                source_key = jl.get("source_key", "")
                via_table = jl.get("via_table", "")
                via_source_key = jl.get("via_source_key", "")
                via_target_key = jl.get("via_target_key", "")
                via_pk = jl.get("via_pk", "id")
                via2_table = jl.get("via2_table", "")
                via2_source_key = jl.get("via2_source_key", "")
                via2_target_key = jl.get("via2_target_key", "")
                target_table = jl.get("target_table", "")
                target_key = jl.get("target_key", "")
                target_via_expr = jl.get("target_via_expr", "")

                # step1: source -> via
                if source_table and source_key and via_table and via_source_key:
                    conditions.append(JoinCondition(
                        from_table=source_table,
                        from_key=source_key,
                        to_table=via_table,
                        to_key=via_source_key,
                        filter_condition=jl.get("filter_condition"),
                    ))

                if via2_table:
                    # step2: via -> via2
                    if via_table and via_pk and via2_source_key:
                        conditions.append(JoinCondition(
                            from_table=via_table,
                            from_key=via_pk,
                            to_table=via2_table,
                            to_key=via2_source_key,
                        ))
                    # step3: via2 -> target
                    if via2_table and via2_target_key and target_table and target_key:
                        conditions.append(JoinCondition(
                            from_table=via2_table,
                            from_key=via2_target_key,
                            to_table=target_table,
                            to_key=target_key,
                        ))
                else:
                    # step2: via -> target
                    left_key = via_target_key or target_via_expr
                    if via_table and left_key and target_table and target_key:
                        conditions.append(JoinCondition(
                            from_table=via_table,
                            from_key=left_key,
                            to_table=target_table,
                            to_key=target_key,
                        ))
            elif strategy in ("Recursive", "Denormalized"):
                # 保留原始 join_logic，不做 JOIN 链拆解
                # Recursive 策略额外构建 RecursiveMapping 索引
                if strategy == "Recursive":
                    rec = RecursiveMapping(
                        logic_relation=item["logic_relation"],
                        table=jl.get("table", ""),
                        self_key=jl.get("self_key", "id"),
                        parent_key=jl.get("parent_key", ""),
                        max_depth=jl.get("max_depth", 20),
                        description=item.get("description", ""),
                        domain_class=item.get("domain_class"),
                        range_class=item.get("range_class"),
                        note=jl.get("note"),
                    )
                    self._recursive_map[rec.logic_relation] = rec
            elif strategy == "EmbeddedJSON":
                # JSONB 数组展开 JOIN：构造一个语义提示性的 JoinCondition
                # 用于给 LLM 提供 JOIN 路径方向，真实 SQL 由 note 中的模板指导
                src_tbl = jl.get("source_table", "")
                tgt_tbl = jl.get("target_table", "")
                jsonb_col = jl.get("jsonb_column", "")
                inner_key = jl.get("inner_key", "")
                tgt_key = jl.get("target_key", "id")
                if src_tbl and tgt_tbl and jsonb_col:
                    # from_key 编码为 "jsonb_col[*].inner_key" 供 LLM 理解方向
                    fk_hint = f"{jsonb_col}->>{inner_key}" if inner_key else jsonb_col
                    conditions.append(JoinCondition(
                        from_table=src_tbl,
                        from_key=fk_hint,
                        to_table=tgt_tbl,
                        to_key=tgt_key,
                    ))

            rm = RelationMapping(
                logic_relation=item["logic_relation"],
                description=item.get("description", ""),
                strategy=strategy,
                domain_class=item.get("domain_class"),
                range_class=item.get("range_class"),
                join_conditions=conditions,
                bridge_table=bridge,
                order_by=order_by,
                note=jl.get("note"),
                applicable_intents=item.get("intent_tags", {}).get("applicable", []),
                forbidden_intents=item.get("intent_tags", {}).get("forbidden", []),
                applicable_record_types=item.get("applicable_record_types", []),
            )
            self._relation_map[rm.logic_relation] = rm
            self._relation_map_list.append(rm)

    def _parse_value_mappings(self, data: Dict[str, Dict]) -> None:
        for domain, values in data.items():
            self._value_map[domain] = {}
            for val_key, val_data in values.items():
                if not isinstance(val_data, dict):
                    continue  # skip metadata keys like "_comment"
                vm = ValueMapping(
                    semantic_value=val_key,
                    name=val_data.get("name", ""),
                    description=val_data.get("description", ""),
                    physical_values=val_data.get("physical_values"),
                    physical_condition=val_data.get("physical_condition"),
                    applies_to_table=val_data.get("applies_to_table"),
                    applies_to_column=val_data.get("applies_to_column"),
                    count_target_table=val_data.get("count_target_table"),
                    count_target_column=val_data.get("count_target_column"),
                    join_path=val_data.get("join_path"),
                    is_terminal=val_data.get("is_terminal", False),
                    nl_triggers=val_data.get("nl_triggers", []),
                    note=val_data.get("note"),
                )
                self._value_map[domain][val_key] = vm

    def _parse_business_rules(self, items: List[Dict]) -> None:
        for item in items:
            br = BusinessRule(
                id=item.get("id") or item.get("rule_id", ""),
                name=item.get("name", ""),
                description=item.get("description", ""),
                semantic_pattern=item.get("semantic_pattern"),
                physical_sql_template=item.get("physical_sql_template"),
                involved_tables=item.get("involved_tables", []),
                involved_relations=item.get("involved_relations", []),
                applies_to=item.get("applies_to", []),
                warning_tables=item.get("warning_tables", []),
                trigger_keywords=item.get("trigger_keywords", []),
            )
            self._business_rules.append(br)

    def _parse_query_patterns(self, items: List[Dict]) -> None:
        """解析 query_patterns 节 — 即席查询模板（nl_triggers + sql_template）"""
        for item in items:
            qp = QueryPattern(
                intent=item.get("intent", ""),
                label_cn=item.get("label_cn", ""),
                nl_triggers=item.get("nl_triggers", []),
                sql_template=item.get("sql_template", ""),
                param_bindings=item.get("param_bindings", {}),
                tables=item.get("tables", []),
                note=item.get("note"),
            )
            self._query_patterns.append(qp)

    # ----------------------------------------------------------------- #
    # 1. 逻辑类 → 物理表
    # ----------------------------------------------------------------- #

    def get_physical_table(self, logic_class: str) -> Optional[PhysicalTable]:
        """
        根据本体类URI查找物理表。

        Args:
            logic_class: 如 "semi:Wafer" 或完整URI
        """
        # 先精确匹配
        if logic_class in self._table_by_class:
            return self._table_by_class[logic_class]
        # 尝试添加 semi: 前缀
        prefixed = f"semi:{logic_class}" if not logic_class.startswith("semi:") else logic_class
        return self._table_by_class.get(prefixed)

    def get_table_by_label(self, label_cn: str) -> Optional[PhysicalTable]:
        """根据中文标签查找物理表"""
        return self._table_by_label.get(label_cn)

    def get_table_by_physical_name(self, table_name: str) -> Optional[PhysicalTable]:
        """根据物理表名反向查找"""
        return self._table_by_physical.get(table_name)

    def list_all_tables(self) -> List[PhysicalTable]:
        """返回所有映射条目（含虚拟类）"""
        return list(self._table_by_class.values())

    def list_physical_tables(self) -> List[PhysicalTable]:
        """返回所有有物理表的映射条目（排除虚拟类）"""
        return [t for t in self._table_by_class.values() if not t.virtual]

    def list_tables_for_class(self, logic_class: str) -> List[PhysicalTable]:
        """
        返回本体类对应的 **所有** 物理表条目（一个类可多表）。

        例: list_tables_for_class("semi:Equipment") 返回 22 个 PhysicalTable 条目,
            包含 equipment, equipment_log, equipment_oee 等。

        Args:
            logic_class: 如 "semi:Equipment" 或无前缀的 "Equipment"

        Returns:
            PhysicalTable 列表，按 mapping 文件顺序；未命中返回空列表。
        """
        result = self._tables_by_class_all.get(logic_class)
        if result:
            return result
        prefixed = f"semi:{logic_class}" if not logic_class.startswith("semi:") else logic_class
        return self._tables_by_class_all.get(prefixed, [])

    def list_table_names_for_class(self, logic_class: str) -> List[str]:
        """
        返回本体类对应的所有物理表名列表（仅名称，排除虚拟表）。

        Example:
            >>> md.list_table_names_for_class("semi:Equipment")
            ['accy_equipment_accessory', 'equipment', 'equipment_log', ...]
        """
        return [
            pt.table_name
            for pt in self.list_tables_for_class(logic_class)
            if pt.table_name and not pt.virtual
        ]

    # ----------------------------------------------------------------- #
    # 2. 关系 → JOIN 条件
    # ----------------------------------------------------------------- #

    def get_join_path(self, relation: str) -> Optional[RelationMapping]:
        """
        根据本体关系URI查找物理JOIN映射。

        Args:
            relation: 如 "semi:belongsToLot"
        """
        if relation in self._relation_map:
            return self._relation_map[relation]
        prefixed = f"semi:{relation}" if not relation.startswith("semi:") else relation
        return self._relation_map.get(prefixed)

    def get_join_between_tables(self, source_table: str, target_table: str) -> List[RelationMapping]:
        """
        查找连接两张物理表的所有关系映射。

        Returns:
            匹配的 RelationMapping 列表
        """
        results = []
        for rm in self._relation_map.values():
            tables_in_path = set()
            for jc in rm.join_conditions:
                tables_in_path.add(jc.from_table)
                tables_in_path.add(jc.to_table)
            if rm.bridge_table:
                tables_in_path.add(rm.bridge_table)
            if source_table in tables_in_path and target_table in tables_in_path:
                results.append(rm)
        return results

    def list_all_relations(self) -> List[RelationMapping]:
        """返回所有关系映射（含同一关系名的多 domain 变体）"""
        return list(self._relation_map_list)

    # ----------------------------------------------------------------- #
    # 3. 语义值 → SQL 条件
    # ----------------------------------------------------------------- #

    def map_value(self, domain: str, semantic_value: str) -> Optional[ValueMapping]:
        """
        将语义值映射到物理 SQL 条件。

        Args:
            domain: 值域，如 "semi:WaferState"
            semantic_value: 语义值，如 "WIP"
        """
        domain_map = self._value_map.get(domain)
        if domain_map is None:
            # 尝试加前缀
            prefixed = f"semi:{domain}" if not domain.startswith("semi:") else domain
            domain_map = self._value_map.get(prefixed)
        if domain_map is None:
            return None
        return domain_map.get(semantic_value)

    def get_wip_condition(self) -> Optional[ValueMapping]:
        """快捷方法：获取 WIP（在制品）的物理过滤条件"""
        return self.map_value("semi:WaferState", "WIP")

    def list_value_domains(self) -> List[str]:
        """返回所有值域名"""
        return list(self._value_map.keys())

    def list_values_in_domain(self, domain: str) -> Dict[str, ValueMapping]:
        """返回某个域下的所有值映射"""
        return self._value_map.get(domain, {})

    def get_terminal_conditions(self, domain: str) -> List[str]:
        """Phase 1: 返回指定域内所有终态的 physical_condition 列表"""
        import re as _re
        domain_map = self.list_values_in_domain(domain)
        if not domain_map:
            prefixed = f"semi:{domain}" if not domain.startswith("semi:") else domain
            domain_map = self.list_values_in_domain(prefixed)
        return [
            vm.physical_condition
            for vm in domain_map.values()
            if vm.is_terminal and vm.physical_condition
        ]

    def get_wip_exclusion_filter(self, domain: str = "semi:BatchStatus") -> Optional[str]:
        """
        Phase 1: 从终态列表自动构造 NOT IN 过滤条件。
        例: 返回 "matrix_routerx_operation_lot.status NOT IN (100, -50)"
        """
        import re as _re
        conditions = self.get_terminal_conditions(domain)
        if not conditions:
            return None
        # 提取数值（含负数），例 "...status = 100" → "100"
        nums: List[str] = []
        for cond in conditions:
            m = _re.search(r'=\s*(-?\d+)', cond)
            if m:
                nums.append(m.group(1))
        if not nums:
            return None
        # 从任意一条 condition 拿 table.column 前缀
        prefix_match = _re.match(r'([\w.]+)\s*=', conditions[0])
        if not prefix_match:
            return None
        col_ref = prefix_match.group(1).rstrip()  # e.g. "matrix_routerx_operation_lot.status"
        return f"{col_ref} NOT IN ({', '.join(nums)})"

    def match_query_pattern(self, user_input: str) -> Optional["QueryPattern"]:
        """
        在 query_patterns 的 nl_triggers 中做关键词匹配（即席查询快速路径）。

        匹配逻辑：任意一个 nl_trigger 出现在用户输入中则命中，优先选最多 triggers 命中的。
        """
        best: Optional[QueryPattern] = None
        best_score = 0
        q = user_input.lower()
        for qp in self._query_patterns:
            hits = sum(1 for t in qp.nl_triggers if t.lower() in q)
            if hits > best_score:
                best = qp
                best_score = hits
        return best if best_score > 0 else None

    def resolve_sql_bindings(self, sql_template: str, param_bindings: Dict[str, str]) -> str:
        """
        将 sql_template 中的 {ParamName} 占位符替换为实际值。

        param_bindings 格式:
          "CarrierAvailableStatus": "value_mappings.semi:CarrierMaintenanceStatus.Available"

        解析路径: "value_mappings.<domain>.<key>" → 查询 self._value_map → physical_values[0]
        """
        import re as _re
        result = sql_template
        for param, path in param_bindings.items():
            value = None
            if path.startswith("value_mappings."):
                # "value_mappings.semi:CarrierMaintenanceStatus.Available"
                rest = path[len("value_mappings."):]
                # 按最后一个 '.' 分割 domain 和 key
                last_dot = rest.rfind(".")
                if last_dot > 0:
                    domain = rest[:last_dot]
                    key = rest[last_dot + 1:]
                    vm = self.map_value(domain, key)
                    if vm and vm.physical_values:
                        value = vm.physical_values[0]
                    elif vm and vm.physical_condition:
                        # 从条件中提取数值, e.g. "status = 1" → "1"
                        m = _re.search(r'=\s*(-?\d+)', vm.physical_condition)
                        if m:
                            value = m.group(1)
            if value is not None:
                result = result.replace(f"{{{param}}}", str(value))
        return result

    def build_table_catalog(self, max_tables: int = 25) -> str:
        """
        为 LLM 构建物理表目录字符串（即席路径 context 构建）。

        格式:
          ### table_name（label_cn）
          说明: <full note>
          关键列: col1, col2, ...（全量）
          强制过滤（必须加入 WHERE）: filter_condition  ← 仅当存在时

        最后附两个附加节：
          ## 表间 JOIN 关系  —— catalog 内 ForeignKey 条目
          ## 业务规则        —— 涉及 catalog 内表的 BusinessRule

        按表名字母序返回，跳过虚拟表，最多 max_tables 条。
        """
        tables = sorted(
            [t for t in self.list_physical_tables() if t.table_name and not t.virtual],
            key=lambda t: t.table_name or ""
        )[:max_tables]

        table_lines: List[str] = []
        table_names: set = set()
        for t in tables:
            table_names.add(t.table_name)
            block = [f"### {t.table_name}（{t.label_cn}）"]
            note = (t.note or "").replace("\n", " ").strip()
            if note:
                block.append(f"说明: {note}")
            if t.key_columns:
                block.append(f"关键列: {', '.join(t.key_columns)}")
            if t.filter_condition:
                block.append(f"强制过滤（必须加入 WHERE）: {t.filter_condition}")
            table_lines.append("\n".join(block))

        # ── 表间 JOIN 关系（仅 ForeignKey，两端均在 catalog 内，去重） ─────────
        join_lines: List[str] = []
        seen_fk: set = set()
        for rm in self._relation_map_list:
            if rm.strategy != "ForeignKey" or not rm.join_conditions:
                continue
            jc = rm.join_conditions[0]
            if jc.from_table not in table_names or jc.to_table not in table_names:
                continue
            fk_key = (jc.from_table, jc.from_key, jc.to_table, jc.to_key)
            if fk_key in seen_fk:
                continue
            seen_fk.add(fk_key)
            entry = f"- {jc.from_table}.{jc.from_key} = {jc.to_table}.{jc.to_key}"
            if rm.description:
                entry += f"  # {rm.description[:80]}"
            if jc.filter_condition:
                entry += f"  （附加条件: {jc.filter_condition}）"
            join_lines.append(entry)

        # ── 业务规则（仅筛选涉及 catalog 内表的规则） ────────────────────────
        rule_lines: List[str] = []
        for br in self.get_business_rules(list(table_names)):
            rule_lines.append(f"- [{br.id}] {br.name}: {br.description}")

        # ── 拼装 ──────────────────────────────────────────────────────────────
        sections: List[str] = ["## 物理表目录"]
        sections.extend(table_lines)
        if join_lines:
            sections.append("\n## 表间 JOIN 关系")
            sections.extend(join_lines)
        if rule_lines:
            sections.append("\n## 业务规则查询注意事项")
            sections.extend(rule_lines)

        return "\n\n".join(sections)

    def build_value_summary(self, max_domains: int = 10) -> str:
        """
        为 LLM 构建业务枚举值摘要（状态码、类型码等）。

        格式:
          <domain>:
            <key>=<physical_value>  # <description>
        """
        lines = []
        for domain, values in list(self._value_map.items())[:max_domains]:
            if not values:
                continue
            domain_label = domain.replace("semi:", "")
            domain_lines = [f"{domain_label}:"]
            for k, vm in list(values.items())[:6]:
                phys = vm.physical_values[0] if vm.physical_values else vm.physical_condition or "?"
                desc = vm.description or vm.name or ""
                domain_lines.append(f"  {k}={phys}  # {desc[:50]}")
            lines.extend(domain_lines)
        return "\n".join(lines)

    def build_entity_context(self, entities: List[str]) -> str:
        """
        **B 路径**：按 skill.required_entities 构建上下文，不提供任何指标级物理定位信息
        （无 anchor_table / join_path / auto_filter）。

        LLM 需要从实体描述 + 实体间关系自行推断 JOIN 路径和 WHERE 条件。

        关系过滤规则（AND 语义）：
          只输出 domain_class **和** range_class 同时在 required_entities 集合内的关系，
          确保输出的关系都是当前指标局部的，避免全图噪声。

        :param entities: logic_class 列表，如 ["semi:CheckOutEventRecord", "semi:WaferTransitionSnapshot"]
        """
        if not entities:
            return ""

        entity_set = set(entities)
        # 对 domain_class 匹配扩展父类（支持抽象父类关系，如 ProductionEventRecord）
        domain_match_set = set(entity_set)
        for lc in entities:
            pt = self.get_physical_table(lc)
            if pt and pt.subclass_of:
                domain_match_set.add(pt.subclass_of)

        # 1. 实体物理信息
        entity_lines: List[str] = ["## 本体实体"]
        involved_tables: List[str] = []
        for lc in entities:
            pt = self.get_physical_table(lc)
            if not pt:
                entity_lines.append(f"### {lc}（未找到物理映射）")
                continue
            entity_lines.append(f"### {lc}（{pt.label_cn}）")
            if pt.table_name:
                entity_lines.append(f"物理表: {pt.table_name}")
                involved_tables.append(pt.table_name)
            if pt.filter_condition:
                entity_lines.append(f"行级过滤: {pt.filter_condition}")
            if pt.time_column:
                entity_lines.append(f"[时间锚点] 时间过滤必须用 {pt.table_name}.{pt.time_column}（禁止使用其他表的同名列）")
            if pt.key_columns:
                entity_lines.append(f"关键列: {', '.join(pt.key_columns[:12])}")
            if pt.note:
                entity_lines.append(f"说明: {pt.note}")
            entity_lines.append("")

        # 2. 实体间关联（AND 语义：domain 在 domain_match_set 中，range 在 entity_set 中）
        relation_lines: List[str] = ["## 实体间关联"]
        seen_relations: set = set()
        for rm in self._relation_map_list:
            dc = rm.domain_class or ""
            rc = rm.range_class
            range_set = set(rc) if isinstance(rc, list) else ({rc} if rc else set())
            # domain 使用扩展集合（含父类），range 使用原始 entity_set
            if dc not in domain_match_set or not (range_set & entity_set):
                continue
            if not rm.join_conditions:
                continue
            matched_range = sorted(range_set & entity_set)
            key = (rm.logic_relation, dc, str(matched_range))
            if key in seen_relations:
                continue
            seen_relations.add(key)
            rc_str = ", ".join(matched_range)
            relation_lines.append(f"- {rm.logic_relation}: {dc} → {rc_str}")
            if rm.description:
                relation_lines.append(f"  描述: {rm.description}")
            for jc in rm.join_conditions:
                filt = f" （过滤: {jc.filter_condition}）" if jc.filter_condition else ""
                relation_lines.append(
                    f"  JOIN: {jc.from_table}.{jc.from_key} → {jc.to_table}.{jc.to_key}{filt}"
                )
            if rm.note:
                relation_lines.append(f"  注: {rm.note[:150]}")
            relation_lines.append("")

        if len(relation_lines) == 1:  # 只有标题行
            relation_lines = []

        # 3. 业务规则
        rules = self.get_business_rules(involved_tables=involved_tables)
        rule_lines: List[str] = []
        if rules:
            rule_lines = ["## 相关业务规则"]
            for r in rules[:5]:
                rule_lines.append(f"- [{r.id}] {r.name}: {r.description}")
            rule_lines.append("")

        parts = entity_lines + relation_lines + rule_lines
        return "\n".join(parts).rstrip()

    # ----------------------------------------------------------------- #
    # 4. 业务规则
    # ----------------------------------------------------------------- #

    def get_business_rules(self, involved_tables: Optional[List[str]] = None) -> List[BusinessRule]:
        """
        获取业务规则。如果指定了表名，只返回相关规则。

        Args:
            involved_tables: 物理表名列表。None 返回全部规则。
        """
        if involved_tables is None:
            return list(self._business_rules)

        table_set = set(involved_tables)
        result = []
        for br in self._business_rules:
            all_tables = set(br.involved_tables) | set(br.applies_to) | set(br.warning_tables)
            # 展开 "table.column" 为 "table"
            expanded = set()
            for t in all_tables:
                expanded.add(t.split(".")[0])
            if expanded & table_set:
                result.append(br)
        return result

    def get_rule_by_id(self, rule_id: str) -> Optional[BusinessRule]:
        """根据ID获取单条业务规则"""
        for br in self._business_rules:
            if br.id == rule_id:
                return br
        return None

    # ----------------------------------------------------------------- #
    # 5. 递归追溯 CTE 编译
    # ----------------------------------------------------------------- #

    def get_recursive_mapping(self, relation: str) -> Optional[RecursiveMapping]:
        """获取递归关系映射"""
        if relation in self._recursive_map:
            return self._recursive_map[relation]
        prefixed = f"semi:{relation}" if not relation.startswith("semi:") else relation
        return self._recursive_map.get(prefixed)

    def list_recursive_relations(self) -> List[RecursiveMapping]:
        """返回所有递归关系映射"""
        return list(self._recursive_map.values())

    def compile_recursive_cte(
        self,
        relation: str,
        anchor_condition: Optional[str] = None,
        select_columns: Optional[List[str]] = None,
        cte_alias: str = "lot_tree",
        include_depth: bool = True,
    ) -> Optional[str]:
        """
        将递归关系编译为 WITH RECURSIVE CTE SQL 片段。

        Args:
            relation: 本体关系，如 "semi:hasParentLot"
            anchor_condition: 锚定条件，如 "batch_code = 'B001'"。None 则查全部根节点。
            select_columns: 要投影的列。None 则返回全表列。
            cte_alias: CTE 名称，默认 "lot_tree"
            include_depth: 是否添加递归深度列

        Returns:
            完整的 WITH RECURSIVE ... SELECT 语句，或 None
        """
        rec = self.get_recursive_mapping(relation)
        if rec is None:
            return None

        table = rec.table
        self_key = rec.self_key
        parent_key = rec.parent_key
        max_depth = rec.max_depth

        # 决定 SELECT 列
        if select_columns:
            cols = ", ".join(select_columns)
            anchor_cols = ", ".join(f"t.{c}" for c in select_columns)
            recursive_cols = ", ".join(f"t.{c}" for c in select_columns)
        else:
            cols = "t.*"
            anchor_cols = "t.*"
            recursive_cols = "t.*"

        depth_col = ", 1 AS lvl" if include_depth else ""
        depth_inc = ", tree.lvl + 1" if include_depth else ""
        depth_filter = f"\n  AND tree.lvl < {max_depth}" if include_depth else ""

        # 锚定条件
        if anchor_condition:
            anchor_where = f"WHERE {anchor_condition}"
        else:
            anchor_where = f"WHERE t.{parent_key} IS NULL"

        order_clause = "\nORDER BY lvl;" if include_depth else ";"

        cte = f"""WITH RECURSIVE {cte_alias} AS (
  -- 锚定查询: 起始节点
  SELECT {anchor_cols}{depth_col}
  FROM {table} t
  {anchor_where}

  UNION ALL

  -- 递归查询: 沿 {parent_key} 向下/向上追溯
  SELECT {recursive_cols}{depth_inc}
  FROM {table} t
  INNER JOIN {cte_alias} tree ON t.{parent_key} = tree.{self_key}{depth_filter}
)
SELECT * FROM {cte_alias}{order_clause}"""

        return cte

    # ----------------------------------------------------------------- #
    # Summary
    # ----------------------------------------------------------------- #

    def summary(self) -> Dict[str, Any]:
        physical_count = sum(1 for t in self._table_by_class.values() if not t.virtual)
        virtual_count = sum(1 for t in self._table_by_class.values() if t.virtual)
        return {
            "version": self._raw.get("version", "unknown"),
            "customer": self._raw.get("customer", "unknown"),
            "object_mappings_total": len(self._table_by_class),
            "physical_tables": physical_count,
            "virtual_classes": virtual_count,
            "relation_mappings": len(self._relation_map_list),
            "recursive_relations": len(self._recursive_map),
            "value_domains": len(self._value_map),
            "business_rules": len(self._business_rules),
        }


# --------------------------------------------------------------------- #
# Module-level convenience functions
# --------------------------------------------------------------------- #

def load_mapping(mapping_file: Optional[Path] = None, force_reload: bool = False) -> MappingDictionary:
    """加载映射字典（带缓存）"""
    global _cached_mapping
    if _cached_mapping is None or force_reload:
        _cached_mapping = MappingDictionary(mapping_file)
    return _cached_mapping


def get_mapping() -> MappingDictionary:
    """获取已缓存的映射字典实例"""
    return load_mapping()
