"""
OEE 日报分析方法

OEE（设备综合效率）= 可用率（A）× 性能效率（P）× 合格率（Q）

数据来源：
  matrix_routerx_operation_lot_batch_resume_log 表
  - operation_type=8 → 进站（check-in），含设备 ID（extra JSON 字段）
  - operation_type=9 → 出站（check-out），事件时间即加工完成时间

设备信息：equipment 表（id, code, name）

SQL 模板（由 method_selector 生成，合并进/出站事件后用 Python 配对）：
```sql
SELECT
    e.operation_type,
    e.lot_code,
    e.process_code,
    e.process_name,
    e.product_code,
    JSON_UNQUOTE(JSON_EXTRACT(e.extra, '$.equipment_id'))   AS eqp_id,
    JSON_UNQUOTE(JSON_EXTRACT(e.extra, '$.equipment_name')) AS eqp_name,
    e.gmt_create                                             AS event_time,
    COALESCE(d.wafer_num, 0)                                AS wafer_num
FROM matrix_routerx_operation_lot_batch_resume_log e
LEFT JOIN matrix_routerx_operation_lot_batch_resume_log_detail d
       ON d.batch_resume_log_id = e.id
WHERE e.operation_type IN (8, 9)
  AND (e.deleted = 0 OR e.deleted IS NULL)
ORDER BY e.lot_code, e.process_code, e.event_time
LIMIT 20000
```

Python 侧逻辑：
  1. 对每条进站记录，找同一 lot_code + process_code 的最近出站记录
  2. run_minutes = 出站时间 - 进站时间（分钟）
  3. 按设备+日期汇总 run_minutes（实际加工时长）
  4. 可用率 A = run_minutes / (planned_minutes_per_day * 24) × 100%
  5. 性能效率 P：如有 wafer_num 可计算，否则默认 1
  6. 合格率 Q：来自良率数据（可选参数），默认 1
  7. OEE = A × P × Q

注意：
  - planned_production_hours 参数控制计划生产时间（默认 24h/天）
  - 未配对的进站记录（无对应出站）将被跳过
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd

from app.analytics.models import AnalysisResult
from app.analytics.registry import register_method


@register_method(
    "oee_report",
    label="OEE日报",
    description="设备综合效率（OEE）日报：统计设备的可用率、性能效率和合格率，生成 OEE 趋势图和设备排名",
    params_schema={
        "event_time_col": {
            "type": "string",
            "default": "event_time",
            "description": "事件时间列名（默认 event_time）",
        },
        "operation_type_col": {
            "type": "string",
            "default": "operation_type",
            "description": "操作类型列（8=进站, 9=出站）",
        },
        "lot_col": {
            "type": "string",
            "default": "lot_code",
            "description": "批次编码列",
        },
        "process_col": {
            "type": "string",
            "default": "process_code",
            "description": "工站编码列",
        },
        "eqp_id_col": {
            "type": "string",
            "default": "eqp_id",
            "description": "设备 ID 列（从 extra JSON 提取后的列名）",
        },
        "eqp_name_col": {
            "type": "string",
            "default": "eqp_name",
            "description": "设备名称列",
        },
        "wafer_num_col": {
            "type": "string",
            "default": "wafer_num",
            "description": "晶圆数量列（用于性能效率计算）",
        },
        "planned_hours_per_day": {
            "type": "number",
            "default": 24.0,
            "description": "每天计划生产小时数（默认 24h）",
        },
        "rated_wafers_per_hour": {
            "type": "number",
            "default": 0.0,
            "description": "设备额定产能（片/小时），0 表示不计算性能效率，默认 85%",
        },
        "default_quality": {
            "type": "number",
            "default": 0.0,
            "description": "合格率（0~100%，0 表示不纳入计算，OEE = A × P），可由良率报表传入",
        },
        "oee_target": {
            "type": "number",
            "default": 65.0,
            "description": "OEE 目标值（%），默认 65%（国际半导体行业参考值）",
        },
        "top_n_equipment": {
            "type": "integer",
            "default": 20,
            "description": "设备排名最多展示前 N 台",
        },
    },
)
def run_oee_report(df: pd.DataFrame, params: Dict[str, Any]) -> AnalysisResult:
    """执行 OEE 日报分析。"""
    event_time_col = params.get("event_time_col", "event_time")
    op_type_col = params.get("operation_type_col", "operation_type")
    lot_col = params.get("lot_col", "lot_code")
    proc_col = params.get("process_col", "process_code")
    eqp_id_col = params.get("eqp_id_col", "eqp_id")
    eqp_name_col = params.get("eqp_name_col", "eqp_name")
    wafer_num_col = params.get("wafer_num_col", "wafer_num")
    planned_hours = float(params.get("planned_hours_per_day", 24.0))
    rated_wafers_per_hour = float(params.get("rated_wafers_per_hour", 0.0))
    default_quality = float(params.get("default_quality", 0.0))
    oee_target = float(params.get("oee_target", 65.0))
    top_n = int(params.get("top_n_equipment", 20))

    # ── 列映射：支持常见的列名变体 ──
    event_time_col = _find_col(df, [event_time_col, "event_time", "gmt_create", "create_time"])
    op_type_col = _find_col(df, [op_type_col, "operation_type", "op_type"])
    lot_col = _find_col(df, [lot_col, "lot_code"])
    proc_col = _find_col(df, [proc_col, "process_code"])
    eqp_id_col = _find_col(df, [eqp_id_col, "eqp_id", "equipment_id"])
    eqp_name_col = _find_col(df, [eqp_name_col, "eqp_name", "equipment_name"])

    if not event_time_col or not op_type_col:
        return AnalysisResult(
            success=False,
            method="oee_report",
            summary="缺少必要列：event_time（事件时间）和 operation_type（操作类型）",
            error=f"可用列: {list(df.columns)}",
        )

    # ── 预处理 ──
    df = df.copy()
    df[event_time_col] = pd.to_datetime(df[event_time_col], errors="coerce")
    df[op_type_col] = pd.to_numeric(df[op_type_col], errors="coerce")

    # 拆分进站（8）/ 出站（9）
    checkin = df[df[op_type_col] == 8].copy()
    checkout = df[df[op_type_col] == 9].copy()

    if checkin.empty:
        return AnalysisResult(
            success=False,
            method="oee_report",
            summary="数据中未找到进站记录（operation_type=8）",
            error="进站数据为空",
        )

    # ── 为进站记录配对最近的出站记录（同 lot + process） ──
    if lot_col and proc_col and not checkout.empty:
        paired = _pair_checkin_checkout(
            checkin, checkout, lot_col, proc_col, event_time_col, eqp_id_col, wafer_num_col
        )
    else:
        # 无法配对：只能统计进站频次，run_minutes=NaN
        paired = checkin[[c for c in [event_time_col, lot_col, proc_col, eqp_id_col, eqp_name_col, wafer_num_col] if c and c in checkin.columns]].copy()
        paired["run_minutes"] = np.nan
        paired["checkout_time"] = pd.NaT

    if paired.empty or "run_minutes" not in paired.columns:
        return AnalysisResult(
            success=False,
            method="oee_report",
            summary="无法配对进出站记录，请检查数据完整性",
            error="run_minutes 列缺失",
        )

    # ── 提取日期 ──
    paired["report_date"] = paired[event_time_col].dt.date.astype(str)

    # ── 按设备+日期聚合 ──
    eqp_col = eqp_id_col or proc_col  # 如果无设备列，用工站代替
    group_col = eqp_col if eqp_col and eqp_col in paired.columns else "report_date"

    agg_cols = [c for c in ["report_date", eqp_id_col, eqp_name_col] if c and c in paired.columns]
    if not agg_cols:
        agg_cols = ["report_date"]

    # 汇总实际加工时间
    group_keys = [c for c in agg_cols if c]
    run_agg = (
        paired[group_keys + ["run_minutes"] + ([wafer_num_col] if wafer_num_col and wafer_num_col in paired.columns else [])]
        .copy()
        .groupby(group_keys, dropna=False)
        .agg(
            actual_run_minutes=("run_minutes", "sum"),
            lot_count=("run_minutes", "count"),
            **({wafer_num_col: (wafer_num_col, "sum")} if wafer_num_col and wafer_num_col in paired.columns else {}),
        )
        .reset_index()
    )

    # ── 计算 OEE 三指标 ──
    planned_minutes = planned_hours * 60
    run_agg["availability"] = (run_agg["actual_run_minutes"] / planned_minutes * 100).clip(0, 100).round(2)

    if rated_wafers_per_hour > 0 and wafer_num_col and wafer_num_col in run_agg.columns:
        theoretical = rated_wafers_per_hour * run_agg["actual_run_minutes"] / 60
        run_agg["performance"] = (run_agg[wafer_num_col] / theoretical.replace(0, np.nan) * 100).clip(0, 100).round(2)
    else:
        run_agg["performance"] = 85.0  # 行业经验默认值

    if default_quality > 0:
        run_agg["quality"] = min(default_quality, 100.0)
    else:
        run_agg["quality"] = 98.0  # 行业经验默认值（未提供良率时）

    run_agg["oee"] = (
        run_agg["availability"] / 100 *
        run_agg["performance"] / 100 *
        run_agg["quality"] / 100 * 100
    ).round(2)

    # ── 汇总统计 ──
    avg_oee = round(run_agg["oee"].mean(), 2)
    avg_avail = round(run_agg["availability"].mean(), 2)
    avg_perf = round(run_agg["performance"].mean(), 2)
    avg_qual = round(run_agg["quality"].mean(), 2)
    below_target = int((run_agg["oee"] < oee_target).sum())
    total_lots = int(paired[lot_col].nunique()) if lot_col and lot_col in paired.columns else 0

    summary = (
        f"OEE 日报：平均 OEE {avg_oee:.1f}%"
        f"（可用率 {avg_avail:.1f}% × 性能效率 {avg_perf:.1f}% × 合格率 {avg_qual:.1f}%）。"
        f"目标 {oee_target}%，{'低于目标的设备/天数: ' + str(below_target) if below_target > 0 else '全部达标。'}"
        f" 共统计批次 {total_lots} 个。"
    )

    # ── 图表 1：OEE 趋势（按日期，全厂平均） ──
    charts = []
    if "report_date" in run_agg.columns:
        trend_daily = (
            run_agg.groupby("report_date", dropna=True)
            .agg(
                oee=("oee", "mean"),
                availability=("availability", "mean"),
                performance=("performance", "mean"),
                quality=("quality", "mean"),
            )
            .reset_index()
            .sort_values("report_date")
        )
        dates = trend_daily["report_date"].astype(str).tolist()

        time_chart = {
            "type": "line",
            "title": "OEE 日趋势",
            "echarts": {
                "tooltip": {"trigger": "axis"},
                "legend": {"bottom": 0, "type": "scroll"},
                "grid": {"left": 50, "right": 20, "top": 40, "bottom": 50},
                "xAxis": {"type": "category", "data": dates, "name": "日期"},
                "yAxis": {"type": "value", "name": "百分比 (%)"},
                "series": [
                    {
                        "type": "line",
                        "name": "OEE",
                        "data": trend_daily["oee"].round(2).tolist(),
                        "symbol": "circle",
                        "symbolSize": 5,
                        "lineStyle": {"color": "#2196F3", "width": 3},
                        "itemStyle": {"color": "#2196F3"},
                    },
                    {
                        "type": "line",
                        "name": "可用率 (A)",
                        "data": trend_daily["availability"].round(2).tolist(),
                        "symbol": "circle",
                        "symbolSize": 4,
                        "lineStyle": {"color": "#4CAF50"},
                        "itemStyle": {"color": "#4CAF50"},
                    },
                    {
                        "type": "line",
                        "name": "性能效率 (P)",
                        "data": trend_daily["performance"].round(2).tolist(),
                        "symbol": "circle",
                        "symbolSize": 4,
                        "lineStyle": {"color": "#FF9800"},
                        "itemStyle": {"color": "#FF9800"},
                    },
                    {
                        "type": "line",
                        "name": f"目标 {oee_target}%",
                        "data": [oee_target] * len(dates),
                        "symbol": "none",
                        "lineStyle": {"color": "#F44336", "type": "dashed"},
                        "itemStyle": {"color": "#F44336"},
                    },
                ],
            },
        }
        charts.append(time_chart)

    # ── 图表 2：设备 OEE 排名（水平柱状） ──
    if eqp_id_col and eqp_id_col in run_agg.columns:
        eqp_agg = (
            run_agg.groupby(eqp_id_col, dropna=True)
            .agg(
                oee=("oee", "mean"),
                availability=("availability", "mean"),
                actual_run_minutes=("actual_run_minutes", "sum"),
            )
            .reset_index()
            .sort_values("oee")
            .head(top_n)
        )

        if eqp_name_col and eqp_name_col in run_agg.columns:
            name_map = run_agg[[eqp_id_col, eqp_name_col]].drop_duplicates().set_index(eqp_id_col)[eqp_name_col]
            eqp_agg["eqp_label"] = eqp_agg[eqp_id_col].map(name_map).fillna(eqp_agg[eqp_id_col])
        else:
            eqp_agg["eqp_label"] = eqp_agg[eqp_id_col].astype(str)

        eqp_labels = eqp_agg["eqp_label"].tolist()
        eqp_oees = eqp_agg["oee"].round(2).tolist()
        colors = ["#F44336" if o < oee_target else "#4CAF50" for o in eqp_oees]

        n_eqp = min(top_n, len(eqp_agg))
        eqp_chart = {
            "type": "bar",
            "title": f"设备 OEE 排名（最低 {n_eqp} 台）",
            "echarts": {
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                "legend": {"bottom": 0},
                "grid": {"left": 150, "right": 30, "top": 40, "bottom": 50},
                "xAxis": {"type": "value", "name": "OEE (%)"},
                "yAxis": {"type": "category", "data": eqp_labels, "name": "设备"},
                "series": [
                    {
                        "type": "bar",
                        "name": "OEE",
                        "data": [
                            {"value": v, "itemStyle": {"color": c}}
                            for v, c in zip(eqp_oees, colors)
                        ],
                    },
                    {
                        "type": "line",
                        "name": f"目标 {oee_target}%",
                        "data": [None] * len(eqp_labels),
                        "markLine": {
                            "silent": True,
                            "data": [{"xAxis": oee_target}],
                            "lineStyle": {"color": "#F44336", "type": "dashed"},
                            "label": {"formatter": f"目标 {oee_target}%"},
                        },
                        "symbol": "none",
                        "lineStyle": {"opacity": 0},
                    },
                ],
            },
        }
        charts.append(eqp_chart)

    return AnalysisResult(
        success=True,
        method="oee_report",
        summary=summary,
        data={
            "avg_oee": avg_oee,
            "avg_availability": avg_avail,
            "avg_performance": avg_perf,
            "avg_quality": avg_qual,
            "oee_target": oee_target,
            "below_target_count": below_target,
            "total_lots_tracked": total_lots,
            "daily_detail": run_agg.head(500).to_dict(orient="records"),
        },
        charts=charts,
        metadata={
            "rows_analyzed": len(df),
            "checkin_records": len(checkin),
            "checkout_records": len(checkout),
            "paired_records": int((~paired["run_minutes"].isna()).sum()),
            "method": "oee_report",
        },
    )


# ── 私有辅助函数 ─────────────────────────────────────────────────────────────

def _find_col(df: pd.DataFrame, candidates: list) -> str | None:
    """从候选列名中找到第一个存在于 DataFrame 的列。"""
    for c in candidates:
        if c and c in df.columns:
            return c
    return None


def _pair_checkin_checkout(
    checkin: pd.DataFrame,
    checkout: pd.DataFrame,
    lot_col: str,
    proc_col: str,
    time_col: str,
    eqp_id_col: str | None,
    wafer_num_col: str | None,
) -> pd.DataFrame:
    """
    将进站记录与最近的出站记录配对，计算 run_minutes。

    策略：对每条进站记录，找同一 lot_code + process_code 下
    gmt_create 最小且大于进站时间的出站记录。
    """
    # 重命名出站时间列避免冲突
    co = checkout[[lot_col, proc_col, time_col]].copy().rename(columns={time_col: "checkout_time"})

    # 使用 merge + filter 方式
    merged = checkin.merge(co, on=[lot_col, proc_col], how="left")
    # 仅保留出站时间晚于进站时间的行
    merged = merged[merged["checkout_time"] >= merged[time_col]].copy()

    # 每条进站记录取最近一条出站
    merged = merged.sort_values("checkout_time")
    merged = merged.groupby(
        [c for c in checkin.columns if c != time_col and c in merged.columns] + [time_col],
        dropna=False,
    ).first().reset_index()

    # 补回没有找到出站记录的进站记录（run_minutes=NaN）
    all_keys = list(checkin.columns)
    paired = checkin[all_keys].merge(
        merged[[lot_col, proc_col, time_col, "checkout_time"]],
        on=[lot_col, proc_col, time_col],
        how="left",
    )

    # 计算加工时长（分钟）
    paired["run_minutes"] = (
        (pd.to_datetime(paired["checkout_time"]) - pd.to_datetime(paired[time_col]))
        .dt.total_seconds()
        / 60
    )
    # 排除异常负值或超大值（超过 7 天视为无效配对）
    paired.loc[paired["run_minutes"] <= 0, "run_minutes"] = np.nan
    paired.loc[paired["run_minutes"] > 7 * 24 * 60, "run_minutes"] = np.nan

    return paired
