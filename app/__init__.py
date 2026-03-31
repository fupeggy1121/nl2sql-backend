"""
应用初始化模块
"""
from flask import Flask
from flask_cors import CORS
import logging
import os
from config.config import config

def create_app(config_name='development'):
    """
    应用工厂函数
    
    Args:
        config_name: 配置环境名称
        
    Returns:
        Flask 应用实例
    """
    app = Flask(__name__)
    
    # 加载配置
    app.config.from_object(config[config_name])
    
    # 获取环境变量
    flask_env = os.getenv('FLASK_ENV', 'development')
    
    # 配置 CORS
    # 关键：在生产环境（Render）上，Bolt.new 前端来自 WebContainer
    # 前端源: https://zp1v56uxy8rdx5ypatb0ockcb9tr6a-oci3--5173--31fc58ec.local-credentialless.webcontainer-api.io
    
    # 为了最大程度解决 CORS 问题，在生产环境上也允许 *（所有源）
    # 注意：这会使 supports_credentials=True 不适用（浏览器安全限制）
    # 但这是解决状态显示"❌ 未连接"问题的必要配置
    cors_origins = "*"
    
    # 应用 CORS 中间件 - 必须在蓝图注册前
    # 使用宽松的 CORS 配置确保前端能正确连接
    CORS(app, 
         origins="*",  # 允许所有源
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
         allow_headers=["*"],  # 允许所有请求头
         expose_headers=["*"],  # 暴露所有响应头
         supports_credentials=False,  # 与 origins="*" 配合使用
         max_age=3600,  # 缓存预检结果 1 小时
         send_wildcard=False,
         always_send=True)  # 始终发送 CORS 头，即使请求不是跨域
    
    # 设置日志
    setup_logging()
    
    # 注册蓝图
    register_blueprints(app)
    
    return app
    
    return app

def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def register_blueprints(app):
    """
    注册蓝图

    Args:
        app: Flask 应用实例
    """
    import logging
    log = logging.getLogger(__name__)

    from app.routes import query_routes, schema_routes, unified_query_routes
    app.register_blueprint(query_routes.bp)
    app.register_blueprint(schema_routes.bp)
    app.register_blueprint(unified_query_routes.bp)

    from app.routes import synonym_routes, admin_routes
    app.register_blueprint(synonym_routes.bp)
    app.register_blueprint(admin_routes.bp)

    # 映射字典管理 Blueprint（独立 try/except，防止启动失败影响其他路由）
    try:
        from app.routes import mapping_routes
        app.register_blueprint(mapping_routes.bp)
        log.info("✅ mapping_manager blueprint registered at /api/mapping (%d routes)",
                 sum(1 for r in app.url_map.iter_rules() if '/api/mapping' in r.rule))
    except Exception as exc:  # noqa: BLE001
        log.error("❌ Failed to register mapping_manager blueprint: %s", exc, exc_info=True)

    # 本体建模技能 Blueprint
    try:
        from app.routes import ontology_skill_routes
        app.register_blueprint(ontology_skill_routes.bp)
        log.info("✅ ontology_skill blueprint registered at /api/ontology-skill")
    except Exception as exc:  # noqa: BLE001
        log.error("❌ Failed to register ontology_skill blueprint: %s", exc, exc_info=True)
