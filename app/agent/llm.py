"""
LLM Client 适配层 — 多 Provider 注册表
支持 DeepSeek / GLM (智谱) 等 OpenAI 兼容 API，可运行时切换。
"""

import os
import logging
from typing import Optional, Dict
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# ── Provider 注册表 ──────────────────────────────────────
# 每个 provider 定义 env 变量前缀，运行时读取对应环境变量
LLM_PROVIDER_REGISTRY: Dict[str, dict] = {
    "deepseek": {
        "env_prefix": "DEEPSEEK",
        "default_base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
    },
    "glm": {
        "env_prefix": "GLM",
        "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
    },
}

# 运行时 LLM 实例缓存  { provider_name: ChatOpenAI }
_llm_cache: Dict[str, ChatOpenAI] = {}

# 当前激活的 provider（默认跟随 LLM_PROVIDER 环境变量）
_active_provider: Optional[str] = None


def _resolve_active_provider() -> str:
    """返回当前激活的 provider 名称"""
    global _active_provider
    if _active_provider:
        return _active_provider
    return os.getenv("LLM_PROVIDER", "deepseek").lower()


def set_active_provider(name: str) -> None:
    """运行时切换 provider"""
    global _active_provider
    name = name.lower()
    if name not in LLM_PROVIDER_REGISTRY:
        raise ValueError(
            f"Unknown provider '{name}'. Available: {list(LLM_PROVIDER_REGISTRY.keys())}"
        )
    _active_provider = name
    logger.info(f"Active LLM provider switched to: {name}")


def get_active_provider() -> str:
    """获取当前激活的 provider 名称"""
    return _resolve_active_provider()


def list_providers() -> list:
    """列出所有已注册且配置了 API Key 的 provider"""
    result = []
    for name, cfg in LLM_PROVIDER_REGISTRY.items():
        prefix = cfg["env_prefix"]
        api_key = os.getenv(f"{prefix}_API_KEY", "")
        result.append({
            "name": name,
            "configured": bool(api_key),
            "model": os.getenv(f"{prefix}_MODEL", cfg["default_model"]),
            "base_url": os.getenv(f"{prefix}_BASE_URL", cfg["default_base_url"]),
            "active": name == _resolve_active_provider(),
        })
    return result


def get_llm(provider: Optional[str] = None) -> ChatOpenAI:
    """
    获取指定 / 当前激活 provider 的 LangChain ChatOpenAI 实例。
    实例按 provider 缓存，切换 provider 不会重建旧实例。
    """
    name = (provider or _resolve_active_provider()).lower()

    if name in _llm_cache:
        return _llm_cache[name]

    cfg = LLM_PROVIDER_REGISTRY.get(name)
    if not cfg:
        raise ValueError(
            f"Unknown provider '{name}'. Available: {list(LLM_PROVIDER_REGISTRY.keys())}"
        )

    prefix = cfg["env_prefix"]
    api_key = os.getenv(f"{prefix}_API_KEY", "")
    base_url = os.getenv(f"{prefix}_BASE_URL", cfg["default_base_url"])
    model = os.getenv(f"{prefix}_MODEL", cfg["default_model"])

    if not api_key:
        logger.warning(f"{prefix}_API_KEY not configured, LLM calls will fail")

    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.2,
        max_tokens=2000,
        request_timeout=30,
    )
    _llm_cache[name] = llm
    logger.info(f"LLM initialized: provider={name}, model={model}, base_url={base_url}")
    return llm


# ── 向后兼容别名 ──
def get_agent_llm() -> ChatOpenAI:
    """向后兼容：等价于 get_llm()"""
    return get_llm()
