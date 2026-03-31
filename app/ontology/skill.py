"""
本体建模技能 (Ontology Builder Skill)

支持通过结构化输入完成：
  1. 语义层建模 — 新增/更新 OWL 类、ObjectProperty、DatatypeProperty → TTL 文件
  2. 物理映射维护 — 新增/更新 object_mappings、relation_mappings、value_mappings → mapping JSON
  3. 一致性校验 — TTL ↔ mapping 双向检查
  4. 原子提交 — TTL 版本快照 + mapping 原子写入 + changelog 追加

设计原则：
  - Staged Builder：先 stage 变更，preview 检查，确认后 commit
  - 幂等性：重复提交相同 spec 不产生副作用
  - 安全性：commit 前校验，失败时回滚
"""
from __future__ import annotations

import copy
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from rdflib import Graph as RDFGraph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

from .config import DEFAULT_TTL_PATH, ONTOLOGY_DATA_DIR, SEMI_NS

logger = logging.getLogger(__name__)

SEMI = Namespace(SEMI_NS)

# XSD 映射
_XSD_MAP = {
    "xsd:string": XSD.string,
    "xsd:integer": XSD.integer,
    "xsd:int": XSD.integer,
    "xsd:boolean": XSD.boolean,
    "xsd:dateTime": XSD.dateTime,
    "xsd:float": XSD.float,
    "xsd:double": XSD.double,
    "xsd:decimal": XSD.decimal,
    "xsd:date": XSD.date,
    "xsd:long": XSD.long,
    "string": XSD.string,
    "integer": XSD.integer,
    "boolean": XSD.boolean,
    "datetime": XSD.dateTime,
}


def _to_semi_uri(name: str) -> URIRef:
    """将 'semi:Wafer' 或 'Wafer' 转为完整 URIRef"""
    clean = name.replace("semi:", "") if name.startswith("semi:") else name
    return SEMI[clean]


def _short(uri: str) -> str:
    """将完整 URI 或 semi:XXX 转为 semi:XXX 短名"""
    s = str(uri)
    if s.startswith(SEMI_NS):
        return "semi:" + s[len(SEMI_NS):]
    if s.startswith("semi:"):
        return s
    return "semi:" + s


# ═════════════════════════════════════════════════════════════════════
# 输入 Spec 数据类
# ═════════════════════════════════════════════════════════════════════

@dataclass
class ClassSpec:
    """类定义规范"""
    uri: str                          # e.g. "semi:NewClass" 或 "NewClass"
    label: str = ""                   # rdfs:label, e.g. "新类(NewClass)"
    comment: str = ""                 # rdfs:comment
    parent_uri: str = ""              # rdfs:subClassOf, e.g. "semi:Material"
    # 物理映射
    physical_table: Optional[str] = None
    primary_key: Optional[str] = None
    label_cn: str = ""
    display_column: Optional[str] = None
    key_columns: List[str] = field(default_factory=list)
    properties: Dict[str, str] = field(default_factory=dict)  # semi:prop → column
    property_constraints: Dict[str, Any] = field(default_factory=dict)  # semi:prop → {applicable_record_types, note}
    virtual: bool = False
    virtual_kind: Optional[str] = None
    filter_condition: Optional[str] = None
    note: Optional[str] = None


@dataclass
class RelationSpec:
    """关系定义规范"""
    uri: str                          # e.g. "semi:newRelation"
    label: str = ""
    comment: str = ""
    domain_uri: str = ""              # 起点类
    range_uri: str = ""               # 终点类 (可为逗号分隔实现 unionOf)
    # 物理映射
    strategy: str = "ForeignKey"      # ForeignKey/JoinTable/Indirect/JoinVia/Recursive/per_record_type/...
    description: str = ""
    join_logic: Dict[str, Any] = field(default_factory=dict)
    per_record_type_join: Dict[str, Any] = field(default_factory=dict)  # {"semi:SplitEventRecord": {strategy, join_logic}, ...}
    applicable_intents: List[str] = field(default_factory=list)
    forbidden_intents: List[str] = field(default_factory=list)
    applicable_record_types: List[str] = field(default_factory=list)
    note: Optional[str] = None


@dataclass
class DataPropertySpec:
    """数据属性定义规范"""
    uri: str                          # e.g. "semi:hasNewProp"
    label: str = ""
    comment: str = ""
    domain_uris: List[str] = field(default_factory=list)  # 所属类列表
    range_type: str = "xsd:string"    # XSD 类型
    applicable_record_types: List[str] = field(default_factory=list)  # 仅适用的事件类型（对齐 RelationSpec）
    physical_mapping_path: str = ""   # 物理列路径，如 "_detail.extra[via:batch_resume_detail_log_id]"


@dataclass
class ValueMappingSpec:
    """值映射规范"""
    domain: str                       # e.g. "semi:EquipmentStatus"
    semantic_value: str               # e.g. "Idle"
    description: str = ""
    physical_values: Optional[List[str]] = None
    physical_condition: Optional[str] = None
    applies_to_table: Optional[str] = None
    applies_to_column: Optional[str] = None
    is_terminal: bool = False
    nl_triggers: List[str] = field(default_factory=list)
    note: Optional[str] = None


@dataclass
class RemoveSpec:
    """删除条目规范"""
    uri: str                     # e.g. "semi:mergedFrom"
    kind: str                    # "class" | "relation" | "data_property"
    reason: str = ""             # 删除原因（记录到 changelog）
    remove_mapping: bool = True  # 同时删除 mapping 条目


@dataclass
class OntologySpec:
    """完整的本体构建规范 — 一次性提交多个变更"""
    classes: List[ClassSpec] = field(default_factory=list)
    relations: List[RelationSpec] = field(default_factory=list)
    data_properties: List[DataPropertySpec] = field(default_factory=list)
    value_mappings: List[ValueMappingSpec] = field(default_factory=list)
    removals: List[RemoveSpec] = field(default_factory=list)  # 待删除条目
    message: str = ""                 # 变更说明
    author: str = "ontology_skill"


# ═════════════════════════════════════════════════════════════════════
# 校验结果
# ═════════════════════════════════════════════════════════════════════

@dataclass
class ValidationIssue:
    """校验问题"""
    level: str          # "error" | "warning" | "info"
    category: str       # "ttl" | "mapping" | "consistency" | "duplicate"
    message: str
    target: str = ""    # 涉及的 URI 或 key


@dataclass
class PreviewResult:
    """提交预览结果"""
    ttl_additions: List[str]      # TTL 中新增的三元组描述
    ttl_updates: List[str]        # TTL 中更新的三元组描述
    mapping_additions: List[str]  # mapping 中新增的条目描述
    mapping_updates: List[str]    # mapping 中更新的条目描述
    issues: List[ValidationIssue]

    @property
    def has_errors(self) -> bool:
        return any(i.level == "error" for i in self.issues)

    @property
    def summary(self) -> Dict[str, Any]:
        return {
            "ttl_additions": len(self.ttl_additions),
            "ttl_updates": len(self.ttl_updates),
            "mapping_additions": len(self.mapping_additions),
            "mapping_updates": len(self.mapping_updates),
            "errors": sum(1 for i in self.issues if i.level == "error"),
            "warnings": sum(1 for i in self.issues if i.level == "warning"),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "ttl_additions": self.ttl_additions,
            "ttl_updates": self.ttl_updates,
            "mapping_additions": self.mapping_additions,
            "mapping_updates": self.mapping_updates,
            "issues": [
                {"level": i.level, "category": i.category,
                 "message": i.message, "target": i.target}
                for i in self.issues
            ],
        }


@dataclass
class CommitResult:
    """提交结果"""
    success: bool
    ttl_version: Optional[int] = None
    changes_count: int = 0
    message: str = ""
    issues: List[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "ttl_version": self.ttl_version,
            "changes_count": self.changes_count,
            "message": self.message,
            "issues": [
                {"level": i.level, "category": i.category,
                 "message": i.message, "target": i.target}
                for i in self.issues
            ],
        }


# ═════════════════════════════════════════════════════════════════════
# 核心技能引擎
# ═════════════════════════════════════════════════════════════════════

class OntologyBuilderSkill:
    """
    本体建模技能引擎

    工作流：
      1. load() — 加载当前 TTL + mapping 到内存
      2. stage(spec) — 将变更 spec 应用到内存副本
      3. preview() — 校验并返回变更预览
      4. commit() — 原子写入 TTL + mapping + changelog + 版本
    """

    def __init__(self, mapping_file: Optional[Path] = None):
        self._mapping_file = mapping_file or self._resolve_mapping_file()
        self._rdf: Optional[RDFGraph] = None
        self._mapping_raw: Optional[Dict[str, Any]] = None
        self._staged_spec: Optional[OntologySpec] = None
        self._loaded = False

    @staticmethod
    def _resolve_mapping_file() -> Path:
        env_val = os.getenv("MAPPING_FILE", "").strip()
        if env_val:
            p = Path(env_val)
            if not p.is_absolute():
                p = ONTOLOGY_DATA_DIR / p
            if p.exists():
                return p
        prod = ONTOLOGY_DATA_DIR / "mapping_prod.json"
        if prod.exists():
            return prod
        return ONTOLOGY_DATA_DIR / "mapping_demo_fab.json"

    # ── 加载 ──────────────────────────────────────────────

    def load(self) -> "OntologyBuilderSkill":
        """加载当前 TTL 和 mapping JSON 到内存"""
        # 加载 TTL
        self._rdf = RDFGraph()
        if DEFAULT_TTL_PATH.exists():
            self._rdf.parse(str(DEFAULT_TTL_PATH), format="turtle")
        self._rdf.bind("semi", SEMI)
        self._rdf.bind("owl", OWL)
        self._rdf.bind("rdfs", RDFS)
        self._rdf.bind("xsd", XSD)

        # 加载 mapping
        with open(self._mapping_file, "r", encoding="utf-8") as f:
            self._mapping_raw = json.load(f)

        self._staged_spec = None
        self._loaded = True
        logger.info("[skill] Loaded TTL (%d triples) + mapping (%s)",
                     len(self._rdf), self._mapping_file.name)
        return self

    def _ensure_loaded(self):
        if not self._loaded:
            raise RuntimeError("Must call load() first")

    # ── Stage ────────────────────────────────────────────

    def stage(self, spec: OntologySpec) -> "OntologyBuilderSkill":
        """暂存变更到内存（不写文件）"""
        self._ensure_loaded()
        self._staged_spec = spec
        return self

    # ── 索引辅助 ─────────────────────────────────────────

    def _existing_class_uris(self) -> Set[str]:
        """从 RDF 图中获取已有的所有 OWL 类 URI (short form)"""
        result = set()
        for s, _, _ in self._rdf.triples((None, RDF.type, OWL.Class)):
            if isinstance(s, URIRef):
                result.add(_short(str(s)))
        return result

    def _existing_relation_uris(self) -> Set[str]:
        """从 RDF 图中获取已有的所有 ObjectProperty URI (short form)"""
        result = set()
        for s, _, _ in self._rdf.triples((None, RDF.type, OWL.ObjectProperty)):
            if isinstance(s, URIRef):
                result.add(_short(str(s)))
        return result

    def _existing_dataprop_uris(self) -> Set[str]:
        result = set()
        for s, _, _ in self._rdf.triples((None, RDF.type, OWL.DatatypeProperty)):
            if isinstance(s, URIRef):
                result.add(_short(str(s)))
        return result

    def _existing_object_mapping_classes(self) -> Set[str]:
        return {om["logic_class"] for om in self._mapping_raw.get("object_mappings", [])}

    def _existing_relation_mapping_uris(self) -> Set[str]:
        return {rm["logic_relation"] for rm in self._mapping_raw.get("relation_mappings", [])}

    def _existing_value_domains(self) -> Dict[str, Set[str]]:
        result: Dict[str, Set[str]] = {}
        for domain, values in self._mapping_raw.get("value_mappings", {}).items():
            result[domain] = set(values.keys()) if isinstance(values, dict) else set()
        return result

    # ── Preview / Validate ───────────────────────────────

    def preview(self) -> PreviewResult:
        """校验暂存的 spec 并返回变更预览"""
        self._ensure_loaded()
        if self._staged_spec is None:
            return PreviewResult([], [], [], [], [
                ValidationIssue("warning", "empty", "No spec staged")
            ])

        spec = self._staged_spec
        ttl_adds: List[str] = []
        ttl_updates: List[str] = []
        map_adds: List[str] = []
        map_updates: List[str] = []
        issues: List[ValidationIssue] = []

        existing_classes = self._existing_class_uris()
        existing_rels = self._existing_relation_uris()
        existing_dps = self._existing_dataprop_uris()
        existing_om = self._existing_object_mapping_classes()
        existing_rm = self._existing_relation_mapping_uris()
        existing_vm = self._existing_value_domains()

        # ── 校验类 ──
        for cs in spec.classes:
            uri = _short(cs.uri)
            if uri in existing_classes:
                ttl_updates.append(f"UPDATE class {uri}")
            else:
                ttl_adds.append(f"ADD class {uri} (label={cs.label})")

            # 父类存在性检查
            if cs.parent_uri:
                parent = _short(cs.parent_uri)
                parent_exists = parent in existing_classes or any(
                    _short(c.uri) == parent for c in spec.classes
                )
                if not parent_exists:
                    issues.append(ValidationIssue(
                        "error", "ttl",
                        f"Parent class {parent} not found in TTL",
                        target=uri,
                    ))

            # mapping 条目
            if cs.physical_table or cs.virtual:
                if uri in existing_om:
                    map_updates.append(f"UPDATE object_mapping for {uri}")
                else:
                    map_adds.append(f"ADD object_mapping: {uri} → {cs.physical_table or '(virtual)'}")

                # 非虚拟类必须有 physical_table
                if not cs.virtual and not cs.physical_table:
                    issues.append(ValidationIssue(
                        "error", "mapping",
                        f"Non-virtual class {uri} must have physical_table",
                        target=uri,
                    ))
            else:
                issues.append(ValidationIssue(
                    "warning", "mapping",
                    f"Class {uri} has no physical mapping (no table or virtual flag)",
                    target=uri,
                ))

        # ── 校验关系 ──
        all_class_uris = existing_classes | {_short(c.uri) for c in spec.classes}
        for rs in spec.relations:
            uri = _short(rs.uri)
            if uri in existing_rels:
                ttl_updates.append(f"UPDATE relation {uri}")
            else:
                ttl_adds.append(f"ADD ObjectProperty {uri} ({rs.domain_uri} → {rs.range_uri})")

            # domain/range 存在性
            if rs.domain_uri:
                d = _short(rs.domain_uri)
                if d not in all_class_uris:
                    issues.append(ValidationIssue(
                        "error", "consistency",
                        f"Domain class {d} of relation {uri} not found",
                        target=uri,
                    ))
            if rs.range_uri:
                for r in rs.range_uri.split(","):
                    r = _short(r.strip())
                    if r not in all_class_uris:
                        issues.append(ValidationIssue(
                            "error", "consistency",
                            f"Range class {r} of relation {uri} not found",
                            target=uri,
                        ))

            # mapping 条目
            if rs.strategy and rs.strategy != "Virtual":
                if uri in existing_rm:
                    map_updates.append(f"UPDATE relation_mapping for {uri}")
                else:
                    map_adds.append(f"ADD relation_mapping: {uri} ({rs.strategy})")

                # ForeignKey 必须有 join_logic；per_record_type 必须有 per_record_type_join
                if rs.strategy == "ForeignKey":
                    jl = rs.join_logic
                    for required_key in ("source_table", "source_key", "target_table", "target_key"):
                        if not jl.get(required_key):
                            issues.append(ValidationIssue(
                                "error", "mapping",
                                f"ForeignKey relation {uri} missing join_logic.{required_key}",
                                target=uri,
                            ))
                elif rs.strategy == "per_record_type":
                    if not rs.per_record_type_join:
                        issues.append(ValidationIssue(
                            "error", "mapping",
                            f"per_record_type relation {uri} missing per_record_type_join",
                            target=uri,
                        ))
            else:
                map_adds.append(f"ADD relation_mapping: {uri} (Virtual)")

        # ── 校验数据属性 ──
        for dp in spec.data_properties:
            uri = _short(dp.uri)
            if uri in existing_dps:
                ttl_updates.append(f"UPDATE DatatypeProperty {uri}")
            else:
                ttl_adds.append(f"ADD DatatypeProperty {uri} (range={dp.range_type})")

            for d in dp.domain_uris:
                d = _short(d)
                if d not in all_class_uris:
                    issues.append(ValidationIssue(
                        "warning", "consistency",
                        f"Domain class {d} of property {uri} not found",
                        target=uri,
                    ))

            # mapping 条目：若有物理路径则预览 object_mapping.properties 更新
            if dp.physical_mapping_path:
                for d_raw in dp.domain_uris:
                    d_short = _short(d_raw)
                    if d_short in existing_om:
                        map_updates.append(
                            f"UPDATE object_mapping[{d_short}].properties[{uri}] = {dp.physical_mapping_path}"
                        )
                    else:
                        issues.append(ValidationIssue(
                            "warning", "mapping",
                            f"DataProp {uri}: domain {d_short} not in object_mappings, path will be skipped",
                            target=uri,
                        ))

        # ── 校验值映射 ──
        for vm in spec.value_mappings:
            domain = vm.domain
            if not domain.startswith("semi:"):
                domain = "semi:" + domain
            existing_vals = existing_vm.get(domain, set())
            if vm.semantic_value in existing_vals:
                map_updates.append(f"UPDATE value_mapping: {domain}.{vm.semantic_value}")
            else:
                map_adds.append(f"ADD value_mapping: {domain}.{vm.semantic_value}")

            if not vm.physical_values and not vm.physical_condition:
                issues.append(ValidationIssue(
                    "warning", "mapping",
                    f"Value mapping {domain}.{vm.semantic_value} has neither physical_values nor physical_condition",
                    target=f"{domain}.{vm.semantic_value}",
                ))

        # ── 校验删除项 ──
        _kind_to_owl = {
            "class": OWL.Class,
            "relation": OWL.ObjectProperty,
            "data_property": OWL.DatatypeProperty,
        }
        for rm in spec.removals:
            rm_short = _short(rm.uri)
            owl_type = _kind_to_owl.get(rm.kind)
            exists_ttl = (
                owl_type is not None
                and (_to_semi_uri(rm.uri), RDF.type, owl_type) in self._rdf
            )
            if exists_ttl:
                ttl_updates.append(
                    f"REMOVE {rm.kind} {rm_short}"
                    + (f" (reason: {rm.reason})" if rm.reason else "")
                )
            else:
                issues.append(ValidationIssue(
                    "warning", "ttl",
                    f"RemoveSpec target {rm_short} ({rm.kind}) not found in TTL — will be skipped",
                    target=rm_short,
                ))
            if rm.remove_mapping:
                if rm.kind == "class" and rm_short in existing_om:
                    map_updates.append(f"REMOVE object_mapping for {rm_short}")
                elif rm.kind in ("relation", "data_property") and rm_short in existing_rm:
                    map_updates.append(f"REMOVE relation_mapping for {rm_short}")

        return PreviewResult(
            ttl_additions=ttl_adds,
            ttl_updates=ttl_updates,
            mapping_additions=map_adds,
            mapping_updates=map_updates,
            issues=issues,
        )

    # ── Commit ───────────────────────────────────────────

    def commit(self, force: bool = False, incremental: bool = False) -> CommitResult:
        """
        原子提交所有暂存变更。

        Args:
            force: 忽略校验错误强制提交
            incremental: 文本级增量写入 TTL（保留人工注释和格式），默认 False（rdflib 全量序列化）

        步骤：
          1. 执行 preview 校验
          2. 如有 error 且 force=False，拒绝提交
          3. 应用 TTL 变更到 RDF 图（包括删除）
          4. 应用 mapping 变更到 JSON 数据（包括删除）
          5. 原子写入 mapping JSON
          6. 保存 TTL 新版本 (version_manager)
          7. 追加 changelog
          8. 触发热重载
        """
        self._ensure_loaded()
        if self._staged_spec is None:
            return CommitResult(success=False, message="No spec staged")

        spec = self._staged_spec
        preview = self.preview()

        if preview.has_errors and not force:
            return CommitResult(
                success=False,
                message=f"Validation failed with {preview.summary['errors']} error(s). Use force=True to override.",
                issues=preview.issues,
            )

        changes = 0

        try:
            # ── Step 1: 应用 TTL 变更 ──
            _original_ttl: Optional[str] = None
            if incremental and DEFAULT_TTL_PATH.exists():
                _original_ttl = DEFAULT_TTL_PATH.read_text(encoding="utf-8")
            changes += self._apply_ttl_removals(spec.removals)
            changes += self._apply_ttl_classes(spec.classes)
            changes += self._apply_ttl_relations(spec.relations)
            changes += self._apply_ttl_data_properties(spec.data_properties)

            # ── Step 2: 应用 mapping 变更 ──
            changes += self._apply_mapping_removals(spec.removals)
            changes += self._apply_mapping_objects(spec.classes)
            changes += self._apply_mapping_relations(spec.relations)
            changes += self._apply_mapping_data_properties(spec.data_properties)
            changes += self._apply_mapping_values(spec.value_mappings)

            # ── Step 3: 原子写入 mapping ──
            self._save_mapping()

            # ── Step 4: 保存 TTL 新版本 ──
            if _original_ttl is not None:
                modified_uris: Set[URIRef] = (
                    {_to_semi_uri(c.uri) for c in spec.classes}
                    | {_to_semi_uri(r.uri) for r in spec.relations}
                    | {_to_semi_uri(dp.uri) for dp in spec.data_properties}
                )
                removed_uris: Set[URIRef] = {_to_semi_uri(rm.uri) for rm in spec.removals}
                ttl_content = self._write_ttl_incremental(_original_ttl, modified_uris, removed_uris)
            else:
                ttl_content = self._rdf.serialize(format="turtle")
            from .version_manager import save_new_version
            version_entry = save_new_version(
                ttl_content=ttl_content,
                message=spec.message or f"Ontology skill: {changes} changes",
                author=spec.author,
            )

            # ── Step 5: Changelog ──
            self._append_changelog(spec, changes)

            # ── Step 6: 热重载 ──
            self._hot_reload()

            self._staged_spec = None

            return CommitResult(
                success=True,
                ttl_version=version_entry.get("version"),
                changes_count=changes,
                message=f"Committed {changes} changes (TTL v{version_entry.get('version')})",
                issues=preview.issues,
            )

        except Exception as e:
            logger.error("[skill] Commit failed: %s", e, exc_info=True)
            # 重新加载以回滚内存状态
            self.load()
            return CommitResult(
                success=False,
                message=f"Commit failed: {e}",
                issues=preview.issues,
            )

    # ── TTL 变更实现 ─────────────────────────────────────

    def _apply_ttl_classes(self, classes: List[ClassSpec]) -> int:
        count = 0
        for cs in classes:
            uri = _to_semi_uri(cs.uri)

            # 移除旧三元组（如果存在）
            self._rdf.remove((uri, RDF.type, None))
            self._rdf.remove((uri, RDFS.label, None))
            self._rdf.remove((uri, RDFS.comment, None))
            self._rdf.remove((uri, RDFS.subClassOf, None))

            # 添加新三元组
            self._rdf.add((uri, RDF.type, OWL.Class))
            if cs.label:
                self._rdf.add((uri, RDFS.label, Literal(cs.label)))
            if cs.comment:
                self._rdf.add((uri, RDFS.comment, Literal(cs.comment)))
            if cs.parent_uri:
                self._rdf.add((uri, RDFS.subClassOf, _to_semi_uri(cs.parent_uri)))
            count += 1
        return count

    def _apply_ttl_relations(self, relations: List[RelationSpec]) -> int:
        count = 0
        for rs in relations:
            uri = _to_semi_uri(rs.uri)

            # 移除旧三元组
            self._rdf.remove((uri, RDF.type, None))
            self._rdf.remove((uri, RDFS.label, None))
            self._rdf.remove((uri, RDFS.comment, None))
            self._rdf.remove((uri, RDFS.domain, None))
            self._rdf.remove((uri, RDFS.range, None))

            # 添加新三元组
            self._rdf.add((uri, RDF.type, OWL.ObjectProperty))
            if rs.label:
                self._rdf.add((uri, RDFS.label, Literal(rs.label)))
            if rs.comment:
                self._rdf.add((uri, RDFS.comment, Literal(rs.comment)))
            if rs.domain_uri:
                self._rdf.add((uri, RDFS.domain, _to_semi_uri(rs.domain_uri)))

            # range 可能是 unionOf (逗号分隔)
            if rs.range_uri:
                range_parts = [r.strip() for r in rs.range_uri.split(",")]
                if len(range_parts) == 1:
                    self._rdf.add((uri, RDFS.range, _to_semi_uri(range_parts[0])))
                else:
                    # unionOf: 创建 blank node list
                    from rdflib import BNode, Collection
                    bnode = BNode()
                    items = [_to_semi_uri(r) for r in range_parts]
                    Collection(self._rdf, bnode, items)
                    union_bnode = BNode()
                    self._rdf.add((union_bnode, OWL.unionOf, bnode))
                    self._rdf.add((uri, RDFS.range, union_bnode))
            count += 1
        return count

    def _apply_ttl_data_properties(self, props: List[DataPropertySpec]) -> int:
        count = 0
        for dp in props:
            uri = _to_semi_uri(dp.uri)

            # 移除旧三元组
            self._rdf.remove((uri, RDF.type, None))
            self._rdf.remove((uri, RDFS.label, None))
            self._rdf.remove((uri, RDFS.comment, None))
            self._rdf.remove((uri, RDFS.domain, None))
            self._rdf.remove((uri, RDFS.range, None))

            # 添加新三元组
            self._rdf.add((uri, RDF.type, OWL.DatatypeProperty))
            if dp.label:
                self._rdf.add((uri, RDFS.label, Literal(dp.label)))
            if dp.comment:
                self._rdf.add((uri, RDFS.comment, Literal(dp.comment)))

            # domain (可能多个 → unionOf)
            if len(dp.domain_uris) == 1:
                self._rdf.add((uri, RDFS.domain, _to_semi_uri(dp.domain_uris[0])))
            elif len(dp.domain_uris) > 1:
                from rdflib import BNode, Collection
                bnode = BNode()
                items = [_to_semi_uri(d) for d in dp.domain_uris]
                Collection(self._rdf, bnode, items)
                union_bnode = BNode()
                self._rdf.add((union_bnode, OWL.unionOf, bnode))
                self._rdf.add((uri, RDFS.domain, union_bnode))

            # range (XSD type)
            xsd_uri = _XSD_MAP.get(dp.range_type, _XSD_MAP.get(dp.range_type.lower(), XSD.string))
            self._rdf.add((uri, RDFS.range, xsd_uri))
            count += 1
        return count

    def _apply_ttl_removals(self, removals: List[RemoveSpec]) -> int:
        """从 RDF 图中删除指定 URI 的所有主语三元组"""
        count = 0
        _kind_to_owl = {
            "class": OWL.Class,
            "relation": OWL.ObjectProperty,
            "data_property": OWL.DatatypeProperty,
        }
        for rm in removals:
            uri = _to_semi_uri(rm.uri)
            owl_type = _kind_to_owl.get(rm.kind)
            if owl_type and (uri, RDF.type, owl_type) in self._rdf:
                for triple in list(self._rdf.triples((uri, None, None))):
                    self._rdf.remove(triple)
                count += 1
                logger.info("[skill] TTL: removed %s %s", rm.kind, rm.uri)
            else:
                logger.warning("[skill] RemoveSpec: %s (%s) not found in TTL, skipping", rm.uri, rm.kind)
        return count

    # ── Mapping 变更实现 ─────────────────────────────────

    def _apply_mapping_objects(self, classes: List[ClassSpec]) -> int:
        """同步 object_mappings"""
        count = 0
        om_list: List[Dict] = self._mapping_raw.setdefault("object_mappings", [])
        om_index = {item["logic_class"]: i for i, item in enumerate(om_list)}

        for cs in classes:
            uri = _short(cs.uri)
            if not cs.physical_table and not cs.virtual:
                continue  # 无物理映射，跳过

            entry = {
                "logic_class": uri,
                "physical_table": cs.physical_table,
                "primary_key": cs.primary_key,
                "label_cn": cs.label_cn or cs.label.split("(")[0] if cs.label else "",
                "display_column": cs.display_column,
                "key_columns": cs.key_columns,
                "properties": cs.properties,
            }
            if cs.virtual:
                entry["virtual"] = True
                if cs.virtual_kind:
                    entry["virtual_kind"] = cs.virtual_kind
            if cs.filter_condition:
                entry["filter_condition"] = cs.filter_condition
            if cs.property_constraints:
                entry["property_constraints"] = cs.property_constraints
            if cs.note:
                entry["note"] = cs.note

            if uri in om_index:
                om_list[om_index[uri]] = entry
            else:
                om_list.append(entry)
            count += 1
        return count

    def _apply_mapping_data_properties(self, props: List[DataPropertySpec]) -> int:
        """将 DataPropertySpec.physical_mapping_path 写入 object_mappings[].properties"""
        count = 0
        om_list = self._mapping_raw.get("object_mappings", [])
        om_index = {item["logic_class"]: i for i, item in enumerate(om_list)}
        for dp in props:
            if not dp.physical_mapping_path:
                continue
            prop_uri = _short(dp.uri)
            for domain_raw in dp.domain_uris:
                cls_uri = _short(domain_raw)
                if cls_uri in om_index:
                    om_list[om_index[cls_uri]].setdefault("properties", {})[prop_uri] = dp.physical_mapping_path
                    count += 1
                    logger.info("[skill] mapping: set %s.properties[%s]", cls_uri, prop_uri)
                else:
                    logger.warning(
                        "[skill] DataProp %s: domain %s not in object_mappings, path skipped",
                        prop_uri, cls_uri,
                    )
        return count

    def _apply_mapping_relations(self, relations: List[RelationSpec]) -> int:
        """同步 relation_mappings（支持 per_record_type 合并策略）"""
        count = 0
        rm_list: List[Dict] = self._mapping_raw.setdefault("relation_mappings", [])
        # 注意：per_record_type 合并后每个 uri 唯一，index 仍用 logic_relation 为键
        rm_index = {item["logic_relation"]: i for i, item in enumerate(rm_list)}

        for rs in relations:
            uri = _short(rs.uri)

            # 构建 range_class（单值或列表）
            range_class: Any = None
            if rs.range_uri:
                parts = [_short(r.strip()) for r in rs.range_uri.split(",")]
                range_class = parts[0] if len(parts) == 1 else parts

            entry: Dict[str, Any] = {
                "logic_relation": uri,
                "description": rs.description or rs.label or "",
                "strategy": rs.strategy,
                "domain_class": _short(rs.domain_uri) if rs.domain_uri else None,
                "range_class": range_class,
            }

            if rs.strategy == "per_record_type" and rs.per_record_type_join:
                # per_record_type：不写顶层 join_logic，改写 per_record_type_join
                entry["per_record_type_join"] = rs.per_record_type_join
            else:
                entry["join_logic"] = rs.join_logic
                if rs.applicable_record_types:
                    entry["applicable_record_types"] = rs.applicable_record_types
                if rs.note:
                    entry.setdefault("join_logic", {})["note"] = rs.note

            if rs.applicable_intents or rs.forbidden_intents:
                entry["intent_tags"] = {
                    "applicable": rs.applicable_intents,
                    "forbidden": rs.forbidden_intents,
                }

            if uri in rm_index:
                rm_list[rm_index[uri]] = entry
            else:
                rm_list.append(entry)
            count += 1
        return count

    def _apply_mapping_values(self, vms: List[ValueMappingSpec]) -> int:
        """同步 value_mappings"""
        count = 0
        vm_dict: Dict[str, Dict] = self._mapping_raw.setdefault("value_mappings", {})

        for vm in vms:
            domain = vm.domain
            if not domain.startswith("semi:"):
                domain = "semi:" + domain

            domain_dict = vm_dict.setdefault(domain, {})
            entry: Dict[str, Any] = {}
            if vm.description:
                entry["description"] = vm.description
            if vm.physical_values is not None:
                entry["physical_values"] = vm.physical_values
            if vm.physical_condition is not None:
                entry["physical_condition"] = vm.physical_condition
            if vm.applies_to_table:
                entry["applies_to_table"] = vm.applies_to_table
            if vm.applies_to_column:
                entry["applies_to_column"] = vm.applies_to_column
            if vm.is_terminal:
                entry["is_terminal"] = True
            if vm.nl_triggers:
                entry["nl_triggers"] = vm.nl_triggers
            if vm.note:
                entry["note"] = vm.note

            domain_dict[vm.semantic_value] = entry
            count += 1
        return count

    def _apply_mapping_removals(self, removals: List[RemoveSpec]) -> int:
        """从 mapping 中删除指定 URI 的条目"""
        count = 0
        for rm in removals:
            if not rm.remove_mapping:
                continue
            uri = _short(rm.uri)
            if rm.kind == "class":
                before = len(self._mapping_raw.get("object_mappings", []))
                self._mapping_raw["object_mappings"] = [
                    om for om in self._mapping_raw.get("object_mappings", [])
                    if om["logic_class"] != uri
                ]
                if len(self._mapping_raw["object_mappings"]) < before:
                    count += 1
                    logger.info("[skill] mapping: removed object_mapping for %s", uri)
            elif rm.kind in ("relation", "data_property"):
                before = len(self._mapping_raw.get("relation_mappings", []))
                self._mapping_raw["relation_mappings"] = [
                    rel for rel in self._mapping_raw.get("relation_mappings", [])
                    if rel["logic_relation"] != uri
                ]
                if len(self._mapping_raw["relation_mappings"]) < before:
                    count += 1
                    logger.info("[skill] mapping: removed relation_mapping for %s", uri)
        return count

    # ── 文件写入 ─────────────────────────────────────────

    def _save_mapping(self) -> None:
        """原子写入 mapping JSON"""
        path = self._mapping_file
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._mapping_raw, f, ensure_ascii=False, indent=2)
        tmp.replace(path)
        logger.info("[skill] Mapping saved to %s", path.name)

    def _serialize_single_uri(self, uri: URIRef) -> str:
        """序列化 RDF 图中单个 URI 的所有三元组为 Turtle 片段（不含 @prefix 头）"""
        from rdflib import BNode
        mini = RDFGraph()
        mini.bind("semi", SEMI)
        mini.bind("owl", OWL)
        mini.bind("rdfs", RDFS)
        mini.bind("xsd", XSD)

        def _collect(subj: Any, visited: set) -> None:
            for triple in self._rdf.triples((subj, None, None)):
                mini.add(triple)
                _, _, obj = triple
                if isinstance(obj, BNode) and obj not in visited:
                    visited.add(obj)
                    _collect(obj, visited)

        _collect(uri, set())
        full = mini.serialize(format="turtle")
        cleaned = re.sub(r"^@prefix[^\n]*\n", "", full, flags=re.MULTILINE)
        return cleaned.strip()

    def _write_ttl_incremental(
        self,
        original_text: str,
        modified_uris: Set[URIRef],
        removed_uris: Set[URIRef],
    ) -> str:
        """
        文本级增量写：只替换/删除变更 URI 对应的块，保留其余内容（含人工注释和格式）。

        约定：TTL 文件顶层声明块以空行（\\n\\n）分隔，每块首行以 semi:LocalName 开头。
        """
        # local_name → URIRef（已修改但未删除的）
        modified_map = {
            _short(str(u)).replace("semi:", ""): u
            for u in (modified_uris - removed_uris)
        }
        removed_names = {_short(str(u)).replace("semi:", "") for u in removed_uris}

        # 以 2+ 空行分割为段落
        paragraphs = re.split(r"\n{2,}", original_text)
        result: List[str] = []
        seen_modified: Set[str] = set()

        for para in paragraphs:
            stripped = para.strip()
            m = re.match(r"^semi:(\w+)\b", stripped)
            if not m:
                result.append(para)
                continue

            local = m.group(1)
            if local in removed_names:
                continue  # 删除：丢弃该段落
            elif local in modified_map:
                result.append(self._serialize_single_uri(modified_map[local]))
                seen_modified.add(local)
            else:
                result.append(para)

        # 追加新增的 URI（原文中不存在的）
        for local, uri in modified_map.items():
            if local not in seen_modified:
                result.append(self._serialize_single_uri(uri))

        return "\n\n".join(result)

    def _append_changelog(self, spec: OntologySpec, changes: int) -> None:
        """追加变更记录"""
        changelog_path = self._mapping_file.parent / "mapping_changelog.jsonl"
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": spec.author,
            "action": "ontology_skill_commit",
            "details": {
                "message": spec.message,
                "classes_count": len(spec.classes),
                "relations_count": len(spec.relations),
                "data_properties_count": len(spec.data_properties),
                "value_mappings_count": len(spec.value_mappings),
                "removals_count": len(spec.removals),
                "total_changes": changes,
            },
        }
        with open(changelog_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _hot_reload(self) -> None:
        """触发热重载"""
        try:
            from .loader import load_ontology
            from .mapping import load_mapping
            load_ontology(force_reload=True)
            load_mapping(force_reload=True)
            logger.info("[skill] Hot-reload complete")
        except Exception as e:
            logger.warning("[skill] Hot-reload failed: %s", e)

    # ── 便捷方法 ─────────────────────────────────────────

    def add_class(self, spec: ClassSpec, message: str = "", author: str = "skill") -> CommitResult:
        """添加单个类并立即提交"""
        return self.load().stage(OntologySpec(
            classes=[spec], message=message or f"Add class {spec.uri}", author=author,
        )).commit()

    def add_relation(self, spec: RelationSpec, message: str = "", author: str = "skill") -> CommitResult:
        """添加单条关系并立即提交"""
        return self.load().stage(OntologySpec(
            relations=[spec], message=message or f"Add relation {spec.uri}", author=author,
        )).commit()

    def add_value_mapping(self, spec: ValueMappingSpec, message: str = "", author: str = "skill") -> CommitResult:
        """添加单条值映射并立即提交"""
        return self.load().stage(OntologySpec(
            value_mappings=[spec], message=message or f"Add value {spec.domain}.{spec.semantic_value}", author=author,
        )).commit()

    def build_from_spec(self, spec: OntologySpec) -> CommitResult:
        """从完整 spec 一次性构建"""
        return self.load().stage(spec).commit()

    def remove_items(
        self,
        removals: List[RemoveSpec],
        message: str = "",
        author: str = "skill",
        incremental: bool = True,
    ) -> CommitResult:
        """删除一批本体条目并立即提交（默认使用增量写，保留手工注释）"""
        names = ", ".join(r.uri for r in removals)
        return self.load().stage(OntologySpec(
            removals=removals,
            message=message or f"Remove {len(removals)} item(s): {names}",
            author=author,
        )).commit(incremental=incremental)

    # ── 查询辅助（当前状态诊断） ─────────────────────────

    def diagnose(self) -> Dict[str, Any]:
        """诊断当前本体 + mapping 的健康状况"""
        self._ensure_loaded()

        ttl_classes = self._existing_class_uris()
        ttl_rels = self._existing_relation_uris()
        ttl_dps = self._existing_dataprop_uris()
        map_classes = self._existing_object_mapping_classes()
        map_rels = self._existing_relation_mapping_uris()

        # 覆盖度
        unmapped_classes = ttl_classes - map_classes
        orphan_mappings = map_classes - ttl_classes
        unmapped_rels = ttl_rels - map_rels
        orphan_rel_mappings = map_rels - ttl_rels

        return {
            "ttl_classes": len(ttl_classes),
            "ttl_relations": len(ttl_rels),
            "ttl_data_properties": len(ttl_dps),
            "mapping_object_classes": len(map_classes),
            "mapping_relations": len(map_rels),
            "unmapped_ttl_classes": sorted(unmapped_classes),
            "orphan_mapping_classes": sorted(orphan_mappings),
            "unmapped_ttl_relations": sorted(unmapped_rels),
            "orphan_mapping_relations": sorted(orphan_rel_mappings),
            "coverage": {
                "class_coverage": f"{len(map_classes & ttl_classes)}/{len(ttl_classes)}"
                if ttl_classes else "0/0",
                "relation_coverage": f"{len(map_rels & ttl_rels)}/{len(ttl_rels)}"
                if ttl_rels else "0/0",
            },
        }


# ═════════════════════════════════════════════════════════════════════
# 模块级便捷函数
# ═════════════════════════════════════════════════════════════════════

def get_skill() -> OntologyBuilderSkill:
    """获取新的 skill 实例（未加载状态）"""
    return OntologyBuilderSkill()


def build_from_dict(data: Dict[str, Any], mapping_file: Optional[Path] = None) -> CommitResult:
    """
    从 JSON 字典构建本体。

    支持的顶层键:
      classes, relations, data_properties, value_mappings, message, author

    这是给 API 路由和 CLI 调用的主入口。
    """
    spec = _parse_spec_dict(data)
    return OntologyBuilderSkill(mapping_file=mapping_file).build_from_spec(spec)


def preview_from_dict(data: Dict[str, Any], mapping_file: Optional[Path] = None) -> PreviewResult:
    """从 JSON 字典返回变更预览（不写文件）"""
    spec = _parse_spec_dict(data)
    skill = OntologyBuilderSkill(mapping_file=mapping_file).load()
    skill.stage(spec)
    return skill.preview()


def diagnose_ontology(mapping_file: Optional[Path] = None) -> Dict[str, Any]:
    """诊断当前本体健康状况"""
    return OntologyBuilderSkill(mapping_file=mapping_file).load().diagnose()


def _parse_spec_dict(data: Dict[str, Any]) -> OntologySpec:
    """将 JSON 字典解析为 OntologySpec"""
    classes = [
        ClassSpec(
            uri=c["uri"],
            label=c.get("label", ""),
            comment=c.get("comment", ""),
            parent_uri=c.get("parent_uri", ""),
            physical_table=c.get("physical_table"),
            primary_key=c.get("primary_key"),
            label_cn=c.get("label_cn", ""),
            display_column=c.get("display_column"),
            key_columns=c.get("key_columns", []),
            properties=c.get("properties", {}),
            property_constraints=c.get("property_constraints", {}),
            virtual=c.get("virtual", False),
            virtual_kind=c.get("virtual_kind"),
            filter_condition=c.get("filter_condition"),
            note=c.get("note"),
        )
        for c in data.get("classes", [])
    ]

    relations = [
        RelationSpec(
            uri=r["uri"],
            label=r.get("label", ""),
            comment=r.get("comment", ""),
            domain_uri=r.get("domain_uri", ""),
            range_uri=r.get("range_uri", ""),
            strategy=r.get("strategy", "ForeignKey"),
            description=r.get("description", ""),
            join_logic=r.get("join_logic", {}),
            per_record_type_join=r.get("per_record_type_join", {}),
            applicable_intents=r.get("applicable_intents", []),
            forbidden_intents=r.get("forbidden_intents", []),
            applicable_record_types=r.get("applicable_record_types", []),
            note=r.get("note"),
        )
        for r in data.get("relations", [])
    ]

    data_properties = [
        DataPropertySpec(
            uri=dp["uri"],
            label=dp.get("label", ""),
            comment=dp.get("comment", ""),
            domain_uris=dp.get("domain_uris", []),
            range_type=dp.get("range_type", "xsd:string"),
            applicable_record_types=dp.get("applicable_record_types", []),
            physical_mapping_path=dp.get("physical_mapping_path", ""),
        )
        for dp in data.get("data_properties", [])
    ]

    value_mappings = [
        ValueMappingSpec(
            domain=vm["domain"],
            semantic_value=vm["semantic_value"],
            description=vm.get("description", ""),
            physical_values=vm.get("physical_values"),
            physical_condition=vm.get("physical_condition"),
            applies_to_table=vm.get("applies_to_table"),
            applies_to_column=vm.get("applies_to_column"),
            is_terminal=vm.get("is_terminal", False),
            nl_triggers=vm.get("nl_triggers", []),
            note=vm.get("note"),
        )
        for vm in data.get("value_mappings", [])
    ]

    return OntologySpec(
        classes=classes,
        relations=relations,
        data_properties=data_properties,
        value_mappings=value_mappings,
        removals=[
            RemoveSpec(
                uri=rm["uri"],
                kind=rm["kind"],
                reason=rm.get("reason", ""),
                remove_mapping=rm.get("remove_mapping", True),
            )
            for rm in data.get("removals", [])
        ],
        message=data.get("message", ""),
        author=data.get("author", "ontology_skill"),
    )
