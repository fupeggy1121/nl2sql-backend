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
    """
    获取标注进度统计
    
    响应:
    {
        "success": true,
        "status": {
            "total_tables": 10,
            "approved_tables": 5,
            "pending_tables": 3,
            "rejected_tables": 2,
            "...": "..."
        }
    }
    """
    try:
        # 获取各类型的统计信息
        pending_tables = schema_annotator.get_pending_annotations("table")
        pending_columns = schema_annotator.get_pending_annotations("column")
        
        return jsonify({
            "success": True,
            "status": {
                "pending_table_annotations": len(pending_tables),
                "pending_column_annotations": len(pending_columns),
                "message": "Use GET /schema/tables/pending and /schema/columns/pending for details"
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get annotation status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
