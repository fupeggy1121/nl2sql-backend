"""
数据清洗器 — 缺失值/异常值处理

所有方法接收 DataFrame 返回 DataFrame + 处理日志，不修改原始数据。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def handle_missing(
    df: pd.DataFrame,
    strategy: Literal["drop", "mean", "median", "ffill", "zero"] = "drop",
    columns: Optional[List[str]] = None,
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """
    处理缺失值。

    :param strategy: 填充策略
    :param columns: 目标列，None 表示全部列
    :return: (处理后 DataFrame, 处理日志)
    """
    df = df.copy()
    target = columns or df.columns.tolist()
    before_nulls = int(df[target].isnull().sum().sum())

    if strategy == "drop":
        df = df.dropna(subset=target)
    elif strategy == "mean":
        for col in target:
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(df[col].mean())
    elif strategy == "median":
        for col in target:
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(df[col].median())
    elif strategy == "ffill":
        df[target] = df[target].ffill()
    elif strategy == "zero":
        df[target] = df[target].fillna(0)

    after_nulls = int(df[target].isnull().sum().sum()) if not df.empty else 0
    log = {
        "step": "handle_missing",
        "strategy": strategy,
        "columns": target,
        "nulls_before": before_nulls,
        "nulls_after": after_nulls,
        "rows_after": len(df),
    }
    return df, log


def detect_outliers(
    df: pd.DataFrame,
    method: Literal["iqr", "zscore"] = "iqr",
    columns: Optional[List[str]] = None,
    threshold: float = 1.5,
    action: Literal["flag", "remove", "clip"] = "flag",
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """
    异常值检测与处理。

    :param method: 检测方法（iqr: 四分位距, zscore: Z分数）
    :param threshold: IQR 乘数 (默认1.5) 或 Z-score 阈值 (默认3)
    :param action: flag=添加标记列, remove=删除, clip=截断
    :return: (处理后 DataFrame, 处理日志)
    """
    df = df.copy()
    numeric_cols = columns or df.select_dtypes(include=[np.number]).columns.tolist()
    total_outliers = 0

    if method == "zscore":
        threshold = threshold if threshold > 2 else 3.0

    for col in numeric_cols:
        if col not in df.columns:
            continue

        series = df[col].dropna()
        if series.empty:
            continue

        if method == "iqr":
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - threshold * iqr
            upper = q3 + threshold * iqr
            mask = (df[col] < lower) | (df[col] > upper)
        else:  # zscore
            mean = series.mean()
            std = series.std()
            if std == 0:
                continue
            mask = ((df[col] - mean) / std).abs() > threshold
            lower = mean - threshold * std
            upper = mean + threshold * std

        n_outliers = int(mask.sum())
        total_outliers += n_outliers

        if action == "flag":
            df[f"{col}_outlier"] = mask
        elif action == "remove":
            df = df[~mask]
        elif action == "clip":
            df[col] = df[col].clip(lower=lower, upper=upper)

    log = {
        "step": "detect_outliers",
        "method": method,
        "threshold": threshold,
        "action": action,
        "columns": numeric_cols,
        "total_outliers": total_outliers,
        "rows_after": len(df),
    }
    return df, log
