"""
LLM 提供者抽象层
支持多个 LLM 服务商（DeepSeek、GLM/智谱、OpenAI 等）
运行时可切换，所有 OpenAI 兼容 API 共享同一套调用逻辑。
"""
import logging
import os
from typing import Optional, Dict
import requests

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# 基类
# ──────────────────────────────────────────────────────────
class LLMProvider:
    """LLM 提供者基类"""

    # 子类需设置
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    provider_name: str = "base"

    def convert_nl_to_sql(self, natural_language: str, schema_info: str = "") -> Optional[str]:
        raise NotImplementedError

    def generate(self, prompt: str, system_prompt: str = "You are an expert assistant.") -> str:
        raise NotImplementedError


# ──────────────────────────────────────────────────────────
# 通用 OpenAI 兼容 Provider（DeepSeek / GLM 共用）
# ──────────────────────────────────────────────────────────
class OpenAICompatProvider(LLMProvider):
    """
    适用于所有 OpenAI 兼容 API 的通用 Provider。
    DeepSeek、GLM (智谱)、Moonshot 等均可直接使用。
    """

    def __init__(self, provider_name: str, api_key: str, base_url: str, model: str):
        self.provider_name = provider_name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

        if not self.api_key:
            logger.warning(f"{provider_name} API key not configured")

    # ── 通用生成 ──
    def generate(self, prompt: str, system_prompt: str = "You are an expert assistant for intent recognition.") -> str:
        if not self.api_key:
            raise RuntimeError(f"{self.provider_name} API key not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 1000,
        }

        logger.info(f"Calling {self.provider_name} API (generate) model={self.model}")
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                if "choices" in data and data["choices"]:
                    content = data["choices"][0]["message"]["content"].strip()
                    logger.info(f"{self.provider_name} generate OK: {content[:80]}...")
                    return content
                raise RuntimeError(f"Invalid response from {self.provider_name} API")
            raise RuntimeError(f"{self.provider_name} API error: {resp.status_code} - {resp.text}")
        except requests.exceptions.Timeout:
            raise RuntimeError(f"{self.provider_name} API timeout")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"{self.provider_name} API request error: {e}")

    # ── NL → SQL ──
    def convert_nl_to_sql(self, natural_language: str, schema_info: str = "") -> Optional[str]:
        if not self.api_key:
            logger.error(f"{self.provider_name} API key not configured")
            return None

        system_prompt = (
            "You are a SQL expert. Convert natural language queries to SQL.\n"
            "Rules:\n"
            "1. Only return the SQL query without any explanation\n"
            "2. The SQL should be valid and executable\n"
            "3. Use appropriate SQL syntax\n"
            "4. Optimize for readability"
        )
        if schema_info:
            system_prompt += f"\n\nDatabase Schema:\n{schema_info}"

        try:
            content = self.generate(
                prompt=f"Convert to SQL: {natural_language}",
                system_prompt=system_prompt,
            )
            logger.info(f"{self.provider_name} NL→SQL OK: {content}")
            return content
        except Exception as e:
            logger.error(f"{self.provider_name} NL→SQL error: {e}")
            return None


# ──────────────────────────────────────────────────────────
# 向后兼容别名（已有代码 import DeepSeekProvider 不会报错）
# ──────────────────────────────────────────────────────────
class DeepSeekProvider(OpenAICompatProvider):
    """DeepSeek 便捷子类，自动读取 DEEPSEEK_* 环境变量"""

    def __init__(self):
        super().__init__(
            provider_name="deepseek",
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        )


class GLMProvider(OpenAICompatProvider):
    """GLM (智谱) 便捷子类，自动读取 GLM_* 环境变量"""

    def __init__(self):
        super().__init__(
            provider_name="glm",
            api_key=os.getenv("GLM_API_KEY", ""),
            base_url=os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
            model=os.getenv("GLM_MODEL", "glm-4-flash"),
        )


class OpenAIProvider(OpenAICompatProvider):
    """OpenAI 便捷子类，自动读取 OPENAI_* 环境变量"""

    def __init__(self):
        super().__init__(
            provider_name="openai",
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
        )


# ──────────────────────────────────────────────────────────
# Provider 注册表 & 工厂
# ──────────────────────────────────────────────────────────
_PROVIDER_MAP: Dict[str, type] = {
    "deepseek": DeepSeekProvider,
    "glm": GLMProvider,
    "openai": OpenAIProvider,
}

# 运行时可切换的 provider 名称
_active_provider: Optional[str] = None


def set_active_provider(name: str) -> None:
    """运行时切换 service 层使用的 LLM provider"""
    global _active_provider
    name = name.lower()
    if name not in _PROVIDER_MAP:
        raise ValueError(f"Unknown provider '{name}'. Available: {list(_PROVIDER_MAP.keys())}")
    _active_provider = name
    logger.info(f"[services] Active LLM provider switched to: {name}")


def get_active_provider_name() -> str:
    """获取当前激活的 provider 名称"""
    if _active_provider:
        return _active_provider
    return os.getenv("LLM_PROVIDER", "deepseek").lower()


def get_llm_provider(provider: Optional[str] = None) -> LLMProvider:
    """
    工厂函数：返回指定 / 当前激活 provider 的实例。

    Args:
        provider: 可选，指定 provider 名称；为 None 时使用当前激活 provider。

    Returns:
        LLMProvider 实例
    """
    name = (provider or get_active_provider_name()).lower()
    cls = _PROVIDER_MAP.get(name)
    if cls is None:
        logger.warning(f"Unknown provider '{name}', falling back to DeepSeek")
        cls = DeepSeekProvider
    logger.info(f"Using {name} as LLM provider")
    return cls()
