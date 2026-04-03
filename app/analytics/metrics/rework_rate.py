"""
返工率 (Rework Rate) 计算器

SQL 拉取 CheckIn 明细，
Python 侧按 (wafer_id, process_code) 统计访问次数，
visit_count > 1 即为返工。
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
    name="rework_rate_computer",
    description=(
        "计算返工率 (Rework Rate)。"
        "按 (wafer_id, process_code) 统计每片晶圆在每个工站的访问次数，"
        "visit_count > 1 即为返工，公式: 返工晶圆数 / 总晶圆数 × 100%。"
        "适用场景: 统计各工站/产品/日期的晶圆返工比例，反映工艺稳定性。"
    ),
    input_schema=["wafer_id", "process_code", "product_code", "report_date"],
)
class ReworkRateComputer(MetricComputer):
    metric_name = "rework_rate"
    skill_name = "rework_rate"

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
                error="DataFrame 为空，无法计算返工率",
            )

        try:
            df.columns = [c.lower() for c in df.columns]

            # 统计每个 wafer 在每个工站的访问次数
            visit_cols = ["wafer_id"]
            if "process_code" in df.columns:
                visit_cols.append("process_code")

            visit_counts = (
                df.groupby(visit_cols, dropna=False)
                .size()
                .reset_index(name="visit_count")
            )
            visit_counts["is_rework"] = visit_counts["visit_count"] > 1

            # 补充 product_code 和 report_date（取每个 wafer 的最早记录）
            if "product_code" in df.columns:
                product_map = df.groupby("wafer_id")["product_code"].first()
                visit_counts["product_code"] = visit_counts["wafer_id"].map(product_map)
            if "report_date" in df.columns:
                date_map = df.groupby("wafer_id")["report_date"].first()
                visit_counts["report_date"] = visit_counts["wafer_id"].map(date_map)

            if group_by is None:
                group_by = self._detect_group_by(visit_counts)

            detail, overall_rate = self._compute_grouped(visit_counts, group_by)
            charts = self._build_charts(detail, group_by)

            return MetricResult(
                metric_name=self.metric_name,
                success=True,
                summary=f"返工率总体: {overall_rate:.2f}%",
                value=round(overall_rate, 2),
                detail=detail,
                charts=charts,
                metadata={
                    "total_rows": len(df),
                    "unique_wafers": visit_counts["wafer_id"].nunique(),
                    "rework_wafers": int(visit_counts["is_rework"].sum()),
                    "group_by": group_by,
                },
            )
        except Exception as e:
            logger.error(f"[ReworkRateComputer] compute error: {e}", exc_info=True)
            return MetricResult(
                metric_name=self.metric_name,
                success=False,
                summary=f"计算返工率时出错: {e}",
                error=str(e),
            )

    def _detect_group_by(self, df: pd.DataFrame) -> List[str]:
        candidates = ["process_code", "report_date", "product_code"]
        return [c for c in candidates if c in df.columns and df[c].nunique() > 1]

    def _compute_grouped(
        self, df: pd.DataFrame, group_by: List[str]
    ) -> tuple[List[Dict[str, Any]], float]:
        total = df["wafer_id"].nunique()
        rework = df[df["is_rework"]]["wafer_id"].nunique()
        overall_rate = (rework / total * 100) if total > 0 else 0.0

        if not group_by:
            return [
                {"total_wafers": total, "rework_wafers": rework, "rework_rate": round(overall_rate, 2)}
            ], overall_rate

        detail_rows = []
        grouped = df.groupby(group_by, dropna=False)
        for keys, grp in grouped:
            if not isinstance(keys, tuple):
                keys = (keys,)
            row: Dict[str, Any] = dict(zip(group_by, [str(k) for k in keys]))
            grp_total = grp["wafer_id"].nunique()
            grp_rework = grp[grp["is_rework"]]["wafer_id"].nunique()
            row["total_wafers"] = grp_total
            row["rework_wafers"] = grp_rework
            row["rework_rate"] = round((grp_rework / grp_total * 100) if grp_total > 0 else 0.0, 2)
            detail_rows.append(row)

        detail_rows.sort(key=lambda r: r["rework_rate"], reverse=True)
        return detail_rows, overall_rate

    def _build_charts(self, detail: List[Dict[str, Any]], group_by: List[str]) -> List[Dict[str, Any]]:
        charts = []
        if not detail or not group_by:
            return charts

        primary_dim = group_by[0]
        labels = [str(r.get(primary_dim, "")) for r in detail]
        values = [r.get("rework_rate", 0) for r in detail]

        charts.append({
            "chart_type": "bar",
            "title": f"返工率 (按{primary_dim})",
            "option": {
                "xAxis": {"type": "category", "data": labels},
                "yAxis": {"type": "value", "name": "返工率(%)"},
                "series": [{"type": "bar", "data": values, "name": "返工率(%)"}],
                "tooltip": {"trigger": "axis"},
            },
        })

        if "report_date" in group_by:
            date_groups: Dict[str, List[float]] = {}
            for r in detail:
                d = str(r.get("report_date", ""))
                if d:
                    date_groups.setdefault(d, []).append(r.get("rework_rate", 0))
            if date_groups:
                dates = sorted(date_groups.keys())
                avg_values = [round(np.mean(date_groups[d]), 2) for d in dates]
                charts.append({
                    "chart_type": "line",
                    "title": "返工率趋势",
                    "option": {
                        "xAxis": {"type": "category", "data": dates},
                        "yAxis": {"type": "value", "name": "返工率(%)"},
                        "series": [{"type": "line", "data": avg_values, "name": "返工率(%)"}],
                        "tooltip": {"trigger": "axis"},
                    },
                })

        return charts
