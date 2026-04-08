"""
OEE 指标查询测试脚本（20 cases，覆盖 7 个分组）

运行方式：
  python _test_oee_queries.py          # Unit + API 全跑
  python _test_oee_queries.py --unit   # 只跑 Unit 层
  python _test_oee_queries.py --api    # 只跑 API 层

Unit 层（Case 1-18）：直接调用 OEEComputer.compute()，不依赖后端
API  层（Case 19-20）：通过 /api/v1/chat 测试模糊路由
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

# ── 去掉代理，避免 httpx 被重定向 ────────────────────────────────────
for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
    os.environ.pop(k, None)

SEP = "=" * 72
PASS = "✅ PASS"
FAIL = "❌ FAIL"
SKIP = "⚠️  SKIP"

BASE_URL = "http://localhost:8000"

# ── 基准时间窗口 ──────────────────────────────────────────────────────
NOW   = datetime(2026, 4, 8, 23, 59, 59)
D7_S  = NOW - timedelta(days=7)
D30_S = NOW - timedelta(days=30)

# ── 辅助：构造出站产出 DataFrame ─────────────────────────────────────
def _make_output_df(
    eq_codes: List[str],
    rows_per_eq: int = 20,
    start: datetime = D7_S,
    end: datetime = NOW,
    recipe_code: str = "GaN_HEMT_std",
    actual_output_per_row: int = 1,
) -> pd.DataFrame:
    records = []
    span = (end - start).total_seconds()
    for eq in eq_codes:
        for i in range(rows_per_eq):
            t = start + timedelta(seconds=span * i / max(rows_per_eq - 1, 1))
            records.append({
                "equipment_code": eq,
                "actual_output": actual_output_per_row,
                "start_time": t.isoformat(),
                "end_time": (t + timedelta(hours=2)).isoformat(),
                "recipe_code": recipe_code,
                "process_code": "EPIT-01",
                "report_date": t.date().isoformat(),
            })
    return pd.DataFrame(records)


def _make_state_df(
    eq_codes: List[str],
    breakdown_hours: float = 8.0,
    start: datetime = D7_S,
) -> pd.DataFrame:
    """注入非计划停机记录（status_code='breakdown'）。"""
    records = []
    for eq in eq_codes:
        t_s = start + timedelta(hours=2)
        t_e = t_s + timedelta(hours=breakdown_hours)
        records.append({
            "equipment_code": eq,
            "status_code": "breakdown",
            "status_name": "设备故障",
            "start_time": t_s.isoformat(),
            "end_time": t_e.isoformat(),
        })
    return pd.DataFrame(records)


# ══════════════════════════════════════════════════════════════════════
# UNIT 层测试（直接调用 OEEComputer）
# ══════════════════════════════════════════════════════════════════════

_pass_count = 0
_fail_count = 0


def _assert(cond: bool, msg: str) -> None:
    global _pass_count, _fail_count
    if cond:
        print(f"  {PASS}  {msg}")
        _pass_count += 1
    else:
        print(f"  {FAIL}  {msg}")
        _fail_count += 1


def _header(case_id: str, title: str) -> None:
    print(f"\n{SEP}")
    print(f"  Case {case_id}: {title}")
    print(SEP)


# ── Group 1: 核心功能 — 单设备查询 (Case 1-4) ─────────────────────────

def case_01_single_eq_full_oee():
    """单设备 MOCVD-01，7天，全三因子正常输出。"""
    _header("01", "单设备 MOCVD-01 全三因子（7天）")
    from app.analytics.metrics.oee import OEEComputer
    c = OEEComputer()
    df = _make_output_df(["MOCVD-01"], rows_per_eq=50, recipe_code="GaN_HEMT_std")
    r = c.compute(df, query_start=D7_S.isoformat(), query_end=NOW.isoformat(), fpy_percent=95.0)
    print(f"  summary: {r.summary}")
    print(f"  value  : {r.value}")
    if r.detail:
        d = r.detail[0]
        print(f"  availability={d['availability_pct']}%  perf={d['performance_pct']}%  quality={d['quality_pct']}%  OEE={d['oee_pct']}%")
    _assert(r.success, "success=True")
    _assert(r.value is not None and 0 < r.value < 100, f"OEE 在 (0, 100) 范围内 (got {r.value})")
    _assert(len(r.detail) == 1, "detail 含 1 条设备记录")
    _assert(r.detail[0]["equipment_code"] == "MOCVD-01", "equipment_code 正确")
    _assert(r.detail[0]["quality_pct"] == 95.0, "良品率=传入的 fpy_percent 95.0")
    _assert(len(r.charts) >= 1, "charts 不为空")


def case_02_single_eq_no_state():
    """单设备，无状态记录 → data_coverage=no_state_records，可用率=100%。"""
    _header("02", "单设备无状态记录（equipment_oee_status 为空）")
    from app.analytics.metrics.oee import OEEComputer
    c = OEEComputer()
    df = _make_output_df(["MOCVD-02"], rows_per_eq=30, recipe_code="GaN_LED_std")
    r = c.compute(df, query_start=D7_S.isoformat(), query_end=NOW.isoformat(), fpy_percent=90.0)
    print(f"  summary: {r.summary}")
    if r.detail:
        d = r.detail[0]
        print(f"  data_coverage={d['data_coverage']}  availability={d['availability_pct']}%")
    _assert(r.success, "success=True")
    _assert(r.detail[0]["data_coverage"] == "no_state_records", "data_coverage=no_state_records")
    _assert(r.detail[0]["unplanned_downtime_hours"] == 0.0, "非计划停机=0（无记录时默认值）")
    _assert(r.detail[0]["availability_pct"] == 100.0, "可用率=100%（无非计划停机）")


def case_03_single_eq_with_breakdown():
    """单设备，注入 8h 故障停机 → 可用率明显下降。"""
    _header("03", "单设备含 8h 故障停机 → 可用率下降")
    from app.analytics.metrics.oee import OEEComputer
    c = OEEComputer()
    df = _make_output_df(["MOCVD-01"], rows_per_eq=40, recipe_code="GaN_HEMT_std")
    state = _make_state_df(["MOCVD-01"], breakdown_hours=8.0)
    r = c.compute(df, state_df=state,
                  query_start=D7_S.isoformat(), query_end=NOW.isoformat(),
                  fpy_percent=92.0)
    print(f"  summary: {r.summary}")
    if r.detail:
        d = r.detail[0]
        print(f"  unplanned_down={d['unplanned_downtime_hours']}h  avail={d['availability_pct']}%")
    _assert(r.success, "success=True")
    _assert(r.detail[0]["unplanned_downtime_hours"] == 8.0, "非计划停机=8h")
    _assert(r.detail[0]["availability_pct"] < 100.0, "可用率 < 100%（有故障停机）")
    _assert(r.detail[0]["oee_pct"] < r.detail[0]["availability_pct"] * r.detail[0]["quality_pct"] / 100, "OEE < avail×quality（性能率<100%）")


def case_04_recipe_cycle_time_lookup():
    """不同 recipe → 理论节拍时间从 config 正确读取。"""
    _header("04", "recipe 节拍查找：GaN_HEMT_std=120min vs GaN_LED_std=90min")
    from app.analytics.metrics.oee import OEEComputer, _get_theoretical_cycle_time, _load_config
    cfg = _load_config()
    ct_hemt = _get_theoretical_cycle_time(cfg, "MOCVD-01", "GaN_HEMT_std")
    ct_led  = _get_theoretical_cycle_time(cfg, "MOCVD-01", "GaN_LED_std")
    ct_miss = _get_theoretical_cycle_time(cfg, "MOCVD-01", "UNKNOWN_RECIPE")
    ct_unknown_eq = _get_theoretical_cycle_time(cfg, "UNKNOWN-EQ", "GaN_HEMT_std")
    print(f"  GaN_HEMT_std={ct_hemt}min  GaN_LED_std={ct_led}min  UNKNOWN={ct_miss}min(default)  UNKNOWN-EQ={ct_unknown_eq}min")
    _assert(ct_hemt == 120, "MOCVD-01 GaN_HEMT_std=120min")
    _assert(ct_led == 90,   "MOCVD-01 GaN_LED_std=90min")
    _assert(ct_miss == cfg["theoretical_cycle_time"]["default"], "未知 recipe 回落到 default")
    _assert(ct_unknown_eq == cfg["theoretical_cycle_time"]["default"], "未知设备回落到 default")


# ── Group 2: 多设备 / 全设备 (Case 5-7) ─────────────────────────────

def case_05_multi_eq_grouped():
    """3台设备同时计算 → detail 各含 1 行，均值作为总 OEE。"""
    _header("05", "多设备（MOCVD-01/02 + MBE-01）分组计算")
    from app.analytics.metrics.oee import OEEComputer
    c = OEEComputer()
    df = _make_output_df(["MOCVD-01", "MOCVD-02", "MBE-01"], rows_per_eq=20, recipe_code="GaN_HEMT_std")
    r = c.compute(df, query_start=D7_S.isoformat(), query_end=NOW.isoformat(), fpy_percent=88.0)
    print(f"  summary: {r.summary}")
    for d in r.detail:
        print(f"  {d['equipment_code']}: avail={d['availability_pct']}%  perf={d['performance_pct']}%  OEE={d['oee_pct']}%")
    _assert(r.success, "success=True")
    _assert(len(r.detail) == 3, "detail 含 3 行（每台设备 1 行）")
    eq_codes = {d["equipment_code"] for d in r.detail}
    _assert(eq_codes == {"MOCVD-01", "MOCVD-02", "MBE-01"}, "三台设备均有记录")
    expected_avg = sum(d["oee_pct"] for d in r.detail) / 3
    _assert(abs(r.value - round(expected_avg, 2)) < 0.01, f"返回值=detail 均值 (got {r.value})")


def case_06_per_equipment_planned_downtime():
    """各设备 planned_downtime 按各自 config 值折算，MOCVD > MBE (月度 36h vs 24h)。"""
    _header("06", "按设备差异化计划停机时间（config.planned_downtime.by_equipment）")
    from app.analytics.metrics.oee import OEEComputer, _get_planned_downtime_hours, _load_config
    cfg = _load_config()
    days = 30
    pd_mocvd = _get_planned_downtime_hours(cfg, "MOCVD-01", days)
    pd_mbe   = _get_planned_downtime_hours(cfg, "MBE-01",   days)
    pd_xrd   = _get_planned_downtime_hours(cfg, "XRD-01",   days)
    pd_unk   = _get_planned_downtime_hours(cfg, "UNKNOWN",  days)
    print(f"  30天计划停机: MOCVD-01={pd_mocvd}h  MBE-01={pd_mbe}h  XRD-01={pd_xrd}h  UNKNOWN={pd_unk}h(default)")
    _assert(pd_mocvd == 36.0, "MOCVD-01 月30天=36h")
    _assert(pd_mbe   == 24.0, "MBE-01 月30天=24h")
    _assert(pd_xrd   == 12.0, "XRD-01 月30天=12h")
    _assert(pd_unk   == cfg["planned_downtime"]["default"], "未知设备=default(24h)")


def case_07_unknown_equipment_code():
    """config 里不存在的设备 → 用 default 值，能正常返回结果（Case 18 边界）。"""
    _header("07/18", "config 里没有的设备（NEW-EQ-99）→ 回落 default 仍正常计算")
    from app.analytics.metrics.oee import OEEComputer
    c = OEEComputer()
    df = _make_output_df(["NEW-EQ-99"], rows_per_eq=10)
    r = c.compute(df, query_start=D7_S.isoformat(), query_end=NOW.isoformat(), fpy_percent=85.0)
    print(f"  summary: {r.summary}")
    if r.detail:
        d = r.detail[0]
        print(f"  theoretical_ct={d['theoretical_cycle_time_min']}min  OEE={d['oee_pct']}%")
    _assert(r.success, "success=True（用 default config 值）")
    _assert(r.detail[0]["theoretical_cycle_time_min"] == 120, "理论节拍=default 120min")


# ── Group 3: 三因子拆解验证 (Case 8-10) ─────────────────────────────

def case_08_factors_multiply_to_oee():
    """OEE = avail × perf × quality / 10000，验证三因子乘积。"""
    _header("08", "三因子乘积验算（OEE = A × P × Q / 10000）")
    from app.analytics.metrics.oee import OEEComputer
    c = OEEComputer()
    df = _make_output_df(["MOCVD-01"], rows_per_eq=25, recipe_code="GaN_HEMT_std")
    r = c.compute(df, query_start=D7_S.isoformat(), query_end=NOW.isoformat(), fpy_percent=90.0)
    _assert(r.success, "success=True")
    d = r.detail[0]
    expected = round(d["availability_pct"] * d["performance_pct"] * d["quality_pct"] / 10000, 2)
    print(f"  A={d['availability_pct']}% × P={d['performance_pct']}% × Q={d['quality_pct']}% = {expected}%  returned={r.value}%")
    _assert(abs(d["oee_pct"] - expected) < 0.01, f"三因子乘积正确（got {d['oee_pct']}，expect {expected}）")


def case_09_quality_default_100():
    """fpy_percent=None → 良品率默认 100%，quality_source='default_100'。"""
    _header("09", "fpy_percent 未传入 → quality 默认 100%（Case 17 特例）")
    from app.analytics.metrics.oee import OEEComputer
    c = OEEComputer()
    df = _make_output_df(["MBE-01"], rows_per_eq=20, recipe_code="InP_base")
    r = c.compute(df, query_start=D7_S.isoformat(), query_end=NOW.isoformat())  # 不传 fpy_percent
    _assert(r.success, "success=True")
    _assert(r.detail[0]["quality_pct"] == 100.0, "quality_pct=100.0（未传 fpy_percent）")
    _assert(r.detail[0]["quality_source"] == "default_100", "quality_source='default_100'")


def case_10_performance_capped_100():
    """实际节拍远快于理论（少量晶圆跑大量时间）→ 性能率 ≤ 100%，不超限。"""
    _header("10", "性能率上限=100%（极端情况：产出远超理论最大值）")
    from app.analytics.metrics.oee import OEEComputer
    c = OEEComputer()
    # 7天 = 168h = 10080min；理论节拍=120min/wafer；最大理论产出=84片
    # 传入 actual_output=500片 → 性能率若不限制会 >100%
    rows = []
    for i in range(500):
        t = D7_S + timedelta(hours=i * 0.3)
        rows.append({
            "equipment_code": "MOCVD-01",
            "actual_output": 1,
            "start_time": D7_S.isoformat(),
            "end_time": NOW.isoformat(),
            "recipe_code": "GaN_HEMT_std",
        })
    df = pd.DataFrame(rows)
    r = c.compute(df, query_start=D7_S.isoformat(), query_end=NOW.isoformat(), fpy_percent=90.0)
    _assert(r.success, "success=True")
    _assert(r.detail[0]["performance_pct"] <= 100.0, f"性能率≤100% (got {r.detail[0]['performance_pct']})")
    print(f"  performance_pct={r.detail[0]['performance_pct']}%（上限截断正常）")


# ── Group 4 & 5: 时间粒度（Case 11-13）、跨 Skill 联动（Case 14-15） ─

def case_11_7day_window():
    """7天窗口：calendar_hours ≈ 168h，query_days≈7。"""
    _header("11", "7天时间窗口校验")
    from app.analytics.metrics.oee import OEEComputer
    c = OEEComputer()
    df = _make_output_df(["MOCVD-01"], rows_per_eq=30)
    r = c.compute(df, query_start=D7_S.isoformat(), query_end=NOW.isoformat(), fpy_percent=90.0)
    ch = r.metadata.get("calendar_hours", 0)
    print(f"  calendar_hours={ch}h (expect ~168)")
    _assert(r.success, "success=True")
    _assert(abs(ch - 168) < 1, f"calendar_hours≈168 (got {ch})")


def case_12_30day_window():
    """30天窗口：calendar_hours ≈ 720h。"""
    _header("12", "30天时间窗口校验")
    from app.analytics.metrics.oee import OEEComputer
    c = OEEComputer()
    df = _make_output_df(["MOCVD-02"], rows_per_eq=30, start=D30_S, end=NOW)
    r = c.compute(df, query_start=D30_S.isoformat(), query_end=NOW.isoformat(), fpy_percent=88.0)
    ch = r.metadata.get("calendar_hours", 0)
    print(f"  calendar_hours={ch}h (expect ~720)")
    _assert(r.success, "success=True")
    _assert(abs(ch - 720) < 2, f"calendar_hours≈720 (got {ch})")


def case_13_charts_structure():
    """charts 包含至少一组 series，且 series 有 availability/performance/quality/oee 四项。"""
    _header("13", "图表结构验证（三因子 + OEE 总值，含 85% 基准线）")
    from app.analytics.metrics.oee import OEEComputer
    c = OEEComputer()
    df = _make_output_df(["MOCVD-01", "MOCVD-02"], rows_per_eq=20)
    r = c.compute(df, query_start=D7_S.isoformat(), query_end=NOW.isoformat(), fpy_percent=88.0)
    _assert(r.success, "success=True")
    _assert(len(r.charts) >= 1, "charts 不为空")
    ch0 = r.charts[0]
    _assert(ch0.get("type") == "bar", "第一张图为柱状图（bar）")
    series_names = [s["name"] for s in ch0.get("series", [])]
    print(f"  series names: {series_names}")
    _assert("可用率 (%)" in series_names, "series 含 可用率")
    _assert("性能率 (%)" in series_names, "series 含 性能率")
    _assert("良品率 (%)" in series_names, "series 含 良品率")
    _assert("OEE (%)" in series_names, "series 含 OEE (%)")
    oee_series = next(s for s in ch0["series"] if s["name"] == "OEE (%)")
    _assert("markLine" in oee_series, "OEE series 含 markLine（85% 基准线）")


def case_14_quality_from_fpy_skill():
    """
    跨 skill 联动验证：手动调用 FirstPassYieldComputer 得到 fpy_percent，
    再传入 OEEComputer → quality_source='first_pass_yield_skill'。
    （依赖 Group 1 测试数据，不走后端）
    """
    _header("14", "跨 Skill 联动：FPY → OEE quality（质量因子由 FPY skill 提供）")
    from app.analytics.metrics.first_pass_yield import FirstPassYieldComputer
    from app.analytics.metrics.oee import OEEComputer

    # 构造 FPY 计算所需的 wafer 明细
    wafer_rows = []
    for i in range(100):
        wafer_rows.append({
            "wafer_id": f"W{i:04d}",
            "process_code": "EPIT-01",
            "wafer_type": "good" if i < 92 else "reject",   # 92% 合格
            "ng_code": None if i < 92 else "NG001",
            "rn": 1,
            "product_code": "GaN-HEMT-A",
            "report_date": "2026-04-01",
        })
    fpy_df = pd.DataFrame(wafer_rows)
    fpy_computer = FirstPassYieldComputer()
    fpy_result = fpy_computer.compute(fpy_df)
    print(f"  FPY result: success={fpy_result.success}  value={fpy_result.value}")
    _assert(fpy_result.success, "FPY skill 计算成功")

    fpy_pct = fpy_result.value  # 某个代表值（None 或 float）
    if fpy_pct is None:
        # FPY skill 按站点联乘返回，取全流程值
        if fpy_result.detail:
            fpy_pct = fpy_result.detail[0].get("fpy_pct") or 92.0
        else:
            fpy_pct = 92.0
    print(f"  使用 fpy_percent={fpy_pct}")

    oee_computer = OEEComputer()
    out_df = _make_output_df(["MOCVD-01"], rows_per_eq=30, recipe_code="GaN_HEMT_std")
    oee_result = oee_computer.compute(out_df,
                                      query_start=D7_S.isoformat(), query_end=NOW.isoformat(),
                                      fpy_percent=fpy_pct)
    print(f"  OEE result: {oee_result.summary}")
    _assert(oee_result.success, "OEE skill 计算成功")
    _assert(oee_result.detail[0]["quality_source"] == "first_pass_yield_skill",
            "quality_source='first_pass_yield_skill'（quality 由 FPY skill 提供）")
    _assert(oee_result.detail[0]["quality_pct"] == fpy_pct,
            f"quality_pct == fpy_percent ({fpy_pct})")


def case_15_fpy_skill_registered():
    """depends_on_skills 架构验证：first_pass_yield_computer 和 oee_computer 均已注册到 tool_registry。"""
    _header("15", "架构验证：FPY + OEE compute_tool 均已注册到 tool_registry")
    from app.analytics.tool_registry import get_compute_tool
    fpy_tool = get_compute_tool("first_pass_yield_computer")
    oee_tool  = get_compute_tool("oee_computer")
    print(f"  first_pass_yield_computer: {type(fpy_tool).__name__}")
    print(f"  oee_computer             : {type(oee_tool).__name__}")
    _assert(fpy_tool is not None, "first_pass_yield_computer 已注册")
    _assert(oee_tool  is not None, "oee_computer 已注册")


# ── Group 6: 边界情况 (Case 16-18) ────────────────────────────────────

def case_16_no_state_records_graceful():
    """equipment_oee_status 为空 → 返回 success=True，data_coverage 标记，可用率=100%。"""
    _header("16", "边界：equipment_oee_status 完全为空 → 优雅降级")
    from app.analytics.metrics.oee import OEEComputer
    c = OEEComputer()
    df = _make_output_df(["XRD-01"], rows_per_eq=15)
    r = c.compute(df,
                  state_df=None,   # 显式传 None
                  query_start=D7_S.isoformat(), query_end=NOW.isoformat(),
                  fpy_percent=97.0)
    _assert(r.success, "success=True（无状态记录时不抛异常）")
    _assert(r.detail[0]["data_coverage"] == "no_state_records", "data_coverage 标记正确")
    _assert(r.detail[0]["availability_pct"] == 100.0, "可用率=100%（无非计划停机）")
    print(f"  OEE={r.detail[0]['oee_pct']}%  data_coverage={r.detail[0]['data_coverage']}")


def case_17_no_output_data():
    """无产出数据 → success=False，error 有说明。"""
    _header("17", "边界：无产出数据 → success=False + error 说明")
    from app.analytics.metrics.oee import OEEComputer
    c = OEEComputer()
    empty_df = pd.DataFrame()
    r = c.compute(empty_df, query_start=D7_S.isoformat(), query_end=NOW.isoformat())
    _assert(not r.success, "success=False（空 DataFrame）")
    _assert(r.error is not None and len(r.error) > 0, "error 字段有说明文本")
    print(f"  error: {r.error}")


def case_18_unknown_equipment():
    """config 中没有的设备（已在 case_07/18 合并测试，此处保留存根跳过）。"""
    _header("18", "边界：config 里没有的设备 → 已由 Case 07 覆盖")
    print(f"  {SKIP}  已在 Case 07 合并覆盖")


# ══════════════════════════════════════════════════════════════════════
# API 层测试（Case 19-20，需要后端运行）
# ══════════════════════════════════════════════════════════════════════

API_QUERIES: List[tuple] = [
    (
        "Case 19 – 模糊路由（跑得怎么样）",
        "MOCVD 设备最近一周跑得怎么样？",
        ["oee", "设备", "OEE"],   # 期望关键词之一出现在回答中
    ),
    (
        "Case 20 – 模糊利用率（clarification 候选）",
        "外延设备这段时间利用率不太好，帮我看看原因",
        ["oee", "可用率", "利用率", "设备", "OEE"],
    ),
]


def run_api_cases() -> None:
    try:
        import httpx
    except ImportError:
        print(f"\n{SKIP}  httpx 未安装，跳过 API 层测试 (pip install httpx)")
        return

    # 先检查后端健康
    try:
        health = httpx.get(f"{BASE_URL}/health", timeout=5)
        print(f"\n后端健康检查: HTTP {health.status_code}")
    except Exception:
        try:
            health = httpx.get(f"{BASE_URL}/", timeout=5)
            print(f"\n后端根路径: HTTP {health.status_code}")
        except Exception as e:
            print(f"\n{SKIP}  后端不可达 ({e})，跳过 Case 19-20")
            return

    for label, query, keywords in API_QUERIES:
        print(f"\n{SEP}")
        print(f"  {label}")
        print(f"  Query: {query}")
        print(SEP)

        t0 = time.time()
        try:
            resp = httpx.post(
                f"{BASE_URL}/api/v1/chat",
                json={"message": query},
                timeout=120,
            )
            elapsed = round(time.time() - t0, 2)
            print(f"  HTTP {resp.status_code}  ({elapsed}s)")

            if resp.status_code != 200:
                print(f"  {FAIL}  HTTP {resp.status_code}: {resp.text[:300]}")
                continue

            data = resp.json()
            inner = data.get("data", {})

            # 收集文本输出
            answer  = inner.get("answer") or inner.get("response") or inner.get("message") or ""
            summary = (inner.get("analysis") or {}).get("summary") or ""
            sql     = inner.get("sql") or inner.get("generated_sql") or ""
            err_msg = inner.get("error") or data.get("error") or ""

            full_text = " ".join([answer, summary, sql]).lower()

            if err_msg:
                print(f"  ERROR: {err_msg}")

            # Pipeline trace
            trace = inner.get("pipeline_trace") or data.get("pipeline_trace") or []
            if trace:
                print(f"  Pipeline: {[t.get('node', t.get('step')) for t in trace]}")

            # 关键词命中检查（任意一个即通过）
            hit = any(kw.lower() in full_text for kw in keywords)
            hit_word = next((kw for kw in keywords if kw.lower() in full_text), None)
            if hit:
                print(f"  {PASS}  路由到 OEE 相关节点（命中关键词: {hit_word}）")
            else:
                # 检查是否是合理的 clarification
                clarification_signals = ["请问", "需要确认", "clarifi", "您是指", "能否明确", "哪台"]
                is_clarification = any(s in (answer + summary).lower() for s in clarification_signals)
                if is_clarification and "利用率" in query:
                    print(f"  {PASS}  Case 20 触发 clarification（合理行为）")
                else:
                    print(f"  {FAIL}  响应未命中 OEE 关键词 {keywords}。响应片段: {(answer or summary)[:200]}")

            if sql:
                print(f"  Generated SQL: {sql[:200]}")
            if answer:
                print(f"  Answer: {answer[:200]}")

        except httpx.ConnectError:
            print(f"  {SKIP}  后端连接失败")
        except Exception as e:
            print(f"  EXCEPTION: {e}")


# ══════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════

UNIT_CASES = [
    case_01_single_eq_full_oee,
    case_02_single_eq_no_state,
    case_03_single_eq_with_breakdown,
    case_04_recipe_cycle_time_lookup,
    case_05_multi_eq_grouped,
    case_06_per_equipment_planned_downtime,
    case_07_unknown_equipment_code,
    case_08_factors_multiply_to_oee,
    case_09_quality_default_100,
    case_10_performance_capped_100,
    case_11_7day_window,
    case_12_30day_window,
    case_13_charts_structure,
    case_14_quality_from_fpy_skill,
    case_15_fpy_skill_registered,
    case_16_no_state_records_graceful,
    case_17_no_output_data,
    case_18_unknown_equipment,
]

if __name__ == "__main__":
    run_unit = "--api"  not in sys.argv
    run_api  = "--unit" not in sys.argv

    if run_unit:
        print(f"\n{'#' * 72}")
        print("  UNIT 层测试（Case 01-18）— 直接调用 OEEComputer，不依赖后端")
        print(f"{'#' * 72}")
        for fn in UNIT_CASES:
            try:
                fn()
            except Exception as exc:
                print(f"  {FAIL}  {fn.__name__} 抛出异常: {exc}")
                import traceback; traceback.print_exc()
                _fail_count += 1

        print(f"\n{SEP}")
        print(f"  Unit 层结果: {PASS} {_pass_count}  {FAIL} {_fail_count}")
        print(SEP)

    if run_api:
        print(f"\n{'#' * 72}")
        print("  API 层测试（Case 19-20）— 通过 /api/v1/chat 测试模糊路由")
        print(f"{'#' * 72}")
        run_api_cases()

    print(f"\n{'#' * 72}")
    print("  完成")
    print(f"{'#' * 72}\n")
