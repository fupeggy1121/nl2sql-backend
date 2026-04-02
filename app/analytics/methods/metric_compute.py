"""
metric_compute 分析方法 — Python 侧指标计算

从 analysis agent 管道接收明细 DataFrame，
调用对应 MetricComputer 完成计算，返回 AnalysisResult。
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Dict

import pandas as pd

from app.analytics.models import AnalysisResult
from app.analytics.registry import register_method, get_metric

logger = logging.getLogger(__name__)


@register_method(
    "metric_compute",
    label="指标计算（Python）",
    description="使用 Python 计算引擎代替 SQL 聚合，适用于一次良率、综合良率、返工率等复杂指标",
    params_schema={
        "metric_name": {
            "type": "string",
            "description": "指标标识名 (e.g. first_pass_yield, final_yield, rework_rate)",
            "required": True,
        },
        "group_by": {
            "type": "array",
            "items": {"type": "string"},
            "description": "分组维度列名列表 (e.g. ['process_code', 'report_date'])",
            "required": False,
        },
    },
)
def run_metric_compute(df: pd.DataFrame, params: dict) -> AnalysisResult:
    """
    Python 指标计算入口。

    params 需包含:
      - metric_name: 指标名称
      - group_by: (可选) 分组维度
    """
    metric_name = params.get("metric_name", "")
    group_by = params.get("group_by")

    if not metric_name:
        return AnalysisResult(
            success=False,
            method="metric_compute",
            summary="缺少 metric_name 参数",
            error="params 中未指定 metric_name",
        )

    computer = get_metric(metric_name)
    if computer is None:
        return AnalysisResult(
            success=False,
            method="metric_compute",
            summary=f"未找到指标计算器: {metric_name}",
            error=f"metric '{metric_name}' not registered in METRIC_REGISTRY",
        )

    logger.info(f"[metric_compute] computing '{metric_name}' with {len(df)} rows, group_by={group_by}")

    # 调用 MetricComputer.compute()
    result = computer.compute(df, group_by=group_by)

    # 提取 compute 方法源码（用于 pipeline trace 展示）
    try:
        python_script = inspect.getsource(type(computer).compute)
    except Exception:
        python_script = None

    # 转换为 AnalysisResult
    return AnalysisResult(
        success=result.success,
        method="metric_compute",
        summary=result.summary,
        data={
            "metric_name": result.metric_name,
            "value": result.value,
            "detail": result.detail,
        },
        charts=result.charts,
        metadata={
            **result.metadata,
            "compute_mode": "python_compute",
            "metric_name": metric_name,
            "python_script": python_script,
        },
        error=result.error,
    )
