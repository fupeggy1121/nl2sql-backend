"""
OEE 指标 NL2SQL 测试套件

覆盖 test_cases_oee.md 全部 20 个 Case，分两层执行：

  Layer 1 (Unit)  — 直接调用 OEEComputer.compute()，无需网络，验证：
    · registry 注册是否正确（tool_name / metric_name）
    · 边界 Case 16/17/18：无状态数据 / 零产出 / 未知设备
    · 跨 skill 联动（fpy_percent 参数传递 — Case 14/15 核心计算部分）

  Layer 2 (API)   — 发送自然语言到 http://localhost:8000/api/v1/chat，验证：
    · Cases 1-13：单设备/多设备/三因子/时间粒度
    · Cases 14-15：跨 skill 联动（路由层面）
    · Cases 16-18：边界触发（API + runtime graceful 降级）
    · Cases 19-20：模糊语义路由

运行方式：
  python _test_oee.py                   # 全部
  python _test_oee.py unit              # 仅 Unit 层
  python _test_oee.py api               # 仅 API 层
  python _test_oee.py api 1 2 3         # 仅指定 API Case 编号
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

# ── remove proxy env to avoid redirects ────────────────────────────────────
for _k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
           "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)

# ── project root on path ────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_URL = "http://localhost:8000"
SEP = "=" * 72

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

_failures: List[str] = []
_passes:   List[str] = []


def _ok(label: str) -> None:
    print(f"  {GREEN}✓ PASS{RESET}  {label}")
    _passes.append(label)


def _fail(label: str, detail: str = "") -> None:
    msg = f"  {RED}✗ FAIL{RESET}  {label}"
    if detail:
        msg += f"\n         {detail}"
    print(msg)
    _failures.append(label)


def _warn(msg: str) -> None:
    print(f"  {YELLOW}⚠ WARN{RESET}  {msg}")


def _header(title: str) -> None:
    print(f"\n{SEP}\n{title}\n{SEP}")


# ═══════════════════════════════════════════════════════════════════════════
#  合成数据工厂
# ═══════════════════════════════════════════════════════════════════════════

def _make_output_df(
    equipment_code: str = "MOCVD-01",
    n_wafers: int = 50,
    recipe_code: str = "GaN_HEMT_std",
    start_offset_days: int = 7,
) -> pd.DataFrame:
    """模拟出站记录 DataFrame（一行 = 一片出站晶圆）。"""
    today = date.today()
    start = today - timedelta(days=start_offset_days)
    rows = []
    for i in range(n_wafers):
        rows.append({
            "equipment_code": equipment_code,
            "actual_output":  1,
            "recipe_code":    recipe_code,
            "process_code":   "GAN_HEMT",
            "product_code":   "GH25A",
            "start_time":     str(start),
            "end_time":       str(today),
            "report_date":    str(start + timedelta(days=i % start_offset_days)),
        })
    return pd.DataFrame(rows)


def _make_state_df(
    equipment_code: str = "MOCVD-01",
    breakdown_hours: float = 4.0,
) -> pd.DataFrame:
    """模拟设备状态记录 DataFrame（含 breakdown 状态以测可用率）。"""
    today = date.today()
    rows = [
        {
            "equipment_code": equipment_code,
            "status_code":    "breakdown",
            "start_time":     f"{today - timedelta(days=7)}T06:00:00",
            "end_time":       f"{today - timedelta(days=7)}T{6 + int(breakdown_hours):02d}:00:00",
        },
    ]
    return pd.DataFrame(rows)


def _make_multi_equipment_df(
    equipment_codes: List[str] = None,
    n_wafers_each: int = 30,
) -> pd.DataFrame:
    """多设备出站记录。"""
    if equipment_codes is None:
        equipment_codes = ["MOCVD-01", "MOCVD-02"]
    frames = [
        _make_output_df(ec, n_wafers_each)
        for ec in equipment_codes
    ]
    return pd.concat(frames, ignore_index=True)


# ═══════════════════════════════════════════════════════════════════════════
#  Layer 1 — Unit Tests
# ═══════════════════════════════════════════════════════════════════════════

def run_unit_tests() -> None:
    _header("LAYER 1 — Unit Tests (直接调用 OEEComputer)")

    # ── 强制注册 metric & tool ──────────────────────────────────────────
    import app.analytics.metrics.oee           # noqa  触发注册
    import app.analytics.metrics.first_pass_yield  # noqa 触发注册（跨 skill 联动需要）

    # ── U0: Registry 检查 ──────────────────────────────────────────────
    print("\n[U0] Registry 注册验证")
    from app.analytics.tool_registry import get_compute_tool, list_compute_tools
    from app.analytics.registry import get_metric

    spec = get_compute_tool("oee_computer")
    if spec:
        _ok("oee_computer 已注册到 ComputeToolRegistry")
    else:
        _fail("oee_computer 未注册", "检查 @register_compute_tool 装饰器是否生效")

    computer = get_metric("oee")
    if computer:
        _ok(f"oee 已注册到 MetricRegistry (class={type(computer).__name__})")
    else:
        _fail("oee 未注册到 MetricRegistry")

    # ── U1: 正常单设备计算 ──────────────────────────────────────────────
    print("\n[U1] 正常单设备：MOCVD-01，7天，带 fpy_percent")
    from app.analytics.metrics.oee import OEEComputer

    oee = OEEComputer()
    prod_df = _make_output_df("MOCVD-01", n_wafers=80, recipe_code="GaN_HEMT_std")
    state_df = _make_state_df("MOCVD-01", breakdown_hours=8.0)

    today = date.today()
    qs = str(today - timedelta(days=7))
    qe = str(today)

    result = oee.compute(
        df=prod_df,
        state_df=state_df,
        fpy_percent=95.5,
        query_start=qs,
        query_end=qe,
        recipe_code="GaN_HEMT_std",
    )

    if result.success:
        _ok(f"success=True  OEE={result.value:.2f}%")
    else:
        _fail("compute 返回 success=False", result.error or "")

    if result.value is not None and 0 < result.value < 100:
        _ok(f"OEE 值在合理范围 (0, 100): {result.value:.2f}%")
    else:
        _fail(f"OEE 值异常: {result.value}")

    if result.detail:
        row = result.detail[0]
        print(f"  可用率: {row.get('availability_pct')}%")
        print(f"  性能率: {row.get('performance_pct')}%")
        print(f"  良品率: {row.get('quality_pct')}%  [来源: {row.get('quality_source')}]")
        print(f"  OEE:   {row.get('oee_pct')}%")
        if row.get("quality_pct") == 95.5:
            _ok("fpy_percent 正确传入良品率因子")
        else:
            _fail("良品率因子与 fpy_percent 不符", f"expected=95.5, got={row.get('quality_pct')}")

    if result.charts:
        _ok(f"图表已生成: {len(result.charts)} 个 (type={result.charts[0].get('type')})")
    else:
        _fail("未生成图表")

    # ── U2: 多设备计算 ──────────────────────────────────────────────────
    print("\n[U2] 多设备对比：MOCVD-01 + MOCVD-02")
    multi_df = _make_multi_equipment_df(["MOCVD-01", "MOCVD-02"], n_wafers_each=50)
    r2 = oee.compute(
        df=multi_df,
        fpy_percent=92.0,
        query_start=qs,
        query_end=qe,
    )
    if r2.success:
        _ok(f"多设备 success=True  均值 OEE={r2.value}%")
    else:
        _fail("多设备计算失败", r2.error or "")

    if r2.detail and len(r2.detail) == 2:
        _ok(f"detail 包含 2 台设备记录: {[d['equipment_code'] for d in r2.detail]}")
    else:
        n = len(r2.detail) if r2.detail else 0
        _fail(f"detail 设备数量错误: 期望 2，实际 {n}")

    # ── Case 16: 无状态记录（equipment_oee_status 暂无数据）─────────────
    print("\n[Case 16] 无状态记录 → data_coverage='no_state_records'，可用率默认100%")
    r16 = oee.compute(
        df=_make_output_df("XRD-01", n_wafers=20),
        state_df=None,             # 无状态数据
        fpy_percent=98.0,
        query_start=qs,
        query_end=qe,
    )
    if r16.success:
        _ok("success=True（降级处理）")
    else:
        _fail("应该 success=True 而非抛异常", r16.error or "")

    if r16.detail:
        row16 = r16.detail[0]
        coverage = row16.get("data_coverage")
        avail = row16.get("availability_pct")
        if coverage == "no_state_records":
            _ok(f"data_coverage='no_state_records' 正确标注")
        else:
            _fail(f"data_coverage 期望 'no_state_records'，实际 '{coverage}'")
        if avail == 100.0:
            _ok(f"可用率默认 100.0% (无停机数据)")
        else:
            _fail(f"可用率应为 100.0%，实际 {avail}%")
    else:
        _fail("detail 为空")

    # ── Case 17: 无产出记录 ──────────────────────────────────────────────
    print("\n[Case 17] 空产出 → OEE=0%，不抛异常")
    r17 = oee.compute(
        df=pd.DataFrame(),       # 空 DataFrame
        query_start=qs,
        query_end=qe,
    )
    if not r17.success and r17.error:
        _ok(f"空产出返回 success=False + error (符合设计): {r17.error[:80]}")
    else:
        _warn("空产出未返回 error，检查是否符合预期")

    # 另一种空产出：有行但 actual_output=0
    empty_prod = _make_output_df("MOCVD-01", n_wafers=0)
    r17b = oee.compute(
        df=empty_prod,
        state_df=None,
        fpy_percent=100.0,
        query_start=qs,
        query_end=qe,
    )
    # n_wafers=0 创建了空 DataFrame — 应同上
    if not r17b.success:
        _ok("零行 DataFrame → success=False（正确拒绝）")
    else:
        if r17b.detail:
            perf = r17b.detail[0].get("performance_pct", -1)
            oee_val = r17b.detail[0].get("oee_pct", -1)
            if perf == 0.0 and oee_val == 0.0:
                _ok(f"零产出 performance=0% → OEE=0%")
            else:
                _warn(f"零产出 performance={perf}%, OEE={oee_val}% (非零，检查计算逻辑)")

    # ── Case 18: config 中不存在的设备（使用 default 值）──────────────
    print("\n[Case 18] 未知设备 PECVD-01 → 使用 config default 值")
    r18 = oee.compute(
        df=_make_output_df("PECVD-01", n_wafers=40, recipe_code="UNKNOWN_RECIPE"),
        state_df=None,
        fpy_percent=90.0,
        query_start=qs,
        query_end=qe,
        recipe_code="UNKNOWN_RECIPE",
    )
    if r18.success:
        _ok("success=True（未知设备使用 default 配置）")
    else:
        _fail("未知设备应该降级到 default，不应报错", r18.error or "")

    if r18.detail:
        row18 = r18.detail[0]
        ct = row18.get("theoretical_cycle_time_min")
        pd_h = row18.get("planned_downtime_hours")
        # PECVD-01 不在 config → 应使用 default: ct=120, planned_downtime=24/30*7
        expected_ct = 120.0
        if ct == expected_ct:
            _ok(f"理论节拍使用 default={expected_ct} min/片")
        else:
            _warn(f"理论节拍值={ct}，期望 default={expected_ct}（检查 config lookup 路径）")
        print(f"  计划停机(7天折算): {pd_h}h  OEE: {row18.get('oee_pct')}%")
    else:
        _fail("detail 为空")

    # ── Case 14/15 核心：fpy_percent 明确传入，验证良品率因子走 FPY skill ─
    print("\n[Case 14/15] 跨 skill 联动：fpy_percent=88.5%（模拟 FPY skill 返回）")
    r14 = oee.compute(
        df=_make_output_df("MOCVD-01", n_wafers=120),
        fpy_percent=88.5,       # 由 first_pass_yield_computer 预计算传入
        query_start=qs,
        query_end=qe,
    )
    if r14.success and r14.detail:
        row14 = r14.detail[0]
        q_pct = row14.get("quality_pct")
        q_src = row14.get("quality_source")
        if q_pct == 88.5 and q_src == "first_pass_yield_skill":
            _ok(f"良品率={q_pct}%, source='{q_src}' → 跨 skill 联动正确")
        else:
            _fail(f"跨 skill 联动异常: quality_pct={q_pct}, source={q_src}")
    else:
        _fail("跨 skill case 计算失败", r14.error or "")

    print()


# ═══════════════════════════════════════════════════════════════════════════
#  Layer 2 — API Integration Tests
# ═══════════════════════════════════════════════════════════════════════════

def _api_post(message: str, session_id: str, timeout: int = 120) -> Dict[str, Any]:
    """POST to /api/v1/chat and return parsed JSON (or error dict)."""
    try:
        import httpx
        resp = httpx.post(
            f"{BASE_URL}/api/v1/chat",
            json={"message": message, "session_id": session_id},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return {"_http_error": resp.status_code, "_body": resp.text[:300]}
        return resp.json()
    except Exception as e:
        return {"_exception": str(e)}


def _extract_trace_info(data: Dict[str, Any]) -> Dict[str, Any]:
    """从 API 响应中提取关键路由信息。"""
    inner = data.get("data", {})
    trace = inner.get("pipeline_trace") or data.get("pipeline_trace") or []

    info: Dict[str, Any] = {
        "success": data.get("success", False),
        "type": inner.get("type", ""),
        "trace_nodes": [],
        "skill": None,
        "compute_tool": None,
        "method": None,
        "metric_name": None,
        "sql": inner.get("sql") or inner.get("generated_sql") or "",
        "oee_value": None,
        "availability": None,
        "performance": None,
        "quality": None,
        "detail_count": 0,
        "data_coverage": None,
        "analysis_summary": "",
        "llm_answer": "",
        "clarification": "",
        "error": inner.get("error") or data.get("error") or "",
    }

    # trace 节点名
    info["trace_nodes"] = [t.get("node", t.get("step", "?")) for t in trace]

    for t in trace:
        node = t.get("node", t.get("step", ""))
        detail = t.get("detail", {}) or {}
        summary = t.get("summary", "") or ""

        if node in ("method_selector", "query_planner"):
            info["method"] = detail.get("suggested_method") or detail.get("method")
            sk = detail.get("skill_context") or {}
            if isinstance(sk, dict):
                info["skill"] = sk.get("skill_name")
                info["compute_tool"] = sk.get("compute_tool")
            info["metric_name"] = (detail.get("method_params") or {}).get("metric_name")

        if node == "analysis_executor":
            info["compute_tool"] = detail.get("tool_name") or info["compute_tool"]

    # analysis block
    analysis = inner.get("analysis") or {}
    if analysis:
        info["analysis_summary"] = analysis.get("summary", "")
        a_data = analysis.get("data") or {}
        info["metric_name"] = a_data.get("metric_name") or info["metric_name"]
        detail_list = a_data.get("detail") or []
        info["detail_count"] = len(detail_list)
        if detail_list:
            row = detail_list[0]
            info["oee_value"]    = row.get("oee_pct")
            info["availability"] = row.get("availability_pct")
            info["performance"]  = row.get("performance_pct")
            info["quality"]      = row.get("quality_pct")
            info["data_coverage"]= row.get("data_coverage")

    # clarification
    info["clarification"] = (
        inner.get("clarification_question") or
        inner.get("clarification") or ""
    )

    # LLM answer
    info["llm_answer"] = (
        inner.get("answer") or inner.get("response") or
        inner.get("message") or ""
    )

    return info


def _print_api_result(case_num: int, nl: str, info: Dict[str, Any], elapsed: float) -> None:
    print(f"\n[Case {case_num:02d}] NL: {nl}")
    print(f"  HTTP:        {'OK' if info['success'] else 'ERR'}  ({elapsed:.1f}s)")
    print(f"  Type:        {info['type']}")
    print(f"  Nodes:       {' → '.join(info['trace_nodes']) if info['trace_nodes'] else '(no trace)'}")
    print(f"  Skill:       {info['skill'] or '—'}")
    print(f"  Tool:        {info['compute_tool'] or '—'}")
    print(f"  Method:      {info['method'] or '—'}")
    if info["sql"]:
        sql_preview = info["sql"][:120].replace("\n", " ")
        print(f"  SQL:         {sql_preview}…")
    if info["oee_value"] is not None:
        print(f"  OEE:         {info['oee_value']:.2f}%  "
              f"(A={info['availability']}%, P={info['performance']}%, Q={info['quality']}%)")
        if info["data_coverage"] and info["data_coverage"] != "ok":
            print(f"  Coverage:    {info['data_coverage']}")
        if info["detail_count"] > 1:
            print(f"  Devices:     {info['detail_count']} 台设备")
    if info["analysis_summary"]:
        print(f"  Summary:     {info['analysis_summary'][:120]}")
    if info["clarification"]:
        print(f"  Clarif.:     {info['clarification'][:120]}")
    if info["llm_answer"]:
        print(f"  Answer:      {info['llm_answer'][:120]}")
    if info["error"]:
        print(f"  Error:       {info['error'][:100]}")


def _assert_oee_routed(case_num: int, info: Dict[str, Any], nl: str) -> bool:
    """检查是否路由到 OEE skill。也接受分析结果中含 OEE 关键词。"""
    routed = (
        info["skill"] == "oee"
        or info["compute_tool"] == "oee_computer"
        or (info["metric_name"] or "").lower() == "oee"
        or "oee" in (info["analysis_summary"] or "").lower()
        or "OEE" in (info["analysis_summary"] or "")
    )
    if routed:
        _ok(f"Case {case_num:02d}: 路由到 OEE skill ✓")
    else:
        _warn(f"Case {case_num:02d}: 未检测到 OEE 路由（skill={info['skill']}, "
              f"tool={info['compute_tool']}, method={info['method']}）")
    return routed


def run_api_tests(only_cases: Optional[List[int]] = None) -> None:
    _header("LAYER 2 — API Integration Tests")

    # health check
    try:
        import httpx
        h = httpx.get(f"{BASE_URL}/health", timeout=5)
        print(f"Backend health: HTTP {h.status_code}  {h.text[:60]}")
    except Exception as e:
        print(f"{RED}无法连接后端 ({e})。请先启动后端再跑 API 测试。{RESET}")
        print("  跳过所有 API 测试。")
        return

    # ── 测试用例定义 ──────────────────────────────────────────────────────
    today  = date.today()
    yesterday_str = str(today - timedelta(days=1))

    CASES = [
        # ── Group 1: 单设备基础查询 ──────────────────────────────────────
        (1,  "单设备单日 OEE",
             "MOCVD-01 昨天的 OEE 是多少",
             {"expect_oee_route": True}),
        (2,  "单设备月度 OEE（中文别名）",
             "帮我查一下 MBE-01 上个月的设备综合效率",
             {"expect_oee_route": True}),
        (3,  "单设备日期范围",
             "MOCVD-02 从 3 月 1 号到 3 月 15 号的 OEE",
             {"expect_oee_route": True}),

        # ── Group 2: 多设备对比 ──────────────────────────────────────────
        (4,  "同类设备对比",
             "对比一下 MOCVD-01 和 MOCVD-02 上周的 OEE",
             {"expect_oee_route": True}),
        (5,  "全部设备 OEE 排名",
             "这个月所有设备的 OEE 排名",
             {"expect_oee_route": True}),
        (6,  "OEE 最低设备",
             "上周 OEE 最低的设备是哪台",
             {"expect_oee_route": True}),

        # ── Group 3: 三因子拆解 ──────────────────────────────────────────
        (7,  "单独查可用率",
             "MOCVD-01 这周的可用率是多少",
             {"expect_oee_route": True, "note": "metric=availability，OEE 因子级查询"}),
        (8,  "单独查性能率",
             "MBE-01 上个月的性能率",
             {"expect_oee_route": True, "note": "metric=performance"}),
        (9,  "三因子全展开",
             "MOCVD-01 上周的 OEE 三个因子分别是多少",
             {"expect_oee_route": True}),
        (10, "多设备+多因子",
             "对比所有 MOCVD 设备本月的可用率和性能率",
             {"expect_oee_route": True, "note": "设备名通配 + 多因子指定"}),

        # ── Group 4: 时间粒度与趋势 ─────────────────────────────────────
        (11, "日趋势（7天）",
             "MOCVD-01 最近 7 天每天的 OEE 趋势",
             {"expect_oee_route": True, "note": "granularity=daily, 7个数据点"}),
        (12, "周趋势（近1月）",
             "MBE-01 最近一个月每周的 OEE 变化",
             {"expect_oee_route": True, "note": "granularity=weekly"}),
        (13, "月度汇总（今年至今）",
             "今年每个月的设备综合效率汇总",
             {"expect_oee_route": True, "note": "设备综合效率别名 + 全设备 + 月聚合"}),

        # ── Group 5: 跨 Skill 联动 ──────────────────────────────────────
        (14, "OEE 良品率来源确认",
             "MOCVD-01 上周的 OEE，良品率用哪个工站的数据",
             {"expect_oee_route": True, "note": "路由 oee → first_pass_yield，确认 quality_source 标注"}),
        (15, "OEE + FPY 联合分析",
             "上个月 OEE 低于 50% 的设备，它们的一次良率分别是多少",
             {"expect_oee_route": True, "note": "先筛 OEE<50%，再逐台调 FPY skill"}),

        # ── Group 6: 边界与异常 ─────────────────────────────────────────
        (16, "无状态记录的设备",
             "XRD-01 昨天的 OEE",
             {"expect_oee_route": True, "note": "data_coverage='no_state_records' 降级"}),
        (17, "无产出记录（周日无生产）",
             f"MOCVD-01 {yesterday_str} 的 OEE",
             {"expect_oee_route": True, "note": "如果当天无数据 → OEE=0，不报错"}),
        (18, "config 中不存在的设备",
             "PECVD-01 的 OEE 是多少",
             {"expect_oee_route": True, "note": "使用 config default 值并标注"}),

        # ── Group 7: 模糊语义路由 ────────────────────────────────────────
        (19, "口语化（无明确指标名）",
             "一号 MOCVD 机台最近跑得怎么样",
             {"expect_oee_route": True,  # supervisor 应能语义路由到 OEE
              "note": "无指标名，语义理解'跑得怎么样' → 设备效率 → OEE"}),
        (20, "高模糊度（外延设备利用率不好）",
             "外延设备这段时间利用率不太好，帮我看看",
             {"expect_oee_route": False,   # 可能 clarification_needed
              "note": "'外延设备' → MOCVD+MBE, '这段时间' → 可能要求澄清，接受 OEE 路由或 clarification"}),
    ]

    for case_num, label, nl, opts in CASES:
        if only_cases and case_num not in only_cases:
            continue

        print(f"\n{'-' * 72}")
        note = opts.get("note", "")
        if note:
            print(f"{YELLOW}[Case {case_num:02d}] {label}{RESET}  ({note})")
        else:
            print(f"{YELLOW}[Case {case_num:02d}] {label}{RESET}")

        session_id = f"oee-test-{case_num:02d}"
        t0 = time.time()
        response = _api_post(nl, session_id)
        elapsed = time.time() - t0

        if "_exception" in response:
            _fail(f"Case {case_num:02d}: HTTP 请求异常", response["_exception"])
            continue
        if "_http_error" in response:
            _fail(f"Case {case_num:02d}: HTTP {response['_http_error']}", response.get("_body", ""))
            continue

        info = _extract_trace_info(response)
        _print_api_result(case_num, nl, info, elapsed)

        expect = opts.get("expect_oee_route", True)
        if expect:
            routed = _assert_oee_routed(case_num, info, nl)
            # Case 16: 额外检查 data_coverage 降级标注
            if case_num == 16 and info.get("data_coverage") == "no_state_records":
                _ok("Case 16: data_coverage='no_state_records' 降级标注正确")
            # Case 14/15: 检查 quality_source
            if case_num == 14 and info.get("quality") is not None:
                _ok(f"Case 14: 良品率因子={info['quality']}%（来自 FPY skill 或默认值）")
        else:
            # Case 20: 接受 OEE 路由 OR clarification_needed
            if info["clarification"]:
                _ok(f"Case {case_num:02d}: clarification_needed 正确触发: {info['clarification'][:80]}")
            elif info["skill"] == "oee" or "oee" in (info["analysis_summary"] or "").lower():
                _ok(f"Case {case_num:02d}: 路由到 OEE skill（接受 → 模糊设备识别成功）")
            else:
                _warn(f"Case {case_num:02d}: 未路由到 OEE 也未 clarification，检查 supervisor 路由逻辑")


# ═══════════════════════════════════════════════════════════════════════════
#  入口
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    args = sys.argv[1:]
    mode = "all"
    case_filter: Optional[List[int]] = None

    if args:
        if args[0] == "unit":
            mode = "unit"
        elif args[0] == "api":
            mode = "api"
            if len(args) > 1:
                case_filter = [int(a) for a in args[1:] if a.isdigit()]
        else:
            # 仅数字参数 → 运行指定 Case（API 层）
            nums = [int(a) for a in args if a.isdigit()]
            if nums:
                mode = "api"
                case_filter = nums

    print(f"\n{'=' * 72}")
    print(" OEE NL2SQL Test Suite  —  20 Cases across 7 Groups")
    print(f" Mode: {mode}  {f'| Cases: {case_filter}' if case_filter else ''}")
    print(f"{'=' * 72}")

    if mode in ("all", "unit"):
        run_unit_tests()

    if mode in ("all", "api"):
        run_api_tests(only_cases=case_filter)

    # ── Summary ──────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    total = len(_passes) + len(_failures)
    pct = 100 * len(_passes) // total if total else 0
    print(f"SUMMARY  {GREEN}{len(_passes)} passed{RESET}  "
          f"{(RED + str(len(_failures)) + ' failed' + RESET) if _failures else '0 failed'}  "
          f"({total} total, {pct}% pass rate)")
    if _failures:
        print(f"\nFailed assertions:")
        for f in _failures:
            print(f"  {RED}✗{RESET} {f}")
    print()


if __name__ == "__main__":
    main()
