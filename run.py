"""
应用入口
"""
import os
from app import create_app

# 获取配置环境
config_name = os.getenv('FLASK_ENV', 'development')

# 创建应用
app = create_app(config_name)

# 这个 if 块确保 app 在生产环境（Gunicorn）中也能被访问
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
