"""
本体语义 API — 血缘可视化 + 语义解析

提供：
  GET  /api/v1/ontology/summary   — 本体 & 映射统计概览
  GET  /api/v1/ontology/classes   — 列出所有映射类
  GET  /api/v1/ontology/lineage   — 两类之间的血缘路径 (本体跳 + 物理 JOIN)
  POST /api/v1/ontology/resolve   — 自然语言 → SemanticContext
  GET  /api/v1/ontology/recursive — 获取递归 CTE SQL
  GET  /api/v1/ontology/values    — 列出所有值域
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.ontology.context_builder import SemanticContextBuilder, build_semantic_context
from app.ontology.loader import get_ontology
from app.ontology.mapping import get_mapping

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ontology", tags=["Ontology"])


# ── 请求/响应模型 ──


class ResolveRequest(BaseModel):
    query: str = Field(..., description="自然语言查询")


class LineageHop(BaseModel):
    from_class: str
    relation: str
    to_class: str
    is_reverse: bool = False


class LineageJoin(BaseModel):
    logic_relation: str
    strategy: str
    conditions: List[Dict[str, str]]
    bridge_table: Optional[str] = None


class LineageResponse(BaseModel):
    source: str
    target: str
    ontology_path: List[LineageHop]
    physical_joins: List[LineageJoin]
    all_paths: List[List[LineageHop]]


class ClassInfo(BaseModel):
    logic_class: str
    label_cn: str
    physical_table: Optional[str]
    primary_key: Optional[str]
    key_columns: List[str]
    virtual: bool


# ── 端点 ──


@router.get("/summary")
async def ontology_summary() -> Dict[str, Any]:
    """本体 & 映射统计概览"""
    ontology = get_ontology()
    mapping = get_mapping()
    return {
        "ontology": ontology.summary(),
        "mapping": mapping.summary(),
    }


@router.get("/classes", response_model=List[ClassInfo])
async def list_classes():
    """列出所有已映射的本体类"""
    mapping = get_mapping()
    result = []
    for pt in mapping.list_all_tables():
        result.append(ClassInfo(
            logic_class=pt.logic_class,
            label_cn=pt.label_cn,
            physical_table=pt.table_name,
            primary_key=pt.primary_key,
            key_columns=pt.key_columns,
            virtual=pt.virtual,
        ))
    return result


@router.get("/lineage", response_model=LineageResponse)
async def get_lineage(
    source: str = Query(..., description="源本体类 (如 Wafer 或 semi:Wafer)"),
    target: str = Query(..., description="目标本体类 (如 ProductionOrder 或 semi:ProductionOrder)"),
):
    """
    查询两个本体类之间的血缘路径。

    返回:
      - ontology_path: 本体层面的最短路径 (类→关系→类 跳)
      - physical_joins: 每一跳对应的物理 JOIN 条件链
      - all_paths: 所有可达路径 (按长度排序)
    """
    ontology = get_ontology()
    mapping = get_mapping()

    # 标准化 URI
    source_uri = _normalize_uri(source)
    target_uri = _normalize_uri(target)

    if source_uri not in ontology.classes:
        raise HTTPException(404, f"Source class not found: {source_uri}")
    if target_uri not in ontology.classes:
        raise HTTPException(404, f"Target class not found: {target_uri}")

    # BFS 最短路径
    path = ontology.find_path(source_uri, target_uri)
    if path is None:
        raise HTTPException(404, f"No path found between {source_uri} and {target_uri}")

    ontology_hops = _path_to_hops(path)

    # 所有路径
    all_paths_raw = ontology.find_all_paths(source_uri, target_uri, max_depth=5)
    all_paths = [_path_to_hops(p) for p in all_paths_raw]

    # 物理 JOIN 翻译
    physical_joins = []
    for from_cls, rel_uri, to_cls in path:
        actual_rel = rel_uri.lstrip("^")
        rm = mapping.get_join_path(actual_rel)
        if rm:
            physical_joins.append(LineageJoin(
                logic_relation=rm.logic_relation,
                strategy=rm.strategy,
                conditions=[
                    {"from": f"{c.from_table}.{c.from_key}",
                     "to": f"{c.to_table}.{c.to_key}"}
                    for c in rm.join_conditions
                ],
                bridge_table=rm.bridge_table,
            ))

    return LineageResponse(
        source=source_uri,
        target=target_uri,
        ontology_path=ontology_hops,
        physical_joins=physical_joins,
        all_paths=all_paths,
    )


@router.post("/resolve")
async def resolve_query(req: ResolveRequest) -> Dict[str, Any]:
    """
    自然语言 → 语义上下文解析。

    返回 SemanticContext 完整结构（匹配类、JOIN、过滤、递归CTE、业务规则）。
    """
    ctx = build_semantic_context(req.query)
    return {
        "success": True,
        "context": ctx.to_dict(),
    }


@router.get("/recursive")
async def get_recursive_cte(
    relation: str = Query(
        "semi:hasParentLot",
        description="递归关系 URI",
    ),
    anchor: Optional[str] = Query(
        None,
        description="锚定条件 (如 batch_code = 'B001')，为空则查全部根节点",
    ),
):
    """将递归关系编译为 WITH RECURSIVE CTE SQL"""
    mapping = get_mapping()
    relation_uri = _normalize_uri(relation)

    rec = mapping.get_recursive_mapping(relation_uri)
    if rec is None:
        raise HTTPException(404, f"No recursive mapping for: {relation_uri}")

    cte_sql = mapping.compile_recursive_cte(
        relation=relation_uri,
        anchor_condition=anchor,
        include_depth=True,
    )

    return {
        "relation": relation_uri,
        "table": rec.table,
        "self_key": rec.self_key,
        "parent_key": rec.parent_key,
        "max_depth": rec.max_depth,
        "cte_sql": cte_sql,
    }


@router.get("/values")
async def list_value_domains() -> Dict[str, Any]:
    """列出所有语义值域及其映射"""
    mapping = get_mapping()
    result = {}
    for domain in mapping.list_value_domains():
        values = mapping.list_values_in_domain(domain)
        result[domain] = {
            k: {
                "description": v.description,
                "physical_condition": v.physical_condition,
                "physical_values": v.physical_values,
                "applies_to_table": v.applies_to_table,
                "applies_to_column": v.applies_to_column,
            }
            for k, v in values.items()
        }
    return {"domains_count": len(result), "domains": result}


# ── 工具函数 ──

def _normalize_uri(name: str) -> str:
    """标准化本体 URI: 'Wafer' → 'semi:Wafer', 'semi:Wafer' → 'semi:Wafer'"""
    if name.startswith("semi:"):
        return name
    return f"semi:{name}"


def _path_to_hops(path: List) -> List[LineageHop]:
    """将本体路径三元组列表转为 LineageHop 列表"""
    hops = []
    for from_cls, rel_uri, to_cls in path:
        is_reverse = rel_uri.startswith("^")
        actual_rel = rel_uri.lstrip("^")
        hops.append(LineageHop(
            from_class=from_cls,
            relation=actual_rel,
            to_class=to_cls,
            is_reverse=is_reverse,
        ))
    return hops
