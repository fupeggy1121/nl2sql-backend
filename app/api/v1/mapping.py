"""
映射字典管理 API — FastAPI Router

提供 object_mappings / relation_mappings / value_mappings / business_rules
的 CRUD 操作，以及变更日志查询和缓存重载。

端点路径：/api/mapping/...

所有写操作：
  1. 原子写入（.tmp + os.replace）
  2. 追加变更记录到 mapping_changelog.jsonl
  3. 强制重载映射缓存
"""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mapping", tags=["Mapping"])


# ══════════════════════════════════════════════════════════════════
# 路径解析 & 工具函数
# ══════════════════════════════════════════════════════════════════

def _get_mapping_path() -> Path:
    """委托 app.ontology.mapping 模块决定当前文件，保证与缓存逻辑完全一致。"""
    from app.ontology.mapping import _resolve_mapping_file
    return _resolve_mapping_file()


def _changelog_path() -> Path:
    return _get_mapping_path().parent / "mapping_changelog.jsonl"


def _load_raw() -> Dict[str, Any]:
    p = _get_mapping_path()
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def _save_raw(data: Dict[str, Any]) -> None:
    p = _get_mapping_path()
    tmp = Path(str(p) + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def _append_changelog(action: str, entry_type: str, key: str,
                      before: Any = None, after: Any = None) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": "api",
        "action": action,
        "entry_type": entry_type,
        "key": key,
        "before": before,
        "after": after,
    }
    cl = _changelog_path()
    with cl.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _reload_cache() -> None:
    try:
        from app.ontology.mapping import load_mapping
        load_mapping(force_reload=True)
    except Exception as exc:
        logger.warning("Cache reload failed: %s", exc)


def _decode_key(raw: str) -> str:
    return urllib.parse.unquote(raw)


def _om_as_dict(raw_om: Any) -> Dict[str, Any]:
    """
    将 mapping_prod.json 中的 object_mappings 规范化为
    { logic_class: {...rest} } 字典，兼容 list 和 dict 两种存储格式。
    """
    if isinstance(raw_om, list):
        result = {}
        for item in raw_om:
            if isinstance(item, dict) and "logic_class" in item:
                lc = item["logic_class"]
                result[lc] = {k: v for k, v in item.items() if k != "logic_class"}
        return result
    if isinstance(raw_om, dict):
        return raw_om
    return {}


def _om_save_back(data: Dict[str, Any], om_dict: Dict[str, Any]) -> None:
    """
    将 om_dict 写回 data["object_mappings"]，保留原始存储格式：
    - 原来是 list → 转回 list  
    - 原来是 dict → 保持 dict
    """
    original = data.get("object_mappings")
    if isinstance(original, list):
        data["object_mappings"] = [
            {"logic_class": lc, **props} for lc, props in om_dict.items()
        ]
    else:
        data["object_mappings"] = om_dict


# ══════════════════════════════════════════════════════════════════
# 请求/响应模型
# ══════════════════════════════════════════════════════════════════

class ObjectMappingIn(BaseModel):
    logic_class: str
    physical_table: Optional[str] = None
    primary_key: Optional[str] = "id"
    label_cn: str = ""
    display_column: Optional[str] = None
    filter_condition: Optional[str] = None  # 同表多类区分条件，e.g. "parent_id != 0"
    key_columns: List[str] = []
    properties: Dict[str, Any] = {}
    virtual: bool = False
    note: Optional[str] = None


class ObjectMappingUpdate(BaseModel):
    physical_table: Optional[str] = None
    primary_key: Optional[str] = None
    label_cn: Optional[str] = None
    display_column: Optional[str] = None
    filter_condition: Optional[str] = None  # 同表多类区分条件
    key_columns: Optional[List[str]] = None
    properties: Optional[Dict[str, Any]] = None
    virtual: Optional[bool] = None
    note: Optional[str] = None


class RelationMappingIn(BaseModel):
    logic_relation: str
    description: str = ""
    strategy: str = "ForeignKey"
    join_logic: Dict[str, Any] = {}
    confidence: Optional[str] = None


class RelationMappingUpdate(BaseModel):
    description: Optional[str] = None
    strategy: Optional[str] = None
    join_logic: Optional[Dict[str, Any]] = None
    confidence: Optional[str] = None


class ValueEntryIn(BaseModel):
    description: Optional[str] = None
    physical_condition: Optional[str] = None
    applies_to_table: Optional[str] = None
    applies_to_column: Optional[str] = None
    note: Optional[str] = None


class BusinessRuleIn(BaseModel):
    id: str
    name: str = ""
    description: str = ""
    trigger_keywords: List[str] = []
    physical_sql_template: str = ""
    involved_tables: List[str] = []
    warning_tables: List[str] = []
    semantic_pattern: Optional[str] = None


class BusinessRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_keywords: Optional[List[str]] = None
    physical_sql_template: Optional[str] = None
    involved_tables: Optional[List[str]] = None
    warning_tables: Optional[List[str]] = None
    semantic_pattern: Optional[str] = None


class MetricDefinitionIn(BaseModel):
    metric_id: str
    zh_names: List[str] = []
    anchor_table: str = ""
    formula: str = ""
    granularity: List[str] = []
    description: str = ""
    join_path: Optional[str] = None
    auto_filter: Optional[str] = None


class MetricDefinitionUpdate(BaseModel):
    zh_names: Optional[List[str]] = None
    anchor_table: Optional[str] = None
    formula: Optional[str] = None
    granularity: Optional[List[str]] = None
    description: Optional[str] = None
    join_path: Optional[str] = None
    auto_filter: Optional[str] = None


class SwitchModeIn(BaseModel):
    mode: str  # "prod" | "demo" | "auto" | "mysql" | "supabase"


# ══════════════════════════════════════════════════════════════════
# Summary & Reload
# ══════════════════════════════════════════════════════════════════

@router.get("/summary")
async def get_summary():
    data = _load_raw()
    om = data.get("object_mappings", {})
    rm = data.get("relation_mappings", [])
    vm = data.get("value_mappings", {})
    br = data.get("business_rules", [])
    md = data.get("metric_definitions", {})
    return {
        "data": {
            "mapping_file": str(_get_mapping_path()),
            "version": data.get("version", ""),
            "customer": data.get("customer", ""),
            "object_mappings": len(om) if isinstance(om, dict) else len(om),
            "relation_mappings": len(rm),
            "value_domains": len(vm),
            "business_rules": len(br),
            "metric_definitions": len(md),
        }
    }


@router.get("/mode")
async def get_mode():
    """返回当前映射模式及数据库连接模式的完整信息。"""
    from app.ontology.mapping import get_current_mode
    from app.services.db_mode import get_current_db_mode
    return {
        "data": {
            "mapping": get_current_mode(),
            "database": get_current_db_mode(),
        }
    }


@router.post("/switch")
async def switch_mode(body: SwitchModeIn):
    """同时切换映射模式和查询数据库目标。\n\nmode: \"prod\" | \"demo\" | \"auto\"（auto = 清除 override，回归 env/auto-detect）"""
    from app.ontology.mapping import set_mapping_mode, get_current_mode
    from app.services.db_mode import set_db_mode, get_current_db_mode
    try:
        new_file = set_mapping_mode(body.mode)
        db_info  = set_db_mode(body.mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    data = _load_raw()
    om = data.get("object_mappings", {})
    rm = data.get("relation_mappings", [])
    vm = data.get("value_mappings", {})
    br = data.get("business_rules", [])
    return {
        "message": f"Switched to {body.mode}",
        "data": {
            "mapping":  get_current_mode(),
            "database": get_current_db_mode(),
            "object_mappings":   len(om),
            "relation_mappings": len(rm),
            "value_domains":     len(vm),
            "business_rules":    len(br),
        }
    }


@router.post("/reload")
async def reload_cache():
    _reload_cache()
    data = _load_raw()
    om = data.get("object_mappings", {})
    rm = data.get("relation_mappings", [])
    vm = data.get("value_mappings", {})
    br = data.get("business_rules", [])
    md = data.get("metric_definitions", {})
    return {
        "message": "Cache reloaded",
        "data": {
            "summary": {
                "object_mappings": len(om),
                "relation_mappings": len(rm),
                "value_domains": len(vm),
                "business_rules": len(br),
                "metric_definitions": len(md),
            }
        }
    }


# ══════════════════════════════════════════════════════════════════
# Object Mappings
# ══════════════════════════════════════════════════════════════════

@router.get("/objects")
async def list_objects(
    q: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
):
    data = _load_raw()
    om = _om_as_dict(data.get("object_mappings", {}))

    items = []
    for logic_class, obj in om.items():
        entry = {"logic_class": logic_class, **obj}
        if q:
            q_l = q.lower()
            searchable = (
                logic_class.lower()
                + " " + (obj.get("physical_table") or "").lower()
                + " " + (obj.get("label_cn") or "").lower()
            )
            if q_l not in searchable:
                continue
        items.append(entry)

    total = len(items)
    start = (page - 1) * page_size
    return {"data": items[start: start + page_size], "total": total}


@router.get("/objects/{logic_class_raw:path}")
async def get_object(logic_class_raw: str):
    logic_class = _decode_key(logic_class_raw)
    data = _load_raw()
    om = _om_as_dict(data.get("object_mappings", {}))
    if logic_class not in om:
        raise HTTPException(status_code=404, detail=f"Not found: {logic_class}")
    return {"data": {"logic_class": logic_class, **om[logic_class]}}


@router.post("/objects", status_code=201)
async def create_object(body: ObjectMappingIn):
    data = _load_raw()
    om = _om_as_dict(data.get("object_mappings", {}))
    if body.logic_class in om:
        raise HTTPException(status_code=409, detail=f"Already exists: {body.logic_class}")
    entry = body.dict(exclude={"logic_class"})
    om[body.logic_class] = entry
    _om_save_back(data, om)
    _save_raw(data)
    _append_changelog("create", "object_mapping", body.logic_class, None, entry)
    _reload_cache()
    return {"data": {"logic_class": body.logic_class, **entry}}


@router.put("/objects/{logic_class_raw:path}")
async def update_object(logic_class_raw: str, body: ObjectMappingUpdate):
    logic_class = _decode_key(logic_class_raw)
    data = _load_raw()
    om = _om_as_dict(data.get("object_mappings", {}))
    if logic_class not in om:
        raise HTTPException(status_code=404, detail=f"Not found: {logic_class}")
    before = dict(om[logic_class])
    updates = {k: v for k, v in body.dict().items() if v is not None}
    om[logic_class].update(updates)
    _om_save_back(data, om)
    _save_raw(data)
    _append_changelog("update", "object_mapping", logic_class, before, om[logic_class])
    _reload_cache()
    return {"data": {"logic_class": logic_class, **om[logic_class]}}


@router.delete("/objects/{logic_class_raw:path}")
async def delete_object(logic_class_raw: str):
    logic_class = _decode_key(logic_class_raw)
    data = _load_raw()
    om = _om_as_dict(data.get("object_mappings", {}))
    if logic_class not in om:
        raise HTTPException(status_code=404, detail=f"Not found: {logic_class}")
    before = om.pop(logic_class)
    _om_save_back(data, om)
    _save_raw(data)
    _append_changelog("delete", "object_mapping", logic_class, before, None)
    _reload_cache()
    return {"message": f"Deleted: {logic_class}"}


# ══════════════════════════════════════════════════════════════════
# Relation Mappings
# ══════════════════════════════════════════════════════════════════

@router.get("/relations")
async def list_relations(
    q: str = Query(""),
    confidence: str = Query(""),
):
    data = _load_raw()
    rm: List[Dict] = data.get("relation_mappings", [])
    items = []
    for rel in rm:
        if q:
            q_l = q.lower()
            searchable = rel.get("logic_relation", "").lower() + " " + rel.get("description", "").lower()
            if q_l not in searchable:
                continue
        if confidence and rel.get("confidence") != confidence:
            continue
        items.append(rel)
    return {"data": items, "total": len(items)}


@router.post("/relations", status_code=201)
async def create_relation(body: RelationMappingIn):
    data = _load_raw()
    rm: List[Dict] = data.setdefault("relation_mappings", [])
    existing = [r["logic_relation"] for r in rm]
    if body.logic_relation in existing:
        raise HTTPException(status_code=409, detail=f"Already exists: {body.logic_relation}")
    entry = body.dict()
    rm.append(entry)
    _save_raw(data)
    _append_changelog("create", "relation_mapping", body.logic_relation, None, entry)
    _reload_cache()
    return {"data": entry}


@router.put("/relations/{relation_raw:path}")
async def update_relation(relation_raw: str, body: RelationMappingUpdate):
    logic_relation = _decode_key(relation_raw)
    data = _load_raw()
    rm: List[Dict] = data.get("relation_mappings", [])
    target = next((r for r in rm if r["logic_relation"] == logic_relation), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Not found: {logic_relation}")
    before = dict(target)
    updates = {k: v for k, v in body.dict().items() if v is not None}
    target.update(updates)
    _save_raw(data)
    _append_changelog("update", "relation_mapping", logic_relation, before, target)
    _reload_cache()
    return {"data": target}


@router.delete("/relations/{relation_raw:path}")
async def delete_relation(relation_raw: str):
    logic_relation = _decode_key(relation_raw)
    data = _load_raw()
    rm: List[Dict] = data.get("relation_mappings", [])
    target = next((r for r in rm if r["logic_relation"] == logic_relation), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Not found: {logic_relation}")
    rm.remove(target)
    _save_raw(data)
    _append_changelog("delete", "relation_mapping", logic_relation, target, None)
    _reload_cache()
    return {"message": f"Deleted: {logic_relation}"}


# ══════════════════════════════════════════════════════════════════
# Value Mappings
# ══════════════════════════════════════════════════════════════════

@router.get("/values")
async def list_value_domains():
    data = _load_raw()
    vm: Dict[str, List] = data.get("value_mappings", {})
    result = [{"domain": k, "value_count": len(v)} for k, v in vm.items()]
    return {"data": result}


@router.get("/values/{domain_raw:path}")
async def get_value_domain(domain_raw: str):
    domain = _decode_key(domain_raw)
    # domain may contain a second segment for semantic_value — handle separately
    # This route only handles domain-level GET
    data = _load_raw()
    vm: Dict[str, List] = data.get("value_mappings", {})
    if domain not in vm:
        raise HTTPException(status_code=404, detail=f"Domain not found: {domain}")
    return {"data": vm[domain]}


@router.put("/values/{domain}/{semantic_value}")
async def upsert_value(domain: str, semantic_value: str, body: ValueEntryIn):
    data = _load_raw()
    vm: Dict[str, List] = data.setdefault("value_mappings", {})
    domain_list: List[Dict] = vm.setdefault(domain, [])
    target = next((v for v in domain_list if v.get("semantic_value") == semantic_value), None)
    before = dict(target) if target else None
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if target:
        target.update(updates)
        after = target
    else:
        after = {"semantic_value": semantic_value, **updates}
        domain_list.append(after)
    _save_raw(data)
    _append_changelog("update" if before else "create", "value_mapping",
                      f"{domain}/{semantic_value}", before, after)
    _reload_cache()
    return {"data": after}


@router.delete("/values/{domain}/{semantic_value}")
async def delete_value(domain: str, semantic_value: str):
    data = _load_raw()
    vm: Dict[str, List] = data.get("value_mappings", {})
    domain_list: List[Dict] = vm.get(domain, [])
    target = next((v for v in domain_list if v.get("semantic_value") == semantic_value), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Not found: {domain}/{semantic_value}")
    domain_list.remove(target)
    _save_raw(data)
    _append_changelog("delete", "value_mapping", f"{domain}/{semantic_value}", target, None)
    _reload_cache()
    return {"message": f"Deleted: {domain}/{semantic_value}"}


# ══════════════════════════════════════════════════════════════════
# Business Rules
# ══════════════════════════════════════════════════════════════════

@router.get("/rules")
async def list_rules(q: str = Query("")):
    data = _load_raw()
    br: List[Dict] = data.get("business_rules", [])
    if q:
        q_l = q.lower()
        br = [r for r in br if
              q_l in r.get("id", "").lower()
              or q_l in r.get("name", "").lower()
              or any(q_l in kw.lower() for kw in r.get("trigger_keywords", []))]
    return {"data": br, "total": len(br)}


@router.post("/rules", status_code=201)
async def create_rule(body: BusinessRuleIn):
    data = _load_raw()
    br: List[Dict] = data.setdefault("business_rules", [])
    if any(r["id"] == body.id for r in br):
        raise HTTPException(status_code=409, detail=f"Rule already exists: {body.id}")
    entry = body.dict()
    br.append(entry)
    _save_raw(data)
    _append_changelog("create", "business_rule", body.id, None, entry)
    _reload_cache()
    return {"data": entry}


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, body: BusinessRuleUpdate):
    data = _load_raw()
    br: List[Dict] = data.get("business_rules", [])
    target = next((r for r in br if r["id"] == rule_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Rule not found: {rule_id}")
    before = dict(target)
    updates = {k: v for k, v in body.dict().items() if v is not None}
    target.update(updates)
    _save_raw(data)
    _append_changelog("update", "business_rule", rule_id, before, target)
    _reload_cache()
    return {"data": target}


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    data = _load_raw()
    br: List[Dict] = data.get("business_rules", [])
    target = next((r for r in br if r["id"] == rule_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Rule not found: {rule_id}")
    br.remove(target)
    _save_raw(data)
    _append_changelog("delete", "business_rule", rule_id, target, None)
    _reload_cache()
    return {"message": f"Deleted: {rule_id}"}


# ══════════════════════════════════════════════════════════════════
# Metric Definitions
# ══════════════════════════════════════════════════════════════════

@router.get("/metrics")
async def list_metrics(q: str = Query("")):
    """列出所有指标定义"""
    data = _load_raw()
    md: Dict[str, Any] = data.get("metric_definitions", {})
    items = []
    for metric_id, m in md.items():
        entry = {"metric_id": metric_id, **m}
        if q:
            q_l = q.lower()
            searchable = (
                metric_id.lower()
                + " " + (m.get("description") or "").lower()
                + " " + " ".join(m.get("zh_names", [])).lower()
            )
            if q_l not in searchable:
                continue
        items.append(entry)
    return {"data": items, "total": len(items)}


@router.post("/metrics", status_code=201)
async def create_metric(body: MetricDefinitionIn):
    """新增指标定义"""
    data = _load_raw()
    md: Dict[str, Any] = data.setdefault("metric_definitions", {})
    if body.metric_id in md:
        raise HTTPException(status_code=409, detail=f"Metric already exists: {body.metric_id}")
    entry = {k: v for k, v in body.dict().items() if k != "metric_id"}
    md[body.metric_id] = entry
    _save_raw(data)
    _append_changelog("create", "metric_definition", body.metric_id, None, entry)
    _reload_cache()
    return {"data": {"metric_id": body.metric_id, **entry}}


@router.put("/metrics/{metric_id}")
async def update_metric(metric_id: str, body: MetricDefinitionUpdate):
    """更新指标定义（部分更新）"""
    data = _load_raw()
    md: Dict[str, Any] = data.get("metric_definitions", {})
    if metric_id not in md:
        raise HTTPException(status_code=404, detail=f"Metric not found: {metric_id}")
    before = dict(md[metric_id])
    updates = {k: v for k, v in body.dict().items() if v is not None}
    md[metric_id].update(updates)
    _save_raw(data)
    _append_changelog("update", "metric_definition", metric_id, before, md[metric_id])
    _reload_cache()
    return {"data": {"metric_id": metric_id, **md[metric_id]}}


@router.delete("/metrics/{metric_id}")
async def delete_metric(metric_id: str):
    """删除指标定义"""
    data = _load_raw()
    md: Dict[str, Any] = data.get("metric_definitions", {})
    if metric_id not in md:
        raise HTTPException(status_code=404, detail=f"Metric not found: {metric_id}")
    before = md.pop(metric_id)
    _save_raw(data)
    _append_changelog("delete", "metric_definition", metric_id, before, None)
    _reload_cache()
    return {"message": f"Deleted: {metric_id}"}


# ══════════════════════════════════════════════════════════════════
# Changelog
# ══════════════════════════════════════════════════════════════════

@router.get("/changelog")
async def get_changelog(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    entry_type: str = Query(""),
    action: str = Query(""),
):
    cl = _changelog_path()
    records: List[Dict] = []
    if cl.exists():
        with cl.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    records.reverse()  # 倒序：最新在前

    if entry_type:
        records = [r for r in records if r.get("entry_type") == entry_type]
    if action:
        records = [r for r in records if r.get("action") == action]

    total = len(records)
    start = (page - 1) * page_size
    return {"data": records[start: start + page_size], "total": total}
