"""
AnalysisEngine — 分析引擎核心调度器

统一入口，接收分析请求，调度注册表中的方法执行分析。
被 API 端点和 Analysis Agent 共同调用。
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

import pandas as pd

from app.analytics.models import AnalysisResult
from app.analytics.registry import get_method, has_method, list_methods

logger = logging.getLogger(__name__)

# 单次分析超时保护 (秒)
_ANALYSIS_TIMEOUT = 60


class AnalysisEngine:
    """分析引擎调度器。"""

    @staticmethod
    def run(
        method: str,
        df: pd.DataFrame,
        params: Dict[str, Any] | None = None,
    ) -> AnalysisResult:
        """
        执行指定的分析方法。

        :param method: 注册表中的方法名（如 "descriptive", "spc"）
        :param df: 输入 DataFrame
        :param params: 方法参数
        :return: AnalysisResult
        """
        params = params or {}

        if not has_method(method):
            available = [m["name"] for m in list_methods()]
            return AnalysisResult(
                success=False,
                method=method,
                summary="",
                error=f"未知分析方法: {method}。可用方法: {available}",
            )

        if df.empty:
            return AnalysisResult(
                success=False,
                method=method,
                summary="",
                error="输入数据为空，无法执行分析",
            )

        func = get_method(method)
        t0 = time.perf_counter()

        try:
            result = func(df, params)
            elapsed = round(time.perf_counter() - t0, 3)
            result.metadata["elapsed_seconds"] = elapsed
            logger.info(
                f"[engine] {method} completed in {elapsed}s, "
                f"rows={len(df)}, success={result.success}"
            )
            return result

        except Exception as e:
            elapsed = round(time.perf_counter() - t0, 3)
            logger.error(f"[engine] {method} failed after {elapsed}s: {e}", exc_info=True)
            return AnalysisResult(
                success=False,
                method=method,
                summary="",
                error=f"分析执行失败: {e}",
                metadata={"elapsed_seconds": elapsed},
            )

    @staticmethod
    def list_available_methods():
        """列出所有可用分析方法。"""
        return list_methods()
