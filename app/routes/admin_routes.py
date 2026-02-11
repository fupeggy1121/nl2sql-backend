"""
同义词管理前端页面路由
提供独立的管理界面，不依赖外部前端项目
"""
from flask import Blueprint, send_from_directory
import os

bp = Blueprint('synonym_admin', __name__, url_prefix='/admin')

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')


@bp.route('/synonyms')
def synonym_management_page():
    """同义词管理主页面"""
    return send_from_directory(STATIC_DIR, 'synonym_admin.html')
