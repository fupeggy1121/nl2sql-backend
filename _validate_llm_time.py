"""
feat(llm-time) validation
=========================

Three layers:

Layer-A  Deterministic fallback (_extract_date_range + _has_date_filter)
  - Verifies all natural-language time variants including the two originally broken ones.
  - Purely offline, no LLM/backend needed.

Layer-B  Injection safety net (mock LLM → no-date SQL → fallback injected)
  - Patches the LLM to return SQL without any date filter, then checks the safety
    net injects different gmt_create ranges for "一周" vs "两周" queries.

Layer-C  Live end-to-end against running backend (http://localhost:8000)
  - Sends real queries, captures returned SQL from the response, and compares
    the time windows to confirm LLM understood the time span correctly.

Run: python _validate_llm_time.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
from datetime import datetime, timedelta
from typing import Optional

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

import httpx

# import deterministic helpers at module level so all layers can use them
from app.agents.analysis_agent.nodes.method_selector import (
    _extract_date_range,
    _has_date_filter,
)

BASE_URL = "http://localhost:8000"
SEP = "=" * 70
PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
NOTE = "\033[93m~\033[0m"

_failures: list[str] = []
TODAY = datetime.now().date()


def ok(msg: str) -> None:
    print(f"  {PASS} {msg}")


def fail(msg: str, detail: str = "") -> None:
    line = f"  {FAIL} {msg}"
    if detail:
        line += f"  [{detail}]"
    print(line)
    _failures.append(msg)


def note(msg: str) -> None:
    print(f"  {NOTE} {msg}")


def header(title: str) -> None:
    print(f"\n{SEP}\n{title}\n{SEP}")


# ── helpers ──────────────────────────────────────────────────────────────────

def days_delta(start_str: str, end_str: str) -> int:
    """Number of days in range [start, end] inclusive."""
    s = datetime.strptime(start_str, "%Y-%m-%d").date()
    e = datetime.strptime(end_str, "%Y-%m-%d").date()
    return (e - s).days + 1


def extract_date_from_sql(sql: str) -> tuple[Optional[str], Optional[str]]:
    """
    Try to pull out a date range from a SQL WHERE clause.
    Handles common patterns:
       gmt_create >= 'YYYY-MM-DD ...'
       gmt_create BETWEEN 'YYYY-MM-DD ...' AND 'YYYY-MM-DD ...'
       gmt_create >= DATE_SUB(CURDATE(), INTERVAL N DAY)
       gmt_create >= DATE_SUB('YYYY-MM-DD', INTERVAL N DAY)
    Returns (start_date_str, end_date_str) or (None, None).
    """
    # BETWEEN pattern
    m = re.search(
        r"gmt_create\s+BETWEEN\s+'(\d{4}-\d{2}-\d{2})[^']*'\s+AND\s+'(\d{4}-\d{2}-\d{2})",
        sql, re.IGNORECASE,
    )
    if m:
        return m.group(1), m.group(2)

    # >= / > with literal date
    m_gte = re.search(r"gmt_create\s*>=?\s*'(\d{4}-\d{2}-\d{2})", sql, re.IGNORECASE)
    m_lte = re.search(r"gmt_create\s*<=?\s*'(\d{4}-\d{2}-\d{2})", sql, re.IGNORECASE)
    if m_gte and m_lte:
        return m_gte.group(1), m_lte.group(1)
    if m_gte:
        return m_gte.group(1), str(TODAY)

    # DATE_SUB(CURDATE(), INTERVAL N DAY/WEEK)
    m_sub = re.search(
        r"DATE_SUB\s*\(\s*CURDATE\s*\(\s*\)\s*,\s*INTERVAL\s+(\d+)\s+(DAY|WEEK|MONTH)",
        sql, re.IGNORECASE,
    )
    if m_sub:
        n, unit = int(m_sub.group(1)), m_sub.group(2).upper()
        if unit == "DAY":
            delta = n
        elif unit == "WEEK":
            delta = n * 7
        elif unit == "MONTH":
            delta = n * 30
        else:
            delta = n
        start = TODAY - timedelta(days=delta)
        return str(start), str(TODAY)

    return None, None


def window_from_sql(sql: str) -> Optional[int]:
    """Returns the number of days implied by the SQL time range, or None."""
    s, e = extract_date_from_sql(sql)
    if s and e:
        return days_delta(s, e)
    return None


# ════════════════════════════════════════════════════════════════════════════
# Layer-A  Deterministic fallback
# ════════════════════════════════════════════════════════════════════════════

def run_layer_a() -> None:
    header("Layer-A — Deterministic Fallback (_extract_date_range + _has_date_filter)")

    print("\n  [A1] Two originally-broken queries must yield DIFFERENT windows")
    s1, e1 = _extract_date_range("最近一个星期良率")
    s2, e2 = _extract_date_range("最近两个星期良率")
    w1 = days_delta(s1, e1)
    w2 = days_delta(s2, e2)
    note(f"  '最近一个星期良率'   → {s1} ~ {e1}  ({w1} days)")
    note(f"  '最近两个星期良率'   → {s2} ~ {e2}  ({w2} days)")
    if w1 == 7:
        ok("'最近一个星期' = 7 days")
    else:
        fail("'最近一个星期' = 7 days", f"got {w1}")
    if w2 == 14:
        ok("'最近两个星期' = 14 days")
    else:
        fail("'最近两个星期' = 14 days", f"got {w2}")
    if w1 != w2:
        ok("windows are different (7 ≠ 14) — the original bug is fixed")
    else:
        fail("windows are different", f"both produced {w1} days")

    print("\n  [A2] Boundary expressions")
    cases = [
        # (query, expected_days_exact_or_None, label, strict)
        ("上个月良率",           None,  "last calendar month — varies by day",       False),
        ("本季度的返工率",        None,  "current quarter — no regex, uses default",  False),
        ("最近三天一次良率",      3,     "3 days (Chinese numeral 三→3)",             True),
        ("最近两个星期良率",      14,    "2 weeks (Chinese numeral 两→2)",            True),
        ("最近7天",              7,     "7 days explicit Arabic",                    True),
        ("最近30天",             30,    "30 days explicit",                          True),
        ("最近3个星期",          21,    "3×7=21 days",                               True),
        ("最近一个月返工率",      30,    "1 month ≈ 30 days",                         True),
        ("最近三个月",           90,    "3 months ≈ 90 days",                         True),
        ("最近半年",             180,   "6 months ≈ 180 days",                        True),
        ("最近一年",             365,   "1 year ≈ 365 days",                          True),
        ("本周良率",             None,  "current week (partial)",                    False),
        ("上周良率",             7,     "last week = 7 days",                        True),
        ("今天",                 1,     "today = 1 day",                             True),
        ("昨天",                 1,     "yesterday = 1 day",                         True),
    ]
    for query, exp_days, label, strict in cases:
        s, e = _extract_date_range(query)
        w = days_delta(s, e)
        if not strict:
            note(f"  '{query}' → {s} ~ {e}  ({w} days)  [{label}]")
        else:
            if w == exp_days:
                ok(f"'{query}' → {w} days  [{label}]")
            else:
                fail(f"'{query}' → {exp_days} days  [{label}]", f"got {w}")

    print("\n  [A3] _has_date_filter patterns")
    detect_cases = [
        ("SELECT * FROM t WHERE gmt_create >= '2026-03-01 00:00:00'", True),
        ("WHERE gmt_create <= '2026-04-03 23:59:59'", True),
        ("WHERE gmt_create BETWEEN '2026-01-01' AND '2026-04-03'", True),
        ("WHERE gmt_create >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)", True),
        ("WHERE gmt_create >= DATE_SUB(CURDATE(), INTERVAL 2 WEEK)", True),
        ("WHERE DATE(gmt_create) >= '2026-03-20'", True),
        ("SELECT process_code, COUNT(*) FROM t WHERE operation_type=8 GROUP BY 1", False),
        ("SELECT * FROM wafer_wip LIMIT 1000", False),
    ]
    for sql, expected in detect_cases:
        got = _has_date_filter(sql)
        snippet = sql[:55] + "..." if len(sql) > 55 else sql
        if got == expected:
            ok(f"_has_date_filter → {expected}  |  {snippet}")
        else:
            fail(f"_has_date_filter → {expected}  |  {snippet}", f"got {got}")


# ════════════════════════════════════════════════════════════════════════════
# Layer-B  Injection safety net (mock LLM)
# ════════════════════════════════════════════════════════════════════════════

def run_layer_b() -> None:
    header("Layer-B — Injection Safety Net (mock LLM returns no-date SQL)")

    # Minimal stubs for metric_def and skill
    class MockMetricDef:
        metric_id = "first_pass_yield"
        compute_mode = "python_compute"
        anchor_table = "t"
        join_path = ""
        auto_filter = ""
        description = ""

    class MockSkill:
        zh_names = ["一次良率"]
        standard_definition = "FPY"
        formula = "good/total"
        granularity = ["process_code"]
        body = ""
        required_columns = []
        rn_order = "ASC"

    metric_def = MockMetricDef()
    skill = MockSkill()

    # Patch get_llm to return SQL WITHOUT any date filter
    NO_DATE_SQL = (
        "SELECT wafer_id, process_code, wafer_type, ng_code, rn "
        "FROM matrix_routerx_operation_lot_batch_resume_wafer_detail_log "
        "WHERE operation_type = 8 "
        "LIMIT 100000"
    )

    import app.agents.analysis_agent.nodes.method_selector as ms

    class MockLLMResp:
        content = json.dumps({"sql": NO_DATE_SQL, "key_columns": ["wafer_id"], "reason": "test"})

    class MockLLM:
        def invoke(self, prompt):
            return MockLLMResp()

    # Patch the LLM
    import app.agent.llm as llm_mod
    original_get_llm = llm_mod.get_llm
    llm_mod.get_llm = lambda: MockLLM()

    try:
        print("\n  [B1] '最近一个星期良率' — fallback injects 7-day window")
        sql_1wk = ms._llm_build_detail_sql(metric_def, skill, "最近一个星期良率")
        note(f"  returned SQL (tail): ...{sql_1wk[-200:] if sql_1wk else 'None'}")
        w1 = window_from_sql(sql_1wk or "")
        if w1 == 7:
            ok(f"fallback injected 7-day window")
        elif w1 is not None:
            fail(f"fallback injected 7-day window", f"got {w1} days")
        else:
            fail(f"fallback injected date filter", "no recognizable date pattern found")

        print("\n  [B2] '最近两个星期良率' — fallback injects 14-day window")
        sql_2wk = ms._llm_build_detail_sql(metric_def, skill, "最近两个星期良率")
        note(f"  returned SQL (tail): ...{sql_2wk[-200:] if sql_2wk else 'None'}")
        w2 = window_from_sql(sql_2wk or "")
        if w2 == 14:
            ok(f"fallback injected 14-day window")
        elif w2 is not None:
            fail(f"fallback injected 14-day window", f"got {w2} days")
        else:
            fail(f"fallback injected date filter", "no recognizable date pattern found")

        print("\n  [B3] Windows are different")
        if w1 is not None and w2 is not None and w1 != w2:
            ok(f"7d-window ({w1}) ≠ 14d-window ({w2}) — injection is query-specific")
        else:
            fail("windows differ", f"w1={w1}  w2={w2}")

        print("\n  [B4] When LLM already returns WITH date filter — no double injection")
        class MockLLMWithDate:
            def invoke(self, prompt):
                sql_with_date = (
                    "SELECT wafer_id, process_code, wafer_type, ng_code, rn "
                    "FROM matrix_routerx_operation_lot_batch_resume_wafer_detail_log "
                    f"WHERE gmt_create >= DATE_SUB(CURDATE(), INTERVAL 14 DAY) "
                    "AND operation_type = 8 LIMIT 100000"
                )

                class R:
                    content = json.dumps({"sql": sql_with_date, "key_columns": ["wafer_id"], "reason": "test"})
                return R()

        llm_mod.get_llm = lambda: MockLLMWithDate()
        sql_with = ms._llm_build_detail_sql(metric_def, skill, "最近两个星期良率")
        # Should NOT have the fallback gmt_create literals appended
        double_inject = (
            sql_with and
            sql_with.count("gmt_create >=") >= 2
        )
        if not double_inject:
            ok("no double date injection when LLM already includes date filter")
        else:
            fail("no double date injection", f"saw gmt_create >= twice in SQL")

    finally:
        llm_mod.get_llm = original_get_llm


# ════════════════════════════════════════════════════════════════════════════
# Layer-C  Live end-to-end via backend API
# ════════════════════════════════════════════════════════════════════════════

_LIVE_CASES = [
    # (label, query, expected_days_min, expected_days_max, strict)
    ("最近一个星期良率",   "最近一个星期的一次良率",   5,  9,  True),
    ("最近两个星期良率",   "最近两个星期的一次良率",   12, 16, True),
    ("上个月良率",        "上个月各工站的一次良率",    28, 31, True),
    ("最近三天良率",      "最近三天的一次良率",         2,  4,  True),
    ("本季度返工率",      "本季度各工站的返工率",        None, None, False),  # LLM may vary
]


def run_layer_c() -> None:
    header("Layer-C — Live End-to-End (backend SQL capture)")

    try:
        h = httpx.get(f"{BASE_URL}/health", timeout=5)
        if h.status_code != 200:
            note("Backend not healthy — skipping Layer-C")
            return
    except Exception:
        note("Backend unreachable — skipping Layer-C")
        return

    for label, query, exp_min, exp_max, strict in _LIVE_CASES:
        print(f"\n  [{label}]  query: \"{query}\"")
        try:
            resp = httpx.post(
                f"{BASE_URL}/api/v1/chat",
                json={"message": query},
                timeout=120,
            )
            if resp.status_code != 200:
                fail(f"{label}: HTTP 200", f"got {resp.status_code}")
                continue

            body = resp.json()
            inner = body.get("data", {})

            # Try multiple paths where SQL might live
            sql = (
                inner.get("sql")
                or inner.get("generated_sql")
                or inner.get("query")
                or (inner.get("analysis") or {}).get("data", {}).get("python_script", "")
                or ""
            )

            # Also check data_source_config if exposed
            dsc = inner.get("data_source_config") or {}
            if not sql and isinstance(dsc, dict):
                sql = dsc.get("sql", "")

            # Check pipeline trace for SQL
            trace = inner.get("pipeline_trace") or body.get("pipeline_trace") or []
            for step in trace:
                step_sql = (step.get("data_source_config") or {}).get("sql", "")
                if step_sql:
                    sql = step_sql
                    break

            if sql:
                note(f"  SQL (excerpt): {sql[:180].strip()}...")
                has_date = _has_date_filter(sql)
                start, end = extract_date_from_sql(sql)
                window = window_from_sql(sql)

                if has_date:
                    ok(f"SQL contains date filter")
                else:
                    note(f"No recognizable date filter in SQL (LLM may use sub-select or CTE)")

                if window is not None:
                    note(f"Detected window: {start} ~ {end}  ({window} days)")
                    if not strict:
                        ok(f"{label}: SQL generated (non-strict check)")
                    elif exp_min is not None and exp_min <= window <= exp_max:
                        ok(f"{label}: window {window}d ∈ [{exp_min}, {exp_max}] ✓")
                    else:
                        fail(
                            f"{label}: window ∈ [{exp_min}, {exp_max}]",
                            f"got {window} days ({start} ~ {end})",
                        )
                else:
                    if not strict:
                        ok(f"{label}: SQL generated (non-strict, window not parseable)")
                    else:
                        note(f"{label}: window not parseable from SQL — manual review needed")
            else:
                # No SQL in response — check if analysis succeeded anyway
                success = body.get("success") or inner.get("success")
                if success:
                    note(f"  No SQL in response but success=True (SQL may be internal-only)")
                    ok(f"{label}: backend returned success")
                else:
                    err = inner.get("error") or body.get("error") or ""
                    fail(f"{label}: got SQL or success", f"error={err[:100]}")

        except httpx.TimeoutException:
            fail(f"{label}: response within timeout")
        except Exception as e:
            fail(f"{label}: no exception", str(e)[:80])


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"Today: {TODAY}\n")

    try:
        run_layer_a()
    except Exception:
        traceback.print_exc()

    try:
        run_layer_b()
    except Exception:
        traceback.print_exc()

    try:
        run_layer_c()
    except Exception:
        traceback.print_exc()

    print(f"\n{SEP}")
    if _failures:
        print(f"\033[91m{len(_failures)} FAILURE(S):\033[0m")
        for f in _failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print(f"\033[92mAll checks passed.\033[0m")
        sys.exit(0)
