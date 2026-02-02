"""
应用初始化模块
"""
from flask import Flask
from flask_cors import CORS
import logging
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
    
    # 启用 CORS - 允许所有来源（开发环境）
    # 生产环境应该限制为特定域名
    if app.config.get('ENV') == 'production':
        # 生产环境：仅允许特定域名
        CORS(app, resources={
            r"/api/*": {
                "origins": [
                    "https://bolt.new",
                    "https://*.bolt.new",
                    "https://*.local-credentialless.webcontainer-api.io",
                    "https://*.webcontainer-api.io",
                ],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"],
                "supports_credentials": True
            }
        })
    else:
        # 开发环境：允许所有来源
        CORS(app, resources={
            r"/api/*": {
                "origins": "*",
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"]
            }
        })
    
    # 设置日志
    setup_logging()
    
    # 注册蓝图
    register_blueprints(app)
    
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
    from app.routes import query_routes
    
    app.register_blueprint(query_routes.bp)
