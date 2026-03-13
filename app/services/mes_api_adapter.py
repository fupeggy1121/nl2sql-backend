"""
MES API Adapter — 执行层组件一：API 适配器

职责：
  1. 从 mapping_prod.json 的 api_bindings 段读取服务绑定配置
  2. 将 TTL transformationLogic 中的 CALL apiBinding 指令解析为真实 HTTP 调用
  3. 将响应字段按 response_mapping 规则映射到 $var 变量
  4. 统一异常处理，向上层暴露 MESAPIError

用法:
    adapter = MESAPIAdapter()
    result = adapter.call("MES_CORE_SERVICE.executeSplitAction", {
        "parentLotId": "LOT-001",
        "splitWaferList": ["W001", "W002"]
    })
    # result = {"$newId": "LOT-001-S1", "_raw": {...}}
"""

import json
import logging
import re
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class MESAPIError(Exception):
    """MES API 调用错误"""
    def __init__(self, binding_name: str, message: str, status_code: int = 0, raw: Any = None):
        self.binding_name = binding_name
        self.status_code = status_code
        self.raw = raw
        super().__init__(f"[{binding_name}] {message}")


class MESAPIAdapter:
    """MES 外部服务 API 适配器"""

    def __init__(self, mapping_path: Optional[str] = None):
        if mapping_path is None:
            import os
            mapping_path = os.path.join(
                os.path.dirname(__file__), "..", "ontology", "data", "mapping_prod.json"
            )
        self._bindings: Dict[str, Dict] = {}
        self._load_bindings(mapping_path)

    def _load_bindings(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            self._bindings = mapping.get("api_bindings", {})
            logger.info(f"[mes_api_adapter] Loaded {len(self._bindings)} API bindings")
        except Exception as e:
            logger.error(f"[mes_api_adapter] Failed to load api_bindings: {e}")
            self._bindings = {}

    def get_binding(self, binding_name: str) -> Dict:
        """获取指定服务绑定配置，不存在则抛出"""
        cfg = self._bindings.get(binding_name)
        if not cfg:
            raise MESAPIError(binding_name, f"未找到 api_binding 配置，请在 mapping_prod.json api_bindings 中维护")
        return cfg

    def call(self, binding_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 API 调用并返回变量映射结果。

        Args:
            binding_name: TTL apiBinding 值，如 "MES_CORE_SERVICE.executeSplitAction"
            params: inputSchema 中定义的入参 dict，如 {"parentLotId": "...", "splitWaferList": [...]}

        Returns:
            {"$newId": "LOT-001-S1", "_raw": <原始响应体>}
            键名来自 response_mapping 配置。
        """
        cfg = self.get_binding(binding_name)
        url = cfg["url"]
        method = cfg.get("method", "POST").upper()
        timeout = cfg.get("timeout_seconds", 30)
        auth_header = cfg.get("auth")

        # 构建请求体：按 request_mapping 重命名字段
        request_mapping = cfg.get("request_mapping", {})
        body = {}
        for target_key, source_path in request_mapping.items():
            # source_path 形如 "$.parentLotId"
            source_key = source_path.lstrip("$.")
            if source_key in params:
                body[target_key] = params[source_key]

        headers = {"Content-Type": "application/json"}
        if auth_header:
            headers["Authorization"] = auth_header

        logger.info(
            f"[mes_api_adapter] CALL {binding_name} → {method} {url}, body={json.dumps(body)[:200]}"
        )

        try:
            # trust_env=False：对 localhost 接口绕过系统代理（如 Clash/Shadowrocket），
            # 避免本机 MES 服务请求被代理转发后返回 502
            with httpx.Client(timeout=timeout, trust_env=False) as client:
                if method == "POST":
                    resp = client.post(url, json=body, headers=headers)
                elif method == "PUT":
                    resp = client.put(url, json=body, headers=headers)
                elif method == "GET":
                    resp = client.get(url, params=body, headers=headers)
                else:
                    raise MESAPIError(binding_name, f"不支持的 HTTP 方法: {method}")
        except httpx.ConnectError as e:
            raise MESAPIError(
                binding_name,
                f"无法连接 MES 服务 {url}（Connection refused / 服务未启动）: {e}",
            )
        except httpx.TimeoutException:
            raise MESAPIError(binding_name, f"API 调用超时（{timeout}s）: {url}")
        except httpx.RequestError as e:
            raise MESAPIError(binding_name, f"网络错误: {e}")

        if resp.status_code >= 400:
            raise MESAPIError(
                binding_name,
                f"HTTP {resp.status_code}：{resp.text[:200]}",
                status_code=resp.status_code,
                raw=resp.text,
            )

        try:
            raw_body = resp.json()
        except Exception:
            raw_body = {"text": resp.text}

        # 提取 response_mapping 中定义的变量
        response_mapping = cfg.get("response_mapping", {})
        result: Dict[str, Any] = {"_raw": raw_body}
        for var_name, json_path in response_mapping.items():
            val = self._extract_jsonpath(raw_body, json_path)
            result[var_name] = val

        logger.info(
            f"[mes_api_adapter] CALL {binding_name} → 成功, vars={[k for k in result if k != '_raw']}"
        )
        return result

    @staticmethod
    def _extract_jsonpath(data: Any, path: str) -> Any:
        """
        简单 JSONPath 提取（只支持 $.a.b.c 形式，不支持数组/过滤器）。
        """
        if not path.startswith("$"):
            return None
        keys = path.lstrip("$.").split(".")
        val = data
        for key in keys:
            if isinstance(val, dict):
                val = val.get(key)
            else:
                return None
        return val


# 全局单例（延迟初始化）
_adapter_instance: Optional[MESAPIAdapter] = None


def get_mes_api_adapter() -> MESAPIAdapter:
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = MESAPIAdapter()
    return _adapter_instance
