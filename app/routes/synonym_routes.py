"""
同义词管理 API 路由
提供表名同义词的 CRUD 操作 + 未匹配词反馈审批
"""
from flask import Blueprint, request, jsonify
import logging

from app.services.synonym_manager import synonym_manager

logger = logging.getLogger(__name__)

bp = Blueprint('synonym_manager', __name__, url_prefix='/api/synonyms')


# ==============================================================
# 同义词 CRUD
# ==============================================================

@bp.route('', methods=['GET'])
def list_synonyms():
    """
    获取同义词列表

    查询参数:
      - table_name: 按表名筛选
      - source: builtin / manual / auto
      - is_active: true / false (默认 true)

    响应: { success, data: [...] }
    """
    table_name = request.args.get('table_name')
    source = request.args.get('source')
    is_active_str = request.args.get('is_active', 'true')
    is_active = is_active_str.lower() != 'false' if is_active_str else True

    data = synonym_manager.get_all_synonyms(table_name, source, is_active)
    return jsonify({"success": True, "data": data, "total": len(data)})


@bp.route('/tables', methods=['GET'])
def list_tables_summary():
    """
    获取每张表的同义词统计摘要

    响应: { success, data: [ {table_name, total, active, manual, auto, builtin}, ... ] }
    """
    data = synonym_manager.get_tables_summary()
    return jsonify({"success": True, "data": data})


@bp.route('', methods=['POST'])
def add_synonym():
    """
    添加同义词

    请求体:
    {
      "table_name": "carriers",
      "synonym": "新别名",
      "source": "manual"        (可选, 默认 manual)
    }
    或批量:
    {
      "table_name": "carriers",
      "synonyms": ["别名1", "别名2"]
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "请求体不能为空"}), 400

    table_name = data.get('table_name')
    if not table_name:
        return jsonify({"success": False, "error": "table_name 必填"}), 400

    source = data.get('source', 'manual')

    # 批量模式
    synonyms = data.get('synonyms')
    if synonyms and isinstance(synonyms, list):
        result = synonym_manager.add_synonyms_batch(table_name, synonyms, source)
        return jsonify({"success": True, **result})

    # 单条模式
    synonym = data.get('synonym')
    if not synonym:
        return jsonify({"success": False, "error": "synonym 或 synonyms 必填"}), 400

    try:
        result = synonym_manager.add_synonym(table_name, synonym, source)
        return jsonify(result), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/<int:synonym_id>', methods=['PUT'])
def update_synonym(synonym_id):
    """
    更新同义词

    请求体 (可选字段):
    {
      "table_name": "new_table",
      "synonym": "新名称",
      "is_active": false
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "请求体不能为空"}), 400

    try:
        result = synonym_manager.update_synonym(synonym_id, **data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/<int:synonym_id>', methods=['DELETE'])
def delete_synonym(synonym_id):
    """
    删除同义词 (软删除)

    查询参数: ?hard=true 物理删除
    """
    hard = request.args.get('hard', 'false').lower() == 'true'

    try:
        if hard:
            result = synonym_manager.hard_delete_synonym(synonym_id)
        else:
            result = synonym_manager.delete_synonym(synonym_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/map', methods=['GET'])
def get_synonym_map():
    """
    获取完整的 {同义词 → 表名} 映射

    响应: { success, data: {"片篮": "carriers", ...}, total: N }
    """
    m = synonym_manager.get_synonym_map()
    return jsonify({"success": True, "data": m, "total": len(m)})


@bp.route('/lookup', methods=['GET'])
def lookup_synonym():
    """
    查询单个关键词对应的表名

    查询参数: ?keyword=片篮

    响应: { success, keyword, table_name, matched }
    """
    keyword = request.args.get('keyword', '').strip()
    if not keyword:
        return jsonify({"success": False, "error": "keyword 参数必填"}), 400

    table_name = synonym_manager.map_table_name(keyword)
    matched = table_name != keyword  # 是否找到了映射
    return jsonify({
        "success": True,
        "keyword": keyword,
        "table_name": table_name,
        "matched": matched,
    })


@bp.route('/stats', methods=['GET'])
def get_stats():
    """
    获取同义词系统总体统计

    响应: { success, data: { synonyms: {...}, unmatched: {...} } }
    """
    stats = synonym_manager.get_stats()
    return jsonify({"success": True, "data": stats})


# ==============================================================
# 未匹配词 (反馈学习) 管理
# ==============================================================

@bp.route('/unmatched', methods=['GET'])
def list_unmatched_terms():
    """
    获取未匹配查询词候选队列

    查询参数:
      - status: pending / approved / rejected / ignored (默认 pending)
      - min_frequency: 最小出现频次 (默认 1)
      - limit: 返回条数 (默认 50)
    """
    status = request.args.get('status', 'pending')
    min_freq = int(request.args.get('min_frequency', 1))
    limit = int(request.args.get('limit', 50))

    data = synonym_manager.get_unmatched_terms(status, min_freq, limit)
    return jsonify({"success": True, "data": data, "total": len(data)})


@bp.route('/unmatched/<int:term_id>/approve', methods=['POST'])
def approve_unmatched(term_id):
    """
    审批未匹配词 → 自动创建同义词映射

    请求体:
    {
      "table_name": "carriers"    // 指定映射到哪个表
    }
    """
    data = request.get_json()
    if not data or not data.get('table_name'):
        return jsonify({"success": False, "error": "table_name 必填"}), 400

    try:
        result = synonym_manager.approve_unmatched_term(
            term_id, data['table_name'],
            reviewed_by=data.get('reviewed_by', 'admin')
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/unmatched/<int:term_id>/reject', methods=['POST'])
def reject_unmatched(term_id):
    """拒绝未匹配词"""
    try:
        result = synonym_manager.reject_unmatched_term(term_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/unmatched/<int:term_id>/ignore', methods=['POST'])
def ignore_unmatched(term_id):
    """忽略未匹配词"""
    try:
        result = synonym_manager.ignore_unmatched_term(term_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==============================================================
# 审计日志
# ==============================================================

@bp.route('/audit-log', methods=['GET'])
def get_audit_log():
    """
    获取同义词操作审计日志

    查询参数: ?limit=50
    """
    limit = int(request.args.get('limit', 50))
    data = synonym_manager.get_audit_log(limit)
    return jsonify({"success": True, "data": data, "total": len(data)})
