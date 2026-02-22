"""
本体 TTL 文件加载器

使用 rdflib 解析 OWL/TTL 文件，构建 OntologyGraph 内存图。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from rdflib import Graph as RDFGraph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from .config import DEFAULT_TTL_PATH, SEMI_NS, CACHE_ONTOLOGY
from .model import OntologyClass, OntologyProperty, OntologyRelation, OntologyGraph

logger = logging.getLogger(__name__)

SEMI = Namespace(SEMI_NS)

# 模块级缓存
_cached_graph: Optional[OntologyGraph] = None


def _short_uri(uri: URIRef, ns_prefix: str = SEMI_NS) -> str:
    """将完整 URI 缩写为 semi:XXX 格式"""
    s = str(uri)
    if s.startswith(ns_prefix):
        return "semi:" + s[len(ns_prefix):]
    return s


def _get_label(rdf_graph: RDFGraph, subject: URIRef) -> str:
    """提取 rdfs:label"""
    for _, _, o in rdf_graph.triples((subject, RDFS.label, None)):
        return str(o)
    return ""


def _get_comment(rdf_graph: RDFGraph, subject: URIRef) -> str:
    """提取 rdfs:comment"""
    for _, _, o in rdf_graph.triples((subject, RDFS.comment, None)):
        return str(o)
    return ""


def _resolve_domain_range(rdf_graph: RDFGraph, prop_uri: URIRef, pred: URIRef) -> list[str]:
    """
    解析 domain / range，处理 owl:unionOf 的情况。
    返回 URI 短名列表。
    """
    results = []
    for _, _, obj in rdf_graph.triples((prop_uri, pred, None)):
        # 可能是直接 URI，也可能是 blank node (unionOf)
        if isinstance(obj, URIRef):
            results.append(_short_uri(obj))
        else:
            # blank node — 尝试解析 owl:unionOf → rdf:List
            for _, _, union_list in rdf_graph.triples((obj, OWL.unionOf, None)):
                for item in rdf_graph.items(union_list):
                    if isinstance(item, URIRef):
                        results.append(_short_uri(item))
    return results


def load_ontology(ttl_path: Optional[Path] = None, force_reload: bool = False) -> OntologyGraph:
    """
    加载 TTL 本体文件，返回 OntologyGraph。

    Args:
        ttl_path: TTL 文件路径，默认使用 config 中的路径
        force_reload: 强制重新加载（忽略缓存）

    Returns:
        OntologyGraph 实例
    """
    global _cached_graph

    if _cached_graph is not None and CACHE_ONTOLOGY and not force_reload:
        return _cached_graph

    path = ttl_path or DEFAULT_TTL_PATH
    if not path.exists():
        raise FileNotFoundError(f"TTL ontology file not found: {path}")

    logger.info(f"Loading ontology from {path}")
    rdf = RDFGraph()
    rdf.parse(str(path), format="turtle")

    onto = OntologyGraph()

    # ── 1. 提取所有 owl:Class ──
    for s, _, _ in rdf.triples((None, RDF.type, OWL.Class)):
        if isinstance(s, URIRef):
            cls = OntologyClass(
                uri=_short_uri(s),
                label=_get_label(rdf, s),
                comment=_get_comment(rdf, s),
            )
            onto.add_class(cls)

    # ── 2. 提取所有 owl:ObjectProperty → OntologyRelation ──
    for s, _, _ in rdf.triples((None, RDF.type, OWL.ObjectProperty)):
        if not isinstance(s, URIRef):
            continue

        domains = _resolve_domain_range(rdf, s, RDFS.domain)
        ranges = _resolve_domain_range(rdf, s, RDFS.range)

        # 对于 unionOf domain/range，展开为多条关系
        domain_list = domains if domains else [""]
        range_list = ranges if ranges else [""]

        for d in domain_list:
            for r in range_list:
                rel = OntologyRelation(
                    uri=_short_uri(s),
                    label=_get_label(rdf, s),
                    comment=_get_comment(rdf, s),
                    domain_uri=d,
                    range_uri=r,
                )
                onto.add_relation(rel)

    # ── 3. 提取所有 owl:DatatypeProperty ──
    for s, _, _ in rdf.triples((None, RDF.type, OWL.DatatypeProperty)):
        if not isinstance(s, URIRef):
            continue

        domains = _resolve_domain_range(rdf, s, RDFS.domain)
        ranges = _resolve_domain_range(rdf, s, RDFS.range)

        prop = OntologyProperty(
            uri=_short_uri(s),
            label=_get_label(rdf, s),
            comment=_get_comment(rdf, s),
            domain_uris=domains,
            range_type=ranges[0] if ranges else "",
        )
        onto.add_data_property(prop)

    # ── 4. 提取 AnnotationProperty (isMappedToTable 等元数据) ──
    for s, _, _ in rdf.triples((None, RDF.type, OWL.AnnotationProperty)):
        if isinstance(s, URIRef):
            prop = OntologyProperty(
                uri=_short_uri(s),
                label=_get_label(rdf, s),
                comment=_get_comment(rdf, s),
            )
            onto.add_data_property(prop)

    if CACHE_ONTOLOGY:
        _cached_graph = onto

    logger.info(f"Ontology loaded: {onto}")
    return onto


def get_ontology() -> OntologyGraph:
    """获取本体图（带缓存的快捷方式）"""
    return load_ontology()
