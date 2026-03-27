"""
描述性统计 — 最基础的分析方法

提供均值、标准差、分位数、分布直方图等基础统计量。
作为 Phase 1 的端到端验证方法。
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd

from app.analytics.models import AnalysisResult
from app.analytics.registry import register_method


@register_method(
    "descriptive",
    label="描述性统计",
    description="计算数值列的均值、标准差、分位数等基础统计量，并生成分布直方图",
    params_schema={
        "columns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "目标数值列（空=全部数值列）",
        },
        "percentiles": {
            "type": "array",
            "items": {"type": "number"},
            "default": [0.25, 0.5, 0.75],
            "description": "分位数列表",
        },
    },
)
def run_descriptive(df: pd.DataFrame, params: Dict[str, Any]) -> AnalysisResult:
    """执行描述性统计分析。"""
    target_cols = params.get("columns") or []
    percentiles = params.get("percentiles") or [0.25, 0.5, 0.75]

    # 选择数值列
    if target_cols:
        num_cols = [c for c in target_cols if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    else:
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    if not num_cols:
        return AnalysisResult(
            success=False,
            method="descriptive",
            summary="未找到数值列，无法执行描述性统计",
            error="数据中没有数值类型的列",
        )

    # 计算统计量
    desc = df[num_cols].describe(percentiles=percentiles)
    stats_dict = {}
    for col in num_cols:
        col_data = df[col].dropna()
        stats_dict[col] = {
            "count": int(col_data.count()),
            "mean": _safe_float(col_data.mean()),
            "std": _safe_float(col_data.std()),
            "min": _safe_float(col_data.min()),
            "max": _safe_float(col_data.max()),
            "median": _safe_float(col_data.median()),
            "skew": _safe_float(col_data.skew()),
            "kurtosis": _safe_float(col_data.kurtosis()),
            "missing": int(df[col].isnull().sum()),
            "missing_pct": round(float(df[col].isnull().mean() * 100), 2),
        }
        # 添加分位数
        for p in percentiles:
            label = f"p{int(p * 100)}"
            stats_dict[col][label] = _safe_float(col_data.quantile(p))

    # 生成直方图 Plotly JSON
    charts = []
    for col in num_cols:
        col_data = df[col].dropna()
        if col_data.empty:
            continue
        hist_values, bin_edges = np.histogram(col_data, bins="auto")
        charts.append({
            "type": "histogram",
            "title": f"{col} 分布直方图",
            "data": [{
                "type": "bar",
                "x": [round(float((bin_edges[i] + bin_edges[i + 1]) / 2), 4) for i in range(len(hist_values))],
                "y": [int(v) for v in hist_values],
                "name": col,
            }],
            "layout": {
                "title": {"text": f"{col} 分布直方图"},
                "xaxis": {"title": {"text": col}},
                "yaxis": {"title": {"text": "频次"}},
            },
        })

    # 一句话摘要
    summary_parts = []
    for col in num_cols[:3]:  # 最多展示前3列
        s = stats_dict[col]
        summary_parts.append(
            f"{col}: 均值={s['mean']:.4g}, 标准差={s['std']:.4g}, "
            f"范围[{s['min']:.4g}, {s['max']:.4g}]"
        )
    summary = "; ".join(summary_parts)
    if len(num_cols) > 3:
        summary += f" ...等共 {len(num_cols)} 个数值列"

    return AnalysisResult(
        success=True,
        method="descriptive",
        summary=summary,
        data={
            "statistics": stats_dict,
            "describe_table": desc.to_dict(),
        },
        charts=charts,
        metadata={
            "num_columns": len(num_cols),
            "total_rows": len(df),
            "analyzed_columns": num_cols,
        },
    )


def _safe_float(val) -> float | None:
    """安全转换为 float，处理 NaN/Inf。"""
    if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
        return None
    try:
        return round(float(val), 6)
    except (TypeError, ValueError):
        return None
