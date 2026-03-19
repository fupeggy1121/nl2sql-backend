"""
映射字典管理 API 路由

提供 object_mappings / relation_mappings / value_mappings / business_rules
的 CRUD 操作，以及变更日志查询和缓存重载。

所有写操作均:
  1. 原子写入（.tmp 文件 + os.rename）
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

from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

bp = Blueprint("mapping_manager", __name__, url_prefix="/api/mapping")

# ------------------------------------------------------------------
# 路径解析
# ------------------------------------------------------------------

def _get_mapping_path() -> Path:
    """解析当前生效的 mapping JSON 文件路径（同 mapping.py 逻辑）"""
    from app.ontology.config import ONTOLOGY_DATA_DIR
    env_val = os.getenv("MAPPING_FILE", "").strip()
    if env_val:
        p = Path(env_val)
        if not p.is_absolute():
            p = ONTOLOGY_DATA_DIR / p
        if p.exists():
            return p
    return ONTOLOGY_DATA_DIR / "mapping_demo_fab.json"


def _changelog_path() -> Path:
    return _get_mapping_path().parent / "mapping_changelog.jsonl"


# ------------------------------------------------------------------
# 内部工具
# ------------------------------------------------------------------

def _load_raw() -> Dict[str, Any]:
    with open(_get_mapping_path(), encoding="utf-8") as f:
        return json.load(f)


def _save_raw(data: Dict[str, Any]) -> None:
    """原子写入"""
    path = _get_mapping_path()
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _append_changelog(
    action: str,
    entry_type: str,
    key: str,
    before: Optional[Any] = None,
    after: Optional[Any] = None,
    user: str = "api",
) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": user,
        "action": action,           # create / update / delete
        "entry_type": entry_type,   # object_mapping / relation_mapping / ...
        "key": key,
        "before": before,
        "after": after,
    }
    with open(_changelog_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _reload_cache() -> None:
    try:
        from app.ontology.mapping import load_mapping
        load_mapping(force_reload=True)
        logger.info("[mapping_manager] cache reloaded")
    except Exception as e:
        logger.warning(f"[mapping_manager] cache reload failed: {e}")


def _decode_key(raw: str) -> str:
    """URL-decode 路径参数（处理 semi%3AEquipment → semi:Equipment）"""
    return urllib.parse.unquote(raw)


# ------------------------------------------------------------------
# 辅助：统一错误响应
# ------------------------------------------------------------------

def _err(msg: str, code: int = 400):
    return jsonify({"success": False, "error": msg}), code


def _ok(data: Any = None, **kwargs):
    resp = {"success": True}
    if data is not None:
        resp["data"] = data
    resp.update(kwargs)
    return jsonify(resp)


# ==================================================================
# 1. object_mappings CRUD
# ==================================================================

@bp.route("/objects", methods=["GET"])
def list_objects():
    """获取所有 object_mappings（可分页/搜索）"""
    raw = _load_raw()
    items = raw.get("object_mappings", [])

    # 搜索过滤
    q = request.args.get("q", "").strip().lower()
    if q:
        items = [
            o for o in items
            if q in o.get("logic_class", "").lower()
            or q in o.get("physical_table", "").lower()
            or q in o.get("label_cn", "").lower()
        ]

    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 50))
    total = len(items)
    start = (page - 1) * page_size
    items = items[start: start + page_size]

    return _ok(items, total=total, page=page, page_size=page_size)


@bp.route("/objects", methods=["POST"])
def create_object():
    """新增一条 object_mapping"""
    body = request.get_json(silent=True) or {}
    logic_class = body.get("logic_class", "").strip()
    physical_table = body.get("physical_table", "").strip()

    if not logic_class:
        return _err("logic_class 必填")

    raw = _load_raw()
    items: List[Dict] = raw.setdefault("object_mappings", [])

    # 检查重复
    if any(o.get("logic_class") == logic_class for o in items):
        return _err(f"logic_class '{logic_class}' 已存在", 409)

    entry: Dict = {
        "logic_class": logic_class,
        "physical_table": physical_table or None,
        "primary_key": body.get("primary_key") or "id",
        "label_cn": body.get("label_cn", ""),
        "display_column": body.get("display_column") or None,
        "filter_condition": body.get("filter_condition") or None,
        "key_columns": body.get("key_columns", []),
        "properties": body.get("properties", {}),
        "virtual": body.get("virtual", False),
        "virtual_kind": body.get("virtual_kind") or None,
        "embedded_in": body.get("embedded_in") or None,
        "source_json_column": body.get("source_json_column") or None,
        "source_json_path": body.get("source_json_path") or None,
        "note": body.get("note"),
    }
    # 移除 None 值的可选字段（保持 JSON 整洁）
    entry = {k: v for k, v in entry.items() if v is not None or k in ("physical_table",)}

    items.append(entry)
    _save_raw(raw)
    _append_changelog("create", "object_mapping", logic_class, after=entry)
    _reload_cache()

    return _ok(entry), 201


@bp.route("/objects/<path:logic_class_raw>", methods=["GET"])
def get_object(logic_class_raw: str):
    """获取单条 object_mapping"""
    logic_class = _decode_key(logic_class_raw)
    raw = _load_raw()
    for o in raw.get("object_mappings", []):
        if o.get("logic_class") == logic_class:
            return _ok(o)
    return _err(f"logic_class '{logic_class}' 不存在", 404)


@bp.route("/objects/<path:logic_class_raw>", methods=["PUT"])
def update_object(logic_class_raw: str):
    """更新一条 object_mapping（部分更新）"""
    logic_class = _decode_key(logic_class_raw)
    body = request.get_json(silent=True) or {}

    raw = _load_raw()
    items: List[Dict] = raw.get("object_mappings", [])
    for i, o in enumerate(items):
        if o.get("logic_class") == logic_class:
            before = dict(o)
            # 允许更新的字段（不允许修改 logic_class 本身）
            for field in [
                "physical_table", "primary_key", "label_cn", "display_column",
                "filter_condition", "key_columns", "properties",
                "virtual", "virtual_kind",
                "embedded_in", "source_json_column", "source_json_path",
                "note",
            ]:
                if field in body:
                    items[i][field] = body[field]
            _save_raw(raw)
            _append_changelog("update", "object_mapping", logic_class, before=before, after=items[i])
            _reload_cache()
            return _ok(items[i])
    return _err(f"logic_class '{logic_class}' 不存在", 404)


@bp.route("/objects/<path:logic_class_raw>", methods=["DELETE"])
def delete_object(logic_class_raw: str):
    """删除一条 object_mapping"""
    logic_class = _decode_key(logic_class_raw)
    raw = _load_raw()
    items: List[Dict] = raw.get("object_mappings", [])
    for i, o in enumerate(items):
        if o.get("logic_class") == logic_class:
            before = items.pop(i)
            _save_raw(raw)
            _append_changelog("delete", "object_mapping", logic_class, before=before)
            _reload_cache()
            return _ok({"deleted": logic_class})
    return _err(f"logic_class '{logic_class}' 不存在", 404)


# ==================================================================
# 2. relation_mappings CRUD
# ==================================================================

@bp.route("/relations", methods=["GET"])
def list_relations():
    """获取所有 relation_mappings"""
    raw = _load_raw()
    items = raw.get("relation_mappings", [])

    q = request.args.get("q", "").strip().lower()
    if q:
        items = [
            r for r in items
            if q in r.get("logic_relation", "").lower()
            or q in r.get("description", "").lower()
            or q in r.get("strategy", "").lower()
        ]

    confidence = request.args.get("confidence", "").strip()
    if confidence:
        items = [r for r in items if r.get("confidence", "") == confidence]

    return _ok(items, total=len(items))


@bp.route("/relations", methods=["POST"])
def create_relation():
    """新增一条 relation_mapping"""
    body = request.get_json(silent=True) or {}
    logic_relation = body.get("logic_relation", "").strip()
    if not logic_relation:
        return _err("logic_relation 必填")
    if not body.get("strategy"):
        return _err("strategy 必填（ForeignKey / JoinTable / Indirect / Recursive）")

    raw = _load_raw()
    items: List[Dict] = raw.setdefault("relation_mappings", [])

    if any(r.get("logic_relation") == logic_relation for r in items):
        return _err(f"logic_relation '{logic_relation}' 已存在", 409)

    entry = {
        "logic_relation": logic_relation,
        "description": body.get("description", ""),
        "strategy": body.get("strategy"),
        "join_logic": body.get("join_logic", {}),
    }
    if body.get("confidence"):
        entry["confidence"] = body["confidence"]

    items.append(entry)
    _save_raw(raw)
    _append_changelog("create", "relation_mapping", logic_relation, after=entry)
    _reload_cache()

    return _ok(entry), 201


@bp.route("/relations/<path:relation_raw>", methods=["PUT"])
def update_relation(relation_raw: str):
    """更新一条 relation_mapping"""
    logic_relation = _decode_key(relation_raw)
    body = request.get_json(silent=True) or {}

    raw = _load_raw()
    items: List[Dict] = raw.get("relation_mappings", [])
    for i, r in enumerate(items):
        if r.get("logic_relation") == logic_relation:
            before = dict(r)
            for field in ["description", "strategy", "join_logic", "confidence"]:
                if field in body:
                    items[i][field] = body[field]
            _save_raw(raw)
            _append_changelog("update", "relation_mapping", logic_relation, before=before, after=items[i])
            _reload_cache()
            return _ok(items[i])
    return _err(f"logic_relation '{logic_relation}' 不存在", 404)


@bp.route("/relations/<path:relation_raw>", methods=["DELETE"])
def delete_relation(relation_raw: str):
    """删除一条 relation_mapping"""
    logic_relation = _decode_key(relation_raw)
    raw = _load_raw()
    items: List[Dict] = raw.get("relation_mappings", [])
    for i, r in enumerate(items):
        if r.get("logic_relation") == logic_relation:
            before = items.pop(i)
            _save_raw(raw)
            _append_changelog("delete", "relation_mapping", logic_relation, before=before)
            _reload_cache()
            return _ok({"deleted": logic_relation})
    return _err(f"logic_relation '{logic_relation}' 不存在", 404)


# ==================================================================
# 3. value_mappings CRUD（语义域 + 值条目）
# ==================================================================

@bp.route("/values", methods=["GET"])
def list_value_domains():
    """列出所有语义域 + 每域值数量"""
    raw = _load_raw()
    vm = raw.get("value_mappings", {})
    result = [
        {"domain": domain, "value_count": len(values)}
        for domain, values in vm.items()
    ]
    return _ok(result, total=len(result))


@bp.route("/values/<path:domain_raw>", methods=["GET"])
def get_value_domain(domain_raw: str):
    """获取某个语义域下所有值条目"""
    domain = _decode_key(domain_raw)
    raw = _load_raw()
    vm = raw.get("value_mappings", {})
    if domain not in vm:
        return _err(f"domain '{domain}' 不存在", 404)
    items = [
        {"semantic_value": k, **v}
        for k, v in vm[domain].items()
    ]
    return _ok(items, domain=domain)


@bp.route("/values/<path:domain_raw>/<semantic_value>", methods=["PUT"])
def upsert_value(domain_raw: str, semantic_value: str):
    """新增或更新语义域中的一个值条目"""
    domain = _decode_key(domain_raw)
    body = request.get_json(silent=True) or {}

    raw = _load_raw()
    vm = raw.setdefault("value_mappings", {})
    vm.setdefault(domain, {})

    before = vm[domain].get(semantic_value)
    vm[domain][semantic_value] = {k: v for k, v in body.items() if k != "semantic_value"}
    action = "update" if before else "create"

    _save_raw(raw)
    _append_changelog(action, "value_mapping", f"{domain}/{semantic_value}", before=before, after=vm[domain][semantic_value])
    _reload_cache()

    return _ok({"domain": domain, "semantic_value": semantic_value, "entry": vm[domain][semantic_value]})


@bp.route("/values/<path:domain_raw>/<semantic_value>", methods=["DELETE"])
def delete_value(domain_raw: str, semantic_value: str):
    """删除语义域中的某个值条目"""
    domain = _decode_key(domain_raw)
    raw = _load_raw()
    vm = raw.get("value_mappings", {})
    if domain not in vm or semantic_value not in vm[domain]:
        return _err(f"'{domain}/{semantic_value}' 不存在", 404)
    before = vm[domain].pop(semantic_value)
    _save_raw(raw)
    _append_changelog("delete", "value_mapping", f"{domain}/{semantic_value}", before=before)
    _reload_cache()
    return _ok({"deleted": f"{domain}/{semantic_value}"})


# ==================================================================
# 4. business_rules CRUD
# ==================================================================

@bp.route("/rules", methods=["GET"])
def list_rules():
    """获取所有业务规则"""
    raw = _load_raw()
    items = raw.get("business_rules", [])
    q = request.args.get("q", "").strip().lower()
    if q:
        items = [
            r for r in items
            if q in r.get("id", "").lower()
            or q in r.get("name", "").lower()
            or q in r.get("description", "").lower()
            or any(q in kw for kw in r.get("trigger_keywords", []))
        ]
    return _ok(items, total=len(items))


@bp.route("/rules", methods=["POST"])
def create_rule():
    """新增业务规则"""
    body = request.get_json(silent=True) or {}
    rule_id = body.get("id", "").strip()
    if not rule_id:
        return _err("id 必填")

    raw = _load_raw()
    items: List[Dict] = raw.setdefault("business_rules", [])

    if any(r.get("id") == rule_id for r in items):
        return _err(f"rule id '{rule_id}' 已存在", 409)

    entry = {
        "id": rule_id,
        "name": body.get("name", ""),
        "description": body.get("description", ""),
        "trigger_keywords": body.get("trigger_keywords", []),
        "physical_sql_template": body.get("physical_sql_template", ""),
        "involved_tables": body.get("involved_tables", []),
        "warning_tables": body.get("warning_tables", []),
    }
    if body.get("semantic_pattern"):
        entry["semantic_pattern"] = body["semantic_pattern"]

    items.append(entry)
    _save_raw(raw)
    _append_changelog("create", "business_rule", rule_id, after=entry)
    _reload_cache()

    return _ok(entry), 201


@bp.route("/rules/<rule_id>", methods=["PUT"])
def update_rule(rule_id: str):
    """更新业务规则"""
    body = request.get_json(silent=True) or {}
    raw = _load_raw()
    items: List[Dict] = raw.get("business_rules", [])
    for i, r in enumerate(items):
        if r.get("id") == rule_id:
            before = dict(r)
            for field in [
                "name", "description", "trigger_keywords",
                "physical_sql_template", "involved_tables",
                "warning_tables", "semantic_pattern",
            ]:
                if field in body:
                    items[i][field] = body[field]
            _save_raw(raw)
            _append_changelog("update", "business_rule", rule_id, before=before, after=items[i])
            _reload_cache()
            return _ok(items[i])
    return _err(f"rule id '{rule_id}' 不存在", 404)


@bp.route("/rules/<rule_id>", methods=["DELETE"])
def delete_rule(rule_id: str):
    """删除业务规则"""
    raw = _load_raw()
    items: List[Dict] = raw.get("business_rules", [])
    for i, r in enumerate(items):
        if r.get("id") == rule_id:
            before = items.pop(i)
            _save_raw(raw)
            _append_changelog("delete", "business_rule", rule_id, before=before)
            _reload_cache()
            return _ok({"deleted": rule_id})
    return _err(f"rule id '{rule_id}' 不存在", 404)


# ==================================================================
# 5. 变更日志
# ==================================================================

@bp.route("/changelog", methods=["GET"])
def get_changelog():
    """
    获取变更日志（倒序，分页）

    查询参数:
      - page: 页码（默认 1）
      - page_size: 每页条数（默认 50，最大 200）
      - entry_type: 过滤类型
      - action: create / update / delete
    """
    cl_path = _changelog_path()
    if not cl_path.exists():
        return _ok([], total=0)

    with open(cl_path, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    records = []
    for line in reversed(lines):
        try:
            records.append(json.loads(line))
        except Exception:
            pass

    entry_type = request.args.get("entry_type", "").strip()
    action = request.args.get("action", "").strip()
    if entry_type:
        records = [r for r in records if r.get("entry_type") == entry_type]
    if action:
        records = [r for r in records if r.get("action") == action]

    total = len(records)
    page = int(request.args.get("page", 1))
    page_size = min(int(request.args.get("page_size", 50)), 200)
    start = (page - 1) * page_size
    records = records[start: start + page_size]

    return _ok(records, total=total, page=page, page_size=page_size)


# ==================================================================
# 6. 缓存重载 + 摘要
# ==================================================================

@bp.route("/reload", methods=["POST"])
def reload_cache():
    """强制重载映射缓存"""
    _reload_cache()
    from app.ontology.mapping import get_mapping
    summary = get_mapping().summary()
    return _ok({"reloaded": True, "summary": summary})


@bp.route("/summary", methods=["GET"])
def get_summary():
    """获取当前 mapping 文件摘要信息"""
    raw = _load_raw()
    return _ok({
        "mapping_file": str(_get_mapping_path()),
        "version": raw.get("version", "unknown"),
        "customer": raw.get("customer", "unknown"),
        "object_mappings": len(raw.get("object_mappings", [])),
        "relation_mappings": len(raw.get("relation_mappings", [])),
        "value_domains": len(raw.get("value_mappings", {})),
        "business_rules": len(raw.get("business_rules", [])),
        "changelog_entries": sum(
            1 for _ in open(_changelog_path(), encoding="utf-8")
        ) if _changelog_path().exists() else 0,
    })
