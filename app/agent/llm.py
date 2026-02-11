"""
LLM Client 适配层
将现有 DeepSeek API 适配为 LangChain ChatOpenAI 接口。
DeepSeek 兼容 OpenAI API 格式，可直接用 ChatOpenAI + base_url。
"""

import os
import logging
from functools import lru_cache
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_agent_llm() -> ChatOpenAI:
    """
    获取 Agent 使用的 LLM 实例（单例）。
    使用 DeepSeek API（兼容 OpenAI 格式）。
    """
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    if not api_key:
        logger.warning("DEEPSEEK_API_KEY not configured, LLM calls will fail")

    # DeepSeek 兼容 OpenAI API，直接用 ChatOpenAI
    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.2,
        max_tokens=2000,
        request_timeout=30,
    )
    logger.info(f"Agent LLM initialized: model={model}, base_url={base_url}")
    return llm
