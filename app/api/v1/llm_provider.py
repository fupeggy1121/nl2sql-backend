"""
LLM Provider 管理 API
支持查询、切换、测试多个 LLM Provider。
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/llm", tags=["LLM Provider"])


# ── 请求 / 响应模型 ──────────────────────────────────────
class SwitchRequest(BaseModel):
    provider: str  # e.g. "deepseek", "glm"


class SwitchResponse(BaseModel):
    message: str
    active_provider: str


class TestRequest(BaseModel):
    provider: str | None = None  # 为空则测试当前激活的 provider
    prompt: str = "请用一句话介绍你自己。"


# ── 路由 ──────────────────────────────────────────────────

@router.get("/providers", summary="列出所有已注册的 LLM Provider")
async def list_providers():
    """
    返回所有已注册的 Provider 及其配置状态。
    - configured: 是否已填写 API Key
    - active: 是否为当前激活的 Provider
    """
    from app.agent.llm import list_providers as agent_list
    return {"providers": agent_list()}


@router.post("/switch", summary="切换当前激活的 LLM Provider", response_model=SwitchResponse)
async def switch_provider(body: SwitchRequest):
    """
    运行时切换 Agent 层 与 Service 层 使用的 LLM Provider。
    切换仅影响当前进程，不修改 .env 文件。
    """
    name = body.provider.lower()

    try:
        # 同时切换两个层
        from app.agent.llm import set_active_provider as agent_switch
        from app.services.llm_provider import set_active_provider as svc_switch

        agent_switch(name)
        svc_switch(name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(f"LLM provider switched to: {name}")
    return SwitchResponse(message=f"Switched to {name}", active_provider=name)


@router.post("/test", summary="测试指定 / 当前 Provider 的连通性")
async def test_provider(body: TestRequest):
    """
    向指定 Provider 发送一条简单 prompt，验证 API Key 和网络连通性。
    """
    from app.services.llm_provider import get_llm_provider

    try:
        provider = get_llm_provider(body.provider)
        result = provider.generate(body.prompt)
        return {
            "success": True,
            "provider": provider.provider_name,
            "model": provider.model,
            "response": result,
        }
    except Exception as e:
        logger.error(f"Provider test failed: {e}")
        return {
            "success": False,
            "provider": body.provider or "(active)",
            "error": str(e),
        }
