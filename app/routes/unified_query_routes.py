"""
统一查询API路由
支持前端的完整查询流程：意图识别 -> SQL生成 -> 执行 -> 结果返回
"""

import logging
from flask import Blueprint, request, jsonify
from app.services.unified_query_service import (
    get_unified_query_service,
    QueryPlan,
    QueryResult
)

logger = logging.getLogger(__name__)

bp = Blueprint('unified_query', __name__, url_prefix='/api/query/unified')


@bp.route('/process', methods=['POST'])
def process_query():
    """
    处理自然语言查询
    
    请求体:
    {
        "natural_language": "查询今天的OEE数据",
        "execution_mode": "explain",  // "explain" 或 "execute"
        "user_context": {...}  // 可选
    }
    
    响应:
    {
        "success": true,
        "query_plan": {...},
        "query_result": {...} // 如果 execution_mode 为 execute
    }
    """
    try:
        import asyncio
        data = request.get_json()
        natural_language = data.get('natural_language', '').strip()
        execution_mode = data.get('execution_mode', 'explain')
        user_context = data.get('user_context')

        if not natural_language:
            return jsonify({
                "success": False,
                "error": "natural_language 不能为空"
            }), 400

        # 验证execution_mode
        if execution_mode not in ['explain', 'execute']:
            execution_mode = 'explain'

        service = get_unified_query_service()
        query_plan, query_result = asyncio.run(service.process_natural_language_query(
            natural_language,
            user_context,
            execution_mode
        ))

        response = {
            "success": True,
            "query_plan": query_plan.to_dict() if query_plan else None,
            "query_result": query_result.to_dict() if query_result else None
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/explain', methods=['POST'])
def explain_query():
    """
    只获取SQL解释（不执行）
    
    请求体:
    {
        "natural_language": "查询今天的OEE数据"
    }
    
    响应包含:
    - generated_sql: 生成的SQL
    - explanation: SQL的人类可读解释
    - suggested_variants: 建议的SQL变体
    """
    try:
        import asyncio
        data = request.get_json()
        natural_language = data.get('natural_language', '').strip()

        if not natural_language:
            return jsonify({
                "success": False,
                "error": "natural_language 不能为空"
            }), 400

        service = get_unified_query_service()
        query_plan, _ = asyncio.run(service.process_natural_language_query(
            natural_language,
            execution_mode='explain'
        ))

        return jsonify({
            "success": True,
            "query_plan": query_plan.to_dict() if query_plan else None
        }), 200

    except Exception as e:
        logger.error(f"Error explaining query: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/execute', methods=['POST'])
def execute_query():
    """
    执行已批准的SQL查询
    
    请求体:
    {
        "sql": "SELECT * FROM oee_records WHERE ...",
        "query_intent": {...}  // 可选，用于优化结果展示
    }
    
    响应:
    {
        "success": true,
        "data": [...],
        "rows_count": 10,
        "summary": "查询成功",
        "visualization_type": "table"
    }
    """
    try:
        import asyncio
        data = request.get_json()
        sql_query = data.get('sql', '').strip()
        query_intent_data = data.get('query_intent')

        if not sql_query:
            return jsonify({
                "success": False,
                "error": "sql 不能为空"
            }), 400

        # 重建QueryIntent对象（如果提供了）
        query_intent = None
        if query_intent_data:
            from app.services.unified_query_service import QueryIntent, QueryType
            try:
                query_intent = QueryIntent(
                    query_type=QueryType(query_intent_data.get('query_type', 'unknown')),
                    natural_language=query_intent_data.get('natural_language', ''),
                    metric=query_intent_data.get('metric'),
                    time_range=query_intent_data.get('time_range'),
                    equipment=query_intent_data.get('equipment'),
                    shift=query_intent_data.get('shift'),
                    table_name=query_intent_data.get('table_name'),
                    comparison=query_intent_data.get('comparison', False)
                )
            except Exception as e:
                logger.warning(f"Could not rebuild query intent: {e}")

        service = get_unified_query_service()
        query_result = asyncio.run(service.execute_approved_query(sql_query, query_intent))

        return jsonify({
            "success": query_result.success,
            "query_result": query_result.to_dict()
        }), 200 if query_result.success else 400

    except Exception as e:
        logger.error(f"Error executing query: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/suggest-variants', methods=['POST'])
def suggest_sql_variants():
    """
    为给定的查询建议SQL变体
    
    请求体:
    {
        "natural_language": "查询OEE数据",
        "base_sql": "SELECT * FROM oee_records"
    }
    
    响应:
    {
        "success": true,
        "variants": [
            {"sql": "...", "description": "..."},
            ...
        ]
    }
    """
    try:
        data = request.get_json()
        natural_language = data.get('natural_language', '').strip()
        base_sql = data.get('base_sql', '').strip()

        if not natural_language or not base_sql:
            return jsonify({
                "success": False,
                "error": "natural_language 和 base_sql 不能为空"
            }), 400

        # 这里可以调用LLM生成变体
        # 目前返回基础建议
        service = get_unified_query_service()
        
        variants = [
            {
                "sql": base_sql,
                "description": "原始查询",
                "confidence": 0.85
            }
        ]

        return jsonify({
            "success": True,
            "variants": variants
        }), 200

    except Exception as e:
        logger.error(f"Error suggesting variants: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/validate-sql', methods=['POST'])
def validate_sql():
    """
    验证SQL语法和合理性
    
    请求体:
    {
        "sql": "SELECT * FROM oee_records WHERE date > '2026-01-01'"
    }
    
    响应:
    {
        "success": true,
        "is_valid": true,
        "errors": [],
        "warnings": []
    }
    """
    try:
        data = request.get_json()
        sql_query = data.get('sql', '').strip()

        if not sql_query:
            return jsonify({
                "success": False,
                "error": "sql 不能为空"
            }), 400

        # 基础SQL验证
        is_valid = True
        errors = []
        warnings = []

        # 检查是否是SELECT查询
        if not sql_query.upper().startswith('SELECT'):
            is_valid = False
            errors.append("仅支持SELECT查询")

        # 检查是否包含LIMIT
        if 'LIMIT' not in sql_query.upper():
            warnings.append("建议添加LIMIT子句以限制返回行数")

        return jsonify({
            "success": True,
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings
        }), 200

    except Exception as e:
        logger.error(f"Error validating SQL: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/execution-history', methods=['GET'])
def get_execution_history():
    """
    获取查询执行历史
    
    查询参数:
    - limit: 返回记录数（默认20）
    - offset: 偏移量（默认0）
    
    响应:
    {
        "success": true,
        "history": [
            {
                "id": "...",
                "natural_language": "...",
                "sql": "...",
                "executed_at": "...",
                "rows_count": 10
            },
            ...
        ],
        "total": 100
    }
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        offset = request.args.get('offset', 0, type=int)

        # 这里可以从数据库获取执行历史
        # 目前返回空列表
        return jsonify({
            "success": True,
            "history": [],
            "total": 0
        }), 200

    except Exception as e:
        logger.error(f"Error getting execution history: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/query-recommendations', methods=['GET'])
def get_query_recommendations():
    """
    获取常用查询建议
    
    响应:
    {
        "success": true,
        "recommendations": [
            {
                "title": "今天的OEE趋势",
                "natural_language": "显示今天各小时的OEE趋势",
                "category": "metric"
            },
            ...
        ]
    }
    """
    try:
        recommendations = [
            {
                "title": "查看今天的OEE",
                "natural_language": "查询今天各设备的OEE数据",
                "category": "metric",
                "icon": "chart"
            },
            {
                "title": "对比设备效率",
                "natural_language": "对比本周所有设备的效率差异",
                "category": "comparison",
                "icon": "compare"
            },
            {
                "title": "查询停机时间",
                "natural_language": "查询本月的设备停机时间统计",
                "category": "metric",
                "icon": "alert"
            },
            {
                "title": "产品质量分析",
                "natural_language": "分析最近30天的产品良率趋势",
                "category": "trend",
                "icon": "trend"
            }
        ]

        return jsonify({
            "success": True,
            "recommendations": recommendations
        }), 200

    except Exception as e:
        logger.error(f"Error getting recommendations: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
