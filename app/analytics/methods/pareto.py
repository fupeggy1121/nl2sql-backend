"""
帕累托分析方法

按分类维度的频次或数值汇总排序，计算累积占比，找到 80/20 切分点。
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd

from app.analytics.models import AnalysisResult
from app.analytics.registry import register_method


@register_method(
    "pareto",
    label="帕累托分析",
    description="帕累托 (80/20) 分析: 按分类汇总排序，计算累积占比，找 80% 切分点",
    params_schema={
        "category_column": {
            "type": "string",
            "description": "分类列（必填）",
        },
        "value_column": {
            "type": "string",
            "description": "数值列（可选，为空则按频次统计）",
        },
        "top_n": {
            "type": "integer",
            "default": 20,
            "description": "最多显示前 N 个分类",
        },
    },
)
def run_pareto(df: pd.DataFrame, params: Dict[str, Any]) -> AnalysisResult:
    """执行帕累托分析。"""
    category_col = params.get("category_column")
    value_col = params.get("value_column")
    top_n = params.get("top_n", 20)

    if not category_col:
        return AnalysisResult(
            success=False,
            method="pareto",
            summary="帕累托分析需要 category_column 参数",
            error="缺少必要参数: category_column",
        )
    if category_col not in df.columns:
        return AnalysisResult(
            success=False,
            method="pareto",
            summary=f"列 '{category_col}' 不存在",
            error=f"列 '{category_col}' 不在数据中",
        )

    # 汇总
    if value_col and value_col in df.columns:
        agg = df.groupby(category_col, dropna=False)[value_col].sum().reset_index()
        agg.columns = ["category", "value"]
        value_label = f"sum({value_col})"
    else:
        agg = df[category_col].value_counts(dropna=False).reset_index()
        agg.columns = ["category", "value"]
        value_label = "频次"

    agg = agg.sort_values("value", ascending=False).reset_index(drop=True)
    agg["category"] = agg["category"].astype(str)

    total = agg["value"].sum()
    if total == 0:
        return AnalysisResult(
            success=False,
            method="pareto",
            summary="汇总值为零，无法执行帕累托分析",
            error="数据汇总结果为零",
        )

    agg["percentage"] = (agg["value"] / total * 100).round(4)
    agg["cumulative_pct"] = agg["percentage"].cumsum().round(4)

    # 截取 top_n
    display = agg.head(top_n)
    total_categories = len(agg)

    # 80% 切分点
    cutoff_mask = agg["cumulative_pct"] >= 80.0
    if cutoff_mask.any():
        cutoff_idx = cutoff_mask.idxmax()
        cutoff_category = agg.loc[cutoff_idx, "category"]
        cutoff_count = cutoff_idx + 1
    else:
        cutoff_category = agg.iloc[-1]["category"]
        cutoff_count = len(agg)

    # Plotly 图表: 柱状 + 累积百分比折线 (双 Y 轴)
    categories = display["category"].tolist()
    values = display["value"].tolist()
    cum_pcts = display["cumulative_pct"].tolist()

    chart = {
        "type": "pareto",
        "title": f"帕累托分析: {category_col}",
        "data": [
            {
                "type": "bar",
                "name": value_label,
                "x": categories,
                "y": values,
                "marker": {"color": "steelblue"},
            },
            {
                "type": "scatter",
                "name": "累积百分比",
                "x": categories,
                "y": cum_pcts,
                "mode": "lines+markers",
                "yaxis": "y2",
                "line": {"color": "firebrick"},
            },
            {
                "type": "scatter",
                "name": "80% 线",
                "x": [categories[0], categories[-1]],
                "y": [80, 80],
                "mode": "lines",
                "yaxis": "y2",
                "line": {"color": "gray", "dash": "dash"},
                "showlegend": True,
            },
        ],
        "layout": {
            "title": f"帕累托分析: {category_col}",
            "xaxis": {"title": category_col, "tickangle": -45},
            "yaxis": {"title": value_label},
            "yaxis2": {
                "title": "累积百分比 (%)",
                "overlaying": "y",
                "side": "right",
                "range": [0, 105],
            },
        },
    }

    table_data = display[["category", "value", "percentage", "cumulative_pct"]].to_dict(orient="records")

    summary = (
        f"帕累托分析: 共 {total_categories} 个分类, "
        f"Top 1 = '{display.iloc[0]['category']}' ({round(float(display.iloc[0]['percentage']), 2)}%), "
        f"前 {cutoff_count} 个分类覆盖 80%"
    )

    return AnalysisResult(
        success=True,
        method="pareto",
        summary=summary,
        data={
            "total_categories": total_categories,
            "total_value": round(float(total), 4),
            "cutoff_80_category": cutoff_category,
            "cutoff_80_count": cutoff_count,
            "table": table_data,
        },
        charts=[chart],
    )
