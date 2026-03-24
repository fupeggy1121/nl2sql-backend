"""
OWL TTL 与 relation_mappings 一致性校验器

职责：
  - 启动时解析 OWL TTL（rdflib），提取所有 ObjectProperty 的 domain/range
  - 与 MappingDictionary 中每条 RelationMapping 的 domain_class/range_class 对比
  - 不一致时抛出 OntologyMismatchError（或仅 warn，由 strict 参数决定）

OWL TTL 是语义契约，relation_mappings 是物理实现，
本模块确保两者在每次部署前保持同步。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Union

from rdflib import Graph as RDFGraph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from .config import SEMI_NS

if TYPE_CHECKING:
    from .mapping import MappingDictionary

logger = logging.getLogger(__name__)

SEMI = Namespace(SEMI_NS)


class OntologyMismatchError(RuntimeError):
    """relation_mappings 中的 domain_class/range_class 与 OWL TTL 不一致"""
    pass


def _short(uri: URIRef, ns: str = SEMI_NS) -> str:
    s = str(uri)
    return ("semi:" + s[len(ns):]) if s.startswith(ns) else s


def _resolve_domain_range(rdf_graph: RDFGraph, prop_uri: URIRef, pred: URIRef) -> List[str]:
    """
    解析 domain/range，处理 owl:unionOf。
    返回 semi:XXX 格式的短名列表（通常只有 1 个，unionOf 时多个）。
    """
    results: List[str] = []
    for _, _, obj in rdf_graph.triples((prop_uri, pred, None)):
        if isinstance(obj, URIRef):
            results.append(_short(obj))
        else:
            # blank node — 解析 owl:unionOf → rdf:List
            for _, _, union_list in rdf_graph.triples((obj, OWL.unionOf, None)):
                node = union_list
                while node and str(node) != str(RDF.nil):
                    first = rdf_graph.value(node, RDF.first)
                    if first:
                        results.append(_short(first))
                    node = rdf_graph.value(node, RDF.rest)
    return results


def _parse_ttl_object_properties(
    ttl_path: str,
) -> tuple:  # (Dict[str, Dict[str, List[str]]], RDFGraph)
    """
    解析 TTL，返回 (props, graph)。
      props: {
        "semi:belongsToLot": {
            "domain": ["semi:Wafer"],
            "range":  ["semi:ProductionLot"]
        },
        ...
      }
    range 可能为空列表（modifiesStateVector）或多元素列表（unionOf）。
    graph: 已解析的 RDFGraph，供 _build_class_ancestors 复用。
    """
    g = RDFGraph()
    g.parse(ttl_path, format="turtle")
    props: Dict[str, Dict[str, List[str]]] = {}
    for prop_uri in g.subjects(RDF.type, OWL.ObjectProperty):
        short_name = _short(prop_uri)
        props[short_name] = {
            "domain": _resolve_domain_range(g, prop_uri, RDFS.domain),
            "range":  _resolve_domain_range(g, prop_uri, RDFS.range),
        }
    return props, g


def _build_class_ancestors(rdf_graph: RDFGraph) -> Dict[str, Set[str]]:
    """
    解析 rdfs:subClassOf，计算传递性祖先集。
    返回 {short_class_name: set_of_all_ancestor_short_names}。
    例：semi:CheckInEventRecord → {semi:ProductionEventRecord, semi:Action, ...}
    """
    direct_parents: Dict[str, List[str]] = {}
    for subclass, _, superclass in rdf_graph.triples((None, RDFS.subClassOf, None)):
        if isinstance(subclass, URIRef) and isinstance(superclass, URIRef):
            sub, sup = _short(subclass), _short(superclass)
            direct_parents.setdefault(sub, []).append(sup)

    memo: Dict[str, Set[str]] = {}

    def _get_ancestors(cls: str) -> Set[str]:
        if cls in memo:
            return memo[cls]
        parents: Set[str] = set(direct_parents.get(cls, []))
        all_anc: Set[str] = set(parents)
        for p in parents:
            all_anc |= _get_ancestors(p)
        memo[cls] = all_anc
        return all_anc

    for cls in list(direct_parents):
        _get_ancestors(cls)

    return memo


def validate_relation_mappings(
    ttl_path: str,
    mapping: "MappingDictionary",
    strict: bool = True,
) -> List[str]:
    """
    将 relation_mappings 中的 domain_class/range_class 与 OWL TTL 对比。

    Parameters
    ----------
    ttl_path : str
        OWL TTL 文件路径（semi-cim-ontology.ttl）
    mapping : MappingDictionary
        已加载的 MappingDictionary 实例
    strict : bool
        True  → 发现不一致时抛出 OntologyMismatchError
        False → 仅记录 WARNING，返回问题列表

    Returns
    -------
    List[str]
        校验问题描述列表（strict=False 时使用）；strict=True 且有问题时抛异常
    """
    ttl_props, ttl_graph = _parse_ttl_object_properties(ttl_path)
    class_ancestors = _build_class_ancestors(ttl_graph)
    issues: List[str] = []

    all_rels = dict(mapping._relation_map)
    # 递归关系也要校验
    for lr, rec in mapping._recursive_map.items():
        all_rels.setdefault(lr, rec)  # type: ignore[arg-type]

    for logic_rel, rm in all_rels.items():
        ttl_info = ttl_props.get(logic_rel)

        # ── 1. OWL TTL 中是否存在该 ObjectProperty ─────────────────────────
        if ttl_info is None:
            msg = f"[MISSING_IN_TTL] {logic_rel} 在 OWL TTL 中未定义为 ObjectProperty"
            issues.append(msg)
            logger.warning(msg)
            continue

        # ── 2. domain_class 比对 ───────────────────────────────────────────
        mapping_domain: Optional[str] = getattr(rm, "domain_class", None)
        ttl_domain = ttl_info["domain"]  # List[str]

        if mapping_domain is None and ttl_domain:
            msg = (
                f"[DOMAIN_MISSING] {logic_rel}: mapping 中 domain_class=None"
                f", TTL domain={ttl_domain}"
            )
            issues.append(msg)
            logger.warning(msg)
        elif mapping_domain and ttl_domain and mapping_domain not in ttl_domain:
            # Allow if mapping_domain is an OWL superclass of every class in TTL domain
            # (mapping uses abstract parent; TTL declares precise subclass union)
            is_superclass = all(
                mapping_domain in class_ancestors.get(ttl_cls, set())
                for ttl_cls in ttl_domain
            )
            if is_superclass:
                logger.debug(
                    f"[DOMAIN_SUPERCLASS_OK] {logic_rel}: "
                    f"mapping.domain_class={mapping_domain!r} is OWL superclass of "
                    f"TTL domain={ttl_domain}"
                )
            else:
                msg = (
                    f"[DOMAIN_MISMATCH] {logic_rel}: "
                    f"mapping.domain_class={mapping_domain!r}"
                    f" vs TTL domain={ttl_domain}"
                )
                issues.append(msg)
                logger.warning(msg)

        # ── 3. range_class 比对 ────────────────────────────────────────────
        mapping_range_raw: Optional[Union[str, List[str]]] = getattr(rm, "range_class", None)
        ttl_range = ttl_info["range"]  # List[str]

        if mapping_range_raw is None:
            if ttl_range:
                # modifiesStateVector 等故意留空可豁免
                msg = (
                    f"[RANGE_MISSING] {logic_rel}: mapping 中 range_class=None"
                    f", TTL range={ttl_range}"
                )
                issues.append(msg)
                logger.warning(msg)
        else:
            # 统一为列表比较
            mapping_range: List[str] = (
                mapping_range_raw if isinstance(mapping_range_raw, list) else [mapping_range_raw]
            )
            if ttl_range and set(mapping_range) != set(ttl_range):
                msg = (
                    f"[RANGE_MISMATCH] {logic_rel}: "
                    f"mapping.range_class={mapping_range}"
                    f" vs TTL range={ttl_range}"
                )
                issues.append(msg)
                logger.warning(msg)

    if issues and strict:
        raise OntologyMismatchError(
            f"OWL TTL 与 relation_mappings 存在 {len(issues)} 处不一致，"
            "请同步更新 mapping_prod.json 或 semi-cim-ontology.ttl：\n"
            + "\n".join(f"  {i}" for i in issues)
        )

    if not issues:
        logger.info(
            f"OntologyValidator: {len(all_rels)} 条 relation_mappings 全部通过 TTL 校验 ✅"
        )

    return issues
