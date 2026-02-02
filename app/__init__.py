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
    # 在 Render 上，即使 FLASK_ENV=production，也需要允许跨域请求
    cors_origins = "*"  # 默认允许所有
    
    if flask_env == 'production':
        # 生产环境：允许特定域名（包括 Render 部署的前端和 Bolt.new）
        cors_origins = [
            "https://bolt.new",
            "https://*.bolt.new",
            "https://*.local-credentialless.webcontainer-api.io",
            "https://*.webcontainer-api.io",
            "https://*.netlify.app",
            "https://*.vercel.app",
            "http://localhost:5173",  # 本地开发
            "http://127.0.0.1:5173",
        ]
    
    # 应用 CORS 中间件 - 必须在蓝图注册前
    CORS(app, 
         origins=cors_origins,
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
         allow_headers=["Content-Type", "Authorization"],
         expose_headers=["Content-Type"],
         supports_credentials=True,
         max_age=3600)
    
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
    from app.routes import query_routes
    
    app.register_blueprint(query_routes.bp)
