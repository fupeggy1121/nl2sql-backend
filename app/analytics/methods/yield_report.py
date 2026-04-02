"""
良率报表分析方法

功能：
  1. 按工站（process_code）和日期统计批次进站晶圆数与不良数
  2. 计算良率（pass_rate = 1 - ng_wafers / input_wafers）
  3. 输出：趋势折线图、各工站良率柱状图、不良类型帕累托（如有 ng_code 列）

期望输入 DataFrame（来自 data_source_config 里的 SQL 查询结果），至少含以下列之一：

方案 A  pre-aggregated（推荐，SQL 侧聚合好）：
  - report_date: 日期字符串 / datetime
  - process_code: 工站编码
  - process_name: 工站名称（可选）
  - product_code: 产品编码（可选）
  - input_wafers: 进站晶圆数
  - ng_wafers: 不良晶圆数

方案 B  wafer 明细（含 ng_code 列，Python 侧聚合）：
  - gmt_create / event_time: 事件时间
  - process_code: 工站
  - wafer_id: 晶圆 ID
  - ng_code: 不良代码（NULL / '' = 合格，有值 = 不良）

SQL 模板（对应方案 A，由 method_selector 生成）：
```sql
SELECT
    DATE(ci.gmt_create)                       AS report_date,
    ci.process_code,
    ci.process_name,
    ci.product_code,
    ci.lot_code,
    COALESCE(SUM(d.wafer_num), 0)             AS input_wafers,
    COUNT(DISTINCT CASE
        WHEN wdl.ng_code IS NOT NULL AND wdl.ng_code <> ''
        THEN wdl.wafer_id END)                AS ng_wafers
FROM matrix_routerx_operation_lot_batch_resume_log ci
LEFT JOIN matrix_routerx_operation_lot_batch_resume_log_detail d
       ON d.batch_resume_log_id = ci.id
LEFT JOIN matrix_routerx_operation_lot_batch_resume_wafer_detail_log wdl
       ON wdl.batch_resume_detail_log_id = d.id
WHERE ci.operation_type = 8
  AND (ci.deleted = 0 OR ci.deleted IS NULL)
GROUP BY DATE(ci.gmt_create), ci.process_code, ci.process_name,
         ci.product_code, ci.lot_code
ORDER BY report_date DESC, ci.process_code
LIMIT 10000
```
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd

from app.analytics.models import AnalysisResult
from app.analytics.registry import register_method


@register_method(
    "yield_report",
    label="良率报表",
    description="半导体批次良率报表：按工站/日期统计进站晶圆数、不良数与良率，生成趋势图和工站分布图",
    params_schema={
        "date_column": {
            "type": "string",
            "default": "report_date",
            "description": "日期列名（默认 report_date）",
        },
        "process_column": {
            "type": "string",
            "default": "process_code",
            "description": "工站列名（默认 process_code）",
        },
        "process_name_column": {
            "type": "string",
            "default": "process_name",
            "description": "工站名称列（可选，默认 process_name）",
        },
        "product_column": {
            "type": "string",
            "default": "product_code",
            "description": "产品编码列（可选）",
        },
        "input_col": {
            "type": "string",
            "default": "input_wafers",
            "description": "进站晶圆数列（默认 input_wafers）",
        },
        "ng_col": {
            "type": "string",
            "default": "ng_wafers",
            "description": "不良晶圆数列（默认 ng_wafers）",
        },
        "ng_code_col": {
            "type": "string",
            "default": "ng_code",
            "description": "不良代码列（明细模式下使用）",
        },
        "wafer_id_col": {
            "type": "string",
            "default": "wafer_id",
            "description": "晶圆 ID 列（明细模式下使用）",
        },
        "target_yield": {
            "type": "number",
            "default": 95.0,
            "description": "良率目标线（%），默认 95.0",
        },
        "top_n_stations": {
            "type": "integer",
            "default": 15,
            "description": "工站良率分布最多展示前 N 个工站",
        },
    },
)
def run_yield_report(df: pd.DataFrame, params: Dict[str, Any]) -> AnalysisResult:
    """执行良率报表分析。"""
    date_col = params.get("date_column", "report_date")
    proc_col = params.get("process_column", "process_code")
    proc_name_col = params.get("process_name_column", "process_name")
    prod_col = params.get("product_column", "product_code")
    input_col = params.get("input_col", "input_wafers")
    ng_col = params.get("ng_col", "ng_wafers")
    ng_code_col = params.get("ng_code_col", "ng_code")
    wafer_id_col = params.get("wafer_id_col", "wafer_id")
    target_yield = float(params.get("target_yield", 95.0))
    top_n = int(params.get("top_n_stations", 15))

    # ── 检测数据模式 ──
    # 方案 C: 双良率 CTE 输出 (first_pass_yield / final_yield 列)
    has_fpy_col = "first_pass_yield" in df.columns or "first_pass_good" in df.columns
    has_final_col = "final_yield" in df.columns or "final_good" in df.columns
    has_input_col = input_col in df.columns
    has_ng_col = ng_col in df.columns
    has_ng_code_col = ng_code_col in df.columns
    has_wafer_id_col = wafer_id_col in df.columns

    if has_fpy_col or has_final_col:
        # 方案 C：双良率 CTE 预聚合数据
        return _run_dual_yield_report(df, date_col, proc_col, proc_name_col, target_yield, top_n)
    elif has_input_col and has_ng_col:
        # 方案 A：直接使用聚合后的列
        agg = _agg_from_precomputed(df, date_col, proc_col, proc_name_col, prod_col, input_col, ng_col)
    elif has_wafer_id_col and has_ng_code_col:
        # 方案 B：从明细聚合
        agg = _agg_from_detail(df, date_col, proc_col, proc_name_col, prod_col, wafer_id_col, ng_code_col)
    else:
        return AnalysisResult(
            success=False,
            method="yield_report",
            summary="缺少必要列：需要 (first_pass_yield/final_yield) 或 (input_wafers + ng_wafers) 或 (wafer_id + ng_code)",
            error=f"可用列: {list(df.columns)}",
        )

    if agg.empty:
        return AnalysisResult(
            success=False,
            method="yield_report",
            summary="聚合后数据为空",
            error="无有效数据",
        )

    # ── 计算良率 ──
    agg["pass_wafers"] = agg["input_wafers"] - agg["ng_wafers"]
    agg["yield_rate"] = np.where(
        agg["input_wafers"] > 0,
        (agg["pass_wafers"] / agg["input_wafers"] * 100).round(2),
        np.nan,
    )

    # ── 汇总统计 ──
    total_input = int(agg["input_wafers"].sum())
    total_ng = int(agg["ng_wafers"].sum())
    total_pass = int(agg["pass_wafers"].sum())
    overall_yield = round(total_pass / total_input * 100, 2) if total_input > 0 else 0.0
    below_target = int((agg["yield_rate"] < target_yield).sum())

    summary = (
        f"良率报表：进站晶圆 {total_input} 片，不良 {total_ng} 片，"
        f"总体良率 {overall_yield:.2f}%（目标 {target_yield}%）。"
        f"{'低于目标的记录数: ' + str(below_target) if below_target > 0 else '全部达标。'}"
    )

    # ── 图表 1：良率趋势（按日期） ──
    charts = []
    if date_col in agg.columns and not agg[date_col].isna().all():
        trend_df = (
            agg.groupby(date_col, dropna=True)
            .agg(
                input_wafers=("input_wafers", "sum"),
                ng_wafers=("ng_wafers", "sum"),
            )
            .reset_index()
        )
        trend_df["yield_rate"] = np.where(
            trend_df["input_wafers"] > 0,
            (trend_df["input_wafers"] - trend_df["ng_wafers"]) / trend_df["input_wafers"] * 100,
            np.nan,
        ).round(2)
        trend_df = trend_df.sort_values(date_col)

        dates = trend_df[date_col].astype(str).tolist()
        yields = trend_df["yield_rate"].tolist()

        trend_chart = {
            "type": "line",
            "title": "良率趋势（按日期）",
            "echarts": {
                "tooltip": {"trigger": "axis"},
                "legend": {"bottom": 0},
                "grid": {"left": 50, "right": 20, "top": 40, "bottom": 50},
                "xAxis": {"type": "category", "data": dates, "name": "日期"},
                "yAxis": {"type": "value", "name": "良率 (%)", "min": 0, "max": 105},
                "series": [
                    {
                        "type": "line",
                        "name": "良率",
                        "data": yields,
                        "symbol": "circle",
                        "symbolSize": 5,
                        "lineStyle": {"color": "#2196F3"},
                        "itemStyle": {"color": "#2196F3"},
                    },
                    {
                        "type": "line",
                        "name": f"目标 {target_yield}%",
                        "data": [target_yield] * len(dates),
                        "symbol": "none",
                        "lineStyle": {"color": "#F44336", "type": "dashed"},
                        "itemStyle": {"color": "#F44336"},
                    },
                ],
            },
        }
        charts.append(trend_chart)

    # ── 图表 2：各工站良率分布（水平柱状图） ──
    if proc_col in agg.columns:
        station_agg = (
            agg.groupby(proc_col, dropna=True)
            .agg(input_wafers=("input_wafers", "sum"), ng_wafers=("ng_wafers", "sum"))
            .reset_index()
        )
        station_agg["yield_rate"] = np.where(
            station_agg["input_wafers"] > 0,
            (station_agg["input_wafers"] - station_agg["ng_wafers"]) / station_agg["input_wafers"] * 100,
            np.nan,
        ).round(2)
        station_agg = station_agg.sort_values("yield_rate").head(top_n)

        # 获取工站名称（如有）
        if proc_name_col and proc_name_col in agg.columns:
            name_map = agg[[proc_col, proc_name_col]].drop_duplicates().set_index(proc_col)[proc_name_col]
            station_agg["station_label"] = station_agg[proc_col].map(name_map).fillna(station_agg[proc_col])
        else:
            station_agg["station_label"] = station_agg[proc_col]

        stations = station_agg["station_label"].tolist()
        station_yields = station_agg["yield_rate"].tolist()
        # 颜色：低于目标的标红
        colors = ["#F44336" if (y is not None and y < target_yield) else "#4CAF50" for y in station_yields]

        station_chart = {
            "type": "bar",
            "title": f"各工站良率分布（最低 {top_n} 站）",
            "echarts": {
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                "legend": {"bottom": 0},
                "grid": {"left": 150, "right": 30, "top": 40, "bottom": 50},
                "xAxis": {"type": "value", "name": "良率 (%)"},
                "yAxis": {"type": "category", "data": stations, "name": "工站"},
                "series": [
                    {
                        "type": "bar",
                        "name": "良率",
                        "data": [
                            {"value": v, "itemStyle": {"color": c}}
                            for v, c in zip(station_yields, colors)
                        ],
                    },
                    {
                        "type": "line",
                        "name": f"目标 {target_yield}%",
                        "data": [None] * len(stations),
                        "markLine": {
                            "silent": True,
                            "data": [{"xAxis": target_yield}],
                            "lineStyle": {"color": "#F44336", "type": "dashed"},
                            "label": {"formatter": f"目标 {target_yield}%"},
                        },
                        "symbol": "none",
                        "lineStyle": {"opacity": 0},
                    },
                ],
            },
        }
        charts.append(station_chart)

    # ── 数据汇总 ──
    station_summary = []
    if proc_col in agg.columns:
        s_agg = (
            agg.groupby(proc_col, dropna=True)
            .agg(input_wafers=("input_wafers", "sum"), ng_wafers=("ng_wafers", "sum"))
            .reset_index()
        )
        s_agg["pass_wafers"] = s_agg["input_wafers"] - s_agg["ng_wafers"]
        s_agg["yield_rate"] = np.where(
            s_agg["input_wafers"] > 0,
            (s_agg["pass_wafers"] / s_agg["input_wafers"] * 100).round(2),
            None,
        )
        s_agg = s_agg.sort_values("yield_rate")
        station_summary = s_agg.to_dict(orient="records")

    return AnalysisResult(
        success=True,
        method="yield_report",
        summary=summary,
        data={
            "overall_yield": overall_yield,
            "total_input_wafers": total_input,
            "total_ng_wafers": total_ng,
            "total_pass_wafers": total_pass,
            "target_yield": target_yield,
            "below_target_count": below_target,
            "station_summary": station_summary,
            "detail_records": agg.head(500).to_dict(orient="records"),
        },
        charts=charts,
        metadata={
            "rows_analyzed": len(df),
            "method": "yield_report",
        },
    )


# ── 私有辅助函数 ─────────────────────────────────────────────────────────────

def _agg_from_precomputed(
    df: pd.DataFrame,
    date_col: str,
    proc_col: str,
    proc_name_col: str,
    prod_col: str,
    input_col: str,
    ng_col: str,
) -> pd.DataFrame:
    """从预聚合列构建标准化 DataFrame。"""
    keep_cols = [input_col, ng_col]
    optional = [date_col, proc_col, proc_name_col, prod_col, "lot_code"]
    group_cols = []
    for c in optional:
        if c and c in df.columns:
            keep_cols.append(c)
            group_cols.append(c)

    if not group_cols:
        # 无分组维度，全量汇总
        return pd.DataFrame(
            [{
                "input_wafers": df[input_col].sum(),
                "ng_wafers": df[ng_col].fillna(0).sum(),
            }]
        )

    agg = (
        df[keep_cols]
        .copy()
        .rename(columns={input_col: "input_wafers", ng_col: "ng_wafers"})
    )
    agg["ng_wafers"] = agg["ng_wafers"].fillna(0)

    # 将 lot 粒度归并到 date+process 粒度
    pivot_cols = [c for c in [date_col, proc_col, proc_name_col, prod_col] if c and c in agg.columns]
    if pivot_cols:
        result = (
            agg.groupby(pivot_cols, dropna=False)
            .agg(input_wafers=("input_wafers", "sum"), ng_wafers=("ng_wafers", "sum"))
            .reset_index()
        )
    else:
        result = agg[["input_wafers", "ng_wafers"]].sum().to_frame().T
    return result


def _agg_from_detail(
    df: pd.DataFrame,
    date_col: str,
    proc_col: str,
    proc_name_col: str,
    prod_col: str,
    wafer_id_col: str,
    ng_code_col: str,
) -> pd.DataFrame:
    """从 wafer 明细行聚合良率数据。"""
    time_col = date_col if date_col in df.columns else None
    if time_col is None:
        # 尝试常见列名
        for candidate in ["gmt_create", "event_time", "create_time"]:
            if candidate in df.columns:
                time_col = candidate
                break

    if time_col and df[time_col].dtype == "object":
        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")

    if time_col:
        df["_date"] = df[time_col].dt.date.astype(str)
    else:
        df["_date"] = "unknown"

    group_cols = ["_date"]
    for c in [proc_col, proc_name_col, prod_col]:
        if c and c in df.columns:
            group_cols.append(c)

    df["_is_ng"] = df[ng_code_col].notna() & (df[ng_code_col].astype(str) != "")

    agg = (
        df.groupby(group_cols, dropna=False)
        .agg(
            input_wafers=(wafer_id_col, "count"),
            ng_wafers=("_is_ng", "sum"),
        )
        .reset_index()
        .rename(columns={"_date": date_col})
    )
    return agg


# ── 方案 C: 双良率分析（一次良率 + 综合良率）──────────────────────────────────

def _run_dual_yield_report(
    df: pd.DataFrame,
    date_col: str,
    proc_col: str,
    proc_name_col: str,
    target_yield: float,
    top_n: int,
) -> AnalysisResult:
    """处理 CTE 模板输出的双良率数据。

    期望列: process_code, product_code, report_date, total_wafers,
            first_pass_good/first_pass_yield 或 final_good/final_yield
    """
    # 标准化列名
    has_fpy = "first_pass_yield" in df.columns
    has_final = "final_yield" in df.columns

    # 确保 total_wafers 列
    tw_col = "total_wafers"
    if tw_col not in df.columns:
        tw_col = next((c for c in df.columns if "total" in c.lower()), None)
        if tw_col:
            df = df.rename(columns={tw_col: "total_wafers"})
        else:
            df["total_wafers"] = 0

    # 计算缺失的良率列
    if "first_pass_yield" not in df.columns and "first_pass_good" in df.columns:
        df["first_pass_yield"] = np.where(
            df["total_wafers"] > 0,
            (df["first_pass_good"] / df["total_wafers"] * 100).round(2),
            np.nan,
        )
        has_fpy = True
    if "final_yield" not in df.columns and "final_good" in df.columns:
        df["final_yield"] = np.where(
            df["total_wafers"] > 0,
            (df["final_good"] / df["total_wafers"] * 100).round(2),
            np.nan,
        )
        has_final = True

    if df.empty:
        return AnalysisResult(
            success=False, method="yield_report",
            summary="双良率分析数据为空", error="无有效数据",
        )

    # ── 汇总统计 ──
    total_wafers = int(df["total_wafers"].sum())
    summary_parts = [f"良率报表：共 {total_wafers} 片晶圆"]

    fpy_overall = None
    final_overall = None
    if has_fpy and "first_pass_good" in df.columns:
        fpy_good = int(df["first_pass_good"].sum())
        fpy_overall = round(fpy_good / total_wafers * 100, 2) if total_wafers > 0 else 0.0
        summary_parts.append(f"一次良率 {fpy_overall:.2f}%")
    if has_final and "final_good" in df.columns:
        final_good = int(df["final_good"].sum())
        final_overall = round(final_good / total_wafers * 100, 2) if total_wafers > 0 else 0.0
        summary_parts.append(f"综合良率 {final_overall:.2f}%")

    summary_parts.append(f"（目标 {target_yield}%）")
    summary = "，".join(summary_parts)

    # ── 图表 ──
    charts = []

    # 图表1: 双良率趋势（按日期）
    if date_col in df.columns and not df[date_col].isna().all():
        trend = df.groupby(date_col, dropna=True).agg(
            total_wafers=("total_wafers", "sum"),
            **({
                "first_pass_good": ("first_pass_good", "sum"),
            } if "first_pass_good" in df.columns else {}),
            **({
                "final_good": ("final_good", "sum"),
            } if "final_good" in df.columns else {}),
        ).reset_index().sort_values(date_col)

        dates = trend[date_col].astype(str).tolist()
        series = []

        if "first_pass_good" in trend.columns:
            fpy_vals = np.where(
                trend["total_wafers"] > 0,
                (trend["first_pass_good"] / trend["total_wafers"] * 100).round(2),
                np.nan,
            ).tolist()
            series.append({
                "type": "line", "name": "一次良率(FPY)",
                "data": fpy_vals, "symbol": "circle", "symbolSize": 5,
                "lineStyle": {"color": "#2196F3"}, "itemStyle": {"color": "#2196F3"},
            })

        if "final_good" in trend.columns:
            final_vals = np.where(
                trend["total_wafers"] > 0,
                (trend["final_good"] / trend["total_wafers"] * 100).round(2),
                np.nan,
            ).tolist()
            series.append({
                "type": "line", "name": "综合良率",
                "data": final_vals, "symbol": "diamond", "symbolSize": 5,
                "lineStyle": {"color": "#4CAF50"}, "itemStyle": {"color": "#4CAF50"},
            })

        series.append({
            "type": "line", "name": f"目标 {target_yield}%",
            "data": [target_yield] * len(dates), "symbol": "none",
            "lineStyle": {"color": "#F44336", "type": "dashed"},
            "itemStyle": {"color": "#F44336"},
        })

        charts.append({
            "type": "line", "title": "良率趋势（一次良率 vs 综合良率）",
            "echarts": {
                "tooltip": {"trigger": "axis"},
                "legend": {"bottom": 0},
                "grid": {"left": 50, "right": 20, "top": 40, "bottom": 50},
                "xAxis": {"type": "category", "data": dates, "name": "日期"},
                "yAxis": {"type": "value", "name": "良率 (%)", "min": 0, "max": 105},
                "series": series,
            },
        })

    # 图表2: 各工站 FPY vs 综合良率 对比柱状图
    if proc_col in df.columns:
        yield_col = "first_pass_yield" if has_fpy else "final_yield"
        sta = df.groupby(proc_col, dropna=True).agg(
            total_wafers=("total_wafers", "sum"),
            **({
                "first_pass_good": ("first_pass_good", "sum"),
            } if "first_pass_good" in df.columns else {}),
            **({
                "final_good": ("final_good", "sum"),
            } if "final_good" in df.columns else {}),
        ).reset_index()

        bar_series = []
        if "first_pass_good" in sta.columns:
            sta["fpy"] = np.where(
                sta["total_wafers"] > 0,
                (sta["first_pass_good"] / sta["total_wafers"] * 100).round(2), np.nan,
            )
            sta = sta.sort_values("fpy")
            bar_series.append({
                "type": "bar", "name": "一次良率",
                "data": sta["fpy"].head(top_n).tolist(),
                "itemStyle": {"color": "#2196F3"},
            })
        if "final_good" in sta.columns:
            sta["fy"] = np.where(
                sta["total_wafers"] > 0,
                (sta["final_good"] / sta["total_wafers"] * 100).round(2), np.nan,
            )
            if "fpy" not in sta.columns:
                sta = sta.sort_values("fy")
            bar_series.append({
                "type": "bar", "name": "综合良率",
                "data": sta["fy"].head(top_n).tolist(),
                "itemStyle": {"color": "#4CAF50"},
            })

        stations = sta[proc_col].head(top_n).tolist()
        if proc_name_col and proc_name_col in df.columns:
            name_map = df[[proc_col, proc_name_col]].drop_duplicates().set_index(proc_col)[proc_name_col]
            stations = [name_map.get(s, s) for s in stations]

        bar_series.append({
            "type": "line", "name": f"目标 {target_yield}%",
            "data": [None] * len(stations), "symbol": "none",
            "lineStyle": {"opacity": 0},
            "markLine": {
                "silent": True,
                "data": [{"xAxis": target_yield}],
                "lineStyle": {"color": "#F44336", "type": "dashed"},
                "label": {"formatter": f"目标 {target_yield}%"},
            },
        })

        charts.append({
            "type": "bar", "title": f"各工站良率对比（最低 {top_n} 站）",
            "echarts": {
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                "legend": {"bottom": 0},
                "grid": {"left": 150, "right": 30, "top": 40, "bottom": 50},
                "xAxis": {"type": "value", "name": "良率 (%)"},
                "yAxis": {"type": "category", "data": stations, "name": "工站"},
                "series": bar_series,
            },
        })

    # 图表3: 返工挽回差值（综合良率 - 一次良率）
    if has_fpy and has_final and proc_col in df.columns:
        gap = df.groupby(proc_col, dropna=True).agg(
            total_wafers=("total_wafers", "sum"),
            first_pass_good=("first_pass_good", "sum"),
            final_good=("final_good", "sum"),
        ).reset_index()
        gap["rework_saved"] = np.where(
            gap["total_wafers"] > 0,
            ((gap["final_good"] - gap["first_pass_good"]) / gap["total_wafers"] * 100).round(2),
            0,
        )
        gap = gap.sort_values("rework_saved", ascending=False).head(top_n)
        gap_stations = gap[proc_col].tolist()
        gap_vals = gap["rework_saved"].tolist()

        charts.append({
            "type": "bar", "title": "返工挽回率（综合良率 − 一次良率）",
            "echarts": {
                "tooltip": {"trigger": "axis"},
                "grid": {"left": 150, "right": 30, "top": 40, "bottom": 30},
                "xAxis": {"type": "value", "name": "挽回百分点 (%)"},
                "yAxis": {"type": "category", "data": gap_stations},
                "series": [{
                    "type": "bar", "name": "返工挽回",
                    "data": gap_vals,
                    "itemStyle": {"color": "#FF9800"},
                }],
            },
        })

    # ── 工段良率乘积 ──
    segment_yield = None
    if proc_col in df.columns:
        sta_final = df.groupby(proc_col, dropna=True).agg(
            total_wafers=("total_wafers", "sum"),
            **({
                "first_pass_good": ("first_pass_good", "sum"),
            } if "first_pass_good" in df.columns else {}),
            **({
                "final_good": ("final_good", "sum"),
            } if "final_good" in df.columns else {}),
        ).reset_index()

        # 用综合良率做工段乘积，回退到一次良率
        good_col = "final_good" if "final_good" in sta_final.columns else "first_pass_good"
        if good_col in sta_final.columns:
            sta_final["station_yield"] = np.where(
                sta_final["total_wafers"] > 0,
                sta_final[good_col] / sta_final["total_wafers"],
                1.0,
            )
            segment_yield = round(float(sta_final["station_yield"].prod()) * 100, 2)
            summary += f"  工段累积良率（乘积）: {segment_yield:.2f}%"

    # ── 站点汇总表 ──
    station_summary = df.head(500).to_dict(orient="records")

    return AnalysisResult(
        success=True,
        method="yield_report",
        summary=summary,
        data={
            "fpy_overall": fpy_overall,
            "final_yield_overall": final_overall,
            "segment_yield": segment_yield,
            "total_wafers": total_wafers,
            "target_yield": target_yield,
            "station_summary": station_summary,
            "detail_records": df.head(500).to_dict(orient="records"),
        },
        charts=charts,
        metadata={
            "rows_analyzed": len(df),
            "method": "yield_report",
            "mode": "dual_yield",
        },
    )
