"""
预处理管道 — 按顺序编排 cleaner → transformer

可配置的管道，每步记录处理日志，支持回溯审计。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from app.analytics.preprocessing.cleaner import detect_outliers, handle_missing
from app.analytics.preprocessing.transformer import (
    extract_time_features,
    scale_numeric,
)

logger = logging.getLogger(__name__)

# 可用的预处理步骤
_STEP_MAP = {
    "handle_missing": handle_missing,
    "detect_outliers": detect_outliers,
    "scale_numeric": scale_numeric,
    "extract_time_features": extract_time_features,
}


class PreprocessingPipeline:
    """
    可配置的预处理管道。

    Usage:
        pipeline = PreprocessingPipeline([
            {"step": "handle_missing", "strategy": "median"},
            {"step": "detect_outliers", "method": "iqr", "action": "clip"},
        ])
        df_clean, logs = pipeline.run(df)
    """

    def __init__(self, steps: Optional[List[Dict[str, Any]]] = None):
        self.steps = steps or [
            {"step": "handle_missing", "strategy": "drop"},
        ]

    def run(self, df: pd.DataFrame) -> tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """
        执行预处理管道。

        :return: (处理后 DataFrame, 每步的处理日志列表)
        """
        logs: List[Dict[str, Any]] = []
        logs.append({
            "step": "_input",
            "rows": len(df),
            "columns": df.columns.tolist(),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        })

        for step_config in self.steps:
            step_name = step_config.get("step", "")
            func = _STEP_MAP.get(step_name)
            if not func:
                logger.warning(f"[pipeline] unknown step: {step_name}, skipping")
                continue

            # 提取步骤参数（排除 "step" key）
            params = {k: v for k, v in step_config.items() if k != "step"}

            try:
                df, log = func(df, **params)
                logs.append(log)
            except Exception as e:
                logger.error(f"[pipeline] step {step_name} failed: {e}")
                logs.append({"step": step_name, "error": str(e)})

        return df, logs


def auto_preprocess(df: pd.DataFrame) -> tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    自动预处理 — 使用sensible默认值。

    1. 丢弃缺失行
    2. 提取时间特征（若有时间列）
    """
    pipeline = PreprocessingPipeline([
        {"step": "handle_missing", "strategy": "drop"},
        {"step": "extract_time_features"},
    ])
    return pipeline.run(df)
