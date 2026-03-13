"""
本体语义 API — 血缘可视化 + 语义解析 + TTL 版本管理

提供：
  GET  /api/v1/ontology/summary   — 本体 & 映射统计概览
  GET  /api/v1/ontology/classes   — 列出所有映射类
  GET  /api/v1/ontology/lineage   — 两类之间的血缘路径 (本体跳 + 物理 JOIN)
  POST /api/v1/ontology/resolve   — 自然语言 → SemanticContext
  GET  /api/v1/ontology/recursive — 获取递归 CTE SQL
  GET  /api/v1/ontology/values    — 列出所有值域
  POST /api/v1/ontology/reload    — 热重载 TTL/mapping JSON（无需重启）
  GET  /api/v1/ontology/ttl       — 获取当前 TTL 文件内容
  POST /api/v1/ontology/ttl/upload — 上传新 TTL 文件（自带版本管理）
  GET  /api/v1/ontology/ttl/versions — 版本历史列表
  GET  /api/v1/ontology/ttl/versions/{version} — 获取历史版本 TTL 内容
  POST /api/v1/ontology/ttl/rollback/{version} — 回滚到指定版本
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.ontology.context_builder import SemanticContextBuilder, build_semantic_context
from app.ontology.loader import get_ontology, load_ontology
from app.ontology.mapping import get_mapping, load_mapping
from app.ontology.version_manager import (
    get_current_ttl,
    list_versions,
    get_version_content,
    get_version_detail,
    save_new_version,
    rollback_to_version,
    diff_versions,
)

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


@router.get("/data_properties")
async def list_data_properties():
    """列出所有 owl:DatatypeProperty"""
    ontology = get_ontology()
    result = []
    for uri, prop in ontology.data_properties.items():
        result.append({
            "uri": uri,
            "label": prop.label or uri.replace("semi:", ""),
            "comment": prop.comment or "",
            "range_type": prop.range_type or "xsd:string",
            "domain_uris": list(prop.domain_uris) if prop.domain_uris else [],
        })
    # 按 uri 排序，方便前端下拉展示
    result.sort(key=lambda x: x["uri"])
    return result


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


@router.post("/reload")
async def reload_ontology_and_mapping() -> Dict[str, Any]:
    """
    热重载 TTL 本体 + mapping JSON，无需重启服务。

    从磁盘重新读取文件，刷新内存缓存，返回最新统计摘要。
    """
    try:
        ontology = load_ontology(force_reload=True)
        mapping = load_mapping(force_reload=True)
        logger.info("Hot-reload complete: ontology=%s, mapping=%s",
                     ontology.summary(), mapping.summary())
        return {
            "success": True,
            "message": "TTL 本体和 mapping JSON 已重新加载",
            "ontology": ontology.summary(),
            "mapping": mapping.summary(),
        }
    except Exception as e:
        logger.error("Hot-reload failed: %s", e)
        raise HTTPException(500, f"重载失败: {e}")


@router.post("/synonyms/reload")
async def reload_synonyms_from_supabase() -> Dict[str, Any]:
    """
    热重载同义词：从 Supabase class_synonyms 表更新内存字典，无需重启服务。

    前端同义词管理页面保存新条目后，调用此接口即可立即让 NL2SQL
    管道识别新增的同义词（_supabase_synonym_overlay 覆盖静态字典）。
    """
    from app.ontology.context_builder import reload_synonyms_from_db
    count = reload_synonyms_from_db()
    return {
        "success": True,
        "loaded": count,
        "message": f"已从 Supabase 加载 {count} 条活跃同义词到管道字典",
    }


@router.get("/graph")
async def get_graph_data() -> Dict[str, Any]:
    """
    返回 D3 力导向图所需的 nodes + links JSON 数据。

    nodes: [{ id, label, comment, type, group }]
      type: "class" | "dataProperty"
      group: 用于颜色分组（首字母模块名或所属域）

    links: [{ source, target, label, type }]
      type: "objectProperty" | "dataPropertyEdge" | "subClassOf"
    """
    ontology = get_ontology()
    nodes = []
    links = []
    node_ids = set()

    # ── 类节点 ──
    for uri, cls in ontology.classes.items():
        # 分组: 取类名首字母作为简单模块分组
        short = uri.replace("semi:", "")
        group = short[0].upper() if short else "?"
        nodes.append({
            "id": uri,
            "label": cls.label or short,
            "comment": cls.comment or "",
            "type": "class",
            "group": group,
        })
        node_ids.add(uri)

    # ── subClassOf 继承边 ──
    for uri, cls in ontology.classes.items():
        if cls.parent_uri and cls.parent_uri in ontology.classes:
            links.append({
                "source": uri,
                "target": cls.parent_uri,
                "label": "subClassOf",
                "uri": "rdfs:subClassOf",
                "type": "subClassOf",
            })

    # ── 对象属性 (关系) → links ──
    for uri, rel in ontology.relations.items():
        if rel.domain_uri and rel.range_uri:
            links.append({
                "source": rel.domain_uri,
                "target": rel.range_uri,
                "label": rel.label or uri.replace("semi:", ""),
                "uri": uri,
                "type": "objectProperty",
            })

    # ── 数据属性 → 小节点 + edge ──
    for uri, prop in ontology.data_properties.items():
        short = uri.replace("semi:", "")
        prop_node_id = f"dp:{uri}"
        nodes.append({
            "id": prop_node_id,
            "label": prop.label or short,
            "comment": prop.comment or "",
            "type": "dataProperty",
            "group": "DP",
            "rangeType": prop.range_type,
        })
        node_ids.add(prop_node_id)
        # 从每个 domain 类 → 数据属性节点
        for d_uri in prop.domain_uris:
            if d_uri in ontology.classes:
                links.append({
                    "source": d_uri,
                    "target": prop_node_id,
                    "label": prop.label or short,
                    "uri": uri,
                    "type": "dataPropertyEdge",
                })

    return {
        "nodes": nodes,
        "links": links,
        "stats": ontology.summary(),
    }


# ── TTL 文件版本管理端点 ──


@router.get("/ttl")
async def get_ttl_content():
    """获取当前 TTL 文件内容（text/turtle）"""
    try:
        content = get_current_ttl()
        return PlainTextResponse(content, media_type="text/turtle")
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/ttl/upload")
async def upload_ttl(
    file: UploadFile = File(..., description="TTL 文件"),
    message: str = Form("", description="版本说明"),
    author: str = Form("web-ui", description="上传者"),
) -> Dict[str, Any]:
    """
    上传新 TTL 文件。

    自动备份当前版本 → 写入新文件 → 触发热重载。
    """
    if not file.filename.endswith((".ttl", ".turtle")):
        raise HTTPException(400, "仅支持 .ttl / .turtle 文件")

    content = await file.read()
    try:
        ttl_text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "文件编码必须为 UTF-8")

    # 基本校验：至少包含 @prefix 或 owl:Ontology
    if "@prefix" not in ttl_text and "owl:Ontology" not in ttl_text:
        raise HTTPException(400, "文件不像是有效的 Turtle 本体文件")

    try:
        entry = save_new_version(ttl_text, message=message, author=author)
    except Exception as e:
        logger.error("TTL upload failed: %s", e)
        raise HTTPException(500, f"保存失败: {e}")

    return {
        "success": True,
        "message": f"已保存为版本 {entry['version']}，热重载完成",
        "version": entry,
    }


@router.get("/ttl/versions")
async def get_ttl_versions() -> Dict[str, Any]:
    """获取版本历史列表（最新在前）"""
    versions = list_versions()
    return {
        "total": len(versions),
        "versions": versions,
    }


@router.get("/ttl/versions/{version}")
async def get_ttl_version_content(version: int):
    """获取指定版本的 TTL 内容"""
    content = get_version_content(version)
    if content is None:
        raise HTTPException(404, f"版本 {version} 不存在")
    detail = get_version_detail(version)
    return {
        "version": detail,
        "content": content,
    }


@router.post("/ttl/rollback/{version}")
async def rollback_ttl(version: int) -> Dict[str, Any]:
    """回滚到指定版本（创建新版本记录，恢复历史内容）"""
    detail = get_version_detail(version)
    if detail is None:
        raise HTTPException(404, f"版本 {version} 不存在")

    try:
        entry = rollback_to_version(version)
    except Exception as e:
        logger.error("Rollback to version %d failed: %s", version, e)
        raise HTTPException(500, f"回滚失败: {e}")

    return {
        "success": True,
        "message": f"已回滚到版本 {version}，生成新版本 {entry['version']}",
        "version": entry,
    }


@router.get("/ttl/diff")
async def diff_ttl_versions(
    v1: int = Query(..., description="版本1"),
    v2: int = Query(..., description="版本2"),
) -> Dict[str, Any]:
    """对比两个版本的差异统计"""
    try:
        return diff_versions(v1, v2)
    except ValueError as e:
        raise HTTPException(404, str(e))


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
