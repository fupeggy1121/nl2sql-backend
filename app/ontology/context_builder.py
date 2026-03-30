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
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from app.ontology.loader import get_ontology
from app.ontology.join_graph import get_join_graph
from app.ontology.mapping import (
    BusinessRule,
    JoinCondition,
    MappingDictionary,
    MetricDefinition,
    PhysicalTable,
    RecursiveMapping,
    RelationMapping,
    ValueMapping,
    get_mapping,
)
from app.ontology.model import OntologyClass, OntologyGraph

logger = logging.getLogger(__name__)

# 策略 E: embedding 相似度阈值 — 只有超过此分才将 token 视为命中
# 0.82 经验判断：足够抗噪声又不过于严格
_EMBED_SIMILARITY_THRESHOLD: float = 0.82


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
    properties: Dict[str, Optional[str]] = field(default_factory=dict)  # 语义属性 → 物理字段
    virtual: bool = False
    filter_condition: Optional[str] = None  # 同表多类区分条件，e.g. "parent_id != 0"


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
    count_target_table: Optional[str] = None   # e.g. "wafers" — COUNT 的目标表
    count_target_column: Optional[str] = None  # e.g. "id" — COUNT 的目标列


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
    metrics: List[MetricDefinition] = field(default_factory=list)  # Phase 2: matched metric definitions

    # 快捷属性
    @staticmethod
    def _format_join_side(table: str, key: str) -> str:
        """将 JOIN 一侧格式化为可读 SQL 片段。

        - 普通列：table.column
        - 表达式列（如 JSON_EXTRACT(...)）：原样返回，避免出现 table.JSON_EXTRACT(...) 这种无效形式
        """
        raw = (key or "").strip()
        if not raw:
            return table
        if any(ch in raw for ch in ("(", " ", ")")):
            return raw
        return f"{table}.{raw}"

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
                lines.append(f"-- {mc.label_cn}({mc.logic_class})")
                lines.append(f"TABLE {mc.physical_table}")
                if mc.properties:
                    lines.append("  -- 语义属性(semantic_prop → physical_column):")
                    for sem_prop, phys_col in mc.properties.items():
                        if phys_col is not None:
                            lines.append(f"  --   {sem_prop} → {phys_col}")
                semantic_cols = set(mc.properties.values()) - {None}
                remaining = [c for c in mc.key_columns if c not in semantic_cols]
                if remaining:
                    lines.append(f"  -- 其余列: {', '.join(remaining)}")
                if mc.filter_condition:
                    lines.append(f"  -- ⚠ 必须应用行过滤: WHERE {mc.filter_condition}")
        if self.joins:
            lines.append("")
            lines.append("-- JOIN conditions")
            for j in self.joins:
                for c in j.conditions:
                    left = self._format_join_side(c.from_table, c.from_key)
                    right = self._format_join_side(c.to_table, c.to_key)
                    lines.append(
                        f"  {left} = {right}"
                    )
                    # 当 from/to 表名极相似时，额外输出显式 INNER JOIN 片段避免 LLM 混淆
                    if c.to_table and c.from_table != c.to_table and (
                        c.to_table.startswith(c.from_table) or c.from_table.startswith(c.to_table)
                    ):
                        lines.append(
                            f"  -- ⚠ 正确 JOIN 写法: INNER JOIN {c.to_table} ON {left} = {c.to_table}.{c.to_key}"
                        )
                    if c.filter_condition:
                        lines.append(
                            f"  -- ⚠ 额外过滤条件(必须加入 WHERE 或 JOIN ON): {c.filter_condition}"
                        )
                if j.note:
                    lines.append(f"  -- note: {j.note}")
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
                # 标注 COUNT 目标（关键：WIP 统计 Wafer 而非 Sublot）
                if f.count_target_table:
                    lines.append(
                        f"  -- ⚠ COUNT target: {f.count_target_table}.{f.count_target_column} (NOT {f.applies_to_table})"
                    )
        if self.recursive:
            lines.append("")
            lines.append("-- Recursive CTE (batch/lot tree)")
            for r in self.recursive:
                lines.append(f"  -- {r.description}")
                lines.append(r.cte_sql)
        if self.metrics:
            lines.append("")
            lines.append("-- Metrics")
            for m in self.metrics:
                lines.append(f"-- Metric: {m.zh_names[0] if m.zh_names else m.metric_id}")
                lines.append(f"   FORMULA: {m.formula}")
                lines.append(f"   ANCHOR_TABLE: {m.anchor_table}")
                if m.join_path:
                    lines.append(f"   JOIN_PATH: {m.join_path}")
                if m.auto_filter:
                    lines.append(f"   AUTO_FILTER: {m.auto_filter}")
                if m.granularity:
                    lines.append(f"   GRANULARITY: {', '.join(m.granularity)}")
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
                    "properties": {k: v for k, v in mc.properties.items() if v is not None},
                    "virtual": mc.virtual,
                    **({"filter_condition": mc.filter_condition} if mc.filter_condition else {}),
                }
                for mc in self.matched_classes
            ],
            "physical_tables": self.physical_tables,
            "joins": [
                {
                    "logic_relation": j.logic_relation,
                    "strategy": j.strategy,
                    "conditions": [
                        {
                            "from": self._format_join_side(c.from_table, c.from_key),
                            "to": self._format_join_side(c.to_table, c.to_key),
                            **({"filter_condition": c.filter_condition} if c.filter_condition else {}),
                        }
                        for c in j.conditions
                    ],
                    "bridge_table": j.bridge_table,
                    **({"note": j.note} if j.note else {}),
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
                    "count_target_table": f.count_target_table,
                    "count_target_column": f.count_target_column,
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
                {
                    "id": br.id,
                    "name": br.name,
                    "description": br.description,
                    **({"sql_example": br.physical_sql_template} if br.physical_sql_template else {}),
                }
                for br in self.business_rules
            ],
            "schema_snippet": self.schema_snippet,
            "metrics": [
                {
                    "metric_id": m.metric_id,
                    "zh_names": m.zh_names,
                    "anchor_table": m.anchor_table,
                    "formula": m.formula,
                    "granularity": m.granularity,
                    "join_path": m.join_path,
                    "auto_filter": m.auto_filter,
                    "description": m.description,
                }
                for m in self.metrics
            ],
        }


# --------------------------------------------------------------------- #
# Synonym dictionary: 常见简称/缩写 → 本体类 URI
#
# 单一数据源：从 app/config/ontology_synonyms.py 动态构建扁平字典，
# 不再在此处维护硬编码列表。
# Supabase class_synonyms 表中用户新增同义词在服务启动时（或调用
# POST /api/v1/ontology/synonyms/reload 热重载接口后）自动合并进来。
# --------------------------------------------------------------------- #

def _build_class_synonyms_static():
    """
    从 ontology_synonyms 展开成两个结构：
    - flat:  word → URI（扁平字典，class + relation + data_property；重复键以最后写入为准）
    - multi: word → [URI, ...]（仅 class 同义词；仅保留映射到 2+ 类的词，支持多类命中）

    multi 的典型场景："过站记录" 同时属于 CheckInEventRecord 和 CheckOutEventRecord，
    命中后两个类都进入 matched_classes，从而触发 IN (8, 9) 过滤。
    """
    try:
        from app.config.ontology_synonyms import CLASS_SYNONYMS as _CS, RELATION_SYNONYMS as _RS, PROPERTY_SYNONYMS as _PS

        # ── 第一步：构建 class 多值映射（word → [uri, ...]，按定义顺序追加）
        _class_multi: Dict[str, List[str]] = {}
        for uri, info in _CS.items():
            for word in info.get("synonyms", []):
                for w in (word, word.lower()):
                    if w not in _class_multi:
                        _class_multi[w] = []
                    if uri not in _class_multi[w]:
                        _class_multi[w].append(uri)

        # ── 第二步：flat dict（class 部分）— 重复键取最后一个 URI（保持向后兼容）
        flat: Dict[str, str] = {w: uris[-1] for w, uris in _class_multi.items()}

        # 关系同义词（单类，直接写入 flat）
        for uri, info in _RS.items():
            for word in info.get("synonyms", []):
                flat[word] = uri
        # 数据属性同义词（单类，直接写入 flat）
        for uri, info in _PS.items():
            for word in info.get("synonyms", []):
                flat[word] = uri
                flat[word.lower()] = uri

        # ── 第三步：multi dict — 只保留映射到 2+ 类的词
        multi: Dict[str, List[str]] = {
            w: uris for w, uris in _class_multi.items() if len(uris) >= 2
        }

        if multi:
            logger.info(
                "[context_builder] Multi-class synonyms: %d keywords → %s",
                len(multi),
                {w: [u.split(":")[-1] for u in us] for w, us in multi.items()},
            )

        return flat, multi

    except Exception as e:
        logger.warning(f"[context_builder] 从 ontology_synonyms.py 构建字典失败，使用内置兜底: {e}")
        # 兜底：保留最小集确保基本功能
        return (
            {
                "设备": "semi:Equipment", "机台": "semi:Equipment",
                "载具": "semi:Carrier", "片篮": "semi:Carrier", "花篮": "semi:Carrier",
                "晶圆": "semi:Wafer", "wafer": "semi:Wafer",
                "批次": "semi:ProductionLot", "lot": "semi:ProductionLot",
                "工单": "semi:ProductionOrder", "工序": "semi:ProcessStation",
            },
            {},
        )


# 静态基础字典（来自 ontology_synonyms.py，服务启动时一次性构建）
_CLASS_SYNONYMS: Dict[str, str]
_MULTI_CLASS_SYNONYMS: Dict[str, List[str]]   # word → [URI, ...]，仅含 2+ 类的词
_CLASS_SYNONYMS, _MULTI_CLASS_SYNONYMS = _build_class_synonyms_static()

# Supabase 动态叠加层：服务启动 + 热重载时更新（DB 词优先于静态词）
_supabase_synonym_overlay: Dict[str, str] = {}


def _get_active_synonyms() -> Dict[str, str]:
    """返回静态词典与 Supabase 动态叠加的合并结果（DB 词优先）。"""
    if not _supabase_synonym_overlay:
        return _CLASS_SYNONYMS
    return {**_CLASS_SYNONYMS, **_supabase_synonym_overlay}


def _get_multi_class_synonyms() -> Dict[str, List[str]]:
    """
    返回「一词多类」同义词映射：{word: [URI1, URI2, ...]}。
    仅包含映射到 2 个及以上本体类的词（例如 "过站记录" → [CheckIn, CheckOut]）。
    Supabase 叠加层暂不合并（多类场景由静态词典维护）。
    """
    return _MULTI_CLASS_SYNONYMS


def reload_synonyms_from_db() -> int:
    """
    从 Supabase class_synonyms 表拉取全部激活同义词，更新内存叠加层。
    在服务启动时调用一次；也可通过 POST /api/v1/ontology/synonyms/reload
    在不重启服务的情况下热重载新增同义词。
    返回加载的同义词条数（0 = Supabase 不可用或表为空）。
    """
    global _supabase_synonym_overlay
    try:
        from app.services.supabase_client import get_supabase_client
        sc = get_supabase_client()
        if not sc or not sc.client:
            logger.warning("[synonym_reload] Supabase 客户端不可用，跳过 DB 同义词加载")
            return 0
        response = (
            sc.client.table("class_synonyms")
            .select("synonym,target_uri")
            .eq("is_active", True)
            .execute()
        )
        rows = response.data or []
        overlay: Dict[str, str] = {}
        for row in rows:
            synonym = (row.get("synonym") or "").strip()
            uri = (row.get("target_uri") or "").strip()
            if synonym and uri:
                overlay[synonym] = uri
                overlay[synonym.lower()] = uri  # 英文小写兜底
        _supabase_synonym_overlay = overlay
        logger.info(f"[synonym_reload] 从 Supabase 加载 {len(overlay)} 条同义词")
        return len(overlay)
    except Exception as e:
        logger.warning(f"[synonym_reload] DB 同义词加载失败（不影响静态字典）: {e}")
        return 0


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

    # ══════════════════════════════════════════════════════════════
    # 以下为生产库 cc_semi_mvp 专用关键词（整数枚举，physical_condition 格式）
    # ══════════════════════════════════════════════════════════════

    # ── BatchStatus (matrix_routerx_operation_lot.status) ──
    "在制品": ("semi:BatchStatus", "Running"),
    "wip": ("semi:BatchStatus", "Running"),
    "在制": ("semi:BatchStatus", "Running"),
    "执行中": ("semi:BatchStatus", "Running"),
    "待执行": ("semi:BatchStatus", "Pending"),
    "完工": ("semi:BatchStatus", "Completed"),
    "已完成批次": ("semi:BatchStatus", "Completed"),
    "取消批次": ("semi:BatchStatus", "Cancelled"),
    "暂存": ("semi:BatchStatus", "Staged"),
    "已暂存": ("semi:BatchStatus", "Staged"),
    "暂存中": ("semi:BatchStatus", "Staged"),
    "暂存状态": ("semi:BatchStatus", "Staged"),
    "线边仓暂存": ("semi:BatchStatus", "Staged"),
    "扣留": ("semi:BatchStatus", "Staged"),
    "被扣留": ("semi:BatchStatus", "Staged"),
    "已扣留": ("semi:BatchStatus", "Staged"),
    "扣留中": ("semi:BatchStatus", "Staged"),
    "扣留状态": ("semi:BatchStatus", "Staged"),

    # ── LotWIPStatus（在制三态，推导型：process_status + 扣留历史）──
    # Run: process_status IN (50,100,150) AND status <> 80
    "在制运行": ("semi:LotWIPStatus", "Run"),
    "wip运行": ("semi:LotWIPStatus", "Run"),
    "run状态": ("semi:LotWIPStatus", "Run"),
    "正常运行中": ("semi:LotWIPStatus", "Run"),
    # IDLE: process_status IN (0,200) AND status <> 80
    "在制闲置": ("semi:LotWIPStatus", "IDLE"),
    "wip闲置": ("semi:LotWIPStatus", "IDLE"),
    "idle状态": ("semi:LotWIPStatus", "IDLE"),
    "空闲批次": ("semi:LotWIPStatus", "IDLE"),
    # Hold: status = 80 (存在激活扣留记录且未释放)
    "在制扣留": ("semi:LotWIPStatus", "Hold"),
    "wip扣留": ("semi:LotWIPStatus", "Hold"),
    "wip hold": ("semi:LotWIPStatus", "Hold"),
    "在制hold": ("semi:LotWIPStatus", "Hold"),

    # ── HoldStatus (matrix_routerx_operation_lot_hold_action.status) ──
    "hold": ("semi:HoldStatus", "Held"),
    "暂停": ("semi:HoldStatus", "Held"),
    "hold中": ("semi:HoldStatus", "Held"),
    "已release": ("semi:HoldStatus", "Released"),
    "已释放": ("semi:HoldStatus", "Released"),

    # ── EquipmentStatus prod (equipment.status 0/1) ──
    "设备启用": ("semi:EquipmentStatus", "Active"),
    "设备开启": ("semi:EquipmentStatus", "Active"),
    "设备停用": ("semi:EquipmentStatus", "Inactive"),
    "设备关闭": ("semi:EquipmentStatus", "Inactive"),
    "宕机": ("semi:EquipmentStatus", "Down"),
    "故障": ("semi:EquipmentStatus", "Down"),

    # ── ProductStatus prod (product_model.product_status 0/1/2) ──
    "草稿产品": ("semi:ProductStatus", "Draft"),
    "待审核产品": ("semi:ProductStatus", "PendingApproval"),
    "激活产品": ("semi:ProductStatus", "Active"),
    "在产产品": ("semi:ProductStatus", "Active"),

    # ── ApproveStatus (product_model_approve.approve_status 0/1/2) ──
    "待审批": ("semi:ApproveStatus", "Pending"),
    "审批通过": ("semi:ApproveStatus", "Approved"),
    "审批拒绝": ("semi:ApproveStatus", "Rejected"),

    # ── BOMStatus (product_bom.status 0/1) ──
    "生效bom": ("semi:BOMStatus", "Active"),
    "失效bom": ("semi:BOMStatus", "Inactive"),

    # ── AccessoryStatus (accy_accessory.status 0/1/2/3) ──
    "待上机": ("semi:AccessoryStatus", "Pending"),
    "上机中": ("semi:AccessoryStatus", "InUse"),
    "退库待确认": ("semi:AccessoryStatus", "PendingReturn"),
    "已退库": ("semi:AccessoryStatus", "Returned"),

    # ── WarnStatus ──
    "已预警": ("semi:WarnStatus", "Warned"),
    "预警中": ("semi:WarnStatus", "Warned"),

    # ── TransferJobStatus (mcs_transfer_job.status 0/1/2) ──
    "搬运中": ("semi:TransferJobStatus", "Running"),
    "搬运完成": ("semi:TransferJobStatus", "Completed"),

    # ── ProductionOrderStatus (production_order.production_status 0/1) ──
    "工单开启": ("semi:ProductionOrderStatus", "Open"),
    "工单关闭": ("semi:ProductionOrderStatus", "Closed"),

    # ── ReportStatus (report_record_info.status 0/1) ──
    "待报工": ("semi:ReportStatus", "Pending"),
    "已报工": ("semi:ReportStatus", "Reported"),
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
        # Phase C: 标签向量索引 (lazy) — [(label, uri, np.ndarray)]
        self._label_vec_index: Optional[List] = None

    # ----------------------------------------------------------------- #
    # 主入口
    # ----------------------------------------------------------------- #

    def build(self, user_query: str, intent_slots=None) -> SemanticContext:
        """
        完整构建流程:
          1. 提取关键词 → 匹配本体类
          2. 提取值关键词 → 值映射过滤
          3. 类间路径发现 → 物理 JOIN 翻译（意图感知子图过滤）
          4. 业务规则匹配

        Args:
            user_query: 原始用户查询文本
            intent_slots: IntentSlots 实例（来自意图识别槽填充），用于定向匹配。
                          subject/dimension_by 会被预注入为高优先级候选类，
                          有效避免同义词引擎因覆盖不足导致的 0-match 问题。
        """
        ctx = SemanticContext(user_query=user_query)

        # Step 1: 匹配本体类（intent_slots 提供预注入高优先级候选）
        matched = self._match_classes(user_query, intent_slots=intent_slots)
        ctx.matched_classes = matched
        logger.info(
            "Matched %d classes from query: %s",
            len(matched),
            [m.keyword for m in matched],
        )

        # Step 1.5: Phase 2 — 指标匹配
        ctx.metrics = self._match_metrics(user_query)
        if ctx.metrics:
            logger.info(
                "Matched %d metrics: %s",
                len(ctx.metrics),
                [m.metric_id for m in ctx.metrics],
            )

        # Step 1.6: 指标驱动的实体注入
        # 当查询命中指标时，自动将指标 join_path 中所有锚点表/中间表对应的逻辑类
        # 注入 matched_classes，使 _resolve_joins 能推导出完整 JOIN 路径。
        # 非指标查询：ctx.metrics 为空，本步直接跳过，完全不影响原有流程。
        if ctx.metrics:
            matched = self._inject_metric_required_classes(matched, ctx.metrics)
            ctx.matched_classes = matched

        # Step 2: 値映射
        filters = self._match_values(user_query)

        # Step 2.1: Phase 1 — nl_triggers 补充匹配（对 _VALUE_KEYWORDS 未覆盖的词产生精确状态过滤）
        nl_filters = self._match_values_nl_triggers(user_query, filters)
        filters.extend(nl_filters)

        # Step 2.2: Phase 1 — WIP 语义自动推导“排除终态”过滤（仅对 Running/WIP 语义）
        wip_filter = self._auto_wip_filter(user_query, filters)
        if wip_filter:
            filters.append(wip_filter)
            # WIP 语义推断：统计口径以 Wafer 为粒度（BR-001: Wafer→Sublot→ProcessStation）
            # 若 semi:Wafer 未被任何 class synonym 命中，自动注入
            if not any(m.logic_class == "semi:Wafer" for m in matched):
                pt_wafer = self._mapping.get_physical_table("semi:Wafer")
                if pt_wafer:
                    matched.append(self._to_matched_class("在制品(WIP推断)", pt_wafer))
                    logger.info(
                        "WIP semantic inference: auto-injected semi:Wafer into matched_classes"
                    )

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
        joins, injected_classes = self._resolve_joins(matched, user_query)
        ctx.joins = joins
        # 将路径发现过程中注入的中间类合并回 matched_classes，
        # 确保 schema_snippet 中的 TABLE 声明包含所有 JOIN 涉及的物理表
        if injected_classes:
            ctx.matched_classes = matched + injected_classes
        if joins:
            logger.info("Resolved %d join paths", len(joins))

        # Step 4: 业务规则
        rules = self._match_business_rules(ctx.physical_tables)
        ctx.business_rules = rules

        return ctx

    # ----------------------------------------------------------------- #
    # Step 1: 关键词 → 本体类匹配
    # ----------------------------------------------------------------- #

    def _match_classes(self, query: str, intent_slots=None) -> List[MatchedClass]:
        """
        从查询中提取中文/英文关键词并匹配到本体类。

        策略（优先级从高到低，静态规则优先）:
          S. [预注入] intent_slots.subject / dimension_by 的同义词定向搜索（最高优先级）
          A. 映射字典的中文标签做精确子串匹配
          B. _CLASS_SYNONYMS 同义词/缩写词典匹配
          C. OntologyGraph 的 label_index 扫描
          D. 正则分词后逐词 find_class_by_label
          E. [Phase C] Embedding 相似度匹配（仅对 A-D 全部未命中的 token）
             → 相似度 < 0.82 时仍 MISS，并通过 synonym_manager 上报等待人工审核
        """
        results: List[MatchedClass] = []
        seen_classes: Set[str] = set()
        query_lower = query.lower()

        # ── 策略S: intent_slots 定向预注入（最高优先级）──────────────────────────
        # 如果意图识别已填充 subject / dimension_by 槽，直接用这些描述词在同义词表中
        # 做精确匹配，将结果预注入 results。这解决了原始查询词无法触发同义词的根本问题。
        if intent_slots is not None:
            active_synonyms = _get_active_synonyms()
            for slot_text in filter(None, [
                getattr(intent_slots, "subject", None),
                getattr(intent_slots, "dimension_by", None),
            ]):
                slot_lower = slot_text.lower()
                for keyword, logic_class in active_synonyms.items():
                    if keyword in slot_lower or slot_lower in keyword:
                        if logic_class not in seen_classes:
                            pt = self._mapping.get_physical_table(logic_class)
                            if pt:
                                seen_classes.add(logic_class)
                                results.append(self._to_matched_class(keyword, pt))
                                logger.info(
                                    "[context_builder] Slot-injected class %s "
                                    "via intent_slots '%s'→keyword '%s'",
                                    logic_class, slot_text, keyword,
                                )
                # 策略S+: 多类命中扩展（同一关键词映射到 2+ 类，如"过站记录"→CheckIn+CheckOut）
                for keyword, uris in _get_multi_class_synonyms().items():
                    if keyword in slot_lower or slot_lower in keyword:
                        for logic_class in uris:
                            if logic_class not in seen_classes:
                                pt = self._mapping.get_physical_table(logic_class)
                                if pt:
                                    seen_classes.add(logic_class)
                                    results.append(self._to_matched_class(keyword, pt))
                                    logger.info(
                                        "[context_builder] Slot-injected multi-class %s "
                                        "via intent_slots '%s'→keyword '%s'",
                                        logic_class, slot_text, keyword,
                                    )

        # 策略A: 映射字典中文标签精确匹配（label_cn 是查询子串）
        for pt in self._mapping.list_all_tables():
            if pt.label_cn and pt.label_cn in query:
                if pt.logic_class not in seen_classes:
                    seen_classes.add(pt.logic_class)
                    results.append(self._to_matched_class(pt.label_cn, pt))

        # 策略B: 同义词/缩写匹配（含 Supabase 动态叠加层）
        for keyword, logic_class in _get_active_synonyms().items():
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

        # 策略B+: 多类命中扩展 — 同一关键词映射到 2+ 类
        # 例："过站记录" → [semi:CheckInEventRecord, semi:CheckOutEventRecord]
        # → 两个类都进入 matched_classes → sql_generator 折叠为 operation_type IN (8, 9)
        for keyword, uris in _get_multi_class_synonyms().items():
            if keyword in query_lower:
                for logic_class in uris:
                    if logic_class not in seen_classes:
                        pt = self._mapping.get_physical_table(logic_class)
                        if pt:
                            seen_classes.add(logic_class)
                            results.append(self._to_matched_class(keyword, pt))
                            logger.info(
                                "[context_builder] Strategy B+ multi-class: '%s' → %s",
                                keyword, logic_class,
                            )

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

        # 策略D: 正则分词后逐词查找（仍保留作为内层兜底）
        chinese_tokens = re.findall(r'[\u4e00-\u9fff]{2,}', query)
        english_tokens = re.findall(r'[a-zA-Z]{2,}', query.lower())
        all_tokens = chinese_tokens + english_tokens
        matched_keywords: Set[str] = {mc.keyword for mc in results}  # 已命中的关键词
        unmatched_tokens: List[str] = []  # A-D 全部未命中的 token，供策略 E 使用

        for token in all_tokens:
            # 如果 token 已被前面任意策略覆盖（是已命中 keyword 的子串或超串）则跳过
            if any(token in kw or kw in token for kw in matched_keywords):
                continue
            cls = self._ontology.find_class_by_label(token)
            if cls and cls.uri not in seen_classes:
                seen_classes.add(cls.uri)
                matched_keywords.add(token)
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
            else:
                # 策略 A-D 全部未命中，候选供策略 E
                unmatched_tokens.append(token)

        # 策略E: embedding 相似度匹配（仅对 A-D 全部未命中的 token 使用）
        _still_unmatched: List[str] = []
        for token in unmatched_tokens:
            matched = self._embed_fuzzy_match(token, seen_classes)
            if matched:
                seen_classes.add(matched.logic_class)
                results.append(matched)
                logger.info(
                    f"[context_builder] Strategy E matched: '{token}' → "
                    f"{matched.logic_class} ({matched.label_cn})"
                )
            else:
                _still_unmatched.append(token)

        # 对全部策略都未命中的词，上报同义词管理层等待人工审核
        if _still_unmatched:
            try:
                from app.services.synonym_manager import synonym_manager as _sm
                for tok in _still_unmatched:
                    _sm.record_unmatched_term(tok, query)
                    logger.debug(f"[context_builder] Unmatched term recorded: '{tok}'")
            except Exception:
                pass  # 同义词服务不可用时不阻塞主流程

        return results

    # ----------------------------------------------------------------- #
    # Phase C: Embedding 向量索引 + 相似度匹配                           #
    # ----------------------------------------------------------------- #

    def _get_label_vec_index(self) -> Optional[List]:
        """
        构建标签向量索引（懒加载 + 实例级缓存）。

        收集来源：
          1. _CLASS_SYNONYMS 中所有同义词键 (key → uri)
          2. OntologyGraph._label_index 中所有标签 (label → uri)
          3. MappingDictionary.list_all_tables() 中所有 label_cn

        返回: List[Tuple[label:str, uri:str, vector:np.ndarray]]
        当 OpenAI API 不可用（hash fallback）时返回 None。
        """
        if self._label_vec_index is not None:
            return self._label_vec_index

        try:
            from app.agent.rag.embeddings import get_embedding_service
        except ImportError:
            return None

        emb_svc = get_embedding_service()
        if not emb_svc.has_real_embeddings:
            logger.debug("[context_builder] No real embedding API — skipping Strategy E index build")
            return None

        # 收集候选标签（去重）
        candidates: Dict[str, str] = {}  # label → uri
        # 来源1: 静态同义词典（含 Supabase 叠加层）
        for label, uri in _get_active_synonyms().items():
            candidates[label] = uri
        # 来源2: 本体图 label_index
        for label, uri in self._ontology._label_index.items():
            if len(label) >= 2:
                candidates.setdefault(label, uri)
        # 来源3: 映射字典 label_cn
        for pt in self._mapping.list_all_tables():
            if pt.label_cn and len(pt.label_cn) >= 2:
                candidates.setdefault(pt.label_cn, pt.logic_class)

        labels = list(candidates.keys())
        uris = list(candidates.values())
        logger.info(f"[context_builder] Building embedding index for {len(labels)} labels...")

        import numpy as np
        vectors = emb_svc.embed_batch(labels)

        index = []
        for label, uri, vec in zip(labels, uris, vectors):
            if vec is not None:
                index.append((label, uri, np.array(vec, dtype=np.float32)))

        self._label_vec_index = index
        logger.info(f"[context_builder] Embedding index built: {len(index)} entries")
        return index

    @staticmethod
    def _cosine_similarity(a: "np.ndarray", b: "np.ndarray") -> float:
        """L2 归一化后的点积（即余弦相似度）"""
        import numpy as np
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _embed_fuzzy_match(
        self, token: str, seen_classes: Set[str]
    ) -> Optional["MatchedClass"]:
        """
        策略 E: 用 embedding 相似度为未命中 token 寻找最近本体类。

        只有相似度 > _EMBED_SIMILARITY_THRESHOLD 且未在 seen_classes 中时才返回结果。
        返回 None 表示没有足够相似的匹配。
        """
        index = self._get_label_vec_index()
        if not index:
            return None

        try:
            from app.agent.rag.embeddings import get_embedding_service
            import numpy as np
        except ImportError:
            return None

        emb_svc = get_embedding_service()
        token_vec = emb_svc.embed_text(token)
        if token_vec is None:
            return None

        token_arr = np.array(token_vec, dtype=np.float32)

        best_sim = -1.0
        best_label = ""
        best_uri = ""
        for label, uri, vec in index:
            if uri in seen_classes:
                continue
            sim = self._cosine_similarity(token_arr, vec)
            if sim > best_sim:
                best_sim = sim
                best_label = label
                best_uri = uri

        if best_sim < _EMBED_SIMILARITY_THRESHOLD:
            logger.debug(
                f"[context_builder] Strategy E: token='{token}' best_sim={best_sim:.3f} < threshold, no match"
            )
            return None

        logger.info(
            f"[context_builder] Strategy E: '{token}' → '{best_label}' ({best_uri}) sim={best_sim:.3f}"
        )

        pt = self._mapping.get_physical_table(best_uri)
        if pt:
            return self._to_matched_class(token, pt)
        else:
            cls = self._ontology.get_class(best_uri)
            label_cn = cls.label if cls else best_label
            return MatchedClass(
                keyword=token,
                logic_class=best_uri,
                label_cn=label_cn,
                physical_table=None,
                primary_key=None,
                display_column=None,
                virtual=True,
            )

    def _to_matched_class(self, keyword: str, pt: PhysicalTable) -> MatchedClass:
        return MatchedClass(
            keyword=keyword,
            logic_class=pt.logic_class,
            label_cn=pt.label_cn,
            physical_table=pt.table_name,
            primary_key=pt.primary_key,
            display_column=pt.display_column,
            key_columns=pt.key_columns,
            properties=pt.properties,
            virtual=pt.virtual,
            filter_condition=pt.filter_condition,
        )

    # ----------------------------------------------------------------- #
    # Step 1.5: Phase 2 --- 指标匹配
    # ----------------------------------------------------------------- #

    def _match_metrics(self, query: str) -> List[MetricDefinition]:
        """Phase 2: 从查询中识别指标名称，返回匹配到的 MetricDefinition 列表"""
        results: List[MetricDefinition] = []
        seen_ids: Set[str] = set()
        for metric in self._mapping.list_all_metrics():
            if metric.metric_id in seen_ids:
                continue
            for name in metric.zh_names:
                if name.lower() in query.lower() or name in query:
                    results.append(metric)
                    seen_ids.add(metric.metric_id)
                    break
        return results

    # ----------------------------------------------------------------- #
    # Step 1.6: 指标驱动的实体注入
    # ----------------------------------------------------------------- #

    def _inject_metric_required_classes(
        self,
        matched: List[MatchedClass],
        metrics: List[MetricDefinition],
    ) -> List[MatchedClass]:
        """
        将指标 join_path 中的所有物理表自动映射为本体类并注入 matched_classes。

        解析规则:
          join_path 格式: "table1 → table2(filter_hint) → table3"
          - anchor_table 作为第一个候选
          - join_path 中的 → 分隔的每段提取表名 + 括号内过滤提示
          - 若同一张物理表映射多个逻辑类（如 main/sublot 同表），
            优先选择 filter_condition 与提示匹配的那个

        非指标查询（metrics 为空）不调用此方法，无副作用。
        """
        seen_tables: Set[str] = {mc.physical_table for mc in matched if mc.physical_table}
        seen_classes: Set[str] = {mc.logic_class for mc in matched}
        added: List[MatchedClass] = []

        for metric in metrics:
            # 收集 (table_name, optional_filter_hint)
            table_hints: List[Tuple[Optional[str], Optional[str]]] = []

            if metric.anchor_table:
                table_hints.append((metric.anchor_table, None))

            if metric.join_path:
                # 支持 → (U+2192) 和 -> 两种分隔符
                for part in re.split(r'\s*[\u2192>-]+\s*', metric.join_path):
                    part = part.strip()
                    if not part:
                        continue
                    m = re.match(r'^(\w+)(?:\(([^)]*)\))?$', part)
                    if m:
                        tbl = m.group(1)
                        hint = m.group(2)  # e.g. "parent_id!=0"
                        if tbl != metric.anchor_table:
                            table_hints.append((tbl, hint))

            for tbl, hint in table_hints:
                if not tbl or tbl in seen_tables:
                    continue

                # 找出所有匹配该物理表名的 PhysicalTable
                candidates = [
                    pt for pt in self._mapping.list_all_tables()
                    if pt.table_name == tbl and not pt.virtual
                ]
                if not candidates:
                    continue

                chosen = None
                if len(candidates) == 1:
                    chosen = candidates[0]
                elif hint:
                    # 规范化比较（去空格）
                    hint_norm = hint.replace(" ", "")
                    for pt in candidates:
                        fc = (pt.filter_condition or "").replace(" ", "")
                        if fc and (hint_norm in fc or fc in hint_norm):
                            chosen = pt
                            break
                    if not chosen:
                        chosen = candidates[0]
                else:
                    chosen = candidates[0]

                if chosen.logic_class in seen_classes:
                    continue

                seen_tables.add(tbl)
                seen_classes.add(chosen.logic_class)
                mc = self._to_matched_class(f"[{metric.metric_id}]", chosen)
                added.append(mc)
                logger.info(
                    "[context_builder] Metric '%s' auto-injected: %s → %s",
                    metric.metric_id, tbl, chosen.logic_class,
                )

        return matched + added

    # ----------------------------------------------------------------- #
    # Step 2.1: Phase 1 --- nl_triggers 精确匹配 + WIP 终态自动推导
    # ----------------------------------------------------------------- #

    def _match_values_nl_triggers(
        self, query: str, existing_filters: List[ResolvedFilter]
    ) -> List[ResolvedFilter]:
        """
        Phase 1: 扫描所有 value_mappings 的 nl_triggers，
        对 _VALUE_KEYWORDS 未覆盖的关键词产生精确状态过滤。
        例: "新投批" → Pending.nl_triggers 命中 → status=0
        """
        results: List[ResolvedFilter] = []
        q_lower = query.lower()
        seen_pairs: Set[Tuple[str, str]] = {
            (f.semantic_domain, f.semantic_value) for f in existing_filters
            if f.semantic_value != "__wip_auto__"
        }
        # 若 LotWIPStatus 已命中（精确推导型三态），抑制 BatchStatus.Running 的 nl_trigger 污染
        # （BatchStatus.Running.nl_triggers 包含 "在制" 等 WIP 通用词，会误触发）
        if any(f.semantic_domain == "semi:LotWIPStatus" for f in existing_filters):
            seen_pairs.add(("semi:BatchStatus", "Running"))
        for domain, domain_map in self._mapping._value_map.items():
            for val_key, vm in domain_map.items():
                pair = (domain, val_key)
                if pair in seen_pairs:
                    continue
                if not vm.nl_triggers:
                    continue
                for trigger in vm.nl_triggers:
                    if trigger.lower() in q_lower:
                        seen_pairs.add(pair)
                        results.append(ResolvedFilter(
                            semantic_domain=domain,
                            semantic_value=val_key,
                            description=vm.description,
                            physical_condition=vm.physical_condition,
                            physical_values=vm.physical_values,
                            applies_to_table=vm.applies_to_table,
                            applies_to_column=vm.applies_to_column,
                            count_target_table=vm.count_target_table,
                            count_target_column=vm.count_target_column,
                        ))
                        break
        return results

    def _auto_wip_filter(
        self, query: str, existing_filters: List[ResolvedFilter]
    ) -> Optional[ResolvedFilter]:
        """
        Phase 1: 当查询包含 Running(WIP) 的 nl_triggers 且没有显式 BatchStatus 过滤时，
        自动注入 status NOT IN (终态值)。

        注意: 只检查 Running 的 nl_triggers，不检查 Pending 等其他状态。
        Pending/Completed 等的 nl_triggers 由 _match_values_nl_triggers() 处理。
        """
        batch_domain = "semi:BatchStatus"
        if any(f.semantic_domain == batch_domain for f in existing_filters):
            return None
        # LotWIPStatus 已提供精确三态推导，不再叠加 BatchStatus 终态排除
        if any(f.semantic_domain == "semi:LotWIPStatus" for f in existing_filters):
            return None

        # 只检查 Running 的 nl_triggers（WIP 语义）
        q_lower = query.lower()
        vm_running = self._mapping.map_value(batch_domain, "Running")
        triggered = False
        if vm_running and vm_running.nl_triggers:
            for trigger in vm_running.nl_triggers:
                if trigger.lower() in q_lower:
                    triggered = True
                    break

        if not triggered:
            return None

        exclusion = self._mapping.get_wip_exclusion_filter(batch_domain)
        if not exclusion:
            return None

        return ResolvedFilter(
            semantic_domain=batch_domain,
            semantic_value="__wip_auto__",
            description="自动排除终态（WIP语义推断：Completed/Cancelled）",
            physical_condition=exclusion,
            applies_to_table="matrix_routerx_operation_lot",
            applies_to_column="status",
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
                        count_target_table=vm.count_target_table,
                        count_target_column=vm.count_target_column,
                    ))

        # 复合语义修正：
        # 情况 A: 查询同时含 "在制" 和 "扣留"/"hold" 且没有更精确的 LotWIPStatus.Hold
        #   → "扣留" 应解释为 WIP hold（激活 HoldEventRecord），而非 BatchStatus.Staged
        # 情况 B: 查询直接指向操作记录（"扣留记录"/"hold记录"/"扣留日志"）
        #   → 目标表是日志表，BatchStatus 过滤不应注入
        hold_log_ctx_words = ("扣留记录", "hold记录", "扣留日志", "hold日志", "扣留历史", "hold历史",
                             "扣留操作记录", "hold操作")
        wip_ctx_words = ("在制", "wip", "在产")
        hold_ctx_words = ("扣留", "hold")

        if any(w in query_lower for w in hold_log_ctx_words):
            # 情况 B：直接删除所有 BatchStatus 干扰（目标表已是日志表）
            results = [
                f for f in results
                if f.semantic_domain != "semi:BatchStatus"
            ]
        elif (any(w in query_lower for w in wip_ctx_words)
                and any(h in query_lower for h in hold_ctx_words)
                and ("semi:LotWIPStatus", "Hold") not in seen_pairs):
            # 情况 A：WIP 语境 + 扣留 → 注入 LotWIPStatus.Hold
            results = [
                f for f in results
                if not (f.semantic_domain == "semi:BatchStatus"
                        and f.semantic_value in ("Staged", "Running"))
            ]
            vm_hold = self._mapping.map_value("semi:LotWIPStatus", "Hold")
            if vm_hold:
                results.append(ResolvedFilter(
                    semantic_domain="semi:LotWIPStatus",
                    semantic_value="Hold",
                    description=vm_hold.description,
                    physical_condition=vm_hold.physical_condition,
                    physical_values=vm_hold.physical_values,
                    applies_to_table=vm_hold.applies_to_table,
                    applies_to_column=vm_hold.applies_to_column,
                    count_target_table=vm_hold.count_target_table,
                    count_target_column=vm_hold.count_target_column,
                ))
        elif any(f.semantic_domain == "semi:LotWIPStatus" for f in results):
            # LotWIPStatus 已精确命中（来自 _VALUE_KEYWORDS 直接匹配），移除 BatchStatus.Running 噪音
            results = [
                f for f in results
                if not (f.semantic_domain == "semi:BatchStatus"
                        and f.semantic_value == "Running")
            ]

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

    # 记录类——具备自身业务状态/历史记录的实体类。
    # 作为未被查询提及的中间节点时，路径会引入隐式业务过滤，导致语义与查询意图相悖。
    # 判断标准：具有状态字段、时间戳、业务过滤条件的记录类，而非分组/分类/配置类。
    _RECORD_CLASSES: Set[str] = {
        "semi:ProductionLot",              # 批次主表，status 表示 WIP 状态
        "semi:Sublot",                     # 子批次，process_id 表示当前在哪个站点
        "semi:Wafer",                      # 晶圆单片
        "semi:Action",                     # 操作日志流水
        "semi:ProductionOrder",            # 生产工单
        # ── 量测事件类 ──
        # ProcessStation 与 Equipment 之间通过 WaferMeasurementSnapshot 存在2跳路径
        # （snapshotAtStation + snapshotOnEquipment），与 EquipmentGroup 路径等长，
        # 若未明确查询量测数据，量测路径会引入 process_measure_data JOIN，导致
        # "按站点统计设备列表" 等查询生成错误 SQL。
        # 加入此集合后，仅当查询明确包含量测语义（WaferMeasurementSnapshot 在
        # matched_classes 中）时才允许量测路径作桥接，否则过滤，
        # ProcessStation→Equipment 唯一化为正确的 EquipmentGroup 路径。
        "semi:WaferMeasurementSnapshot",   # 量测快照（逐参数记录层）
        "semi:MeasurementPassRecord",      # 量测录入事件（事件层）
    }

    def _path_has_unmentioned_record_class(
        self,
        edges: List,
        endpoint_classes: Set[str],
        matched_class_uris: Set[str],
    ) -> bool:
        """
        检查路径中是否存在未被查询提及的记录类中间节点。

        原则：
          - 路径端点（source/target）不检查
          - 中间节点如果是 _RECORD_CLASSES 且未出现在 matched_classes 中，返回 True
          - 分类/配置/组分类类（CarrierGroup, EquipmentGroup, Route 等）充当自然桥接节点，不影响
        """
        for edge in edges:
            intermediate = edge.from_class
            if intermediate in endpoint_classes:
                continue
            if intermediate in self._RECORD_CLASSES and intermediate not in matched_class_uris:
                return True
        return False

    def _resolve_joins(
        self, classes: List[MatchedClass], query: str = ""
    ) -> tuple:
        """
        对匹配到的类两两做路径发现，然后将每一跳的本体关系翻译为物理 JOIN。

        路径发现策略（优先级）：
          1. NetworkX JoinGraph 所有最短路径 → 语义验证（中间节点纯洁性检查）→ 选最佳路径
          2. NetworkX JoinGraph 无向 BFS fallback
          3. OntologyGraph（rdflib）— JoinGraph 未命中时 fallback

        语义验证原则：
          当多条最短路径存在时，优先选择中间节点不包含未被查询提及的记录类的路径。
          此原则直接使用 domain_class/range_class 已有信息，不需要额外语义标注。

        Returns:
            (List[ResolvedJoin], List[MatchedClass]) — joins 列表 + 中间路径注入的额外 MatchedClass 列表
        """
        if len(classes) < 2:
            return [], []

        injected_classes: List[MatchedClass] = []  # 路径发现过程中注入的中间类

        resolved: List[ResolvedJoin] = []
        seen_relations: Set[str] = set()

        # 取非虚拟类来做 JOIN
        physical_classes = [c for c in classes if not c.virtual and c.physical_table]
        if len(physical_classes) < 2:
            return [], []

        join_graph = get_join_graph()  # 全局单例，lifespan 初始化后可用

        # 已匹配类的语义 URI 集合，用于中间节点纯洁性检查
        matched_class_uris: Set[str] = {c.logic_class for c in physical_classes}

        query_lower = (query or "").lower()

        # relation preference inferred from query wording (用于最短路径并列时择优)
        prefer_output_rel = any(k in query_lower for k in [
            "新批次", "产出", "输出", "拆出", "目标批次", "新增一列", "增加一列",
            "new lot", "output lot", "produced",
        ])
        prefer_input_rel = any(k in query_lower for k in [
            "源批次", "原批次", "输入批次", "作用批次",
        ])
        # 拆批场景默认关注源批次（splitsFromLot）；
        # 只有明确表达“新增/拆出/新批次/产出”时才切换为产出路径（producesLot）。
        split_context = any(k in query_lower for k in ["拆批", "split"])
        if split_context and not prefer_output_rel and not prefer_input_rel:
            prefer_input_rel = True

        preferred_relation_tokens: List[str] = []
        if prefer_output_rel:
            preferred_relation_tokens.extend([
                "produceslot", "producessublot", "haswafertransitiondetail",
            ])
        if prefer_input_rel:
            preferred_relation_tokens.extend([
                "splitsfromlot", "splitsfromsublot",
            ])

        def _score_path(edges: List) -> int:
            if not preferred_relation_tokens:
                return 0
            score = 0
            for e in edges:
                rel = e.logic_relation.lstrip("^").lower()
                if any(tok in rel for tok in preferred_relation_tokens):
                    score += 10
            return score

        for i in range(len(physical_classes)):
            for j in range(i + 1, len(physical_classes)):
                source = physical_classes[i].logic_class
                target = physical_classes[j].logic_class
                endpoint_classes = {source, target}

                # ── 优先：所有最短路径 + 语义验证 ──────────────────────────────
                if join_graph and join_graph.is_ready:
                    all_paths = join_graph.find_all_shortest_paths(source, target)

                    # 多条等长路径时：优先选择中间节点不含未提及记录类的路径
                    if len(all_paths) > 1:
                        clean_paths = [
                            p for p in all_paths
                            if not self._path_has_unmentioned_record_class(
                                p, endpoint_classes, matched_class_uris
                            )
                        ]
                        chosen_paths = clean_paths if clean_paths else all_paths
                        if len(chosen_paths) > 1 and preferred_relation_tokens:
                            chosen_paths = sorted(chosen_paths, key=_score_path, reverse=True)
                        logger.info(
                            "[context_builder] %s→%s: %d paths, %d passed semantic validation",
                            source, target, len(all_paths), len(chosen_paths),
                        )
                    else:
                        chosen_paths = all_paths

                    jg_edges = chosen_paths[0] if chosen_paths else None

                    if jg_edges is None:
                        jg_edges = join_graph.find_path_undirected(source, target)

                    if jg_edges is not None:
                        for edge in jg_edges:
                            actual_rel = edge.logic_relation.lstrip("^")
                            if actual_rel in seen_relations:
                                continue
                            seen_relations.add(actual_rel)
                            rm = edge.relation_mapping
                            resolved.append(ResolvedJoin(
                                logic_relation=rm.logic_relation,
                                strategy=rm.strategy,
                                conditions=rm.join_conditions,
                                bridge_table=rm.bridge_table,
                                order_by=rm.order_by,
                                note=rm.note,
                            ))
                        continue  # 本对已处理，跳到下一对

                # ── Fallback：OntologyGraph（rdflib TTL 图）───────────────
                all_paths = self._ontology.find_all_paths(source, target)
                if not all_paths:
                    continue

                shortest_len = len(all_paths[0])
                shortest_paths = [p for p in all_paths if len(p) == shortest_len]

                if len(shortest_paths) > 1 and preferred_relation_tokens:
                    def _score_onto_path(path_edges: List[Tuple[str, str, str]]) -> int:
                        score = 0
                        for _from_cls, rel_uri, _to_cls in path_edges:
                            rel = rel_uri.lstrip("^").lower()
                            if any(tok in rel for tok in preferred_relation_tokens):
                                score += 10
                        return score

                    shortest_paths = sorted(shortest_paths, key=_score_onto_path, reverse=True)

                path = shortest_paths[0]

                for from_cls, rel_uri, to_cls in path:
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

        return resolved, injected_classes

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
    intent_slots=None,
) -> SemanticContext:
    """一行调用: 从自然语言 → SemanticContext

    Args:
        user_query: 原始用户查询文本
        ontology: 可选，覆盖默认 OntologyGraph
        mapping: 可选，覆盖默认 MappingDictionary
        intent_slots: 可选，IntentSlots 实例，用于定向匹配（策略S）
    """
    builder = SemanticContextBuilder(ontology=ontology, mapping=mapping)
    return builder.build(user_query, intent_slots=intent_slots)
