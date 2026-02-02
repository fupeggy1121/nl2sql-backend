"""
查询路由
处理自然语言查询请求 - 支持 Supabase 和本地数据库
"""
from flask import Blueprint, request, jsonify
from app.services.nl2sql import NL2SQLConverter
from app.services.query_executor import QueryExecutor
import logging

bp = Blueprint('query', __name__, url_prefix='/api/query')
logger = logging.getLogger(__name__)

# 初始化服务（延迟加载 Supabase，避免启动时连接失败）
converter = NL2SQLConverter()
executor = QueryExecutor()
supabase = None  # 延迟初始化

def get_supabase():
    """获取或初始化 Supabase 客户端"""
    global supabase
    if supabase is None:
        from app.services.supabase_client import get_supabase_client
        supabase = get_supabase_client()
    return supabase

@bp.route('/nl-to-sql', methods=['POST'])
def convert_nl_to_sql():
    """
    将自然语言转换为 SQL
    
    请求体:
        {
            "natural_language": "查询所有用户"
        }
    
    返回:
        {
            "success": true,
            "sql": "SELECT * FROM users",
            "message": "转换成功"
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'natural_language' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: natural_language'
            }), 400
        
        natural_language = data['natural_language']
        
        if not natural_language.strip():
            return jsonify({
                'success': False,
                'error': 'natural_language cannot be empty'
            }), 400
        
        # 转换为 SQL
        sql = converter.convert(natural_language)
        
        if sql is None:
            return jsonify({
                'success': False,
                'error': 'Failed to convert natural language to SQL'
            }), 500
        
        return jsonify({
            'success': True,
            'sql': sql,
            'natural_language': natural_language,
            'message': 'Conversion successful'
        }), 200
        
    except Exception as e:
        logger.error(f"Error in convert_nl_to_sql: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/execute', methods=['POST'])
def execute_query():
    """
    执行 SQL 查询
    
    请求体:
        {
            "sql": "SELECT * FROM users LIMIT 10"
        }
    
    返回:
        {
            "success": true,
            "data": [...],
            "count": 10,
            "columns": ["id", "name", "email"]
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'sql' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: sql'
            }), 400
        
        sql = data['sql'].strip()
        
        if not sql:
            return jsonify({
                'success': False,
                'error': 'SQL cannot be empty'
            }), 400
        
        # 执行查询
        result = executor.execute_query(sql)
        
        return jsonify(result), 200 if result['success'] else 500
        
    except Exception as e:
        logger.error(f"Error in execute_query: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/nl-execute', methods=['POST'])
def nl_execute():
    """
    从自然语言直接执行查询
    
    请求体:
        {
            "natural_language": "查询所有用户"
        }
    
    返回:
        {
            "success": true,
            "sql": "SELECT * FROM users",
            "data": [...],
            "count": 10
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'natural_language' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: natural_language'
            }), 400
        
        natural_language = data['natural_language'].strip()
        
        if not natural_language:
            return jsonify({
                'success': False,
                'error': 'natural_language cannot be empty'
            }), 400
        
        # 第一步：转换为 SQL
        sql = converter.convert(natural_language)
        
        if sql is None:
            return jsonify({
                'success': False,
                'error': 'Failed to convert natural language to SQL'
            }), 500
        
        # 第二步：执行查询
        result = executor.execute_query(sql)
        
        # 添加生成的 SQL 信息
        result['sql'] = sql
        
        return jsonify(result), 200 if result['success'] else 500
        
    except Exception as e:
        logger.error(f"Error in nl_execute: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/health', methods=['GET'])
def health_check():
    """
    健康检查端点 - 返回详细诊断信息
    """
    import os
    
    # 获取环境变量
    supabase_url = os.getenv('SUPABASE_URL', 'NOT SET')
    supabase_key = os.getenv('SUPABASE_ANON_KEY', 'NOT SET')
    
    db_connected = False
    db_status = 'disconnected'
    db_error = None
    
    # 诊断信息 - 始终显示环境变量状态
    diagnosis = {
        'supabase_url_set': 'YES' if supabase_url != 'NOT SET' else 'NO',
        'supabase_key_set': 'YES' if supabase_key != 'NOT SET' else 'NO',
    }
    
    # 如果两个都设置了，尝试连接并显示错误
    if supabase_url != 'NOT SET' and supabase_key != 'NOT SET':
        diagnosis.update({
            'supabase_url_preview': f"{supabase_url[:30]}..." if len(supabase_url) > 30 else supabase_url,
            'supabase_key_length': len(supabase_key),
        })
        
        try:
            sb = get_supabase()
            if sb is None:
                diagnosis['connection_status'] = 'get_supabase() returned None'
                db_error = 'SupabaseClient is None'
            elif sb.client:
                # 如果客户端成功初始化，就认为已连接
                # （不需要进行额外的查询测试，这可能失败如果表不存在）
                db_connected = True
                db_status = 'connected'
                diagnosis['connection_status'] = 'Successfully connected to Supabase'
                logger.info(f"✅ Supabase client is connected")
            elif sb.init_error:
                # 优先返回初始化错误
                diagnosis['connection_status'] = f'Init error: {sb.init_error}'
                db_error = sb.init_error
            else:
                db_status = 'disconnected'
                diagnosis['connection_status'] = 'Client is None and no init_error set'
        except Exception as e:
            db_status = 'disconnected'
            db_error = str(e)
            diagnosis['connection_status'] = f'Error: {str(e)[:100]}'
            logger.error(f"Health check connection error: {str(e)}")
    else:
        diagnosis['warning'] = 'SUPABASE_URL or SUPABASE_ANON_KEY not set'
    
    # 如果有数据库直接连接信息，也显示
    if os.getenv('DB_HOST'):
        diagnosis.update({
            'db_host': os.getenv('DB_HOST', 'NOT SET'),
            'db_port': os.getenv('DB_PORT', 'NOT SET'),
            'db_user': os.getenv('DB_USER', 'NOT SET'),
            'db_name': os.getenv('DB_NAME', 'NOT SET'),
        })
    
    return jsonify({
        'status': 'healthy',
        'service': 'NL2SQL Report Backend',
        'supabase': db_status,
        'error': db_error,
        'diagnosis': diagnosis
    }), 200

@bp.route('/nl-execute-supabase', methods=['POST'])
def nl_execute_supabase():
    """
    执行 Supabase 查询 - 自然语言转 SQL 并执行
    
    请求体:
        {
            "natural_language": "查询所有用户"
        }
    
    返回:
        {
            "success": true,
            "sql": "SELECT * FROM users",
            "data": [...],
            "message": "..."
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'natural_language' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: natural_language'
            }), 400
        
        natural_language = data['natural_language']
        
        if not natural_language.strip():
            return jsonify({
                'success': False,
                'error': 'natural_language cannot be empty'
            }), 400
        
        # 第一步：转换为 SQL
        sql = converter.convert(natural_language)
        
        if sql is None:
            return jsonify({
                'success': False,
                'error': 'Failed to convert natural language to SQL'
            }), 500
        
        # 第二步：检查 Supabase 连接
        sb = get_supabase()
        if not sb.is_connected():
            return jsonify({
                'success': False,
                'error': 'Supabase database connection failed. Please check your configuration.',
                'sql': sql
            }), 500
        
        # 第三步：执行查询
        result = sb.execute_query(sql)
        result['sql'] = sql
        
        return jsonify(result), 200 if result['success'] else 400
        
    except Exception as e:
        logger.error(f"Error in nl_execute_supabase: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/supabase/schema', methods=['GET'])
def get_supabase_schema():
    """获取 Supabase 数据库 schema 信息"""
    try:
        sb = get_supabase()
        table_name = request.args.get('table')
        result = sb.get_schema_info(table_name)
        return jsonify(result), 200 if result['success'] else 400
    except Exception as e:
        logger.error(f"Error getting schema: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/supabase/connection', methods=['GET'])
def check_supabase_connection():
    """检查 Supabase 连接状态"""
    try:
        sb = get_supabase()
        is_connected = sb.is_connected()
        schema_info = sb.get_schema_info() if is_connected else {}
        
        return jsonify({
            'success': True,
            'connected': is_connected,
            'tables': schema_info.get('data', []) if is_connected else [],
            'host': sb.host,
            'database': sb.database
        }), 200
    except Exception as e:
        logger.error(f"Error checking connection: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
