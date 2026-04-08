"""
OEE (设备综合效率) 计算器

三因子分解：
  可用率 = 实际运行时间 / 计划生产时间 × 100%
  性能率 = (理论节拍时间 × 实际产出数量) / 实际运行时间 × 100%
  良品率 = 首次检验合格晶圆数 / 首次检验总晶圆数 × 100%（调用 first_pass_yield）
  OEE   = 可用率 × 性能率 × 良品率 / 10000

数据源：
  - 非计划停机：equipment_oee_status（关联 equipment_oee），暂无数据时默认 0
  - 实际产出：matrix_routerx_operation_lot_batch_resume_log（operation_type=9 出站记录）
  - 计划停机/理论节拍：app/skills/oee_config.json 固定值
  - 良品率：FirstPassYieldComputer（first_pass_yield skill）
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from app.analytics.metrics.base import MetricComputer, MetricResult
from app.analytics.registry import register_metric
from app.analytics.tool_registry import register_compute_tool

logger = logging.getLogger(__name__)

# 配置文件路径（相对于项目根目录）
_CONFIG_PATH = Path(__file__).parent.parent.parent / "skills" / "oee_config.json"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_planned_downtime_hours(config: dict, equipment_code: str, query_days: float) -> float:
    """按设备获取计划停机时长（小时），月度固定值按天折算。"""
    pd_cfg = config["planned_downtime"]
    monthly = pd_cfg["by_equipment"].get(equipment_code, pd_cfg["default"])
    return monthly / 30.0 * query_days


def _get_theoretical_cycle_time(config: dict, equipment_code: str, recipe_code: str) -> float:
    """按设备+recipe 获取理论节拍时间（分钟/片）。"""
    ct_cfg = config["theoretical_cycle_time"]
    recipes = ct_cfg["by_equipment_recipe"].get(equipment_code, {})
    return recipes.get(recipe_code, ct_cfg["default"])


def _compute_unplanned_downtime(
    state_df: pd.DataFrame,
    config: dict,
    query_start: pd.Timestamp,
    query_end: pd.Timestamp,
) -> float:
    """
    从设备状态 DataFrame 汇总非计划停机时长（小时）。
    state_df 需含列: status_code, start_time, end_time
    跨查询边界的记录按时间范围裁剪。
    """
    if state_df is None or state_df.empty:
        return 0.0

    unplanned = set(config["unplanned_downtime_states"]["values"])
    total_min = 0.0
    for _, row in state_df.iterrows():
        if str(row.get("status_code", "")) not in unplanned:
            continue
        try:
            start = max(pd.Timestamp(row["start_time"]), query_start)
            end = min(pd.Timestamp(row["end_time"]), query_end)
            if end > start:
                total_min += (end - start).total_seconds() / 60.0
        except Exception:
            continue
    return total_min / 60.0


@register_metric
@register_compute_tool(
    name="oee_computer",
    description=(
        "计算设备综合效率 (OEE = 可用率 × 性能率 × 良品率)。"
        "输入 DataFrame 需含出站记录（实际产出）和设备状态记录（停机时长）两类数据，"
        "或分别通过 output_df / state_df 参数传入。"
        "计划停机时间和理论节拍时间从 oee_config.json 读取固定值。"
        "良品率通过 fpy_percent 参数传入（由调用方先调用 first_pass_yield_computer 获取）。"
    ),
    input_schema=[
        "equipment_code", "actual_output", "process_code", "recipe_code",
        "start_time", "end_time", "report_date",
        "status_code",   # 设备状态记录（equipment_oee_status）
    ],
)
class OEEComputer(MetricComputer):
    metric_name = "oee"
    skill_name = "oee"

    def compute(
        self,
        df: pd.DataFrame,
        group_by: Optional[List[str]] = None,
        # ── 额外参数 ──────────────────────────────────────────────
        output_df: Optional[pd.DataFrame] = None,   # 实际产出明细（出站记录）
        state_df: Optional[pd.DataFrame] = None,    # 设备状态记录（equipment_oee_status）
        fpy_percent: Optional[float] = None,        # 良品率（0~100），由调用方先调 FPY skill
        query_start: Optional[str] = None,          # 查询起始时间（ISO 字符串）
        query_end: Optional[str] = None,            # 查询结束时间（ISO 字符串）
        recipe_code: str = "",                      # 理论节拍查找用
        **kwargs,
    ) -> MetricResult:
        """
        计算 OEE。

        调用方负责：
          1. 执行 SQL 获取 output_df（出站记录）和 state_df（设备状态记录）
          2. 调用 first_pass_yield_computer 获取 fpy_percent
          3. 传入 query_start / query_end（时间范围边界）
          4. 传入 recipe_code（理论节拍查找）

        output_df 期望列：equipment_code, actual_output（或通过 wafer 明细计数），
                          start_time/end_time, product_code, report_date
        state_df  期望列：equipment_code, status_code, start_time, end_time
        """
        try:
            config = _load_config()
        except Exception as e:
            return MetricResult(
                metric_name=self.metric_name,
                success=False,
                summary="无法加载 oee_config.json",
                error=str(e),
            )

        # 合并 df 参数：优先使用明确传入的 output_df，否则用 df（兼容统一调用接口）
        prod_df = output_df if output_df is not None else df
        if prod_df is None or prod_df.empty:
            return MetricResult(
                metric_name=self.metric_name,
                success=False,
                summary="无产出数据",
                error="output_df / df 为空，无法计算 OEE",
            )

        prod_df = prod_df.copy()
        prod_df.columns = [c.lower() for c in prod_df.columns]

        # ── 自动调用 FPY skill（当 fpy_percent 未由调用方传入时）──────────────
        # depends_on_skills 的实现：supervisor/executor 暂未编排 skill 依赖链，
        # 在此内部自调 FirstPassYieldComputer，避免质量因子恒为 100%。
        # 触发条件：fpy_percent=None 且 prod_df 含有 FPY 所需列
        _FPY_REQUIRED = {"wafer_id", "wafer_type", "ng_code", "rn"}
        if fpy_percent is None and _FPY_REQUIRED.issubset(set(prod_df.columns)):
            try:
                from app.analytics.metrics.first_pass_yield import FirstPassYieldComputer
                fpy_result = FirstPassYieldComputer().compute(prod_df, group_by=[])
                if fpy_result.success and fpy_result.value is not None:
                    fpy_percent = float(fpy_result.value)
                    logger.info(f"[OEEComputer] auto-called FPY skill → fpy_percent={fpy_percent:.2f}%")
            except Exception as e:
                logger.warning(f"[OEEComputer] auto FPY call failed, defaulting quality to 100%: {e}")
        # fpy_df 参数（old interface）仍支持：若传入则以 fpy_df 列重新算 FPY
        if fpy_percent is None:
            _fpy_df = kwargs.get("fpy_df")
            if _fpy_df is not None and not _fpy_df.empty:
                try:
                    from app.analytics.metrics.first_pass_yield import FirstPassYieldComputer
                    fpy_result = FirstPassYieldComputer().compute(_fpy_df, group_by=[])
                    if fpy_result.success and fpy_result.value is not None:
                        fpy_percent = float(fpy_result.value)
                        logger.info(f"[OEEComputer] fpy_df FPY → fpy_percent={fpy_percent:.2f}%")
                except Exception as e:
                    logger.warning(f"[OEEComputer] fpy_df FPY call failed: {e}")

        # 时间范围
        try:
            ts_start = pd.Timestamp(query_start) if query_start else pd.Timestamp(prod_df["start_time"].min())
            ts_end   = pd.Timestamp(query_end)   if query_end   else pd.Timestamp(prod_df["end_time"].max())
        except Exception:
            ts_start = pd.Timestamp.now() - pd.Timedelta(days=30)
            ts_end   = pd.Timestamp.now()

        calendar_hours = (ts_end - ts_start).total_seconds() / 3600.0
        query_days = calendar_hours / 24.0

        # ── 按设备分组计算 ──────────────────────────────────────────
        if "equipment_code" not in prod_df.columns:
            # 降级：计算全局单一 OEE
            return self._compute_single(
                prod_df, state_df, config,
                equipment_code="unknown",
                calendar_hours=calendar_hours,
                query_days=query_days,
                ts_start=ts_start, ts_end=ts_end,
                fpy_percent=fpy_percent,
                recipe_code=recipe_code,
                group_by=group_by or [],
            )

        equipment_codes = prod_df["equipment_code"].dropna().unique().tolist()
        if not equipment_codes:
            return MetricResult(
                metric_name=self.metric_name,
                success=False,
                summary="产出记录中无 equipment_code",
                error="无法识别设备，请检查数据",
            )

        detail = []
        for eq_code in equipment_codes:
            eq_prod = prod_df[prod_df["equipment_code"] == eq_code]
            eq_state = None
            if state_df is not None and not state_df.empty:
                st = state_df.copy()
                st.columns = [c.lower() for c in st.columns]
                if "equipment_code" in st.columns:
                    eq_state = st[st["equipment_code"] == eq_code]

            row = self._calc_oee_row(
                eq_prod, eq_state, config,
                equipment_code=eq_code,
                calendar_hours=calendar_hours,
                query_days=query_days,
                ts_start=ts_start, ts_end=ts_end,
                fpy_percent=fpy_percent,
                recipe_code=recipe_code,
            )
            detail.append(row)

        overall = sum(r["oee_pct"] for r in detail) / len(detail) if detail else 0.0

        charts = self._build_charts(detail)
        return MetricResult(
            metric_name=self.metric_name,
            success=True,
            summary=f"设备 OEE 均值: {overall:.2f}%（共 {len(detail)} 台设备）",
            value=round(overall, 2),
            detail=detail,
            charts=charts,
            metadata={
                "query_start": ts_start.isoformat(),
                "query_end": ts_end.isoformat(),
                "calendar_hours": round(calendar_hours, 2),
                "equipment_count": len(detail),
                "group_by": group_by or ["equipment_code"],
            },
        )

    # ── 内部计算方法 ─────────────────────────────────────────────

    def _calc_oee_row(
        self,
        prod_df: pd.DataFrame,
        state_df: Optional[pd.DataFrame],
        config: dict,
        *,
        equipment_code: str,
        calendar_hours: float,
        query_days: float,
        ts_start: pd.Timestamp,
        ts_end: pd.Timestamp,
        fpy_percent: Optional[float],
        recipe_code: str,
    ) -> Dict[str, Any]:
        """计算单台设备的 OEE 行数据。"""

        # ── 可用率 ──────────────────────────────────────────────
        planned_down_h = _get_planned_downtime_hours(config, equipment_code, query_days)
        planned_prod_h = max(0.0, calendar_hours - planned_down_h)

        data_coverage = "ok"
        if state_df is None or state_df.empty:
            unplanned_down_h = 0.0
            data_coverage = "no_state_records"
        else:
            unplanned_down_h = _compute_unplanned_downtime(state_df, config, ts_start, ts_end)

        actual_run_h = max(0.0, planned_prod_h - unplanned_down_h)
        availability = (actual_run_h / planned_prod_h * 100) if planned_prod_h > 0 else 0.0
        availability = max(0.0, min(100.0, availability))

        # ── 性能率 ──────────────────────────────────────────────
        # 实际产出数量：直接按行数统计（每行=1片晶圆出站），也可读 actual_output 列
        if "actual_output" in prod_df.columns:
            actual_output = int(prod_df["actual_output"].sum())
        else:
            # 降级：按行数统计（wafer detail log 每行=1片）
            actual_output = len(prod_df)

        # recipe_code：优先参数，其次从 prod_df 中取众数
        rc = recipe_code
        if not rc and "recipe_code" in prod_df.columns:
            rc_counts = prod_df["recipe_code"].value_counts()
            rc = str(rc_counts.index[0]) if not rc_counts.empty else ""

        theoretical_ct_min = _get_theoretical_cycle_time(config, equipment_code, rc)
        actual_run_min = actual_run_h * 60.0
        if actual_run_min > 0:
            performance = min(100.0, theoretical_ct_min * actual_output / actual_run_min * 100)
        else:
            performance = 0.0

        # ── 良品率 ──────────────────────────────────────────────
        quality = fpy_percent if fpy_percent is not None else 100.0
        quality_source = "first_pass_yield_skill" if fpy_percent is not None else "default_100"

        # ── OEE ────────────────────────────────────────────────
        oee = availability * performance * quality / 10000.0

        return {
            "equipment_code": equipment_code,
            "calendar_hours": round(calendar_hours, 2),
            "planned_downtime_hours": round(planned_down_h, 2),
            "unplanned_downtime_hours": round(unplanned_down_h, 2),
            "planned_production_hours": round(planned_prod_h, 2),
            "actual_run_hours": round(actual_run_h, 2),
            "availability_pct": round(availability, 2),
            "actual_output_count": actual_output,
            "theoretical_cycle_time_min": theoretical_ct_min,
            "recipe_code": rc,
            "performance_pct": round(performance, 2),
            "quality_pct": round(quality, 2),
            "quality_source": quality_source,
            "oee_pct": round(oee, 2),
            "data_coverage": data_coverage,
        }

    def _compute_single(
        self,
        prod_df: pd.DataFrame,
        state_df: Optional[pd.DataFrame],
        config: dict,
        *,
        equipment_code: str,
        calendar_hours: float,
        query_days: float,
        ts_start: pd.Timestamp,
        ts_end: pd.Timestamp,
        fpy_percent: Optional[float],
        recipe_code: str,
        group_by: List[str],
    ) -> MetricResult:
        """equipment_code 列不存在时的降级路径，计算全局汇总 OEE。"""
        row = self._calc_oee_row(
            prod_df, state_df, config,
            equipment_code=equipment_code,
            calendar_hours=calendar_hours,
            query_days=query_days,
            ts_start=ts_start, ts_end=ts_end,
            fpy_percent=fpy_percent,
            recipe_code=recipe_code,
        )
        return MetricResult(
            metric_name=self.metric_name,
            success=True,
            summary=f"OEE: {row['oee_pct']:.2f}%（可用率 {row['availability_pct']:.2f}% × 性能率 {row['performance_pct']:.2f}% × 良品率 {row['quality_pct']:.2f}%）",
            value=round(row["oee_pct"], 2),
            detail=[row],
            charts=self._build_charts([row]),
            metadata={
                "query_start": ts_start.isoformat(),
                "query_end": ts_end.isoformat(),
                "calendar_hours": round(calendar_hours, 2),
                "data_coverage": row.get("data_coverage"),
            },
        )

    def _build_charts(self, detail: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """构建 ECharts 配置：三因子分组条形图 + OEE 总值。"""
        if not detail:
            return []

        eq_codes = [r["equipment_code"] for r in detail]

        # 三因子分组条形图
        bar_chart = {
            "type": "bar",
            "title": "设备 OEE 三因子分解",
            "xAxis": eq_codes,
            "series": [
                {
                    "name": "可用率 (%)",
                    "data": [r["availability_pct"] for r in detail],
                },
                {
                    "name": "性能率 (%)",
                    "data": [r["performance_pct"] for r in detail],
                },
                {
                    "name": "良品率 (%)",
                    "data": [r["quality_pct"] for r in detail],
                },
                {
                    "name": "OEE (%)",
                    "data": [r["oee_pct"] for r in detail],
                    "markLine": {
                        "data": [{"yAxis": 85}],
                        "label": {"formatter": "世界级基准 85%"},
                    },
                },
            ],
            "yAxis": {"max": 100},
        }

        return [bar_chart]
