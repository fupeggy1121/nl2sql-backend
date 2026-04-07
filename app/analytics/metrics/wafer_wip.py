"""
在制品数量 (Wafer WIP) 计算器

SQL 拉取活跃在制晶圆明细（lot.status=50, lot.parent_id!=0），
Python 侧按工站/产品/日期维度统计 COUNT DISTINCT wafer_id。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.analytics.metrics.base import MetricComputer, MetricResult
from app.analytics.registry import register_metric
from app.analytics.tool_registry import register_compute_tool

logger = logging.getLogger(__name__)


@register_metric
@register_compute_tool(
    name="wafer_wip_computer",
    description=(
        "计算在制品数量 (Wafer WIP)。"
        "按工站/产品/日期维度统计 COUNT DISTINCT wafer_id，"
        "仅统计 lot.status=50（在制）且 lot.parent_id!=0（子批次）的活跃晶圆。"
        "适用场景: 查看各工站当前在制晶圆数、WIP分布、按时段的WIP趋势。"
    ),
    input_schema=["wafer_id", "process_name", "process_code", "product_code", "report_date"],
)
class WaferWipComputer(MetricComputer):
    metric_name = "wafer_wip"
    skill_name = "wafer_wip"

    def compute(
        self,
        df: pd.DataFrame,
        group_by: Optional[List[str]] = None,
        **kwargs,
    ) -> MetricResult:
        if df is None or df.empty:
            return MetricResult(
                metric_name=self.metric_name,
                success=False,
                summary="无数据",
                error="DataFrame 为空，无法计算在制品数量",
            )

        try:
            df.columns = [c.lower() for c in df.columns]

            # 统一工站维度：优先用 process_name，fallback 到 process_code
            if "process_name" not in df.columns and "process_code" in df.columns:
                df["process_name"] = df["process_code"]
            elif "process_name" not in df.columns:
                df["process_name"] = "未知工站"

            # 如果数据已经预聚合（有 wip_count 列），直接使用
            if "wip_count" in df.columns:
                return self._compute_from_aggregated(df, group_by)

            # 明细模式：COUNT DISTINCT wafer_id
            if "wafer_id" not in df.columns:
                return MetricResult(
                    metric_name=self.metric_name,
                    success=False,
                    summary="缺少 wafer_id 列",
                    error="DataFrame 中未找到 wafer_id 列",
                )

            if group_by is None:
                group_by = self._detect_group_by(df)

            detail, total_wip = self._compute_grouped(df, group_by)
            charts = self._build_charts(detail, group_by)

            return MetricResult(
                metric_name=self.metric_name,
                success=True,
                summary=f"在制品总数: {total_wip:,} 片",
                value=float(total_wip),
                detail=detail,
                charts=charts,
                metadata={
                    "total_rows": len(df),
                    "unique_wafers": int(df["wafer_id"].nunique()),
                    "group_by": group_by,
                },
            )
        except Exception as e:
            logger.error(f"[WaferWipComputer] compute error: {e}", exc_info=True)
            return MetricResult(
                metric_name=self.metric_name,
                success=False,
                summary=f"计算在制品数量时出错: {e}",
                error=str(e),
            )

    def _compute_from_aggregated(
        self, df: pd.DataFrame, group_by: Optional[List[str]]
    ) -> MetricResult:
        """处理预聚合数据（含 wip_count 列的 SQL 已 GROUP BY 结果）。"""
        try:
            total_wip = int(df["wip_count"].sum())

            if group_by is None:
                dim_candidates = ["process_name", "process_code", "product_code", "time_period", "report_date"]
                group_by = [c for c in dim_candidates if c in df.columns and df[c].nunique() > 1]

            label_col = group_by[0] if group_by else (df.columns[0] if len(df.columns) > 0 else None)
            detail = df.to_dict(orient="records")
            charts = []

            if label_col and label_col in df.columns:
                bar_data = df.groupby(label_col)["wip_count"].sum().reset_index()
                bar_data = bar_data.sort_values("wip_count", ascending=False)
                charts.append({
                    "chart_type": "bar",
                    "title": f"在制品数量 (按{label_col})",
                    "option": {
                        "xAxis": {"type": "category", "data": bar_data[label_col].astype(str).tolist()},
                        "yAxis": {"type": "value", "name": "WIP数量(片)"},
                        "series": [{"type": "bar", "data": bar_data["wip_count"].tolist(), "name": "WIP数量"}],
                        "tooltip": {"trigger": "axis"},
                    },
                })

            date_col = next((c for c in ["time_period", "report_date"] if c in df.columns), None)
            if date_col and label_col != date_col:
                time_data = df.groupby(date_col)["wip_count"].sum().reset_index()
                time_data = time_data.sort_values(date_col)
                charts.append({
                    "chart_type": "line",
                    "title": "在制品数量趋势",
                    "option": {
                        "xAxis": {"type": "category", "data": time_data[date_col].astype(str).tolist()},
                        "yAxis": {"type": "value", "name": "WIP数量(片)"},
                        "series": [{"type": "line", "data": time_data["wip_count"].tolist(), "name": "WIP数量"}],
                        "tooltip": {"trigger": "axis"},
                    },
                })

            return MetricResult(
                metric_name=self.metric_name,
                success=True,
                summary=f"在制品总数: {total_wip:,} 片",
                value=float(total_wip),
                detail=detail,
                charts=charts,
                metadata={"total_rows": len(df), "unique_wafers": total_wip, "group_by": group_by},
            )
        except Exception as e:
            logger.error(f"[WaferWipComputer] aggregated compute error: {e}", exc_info=True)
            return MetricResult(
                metric_name=self.metric_name,
                success=False,
                summary=f"计算在制品数量时出错: {e}",
                error=str(e),
            )

    def _detect_group_by(self, df: pd.DataFrame) -> List[str]:
        candidates = ["process_name", "process_code", "report_date", "product_code"]
        return [c for c in candidates if c in df.columns and df[c].nunique() > 1]

    def _compute_grouped(
        self, df: pd.DataFrame, group_by: List[str]
    ) -> tuple[List[Dict[str, Any]], int]:
        total_wip = int(df["wafer_id"].nunique())

        if not group_by:
            return [{"total_wip": total_wip}], total_wip

        detail_rows = []
        grouped = df.groupby(group_by, dropna=False)
        for keys, grp in grouped:
            if not isinstance(keys, tuple):
                keys = (keys,)
            row: Dict[str, Any] = dict(zip(group_by, [str(k) for k in keys]))
            row["wip_count"] = int(grp["wafer_id"].nunique())
            detail_rows.append(row)

        detail_rows.sort(key=lambda r: r["wip_count"], reverse=True)
        return detail_rows, total_wip

    def _build_charts(self, detail: List[Dict[str, Any]], group_by: List[str]) -> List[Dict[str, Any]]:
        charts = []
        if not detail or not group_by:
            return charts

        primary_dim = group_by[0]
        labels = [str(r.get(primary_dim, "")) for r in detail]
        values = [r.get("wip_count", 0) for r in detail]

        charts.append({
            "chart_type": "bar",
            "title": f"在制品数量 (按{primary_dim})",
            "option": {
                "xAxis": {"type": "category", "data": labels},
                "yAxis": {"type": "value", "name": "WIP数量(片)"},
                "series": [{"type": "bar", "data": values, "name": "WIP数量"}],
                "tooltip": {"trigger": "axis"},
            },
        })

        if "report_date" in group_by:
            date_groups: Dict[str, List[int]] = {}
            for r in detail:
                d = str(r.get("report_date", ""))
                if d:
                    date_groups.setdefault(d, []).append(r.get("wip_count", 0))
            if date_groups:
                dates = sorted(date_groups.keys())
                total_values = [int(np.sum(date_groups[d])) for d in dates]
                charts.append({
                    "chart_type": "line",
                    "title": "在制品数量趋势",
                    "option": {
                        "xAxis": {"type": "category", "data": dates},
                        "yAxis": {"type": "value", "name": "WIP数量(片)"},
                        "series": [{"type": "line", "data": total_values, "name": "WIP数量"}],
                        "tooltip": {"trigger": "axis"},
                    },
                })

        return charts
