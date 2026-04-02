"""
一次良率 (First Pass Yield) 计算器

SQL 拉取 CheckOut 明细 + ROW_NUMBER(ASC)，
Python 侧筛选 rn=1 + 统计合格率。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.analytics.metrics.base import MetricComputer, MetricResult
from app.analytics.registry import register_metric

logger = logging.getLogger(__name__)

# 三表简称
_LOG_TABLE = "matrix_routerx_operation_lot_batch_resume_log"
_DETAIL_TABLE = "matrix_routerx_operation_lot_batch_resume_log_detail"
_WAFER_TABLE = "matrix_routerx_operation_lot_batch_resume_wafer_detail_log"


@register_metric
class FirstPassYieldComputer(MetricComputer):
    metric_name = "first_pass_yield"
    skill_name = "first_pass_yield"

    def required_raw_sql(
        self,
        station_filter: str = "",
        product_filter: str = "",
        date_filter: str = "",
        extra_where: str = "",
        limit: int = 100000,
    ) -> str:
        where_extra = self._build_where_extra(
            station_filter, product_filter, date_filter, extra_where
        )

        return f"""\
SELECT wdl.wafer_id, log.process_code, log.product_code,
       DATE(log.gmt_create) AS report_date,
       wdl.wafer_type, wdl.ng_code,
       ROW_NUMBER() OVER (
         PARTITION BY wdl.wafer_id, log.process_code
         ORDER BY log.gmt_create ASC
       ) AS rn
FROM {_LOG_TABLE} log
JOIN {_DETAIL_TABLE} d
     ON d.batch_resume_log_id = log.id
JOIN {_WAFER_TABLE} wdl
     ON wdl.batch_resume_detail_log_id = d.id
WHERE log.operation_type = 9
  AND (log.deleted = 0 OR log.deleted IS NULL)
  {where_extra}
LIMIT {limit}"""

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
                error="DataFrame 为空，无法计算一次良率",
            )

        try:
            # 标准化列名为小写
            df.columns = [c.lower() for c in df.columns]

            # 筛选首次出站 (rn = 1)
            if "rn" in df.columns:
                first_pass = df[df["rn"] == 1].copy()
            else:
                # 如果没有 rn 列，手动计算
                first_pass = self._add_row_number(df)

            if first_pass.empty:
                return MetricResult(
                    metric_name=self.metric_name,
                    success=False,
                    summary="筛选首次出站后无数据",
                    error="rn=1 筛选后 DataFrame 为空",
                )

            # 合格判定: wafer_type IS NULL (整型) 或 =='good' (字符型)，且 ng_code 为空
            wt = first_pass["wafer_type"]
            wt_non_null = wt.dropna()
            if (
                len(wt_non_null) > 0
                and isinstance(wt_non_null.iloc[0], (int, float, np.integer, np.floating))
            ):
                # 整型编码: NULL = 合格，任何非 NULL 值 = 不合格
                wt_good = wt.isna()
            else:
                # 字符串编码: 'good' / NULL = 合格
                wt_good = wt.fillna("good").astype(str).str.lower().eq("good")
            first_pass["is_good"] = (
                wt_good
                & (first_pass["ng_code"].fillna("").astype(str).str.strip().eq(""))
            )

            # 默认分组维度
            if group_by is None:
                group_by = self._detect_group_by(first_pass)

            # 分组计算
            detail, overall_yield = self._compute_grouped(first_pass, group_by)

            # 构建图表
            charts = self._build_charts(detail, group_by)

            return MetricResult(
                metric_name=self.metric_name,
                success=True,
                summary=f"一次良率(FPY)总体: {overall_yield:.2f}%",
                value=round(overall_yield, 2),
                detail=detail,
                charts=charts,
                metadata={
                    "total_rows": len(df),
                    "first_pass_rows": len(first_pass),
                    "group_by": group_by,
                },
            )
        except Exception as e:
            logger.error(f"[FirstPassYieldComputer] compute error: {e}", exc_info=True)
            return MetricResult(
                metric_name=self.metric_name,
                success=False,
                summary=f"计算一次良率时出错: {e}",
                error=str(e),
            )

    def _add_row_number(self, df: pd.DataFrame) -> pd.DataFrame:
        """当 SQL 未返回 rn 列时，手动计算首次出站"""
        df = df.copy()
        if "gmt_create" in df.columns:
            sort_col = "gmt_create"
        elif "report_date" in df.columns:
            sort_col = "report_date"
        else:
            # 无法排序，取全部
            return df

        df = df.sort_values(sort_col, ascending=True)
        partition_cols = ["wafer_id"]
        if "process_code" in df.columns:
            partition_cols.append("process_code")

        df["rn"] = df.groupby(partition_cols).cumcount() + 1
        return df[df["rn"] == 1].copy()

    def _detect_group_by(self, df: pd.DataFrame) -> List[str]:
        """根据 DataFrame 列自动选择分组维度"""
        candidates = ["process_code", "report_date", "product_code"]
        return [c for c in candidates if c in df.columns and df[c].nunique() > 1]

    def _compute_grouped(
        self, df: pd.DataFrame, group_by: List[str]
    ) -> tuple[List[Dict[str, Any]], float]:
        """分组计算良率，返回 (detail_list, overall_yield)"""
        # 总体
        total = df["wafer_id"].nunique()
        good = df[df["is_good"]]["wafer_id"].nunique()
        overall_yield = (good / total * 100) if total > 0 else 0.0

        if not group_by:
            return [
                {"total_wafers": total, "good_wafers": good, "first_pass_yield": round(overall_yield, 2)}
            ], overall_yield

        # 分组
        detail_rows = []
        grouped = df.groupby(group_by, dropna=False)
        for keys, grp in grouped:
            if not isinstance(keys, tuple):
                keys = (keys,)
            row: Dict[str, Any] = dict(zip(group_by, [str(k) for k in keys]))
            grp_total = grp["wafer_id"].nunique()
            grp_good = grp[grp["is_good"]]["wafer_id"].nunique()
            row["total_wafers"] = grp_total
            row["good_wafers"] = grp_good
            row["first_pass_yield"] = round((grp_good / grp_total * 100) if grp_total > 0 else 0.0, 2)
            detail_rows.append(row)

        # 按良率排序
        detail_rows.sort(key=lambda r: r["first_pass_yield"], reverse=True)
        return detail_rows, overall_yield

    def _build_charts(self, detail: List[Dict[str, Any]], group_by: List[str]) -> List[Dict[str, Any]]:
        """构建 ECharts 配置"""
        charts = []

        if not detail or not group_by:
            return charts

        # 柱状图：按首个分组维度
        primary_dim = group_by[0]
        labels = [str(r.get(primary_dim, "")) for r in detail]
        values = [r.get("first_pass_yield", 0) for r in detail]

        charts.append({
            "chart_type": "bar",
            "title": f"一次良率 (按{primary_dim})",
            "option": {
                "xAxis": {"type": "category", "data": labels},
                "yAxis": {"type": "value", "name": "良率(%)", "max": 100},
                "series": [{"type": "bar", "data": values, "name": "一次良率(%)"}],
                "tooltip": {"trigger": "axis"},
            },
        })

        # 趋势图（如果有日期维度）
        if "report_date" in group_by:
            date_groups: Dict[str, List[float]] = {}
            for r in detail:
                d = str(r.get("report_date", ""))
                if d:
                    date_groups.setdefault(d, []).append(r.get("first_pass_yield", 0))
            if date_groups:
                dates = sorted(date_groups.keys())
                avg_values = [round(np.mean(date_groups[d]), 2) for d in dates]
                charts.append({
                    "chart_type": "line",
                    "title": "一次良率趋势",
                    "option": {
                        "xAxis": {"type": "category", "data": dates},
                        "yAxis": {"type": "value", "name": "良率(%)", "max": 100},
                        "series": [{"type": "line", "data": avg_values, "name": "一次良率(%)"}],
                        "tooltip": {"trigger": "axis"},
                    },
                })

        return charts
