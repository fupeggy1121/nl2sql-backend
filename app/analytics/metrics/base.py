"""
MetricComputer 基类 + MetricResult 数据类

所有 Python 侧指标计算器继承 MetricComputer，
实现 required_raw_sql() 和 compute() 两个方法。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MetricResult:
    """指标计算统一返回格式"""
    metric_name: str
    success: bool
    summary: str                                     # 一句话结论
    value: Optional[float] = None                    # 总体值（%）
    detail: List[Dict[str, Any]] = field(default_factory=list)  # 分组明细
    charts: List[Dict[str, Any]] = field(default_factory=list)  # ECharts 配置
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "success": self.success,
            "summary": self.summary,
            "value": self.value,
            "detail": self.detail,
            "charts": self.charts,
            "metadata": self.metadata,
            "error": self.error,
        }


class MetricComputer(ABC):
    """
    指标计算器基类。

    子类需实现:
      - metric_name: 指标唯一标识
      - skill_name: 对应 skill 文件名
      - compute(df, **kwargs) -> MetricResult: 用 pandas 在 Python 侧完成计算

    数据 SQL 由 method_selector 三层协同编排：
      - Mapping 层: join_path / auto_filter / anchor_table（物理数据源定位）
      - Skill 层: formula / body（计算方法论，指导 SQL 列推断）
    子类只负责纯计算逻辑，不涉及 SQL 构建。
    """

    metric_name: str = ""
    skill_name: str = ""

    @abstractmethod
    def compute(
        self,
        df: pd.DataFrame,
        group_by: Optional[List[str]] = None,
        **kwargs,
    ) -> MetricResult:
        """
        基于明细 DataFrame 计算指标。

        :param df: 由 method_selector 编排的 SQL 查询得到的明细数据 DataFrame
        :param group_by: 分组维度 (e.g. ["process_code", "report_date"])
        :param kwargs: 额外参数
        """
        ...

    def _build_where_extra(
        self,
        station_filter: str = "",
        product_filter: str = "",
        date_filter: str = "",
        extra_where: str = "",
    ) -> str:
        """组装额外 WHERE 条件片段"""
        parts = []
        if station_filter:
            parts.append(station_filter)
        if product_filter:
            parts.append(product_filter)
        if date_filter:
            parts.append(date_filter)
        if extra_where:
            parts.append(extra_where)

        if not parts:
            return ""
        return "AND " + " AND ".join(f"({p})" for p in parts)
