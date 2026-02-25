"""
FastAPI 应用入口 — AI Agent 服务

新的应用入口，替代旧的 Flask app。
保留旧 API 路径兼容层，确保前端零改动。
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# ── 日志配置 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化 Agent"""
    logger.info("Starting AI Agent service...")

    # 预编译 Agent 图（避免首次请求慢）
    from app.agent.graph import get_agent_app
    get_agent_app()
    logger.info("Agent graph compiled and ready")

    yield

    logger.info("AI Agent service shutting down")


def create_fastapi_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="CIM 智能报表 AI Agent",
        description="基于 LangGraph 的 AI Agent 服务，支持自然语言查询、智能报表生成",
        version="2.0.0",
        lifespan=lifespan,
    )

    # ── CORS ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=3600,
    )

    # ── 注册路由 ──
    _register_routes(app)

    return app


def _register_routes(app: FastAPI):
    """注册所有路由"""
    # 新 Agent API
    from app.api.v1.chat import router as chat_router
    app.include_router(chat_router)

    # LLM Provider 管理 API
    from app.api.v1.llm_provider import router as llm_provider_router
    app.include_router(llm_provider_router)

    # 本体语义 API (Phase 4)
    from app.api.v1.ontology import router as ontology_router
    app.include_router(ontology_router)

    # 旧 API 兼容层
    from app.api.compat import router as compat_router
    app.include_router(compat_router)

    # ── 静态文件 & 页面路由 ──
    static_dir = os.path.join(os.path.dirname(__file__), "static")

    @app.get("/viewer")
    async def ontology_viewer():
        """本体可视化查看器"""
        return FileResponse(
            os.path.join(static_dir, "ontology-viewer.html"),
            media_type="text/html",
        )

    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # 健康检查
    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "ai-agent", "version": "2.0.0"}

    # ── B2: 缓存统计 & 清理 ──
    @app.get("/cache/stats")
    async def cache_stats():
        """返回各级缓存的命中率统计"""
        from app.agent.cache import get_cache_stats
        return get_cache_stats()

    @app.post("/cache/clear")
    async def cache_clear():
        """手动清空所有缓存（热更新配置后调用）"""
        from app.agent.cache import intent_cache, semantic_cache, result_cache
        intent_cache.clear()
        semantic_cache.clear()
        result_cache.clear()
        return {"message": "All caches cleared"}


# ── 全局 app 实例（供 uvicorn 使用）──
app = create_fastapi_app()
