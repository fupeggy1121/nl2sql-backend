"""
流式 SSE 端点错误消息目录 — Phase 2
=====================================
定义 17 种错误类型，每种附带：
  - 用户友好中文描述
  - 可操作建议
  - 英文技术标识（用于日志 / 国际化）

使用方式（在 chat.py 中）：
    from app.utils.stream_errors import StreamError, stream_error_response

    yield stream_error_response(StreamError.DB_CONNECTION, detail="host unreachable")
"""

from __future__ import annotations
import json
import traceback
from enum import Enum
from typing import Any


# ──────────────────────────────────────────────
# 错误类型枚举
# ──────────────────────────────────────────────

class StreamError(str, Enum):
    # 网络 / 连接层
    NETWORK_TIMEOUT      = "NETWORK_TIMEOUT"       # 请求超时
    NETWORK_UNREACHABLE  = "NETWORK_UNREACHABLE"    # 网络不可达
    CONNECTION_LOST      = "CONNECTION_LOST"        # 连接中断

    # HTTP 层
    HTTP_BAD_REQUEST     = "HTTP_BAD_REQUEST"       # 400
    HTTP_UNAUTHORIZED    = "HTTP_UNAUTHORIZED"      # 401
    HTTP_FORBIDDEN       = "HTTP_FORBIDDEN"         # 403
    HTTP_NOT_FOUND       = "HTTP_NOT_FOUND"         # 404
    HTTP_RATE_LIMITED    = "HTTP_RATE_LIMITED"      # 429
    HTTP_SERVER_ERROR    = "HTTP_SERVER_ERROR"      # 5xx

    # LLM 层
    LLM_UNAVAILABLE      = "LLM_UNAVAILABLE"        # LLM 服务不可用
    LLM_QUOTA_EXCEEDED   = "LLM_QUOTA_EXCEEDED"     # 配额耗尽
    SQL_GENERATION_FAILED = "SQL_GENERATION_FAILED" # SQL 生成失败

    # 数据库层
    DB_CONNECTION        = "DB_CONNECTION"          # 数据库连接失败
    DB_QUERY_FAILED      = "DB_QUERY_FAILED"        # SQL 执行错误
    DB_PERMISSION        = "DB_PERMISSION"          # 无权限

    # 应用层
    INTENT_AMBIGUOUS     = "INTENT_AMBIGUOUS"       # 意图不明确
    STREAM_TERMINATED    = "STREAM_TERMINATED"      # 流异常终止


# ──────────────────────────────────────────────
# 错误消息字典
# ──────────────────────────────────────────────

_MESSAGES: dict[StreamError, dict[str, str]] = {
    # ── 网络层 ──
    StreamError.NETWORK_TIMEOUT: {
        "title":       "请求超时",
        "description": "服务响应时间过长，请求已超时。",
        "suggestion":  "请稍后重试，或检查网络连接是否稳定。",
        "en_code":     "request_timeout",
    },
    StreamError.NETWORK_UNREACHABLE: {
        "title":       "网络不可达",
        "description": "无法连接到后端服务。",
        "suggestion":  "请检查网络设置，确认后端服务已启动（默认端口 8000）。",
        "en_code":     "network_unreachable",
    },
    StreamError.CONNECTION_LOST: {
        "title":       "连接中断",
        "description": "与服务的连接在处理过程中意外断开。",
        "suggestion":  "请重新发送请求；如果问题持续，请联系系统管理员。",
        "en_code":     "connection_lost",
    },

    # ── HTTP 层 ──
    StreamError.HTTP_BAD_REQUEST: {
        "title":       "请求格式有误",
        "description": "服务器无法理解请求内容（400）。",
        "suggestion":  "请检查输入内容，避免包含特殊字符后重试。",
        "en_code":     "http_400",
    },
    StreamError.HTTP_UNAUTHORIZED: {
        "title":       "未授权访问",
        "description": "当前会话已过期或未登录（401）。",
        "suggestion":  "请刷新页面重新登录后再试。",
        "en_code":     "http_401",
    },
    StreamError.HTTP_FORBIDDEN: {
        "title":       "无访问权限",
        "description": "当前账户无权执行该操作（403）。",
        "suggestion":  "请联系管理员获取相应权限。",
        "en_code":     "http_403",
    },
    StreamError.HTTP_NOT_FOUND: {
        "title":       "接口不存在",
        "description": "请求的 API 路径不存在（404）。",
        "suggestion":  "请联系技术支持，可能是版本不匹配。",
        "en_code":     "http_404",
    },
    StreamError.HTTP_RATE_LIMITED: {
        "title":       "请求过于频繁",
        "description": "短时间内请求次数过多，已被限流（429）。",
        "suggestion":  "请等待 1 分钟后重试。",
        "en_code":     "http_429",
    },
    StreamError.HTTP_SERVER_ERROR: {
        "title":       "服务器内部错误",
        "description": "后端服务处理时发生意外错误（5xx）。",
        "suggestion":  "请稍后重试；若持续出现，请记录操作步骤并联系技术支持。",
        "en_code":     "http_5xx",
    },

    # ── LLM 层 ──
    StreamError.LLM_UNAVAILABLE: {
        "title":       "AI 服务暂时不可用",
        "description": "语言模型服务（DeepSeek/OpenAI）当前无法响应。",
        "suggestion":  "请稍等 1-2 分钟后重试；如持续失败请联系管理员检查 API Key 配置。",
        "en_code":     "llm_unavailable",
    },
    StreamError.LLM_QUOTA_EXCEEDED: {
        "title":       "AI 服务额度不足",
        "description": "语言模型 API 调用额度已耗尽。",
        "suggestion":  "请联系管理员续充 API 额度。",
        "en_code":     "llm_quota_exceeded",
    },
    StreamError.SQL_GENERATION_FAILED: {
        "title":       "SQL 生成失败",
        "description": "AI 无法将您的问题转换为有效的数据库查询语句。",
        "suggestion":  "请尝试更具体地描述您的需求，例如指明表名、时间范围或具体字段。",
        "en_code":     "sql_generation_failed",
    },

    # ── 数据库层 ──
    StreamError.DB_CONNECTION: {
        "title":       "数据库连接失败",
        "description": "系统无法连接到生产数据库。",
        "suggestion":  "请联系 DBA or 运维人员检查数据库服务状态。",
        "en_code":     "db_connection_failed",
    },
    StreamError.DB_QUERY_FAILED: {
        "title":       "查询执行失败",
        "description": "生成的 SQL 语句在数据库执行时出错。",
        "suggestion":  "您可以在'查询追踪'中查看 SQL 详情并手动修改后重试。",
        "en_code":     "db_query_failed",
    },
    StreamError.DB_PERMISSION: {
        "title":       "数据库权限不足",
        "description": "当前数据库账户无权访问所请求的数据表。",
        "suggestion":  "请联系 DBA 授予相应表的 SELECT 权限。",
        "en_code":     "db_permission_denied",
    },

    # ── 应用层 ──
    StreamError.INTENT_AMBIGUOUS: {
        "title":       "问题描述不够清晰",
        "description": "AI 无法确定您想查询的确切内容。",
        "suggestion":  "请补充更多信息，例如具体站点名称、时间范围、指标类型等。",
        "en_code":     "intent_ambiguous",
    },
    StreamError.STREAM_TERMINATED: {
        "title":       "数据流中断",
        "description": "流式传输在完成前意外终止。",
        "suggestion":  "请重新发送请求；如果问题重复出现，请联系技术支持。",
        "en_code":     "stream_terminated",
    },
}


# ──────────────────────────────────────────────
# 公共 API
# ──────────────────────────────────────────────

def get_error_info(error: StreamError, detail: str | None = None) -> dict[str, Any]:
    """
    返回完整的错误信息字典，可直接序列化为 SSE data 字段。

    结构：
    {
        "error_code": "SQL_GENERATION_FAILED",
        "title":      "SQL 生成失败",
        "description": "...",
        "suggestion":  "...",
        "detail":      "<原始异常信息，仅开发环境>",
        "en_code":     "sql_generation_failed"
    }
    """
    msg = _MESSAGES.get(error, {
        "title": "未知错误",
        "description": "发生了一个未知错误。",
        "suggestion": "请重试或联系技术支持。",
        "en_code": "unknown_error",
    })
    payload: dict[str, Any] = {
        "error_code": error.value,
        **msg,
    }
    if detail:
        payload["detail"] = detail
    return payload


def classify_exception(exc: Exception) -> StreamError:
    """
    根据异常类型自动分类到对应的 StreamError。
    用于 except 块的统一处理。
    """
    import httpx as _httpx  # 避免循环导入

    exc_str = str(exc).lower()
    exc_type = type(exc).__name__

    if isinstance(exc, _httpx.TimeoutException):
        return StreamError.NETWORK_TIMEOUT
    if isinstance(exc, (_httpx.ConnectError, _httpx.NetworkError)):
        return StreamError.NETWORK_UNREACHABLE
    if isinstance(exc, _httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 400:
            return StreamError.HTTP_BAD_REQUEST
        if code == 401:
            return StreamError.HTTP_UNAUTHORIZED
        if code == 403:
            return StreamError.HTTP_FORBIDDEN
        if code == 404:
            return StreamError.HTTP_NOT_FOUND
        if code == 429:
            return StreamError.HTTP_RATE_LIMITED
        return StreamError.HTTP_SERVER_ERROR

    if "quota" in exc_str or "rate limit" in exc_str or "insufficient_quota" in exc_str:
        return StreamError.LLM_QUOTA_EXCEEDED
    if "openai" in exc_str or "deepseek" in exc_str or "llm" in exc_str or "api key" in exc_str:
        return StreamError.LLM_UNAVAILABLE
    if "sql" in exc_str and ("syntax" in exc_str or "invalid" in exc_str or "parse" in exc_str):
        return StreamError.SQL_GENERATION_FAILED
    if "connection refused" in exc_str or "no route to host" in exc_str:
        return StreamError.DB_CONNECTION
    if "permission denied" in exc_str or "access denied" in exc_str:
        return StreamError.DB_PERMISSION
    if "operational error" in exc_str or "programming error" in exc_str:
        return StreamError.DB_QUERY_FAILED

    return StreamError.HTTP_SERVER_ERROR


def stream_error_sse(error: StreamError, detail: str | None = None) -> str:
    """
    返回格式化好的 SSE error 帧字符串，可直接 yield。

    示例输出：
        event: error
        data: {"error_code": "DB_CONNECTION", "title": "数据库连接失败", ...}

    """
    payload = get_error_info(error, detail)
    return f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def format_exception_as_sse(exc: Exception) -> str:
    """
    将任意异常自动分类并格式化为 SSE error 帧。
    推荐在 except Exception as e 块中使用。

    用法：
        try:
            ...
        except Exception as exc:
            yield format_exception_as_sse(exc)
    """
    error_type = classify_exception(exc)
    detail = f"{type(exc).__name__}: {exc}"
    return stream_error_sse(error_type, detail)
