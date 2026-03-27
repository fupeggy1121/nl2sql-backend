"""
相关性分析方法

计算相关系数矩阵、p 值矩阵，生成热力图，找出 Top-N 强相关对。
"""

from __future__ import annotations

from itertools import combinations
from typing import Any, Dict

import numpy as np
import pandas as pd
from scipy import stats

from app.analytics.models import AnalysisResult
from app.analytics.registry import register_method


def _compute_pvalues(df: pd.DataFrame, method: str) -> pd.DataFrame:
    """计算每对列之间的 p 值矩阵。"""
    cols = df.columns
    n = len(cols)
    pvals = pd.DataFrame(np.ones((n, n)), index=cols, columns=cols)
    corr_func = stats.pearsonr if method == "pearson" else stats.spearmanr

    for i, j in combinations(range(n), 2):
        col_i, col_j = cols[i], cols[j]
        valid = df[[col_i, col_j]].dropna()
        if len(valid) < 3:
            continue
        _, p = corr_func(valid[col_i], valid[col_j])
        pvals.iloc[i, j] = p
        pvals.iloc[j, i] = p

    for i in range(n):
        pvals.iloc[i, i] = 0.0

    return pvals


@register_method(
    "correlation",
    label="相关性分析",
    description="计算相关系数矩阵与 p 值，生成热力图，找出最强相关对",
    params_schema={
        "columns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "目标数值列（空=全部数值列）",
        },
        "method": {
            "type": "string",
            "enum": ["pearson", "spearman"],
            "default": "pearson",
            "description": "相关系数方法",
        },
        "top_n": {
            "type": "integer",
            "default": 10,
            "description": "返回最强相关的前 N 对",
        },
    },
)
def run_correlation(df: pd.DataFrame, params: Dict[str, Any]) -> AnalysisResult:
    """执行相关性分析。"""
    method = params.get("method", "pearson")
    if method not in ("pearson", "spearman"):
        method = "pearson"
    top_n = params.get("top_n", 10)
    columns = params.get("columns") or []

    # 选择数值列
    if columns:
        num_cols = [c for c in columns if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    else:
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    if len(num_cols) < 2:
        return AnalysisResult(
            success=False,
            method="correlation",
            summary="至少需要 2 个数值列执行相关性分析",
            error=f"数值列不足: 找到 {len(num_cols)} 列",
        )

    sub = df[num_cols]
    corr_matrix = sub.corr(method=method)
    p_matrix = _compute_pvalues(sub, method)

    # Top-N 强相关对 (排除对角线)
    pairs = []
    for i, j in combinations(range(len(num_cols)), 2):
        ci, cj = num_cols[i], num_cols[j]
        r = corr_matrix.iloc[i, j]
        p = p_matrix.iloc[i, j]
        pairs.append({
            "column_1": ci,
            "column_2": cj,
            "correlation": round(float(r), 6),
            "abs_correlation": round(abs(float(r)), 6),
            "p_value": round(float(p), 6),
            "significant": bool(p < 0.05),
        })

    pairs.sort(key=lambda x: x["abs_correlation"], reverse=True)
    top_pairs = pairs[:top_n]

    # 热力图
    cols_list = corr_matrix.columns.tolist()
    chart = {
        "type": "heatmap",
        "title": f"相关系数矩阵 ({method})",
        "data": [{
            "type": "heatmap",
            "z": [[round(float(v), 4) for v in row] for row in corr_matrix.values],
            "x": cols_list,
            "y": cols_list,
            "colorscale": "RdBu",
            "zmin": -1,
            "zmax": 1,
        }],
        "layout": {
            "title": f"相关系数矩阵 ({method})",
            "width": max(400, 60 * len(cols_list)),
            "height": max(400, 60 * len(cols_list)),
        },
    }

    # 摘要
    if top_pairs:
        best = top_pairs[0]
        summary = (
            f"{method} 相关性分析: {len(num_cols)} 列, "
            f"最强相关: {best['column_1']} ↔ {best['column_2']} "
            f"(r={best['correlation']}, p={best['p_value']})"
        )
    else:
        summary = f"{method} 相关性分析: {len(num_cols)} 列，无有效相关对"

    return AnalysisResult(
        success=True,
        method="correlation",
        summary=summary,
        data={
            "method": method,
            "n_columns": len(num_cols),
            "columns": num_cols,
            "correlation_matrix": {
                str(k): {str(kk): round(float(vv), 6) for kk, vv in v.items()}
                for k, v in corr_matrix.to_dict().items()
            },
            "p_value_matrix": {
                str(k): {str(kk): round(float(vv), 6) for kk, vv in v.items()}
                for k, v in p_matrix.to_dict().items()
            },
            "top_pairs": top_pairs,
        },
        charts=[chart],
    )
