"""
统一应用入口

将 FastAPI 应用暴露为模块级 `app` 变量，以兼容各种启动方式:
  1. uvicorn run:app          (直接 ASGI)
  2. gunicorn -k uvicorn.workers.UvicornWorker run:app  (生产推荐)
  3. python run.py             (本地调试)

旧 Flask 应用已废弃，所有 API 均由 FastAPI 提供。
"""
import os

# ── 暴露 FastAPI app（供 gunicorn / uvicorn 直接 import）──
from app.main import app  # noqa: F401

if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv('PORT', 8000))
    uvicorn.run(app, host='0.0.0.0', port=port)
