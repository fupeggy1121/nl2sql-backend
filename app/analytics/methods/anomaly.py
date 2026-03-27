"""
异常检测方法

支持三种策略：
  - zscore   : 统计 3σ 规则
  - iqr      : 四分位距规则
  - isolation: Isolation Forest（无监督 ML）

输出：异常点列表、异常率、散点图（正常点 vs 异常点）。
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.analytics.models import AnalysisResult
from app.analytics.registry import register_method


def _anomaly_scatter_chart(
    df_idx: pd.Index,
    values: pd.Series,
    anomaly_mask: np.ndarray,
    col: str,
) -> Dict[str, Any]:
    idx = list(range(len(values)))
    normal_x = [i for i, a in zip(idx, anomaly_mask) if not a]
    normal_y = [v for v, a in zip(values.tolist(), anomaly_mask) if not a]
    anomaly_x = [i for i, a in zip(idx, anomaly_mask) if a]
    anomaly_y = [v for v, a in zip(values.tolist(), anomaly_mask) if a]

    return {
        "type": "scatter",
        "title": f"异常检测 — {col}",
        "data": [
            {
                "type": "scatter",
                "mode": "markers",
                "x": normal_x,
                "y": normal_y,
                "name": "正常",
                "marker": {"color": "#1f77b4", "size": 5, "opacity": 0.7},
            },
            {
                "type": "scatter",
                "mode": "markers",
                "x": anomaly_x,
                "y": anomaly_y,
                "name": "异常",
                "marker": {"color": "#d62728", "size": 8, "symbol": "x"},
            },
        ],
        "layout": {
            "title": f"异常检测 — {col}",
            "xaxis": {"title": "样本序号"},
            "yaxis": {"title": col},
        },
    }


def _zscore_detect(
    series: pd.Series, threshold: float
) -> tuple[np.ndarray, Dict[str, float]]:
    mean = series.mean()
    std = series.std(ddof=1)
    if std == 0:
        return np.zeros(len(series), dtype=bool), {"mean": mean, "std": 0}
    z_scores = np.abs((series.values - mean) / std)
    return z_scores > threshold, {"mean": round(mean, 4), "std": round(std, 4)}


def _iqr_detect(
    series: pd.Series, threshold: float
) -> tuple[np.ndarray, Dict[str, float]]:
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - threshold * iqr
    upper = q3 + threshold * iqr
    mask = (series.values < lower) | (series.values > upper)
    return mask, {
        "q1": round(q1, 4), "q3": round(q3, 4),
        "iqr": round(iqr, 4), "lower": round(lower, 4), "upper": round(upper, 4),
    }


@register_method(
    "anomaly",
    label="异常检测",
    description="多策略异常检测：3σ / IQR / Isolation Forest，标记异常点并生成散点图",
    params_schema={
        "columns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "待检测数值列（空=全部数值列，isolation 模式同时分析所有列）",
        },
        "method": {
            "type": "string",
            "enum": ["zscore", "iqr", "isolation"],
            "default": "zscore",
            "description": "检测策略",
        },
        "threshold": {
            "type": "number",
            "default": 3.0,
            "description": "zscore: σ 倍数阈值；iqr: IQR 倍数；isolation: 无效",
        },
        "contamination": {
            "type": "number",
            "default": 0.05,
            "description": "isolation: 预期异常比例（0.01~0.5）",
        },
        "add_flag_column": {
            "type": "boolean",
            "default": False,
            "description": "是否在结果数据中包含 is_anomaly 标记列",
        },
    },
)
def run_anomaly(df: pd.DataFrame, params: Dict[str, Any]) -> AnalysisResult:
    """执行异常检测。"""
    columns = params.get("columns") or []
    method = params.get("method", "zscore")
    threshold = float(params.get("threshold", 3.0))
    contamination = float(params.get("contamination", 0.05))
    add_flag = params.get("add_flag_column", False)

    # 选数值列
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if columns:
        target_cols = [c for c in columns if c in df.columns and c in num_cols]
    else:
        target_cols = num_cols

    if not target_cols:
        return AnalysisResult(
            success=False, method="anomaly",
            summary="没有可用的数值列",
            error="数值列为空",
        )

    sub = df[target_cols].copy()
    n_total = len(sub)

    charts: List[Dict[str, Any]] = []
    all_stats: Dict[str, Any] = {}

    if method in ("zscore", "iqr"):
        combined_mask = np.zeros(n_total, dtype=bool)
        for col in target_cols:
            series = sub[col].fillna(sub[col].mean())
            if method == "zscore":
                mask, stats = _zscore_detect(series, threshold)
            else:
                mask, stats = _iqr_detect(series, threshold)
            combined_mask |= mask
            all_stats[col] = {
                **stats,
                "anomaly_count": int(mask.sum()),
                "anomaly_rate": round(float(mask.mean()), 4),
            }
            if len(target_cols) <= 5:
                charts.append(_anomaly_scatter_chart(sub.index, series, mask, col))

        n_anomaly = int(combined_mask.sum())
        anomaly_rate = round(float(combined_mask.mean()), 4)
        anomaly_indices = sub.index[combined_mask].tolist()

    elif method == "isolation":
        clean = sub.dropna()
        if len(clean) < 10:
            return AnalysisResult(
                success=False, method="anomaly",
                summary=f"有效样本量不足 ({len(clean)} 行)",
                error="样本量过少",
            )
        contamination = max(0.01, min(0.5, contamination))
        iso = IsolationForest(contamination=contamination, random_state=42, n_jobs=-1)
        preds = iso.fit_predict(clean.values)
        mask_full = np.zeros(n_total, dtype=bool)
        mask_full[clean.index.map(lambda i: sub.index.get_loc(i))] = (preds == -1)

        # 绘制第一列散点图代表
        first_col = target_cols[0]
        charts.append(_anomaly_scatter_chart(sub.index, sub[first_col], mask_full, first_col))

        n_anomaly = int(mask_full.sum())
        anomaly_rate = round(float(mask_full.mean()), 4)
        anomaly_indices = sub.index[mask_full].tolist()
        combined_mask = mask_full
        all_stats = {"method": "isolation_forest", "contamination": contamination}
    else:
        return AnalysisResult(
            success=False, method="anomaly",
            summary=f"不支持的检测方法: {method}",
            error=f"method 必须是 zscore/iqr/isolation 之一",
        )

    summary = (
        f"异常检测 ({method}): 共 {n_total} 个样本，"
        f"检测到 {n_anomaly} 个异常点 (异常率 {anomaly_rate*100:.1f}%)"
    )

    result_data: Dict[str, Any] = {
        "method": method,
        "n_total": n_total,
        "n_anomaly": n_anomaly,
        "anomaly_rate": anomaly_rate,
        "anomaly_indices": anomaly_indices[:100],  # 最多返回 100 个
        "column_stats": all_stats,
    }

    if add_flag:
        result_data["flagged_rows"] = df[combined_mask][target_cols].head(100).to_dict(orient="records")

    return AnalysisResult(
        success=True,
        method="anomaly",
        summary=summary,
        data=result_data,
        charts=charts,
        metadata={"n_samples": n_total, "analyzed_columns": target_cols},
    )
