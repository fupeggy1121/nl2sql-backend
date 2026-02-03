"""
Schema 标注 API 路由
提供标注的 CRUD 操作和自动生成功能
"""
from flask import Blueprint, request, jsonify
import logging
import asyncio
from app.services.schema_annotator import schema_annotator

logger = logging.getLogger(__name__)

# 创建蓝图
bp = Blueprint('schema_annotator', __name__, url_prefix='/api/schema')


@bp.route('/tables/auto-annotate', methods=['POST'])
def auto_annotate_tables():
    """
    自动为所有表生成 LLM 标注
    
    请求体:
    {
        "table_names": ["table1", "table2"] (可选，不指定则标注所有表)
    }
    
    响应:
    {
        "success": true,
        "annotations": [...]
    }
    """
    try:
        data = request.json or {}
        table_names = data.get('table_names')
        
        logger.info(f"Starting auto-annotation for tables: {table_names}")
        
        # TODO: 调用 schema_annotator 获取表信息并生成标注
        # 这里需要实现与数据库连接获取实际的表信息
        
        return jsonify({
            "success": True,
            "message": "Auto-annotation job started",
            "tables_to_annotate": table_names or "all"
        }), 202
        
    except Exception as e:
        logger.error(f"Failed to start auto-annotation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/tables/pending', methods=['GET'])
def get_pending_table_annotations():
    """
    获取待审核的表标注
    
    响应:
    {
        "success": true,
        "annotations": [...]
    }
    """
    try:
        annotations = schema_annotator.get_pending_annotations("table")
        
        return jsonify({
            "success": True,
            "count": len(annotations),
            "annotations": annotations
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get pending annotations: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/columns/pending', methods=['GET'])
def get_pending_column_annotations():
    """
    获取待审核的列标注
    
    响应:
    {
        "success": true,
        "annotations": [...]
    }
    """
    try:
        annotations = schema_annotator.get_pending_annotations("column")
        
        return jsonify({
            "success": True,
            "count": len(annotations),
            "annotations": annotations
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get pending annotations: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/tables/<annotation_id>/approve', methods=['POST'])
def approve_table_annotation(annotation_id):
    """
    审核通过表标注
    
    请求体:
    {
        "reviewer": "admin"
    }
    
    响应:
    {
        "success": true,
        "annotation": {...}
    }
    """
    try:
        data = request.json or {}
        reviewer = data.get('reviewer', 'admin')
        
        result = schema_annotator.approve_annotation(
            annotation_id, 
            "table",
            reviewer
        )
        
        return jsonify({
            "success": True,
            "annotation": result
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to approve annotation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/tables/<annotation_id>/reject', methods=['POST'])
def reject_table_annotation(annotation_id):
    """
    拒绝表标注
    
    请求体:
    {
        "reason": "描述不准确",
        "reviewer": "admin"
    }
    
    响应:
    {
        "success": true,
        "annotation": {...}
    }
    """
    try:
        data = request.json or {}
        reason = data.get('reason', '')
        reviewer = data.get('reviewer', 'admin')
        
        result = schema_annotator.reject_annotation(
            annotation_id,
            "table",
            reason,
            reviewer
        )
        
        return jsonify({
            "success": True,
            "annotation": result
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to reject annotation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/tables/<annotation_id>', methods=['PUT'])
def update_table_annotation(annotation_id):
    """
    更新（手动编辑）表标注
    
    请求体:
    {
        "table_name_cn": "新的中文名称",
        "description_cn": "新的描述",
        ...
    }
    
    响应:
    {
        "success": true,
        "annotation": {...}
    }
    """
    try:
        data = request.json or {}
        
        result = schema_annotator.update_annotation(
            annotation_id,
            "table",
            data
        )
        
        return jsonify({
            "success": True,
            "annotation": result
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to update annotation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/columns/<annotation_id>/approve', methods=['POST'])
def approve_column_annotation(annotation_id):
    """
    审核通过列标注
    """
    try:
        data = request.json or {}
        reviewer = data.get('reviewer', 'admin')
        
        result = schema_annotator.approve_annotation(
            annotation_id,
            "column",
            reviewer
        )
        
        return jsonify({
            "success": True,
            "annotation": result
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to approve annotation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/metadata', methods=['GET'])
def get_approved_metadata():
    """
    获取所有已批准的 schema 元数据
    用于 NL2SQL 理解和查询
    
    响应:
    {
        "success": true,
        "metadata": {
            "tables": {...},
            "columns": {...},
            "last_updated": "2024-02-03T..."
        }
    }
    """
    try:
        metadata = schema_annotator.get_approved_schema_metadata()
        
        return jsonify({
            "success": True,
            "metadata": metadata
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get approved metadata: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/status', methods=['GET'])
def get_annotation_status():
    """获取标注进度统计（含各状态计数）"""
    try:
        counts = schema_annotator.get_annotation_counts()
        return jsonify({
            "success": True,
            "status": counts
        }), 200
    except Exception as e:
        logger.error(f"Failed to get annotation status: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/tables/all', methods=['GET'])
def get_all_table_annotations():
    """获取所有表标注（支持 ?status= 过滤）"""
    try:
        status_filter = request.args.get('status')
        annotations = schema_annotator.get_all_annotations("table", status_filter=status_filter)
        return jsonify({
            "success": True,
            "count": len(annotations),
            "annotations": annotations
        }), 200
    except Exception as e:
        logger.error(f"Failed to get all table annotations: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/columns/all', methods=['GET'])
def get_all_column_annotations():
    """获取所有列标注（支持 ?status= 和 ?table_name= 过滤）"""
    try:
        status_filter = request.args.get('status')
        table_name_filter = request.args.get('table_name')
        annotations = schema_annotator.get_all_annotations(
            "column", status_filter=status_filter, table_name_filter=table_name_filter
        )
        return jsonify({
            "success": True,
            "count": len(annotations),
            "annotations": annotations
        }), 200
    except Exception as e:
        logger.error(f"Failed to get all column annotations: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/columns/<annotation_id>/reject', methods=['POST'])
def reject_column_annotation(annotation_id):
    """拒绝列标注"""
    try:
        data = request.json or {}
        reason = data.get('reason', '')
        reviewer = data.get('reviewer', 'admin')
        result = schema_annotator.reject_annotation(annotation_id, "column", reason, reviewer)
        return jsonify({"success": True, "annotation": result}), 200
    except Exception as e:
        logger.error(f"Failed to reject column annotation: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/columns/<annotation_id>', methods=['PUT'])
def update_column_annotation(annotation_id):
    """更新（手动编辑）列标注"""
    try:
        data = request.json or {}
        result = schema_annotator.update_annotation(annotation_id, "column", data)
        return jsonify({"success": True, "annotation": result}), 200
    except Exception as e:
        logger.error(f"Failed to update column annotation: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/tables', methods=['POST'])
def create_table_annotation():
    """手动创建表标注"""
    try:
        data = request.json or {}
        if not data.get('table_name'):
            return jsonify({"success": False, "error": "table_name is required"}), 400

        record = {
            "table_name": data["table_name"],
            "table_name_cn": data.get("table_name_cn"),
            "description_cn": data.get("description_cn"),
            "description_en": data.get("description_en"),
            "business_meaning": data.get("business_meaning"),
            "use_case": data.get("use_case"),
            "status": "pending",
            "created_by": data.get("created_by", "manual"),
        }
        result = schema_annotator.supabase.table(
            schema_annotator.SCHEMA_TABLES_TABLE
        ).insert(record).execute()

        created = result.data[0] if result.data else record
        schema_annotator._log_audit("table", created.get("id", ""), "create",
                                     new_value=record, actor=record["created_by"])
        return jsonify({"success": True, "annotation": created}), 201
    except Exception as e:
        logger.error(f"Failed to create table annotation: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/columns', methods=['POST'])
def create_column_annotation():
    """手动创建列标注"""
    try:
        data = request.json or {}
        if not data.get('table_name') or not data.get('column_name'):
            return jsonify({"success": False, "error": "table_name and column_name are required"}), 400

        record = {
            "table_name": data["table_name"],
            "column_name": data["column_name"],
            "column_name_cn": data.get("column_name_cn"),
            "data_type": data.get("data_type"),
            "description_cn": data.get("description_cn"),
            "description_en": data.get("description_en"),
            "example_value": data.get("example_value"),
            "business_meaning": data.get("business_meaning"),
            "value_range": data.get("value_range"),
            "status": "pending",
            "created_by": data.get("created_by", "manual"),
        }
        result = schema_annotator.supabase.table(
            schema_annotator.SCHEMA_COLUMNS_TABLE
        ).insert(record).execute()

        created = result.data[0] if result.data else record
        schema_annotator._log_audit("column", created.get("id", ""), "create",
                                     new_value=record, actor=record["created_by"])
        return jsonify({"success": True, "annotation": created}), 201
    except Exception as e:
        logger.error(f"Failed to create column annotation: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/audit-log', methods=['GET'])
def get_audit_log():
    """获取审计日志"""
    try:
        annotation_id = request.args.get('annotation_id')
        limit = request.args.get('limit', 50, type=int)

        query = schema_annotator.supabase.table("annotation_audit_log").select("*")
        if annotation_id:
            query = query.eq("annotation_id", annotation_id)
        result = query.order("created_at", desc=True).limit(limit).execute()

        return jsonify({
            "success": True,
            "count": len(result.data) if result.data else 0,
            "entries": result.data or []
        }), 200
    except Exception as e:
        logger.error(f"Failed to get audit log: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
