"""
adhoc_query 分析方法 — 即席探索查询直传

即席路径：LLM 生成 SQL → data_loader 取数 → 此方法原样返回 DataFrame。
无需额外计算，数据展示交给前端或 LLM 响应节点处理。
"""

from __future__ import annotations

import logging

import pandas as pd

from app.analytics.models import AnalysisResult
from app.analytics.registry import register_method

logger = logging.getLogger(__name__)


@register_method(
    "adhoc_query",
    label="即席探索查询",
    description="即席 SQL 查询结果直传，适用于没有预定义 skill 的数据探索场景",
    params_schema={},
)
def run_adhoc_query(df: pd.DataFrame, params: dict) -> AnalysisResult:
    """
    即席探索查询直传。

    data_loader 已通过 LLM 生成的 SQL 取数，此方法将 DataFrame 原样打包返回。
    LLM 响应节点负责解读数据并生成自然语言答复。
    """
    if df.empty:
        return AnalysisResult(
            success=False,
            method="adhoc_query",
            summary="查询结果为空",
            error="未查询到数据",
        )

    row_count = len(df)
    col_count = len(df.columns)
    col_names = list(df.columns)

    summary = f"即席查询返回 {row_count} 行 × {col_count} 列数据，字段: {', '.join(col_names[:8])}"
    if col_count > 8:
        summary += f"（及 {col_count - 8} 个其他字段）"

    logger.info(f"[adhoc_query] {row_count} rows × {col_count} cols")

    # 转为 records 列表，方便前端展示
    records = df.head(500).to_dict(orient="records")  # 前端最多展示 500 行

    return AnalysisResult(
        success=True,
        method="adhoc_query",
        summary=summary,
        data={
            "records": records,
            "total_rows": row_count,
            "columns": col_names,
        },
    )
