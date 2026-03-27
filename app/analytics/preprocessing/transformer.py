"""
特征变换器 — 标准化、编码、时间特征提取
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def scale_numeric(
    df: pd.DataFrame,
    method: Literal["standard", "minmax"] = "standard",
    columns: Optional[List[str]] = None,
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """
    数值列标准化。

    :param method: standard=零均值单位方差, minmax=归一化到[0,1]
    """
    df = df.copy()
    numeric_cols = columns or df.select_dtypes(include=[np.number]).columns.tolist()
    scaled_cols = []

    for col in numeric_cols:
        if col not in df.columns:
            continue
        series = df[col].dropna()
        if series.empty:
            continue

        if method == "standard":
            mean, std = series.mean(), series.std()
            if std > 0:
                df[col] = (df[col] - mean) / std
                scaled_cols.append(col)
        elif method == "minmax":
            vmin, vmax = series.min(), series.max()
            if vmax > vmin:
                df[col] = (df[col] - vmin) / (vmax - vmin)
                scaled_cols.append(col)

    log = {
        "step": "scale_numeric",
        "method": method,
        "scaled_columns": scaled_cols,
    }
    return df, log


def extract_time_features(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    features: Optional[List[str]] = None,
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """
    时间列特征提取。

    :param columns: 需要提取特征的时间列
    :param features: 要提取的特征列表，默认 ["hour", "weekday", "month"]
    """
    df = df.copy()
    features = features or ["hour", "weekday", "month"]
    added = []

    # 自动检测时间列
    if not columns:
        columns = df.select_dtypes(include=["datetime64"]).columns.tolist()
        # 尝试转换看起来像日期的字符串列
        for col in df.select_dtypes(include=["object"]).columns:
            try:
                pd.to_datetime(df[col].head(10), errors="raise")
                df[col] = pd.to_datetime(df[col], errors="coerce")
                columns.append(col)
            except (ValueError, TypeError):
                pass

    for col in columns:
        if col not in df.columns:
            continue
        dt = pd.to_datetime(df[col], errors="coerce")
        if dt.isnull().all():
            continue

        if "hour" in features:
            df[f"{col}_hour"] = dt.dt.hour
            added.append(f"{col}_hour")
        if "weekday" in features:
            df[f"{col}_weekday"] = dt.dt.weekday
            added.append(f"{col}_weekday")
        if "month" in features:
            df[f"{col}_month"] = dt.dt.month
            added.append(f"{col}_month")
        if "day" in features:
            df[f"{col}_day"] = dt.dt.day
            added.append(f"{col}_day")
        if "shift" in features:
            # 常见半导体三班制: 白班(8-16), 中班(16-24), 夜班(0-8)
            hour = dt.dt.hour
            df[f"{col}_shift"] = pd.cut(
                hour, bins=[-1, 8, 16, 24], labels=["night", "day", "evening"]
            )
            added.append(f"{col}_shift")

    log = {
        "step": "extract_time_features",
        "source_columns": columns,
        "added_columns": added,
    }
    return df, log
