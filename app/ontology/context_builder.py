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

    # ══════════════════════════════════════════════════════════════
    # 以下为生产库 cc_semi_mvp 专用关键词（整数枚举，physical_condition 格式）
    # ══════════════════════════════════════════════════════════════

    # ── BatchStatus (local_production_batch.status) ──
    "在制品": ("semi:BatchStatus", "Running"),
    "wip": ("semi:BatchStatus", "Running"),
    "在制": ("semi:BatchStatus", "Running"),
    "执行中": ("semi:BatchStatus", "Running"),
    "待执行": ("semi:BatchStatus", "Pending"),
    "完工": ("semi:BatchStatus", "Completed"),
    "已完成批次": ("semi:BatchStatus", "Completed"),
    "取消批次": ("semi:BatchStatus", "Cancelled"),

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

        策略（优先级从高到低，静态规则优先）:
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
        # 来源1: 静态同义词典
        for label, uri in _CLASS_SYNONYMS.items():
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
                        count_target_table=vm.count_target_table,
                        count_target_column=vm.count_target_column,
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
