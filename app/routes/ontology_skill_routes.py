"""
本体建模技能 API 路由

提供本体建模的 preview / commit / diagnose REST 接口。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

bp = Blueprint("ontology_skill", __name__, url_prefix="/api/ontology-skill")


@bp.route("/preview", methods=["POST"])
def preview_changes():
    """
    预览本体变更（不写文件）。

    请求体: OntologySpec JSON（classes / relations / data_properties / value_mappings）
    响应: PreviewResult — 新增/更新/校验问题列表
    """
    data: Dict[str, Any] = request.get_json(force=True)
    if not data:
        return jsonify({"success": False, "error": "Empty request body"}), 400

    try:
        from app.ontology.skill import preview_from_dict
        result = preview_from_dict(data)
        return jsonify({
            "success": True,
            "has_errors": result.has_errors,
            **result.to_dict(),
        })
    except Exception as e:
        logger.error("[ontology_skill] preview failed: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/commit", methods=["POST"])
def commit_changes():
    """
    提交本体变更（写入 TTL + mapping + changelog + 版本）。

    请求体: OntologySpec JSON + 可选 {"force": true} 跳过 error 校验
    响应: CommitResult — 成功/失败 + TTL 版本号 + 变更计数
    """
    data: Dict[str, Any] = request.get_json(force=True)
    if not data:
        return jsonify({"success": False, "error": "Empty request body"}), 400

    force = data.pop("force", False)

    try:
        from app.ontology.skill import OntologyBuilderSkill, _parse_spec_dict
        spec = _parse_spec_dict(data)
        skill = OntologyBuilderSkill()
        skill.load().stage(spec)
        result = skill.commit(force=bool(force))
        status = 200 if result.success else 422
        return jsonify(result.to_dict()), status
    except Exception as e:
        logger.error("[ontology_skill] commit failed: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/diagnose", methods=["GET"])
def diagnose():
    """
    诊断当前本体 + mapping 健康状况。

    返回 TTL ↔ mapping 的覆盖度、未映射类/关系、孤儿映射等。
    """
    try:
        from app.ontology.skill import diagnose_ontology
        result = diagnose_ontology()
        return jsonify({"success": True, **result})
    except Exception as e:
        logger.error("[ontology_skill] diagnose failed: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/add-class", methods=["POST"])
def add_class():
    """
    快捷接口：添加单个类（语义 + 物理映射）。

    请求体:
    {
      "uri": "semi:NewClass",
      "label": "新类(NewClass)",
      "comment": "描述",
      "parent_uri": "semi:Material",
      "physical_table": "new_table",
      "primary_key": "id",
      "label_cn": "新类",
      "display_column": "code",
      "key_columns": ["id", "code"],
      "properties": {"semi:hasCode": "code"},
      "message": "添加新类",
      "author": "admin"
    }
    """
    data: Dict[str, Any] = request.get_json(force=True)
    if not data or "uri" not in data:
        return jsonify({"success": False, "error": "Missing 'uri' field"}), 400

    try:
        from app.ontology.skill import ClassSpec, OntologyBuilderSkill
        spec = ClassSpec(
            uri=data["uri"],
            label=data.get("label", ""),
            comment=data.get("comment", ""),
            parent_uri=data.get("parent_uri", ""),
            physical_table=data.get("physical_table"),
            primary_key=data.get("primary_key"),
            label_cn=data.get("label_cn", ""),
            display_column=data.get("display_column"),
            key_columns=data.get("key_columns", []),
            properties=data.get("properties", {}),
            virtual=data.get("virtual", False),
            virtual_kind=data.get("virtual_kind"),
            filter_condition=data.get("filter_condition"),
            note=data.get("note"),
        )
        result = OntologyBuilderSkill().add_class(
            spec,
            message=data.get("message", ""),
            author=data.get("author", "api"),
        )
        status = 200 if result.success else 422
        return jsonify(result.to_dict()), status
    except Exception as e:
        logger.error("[ontology_skill] add-class failed: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/add-relation", methods=["POST"])
def add_relation():
    """
    快捷接口：添加单条关系（语义 + 物理 JOIN 映射）。

    请求体:
    {
      "uri": "semi:newRelation",
      "label": "关系名",
      "domain_uri": "semi:ClassA",
      "range_uri": "semi:ClassB",
      "strategy": "ForeignKey",
      "description": "A 关联 B",
      "join_logic": {
        "source_table": "table_a",
        "source_key": "b_id",
        "target_table": "table_b",
        "target_key": "id"
      }
    }
    """
    data: Dict[str, Any] = request.get_json(force=True)
    if not data or "uri" not in data:
        return jsonify({"success": False, "error": "Missing 'uri' field"}), 400

    try:
        from app.ontology.skill import OntologyBuilderSkill, RelationSpec
        spec = RelationSpec(
            uri=data["uri"],
            label=data.get("label", ""),
            comment=data.get("comment", ""),
            domain_uri=data.get("domain_uri", ""),
            range_uri=data.get("range_uri", ""),
            strategy=data.get("strategy", "ForeignKey"),
            description=data.get("description", ""),
            join_logic=data.get("join_logic", {}),
            applicable_intents=data.get("applicable_intents", []),
            forbidden_intents=data.get("forbidden_intents", []),
            applicable_record_types=data.get("applicable_record_types", []),
            note=data.get("note"),
        )
        result = OntologyBuilderSkill().add_relation(
            spec,
            message=data.get("message", ""),
            author=data.get("author", "api"),
        )
        status = 200 if result.success else 422
        return jsonify(result.to_dict()), status
    except Exception as e:
        logger.error("[ontology_skill] add-relation failed: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/add-value-mapping", methods=["POST"])
def add_value_mapping():
    """
    快捷接口：添加单条值映射。

    请求体:
    {
      "domain": "semi:EquipmentStatus",
      "semantic_value": "Maintenance",
      "description": "维护中",
      "physical_condition": "status = 3",
      "applies_to_table": "equipment",
      "applies_to_column": "status"
    }
    """
    data: Dict[str, Any] = request.get_json(force=True)
    if not data or "domain" not in data or "semantic_value" not in data:
        return jsonify({"success": False, "error": "Missing 'domain' or 'semantic_value'"}), 400

    try:
        from app.ontology.skill import OntologyBuilderSkill, ValueMappingSpec
        spec = ValueMappingSpec(
            domain=data["domain"],
            semantic_value=data["semantic_value"],
            description=data.get("description", ""),
            physical_values=data.get("physical_values"),
            physical_condition=data.get("physical_condition"),
            applies_to_table=data.get("applies_to_table"),
            applies_to_column=data.get("applies_to_column"),
            is_terminal=data.get("is_terminal", False),
            nl_triggers=data.get("nl_triggers", []),
            note=data.get("note"),
        )
        result = OntologyBuilderSkill().add_value_mapping(
            spec,
            message=data.get("message", ""),
            author=data.get("author", "api"),
        )
        status = 200 if result.success else 422
        return jsonify(result.to_dict()), status
    except Exception as e:
        logger.error("[ontology_skill] add-value-mapping failed: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════
# 自然语言驱动接口（NL → OntologySpec → 执行）
# ══════════════════════════════════════════════════════════════════════

@bp.route("/nl-to-spec", methods=["POST"])
def nl_to_spec():
    """
    自然语言 → OntologySpec JSON（只转换，不执行）。

    请求体:
    {
      "request": "添加一个机械臂类，继承自Equipment，物理表 robot_arms，主键 id"
    }

    返回: { spec: OntologySpec, raw_llm_output, success }
    """
    data: Dict[str, Any] = request.get_json(force=True)
    user_request = (data or {}).get("request", "").strip()
    if not user_request:
        return jsonify({"success": False, "error": "Missing 'request' field"}), 400

    try:
        from app.ontology.skill_assistant import nl_to_spec as _nl_to_spec
        result = _nl_to_spec(user_request)
        return jsonify(result)
    except Exception as e:
        logger.error("[ontology_skill] nl-to-spec failed: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/nl-preview", methods=["POST"])
def nl_preview():
    """
    自然语言 → preview（转换 + 校验，不写文件）。

    请求体: { "request": "..." }
    返回: { spec, preview: { ttl_additions, mapping_additions, issues }, has_errors }
    """
    data: Dict[str, Any] = request.get_json(force=True)
    user_request = (data or {}).get("request", "").strip()
    if not user_request:
        return jsonify({"success": False, "error": "Missing 'request' field"}), 400

    try:
        from app.ontology.skill_assistant import nl_preview as _nl_preview
        result = _nl_preview(user_request)
        return jsonify(result)
    except Exception as e:
        logger.error("[ontology_skill] nl-preview failed: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/nl-process", methods=["POST"])
def nl_process():
    """
    自然语言 → 全流程（NL → spec → preview → commit → diagnose）。

    请求体:
    {
      "request": "用一句话描述本体变更",
      "auto_commit": true,    // 默认 true，false 时只返回 preview
      "force": false          // 有 error 时是否强制提交
    }

    返回: { stage, spec, preview, commit, diagnose, success }
    stage 值: "nl_to_spec" | "preview" | "blocked_by_errors" |
               "preview_only" | "commit" | "done"
    """
    data: Dict[str, Any] = request.get_json(force=True)
    user_request = (data or {}).get("request", "").strip()
    if not user_request:
        return jsonify({"success": False, "error": "Missing 'request' field"}), 400

    auto_commit = (data or {}).get("auto_commit", True)
    force = (data or {}).get("force", False)

    try:
        from app.ontology.skill_assistant import nl_process as _nl_process
        result = _nl_process(user_request, auto_commit=bool(auto_commit), force=bool(force))
        http_status = 200 if result.get("success") else 422
        return jsonify(result), http_status
    except Exception as e:
        logger.error("[ontology_skill] nl-process failed: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
