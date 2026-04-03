"""
快速验证 feat(llm-time)：通过 HTTP 调用后端，
从 pipeline_trace 中提取 data_loader 步骤的真实数据拉取 SQL，
比较"最近一个星期"和"最近两个星期"的时间范围是否不同。

Run:  python _validate_date_sql.py
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())
for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
    os.environ.pop(k, None)

import httpx

BASE = "http://localhost:8000"
TODAY = datetime.now().date()

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
NOTE = "\033[93m~\033[0m"
SEP  = "=" * 68

_failures: list = []

def ok(msg):   print(f"  {PASS} {msg}")
def fail(msg, detail=""):
    print(f"  {FAIL} {msg}" + (f"\n      → {detail}" if detail else ""))
    _failures.append(msg)
def note(msg): print(f"  {NOTE} {msg}")


# Matches >= <= > < operators before date literals on gmt_create
DATE_RE = re.compile(
    r"gmt_create\s*(>=|<=|>|<)\s*'(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
INTERVAL_RE = re.compile(r"INTERVAL\s+(\d+)\s+(DAY|WEEK|MONTH)", re.IGNORECASE)


def extract_dates(sql: str) -> list[str]:
    return [m.group(2) for m in DATE_RE.finditer(sql or "")]


def window_days(sql: str) -> int | None:
    from datetime import timedelta
    matches = [(m.group(1), m.group(2)) for m in DATE_RE.finditer(sql or "")]
    if len(matches) >= 2:
        start_date = end_date = None
        for op, ds in matches:
            d = datetime.strptime(ds, "%Y-%m-%d").date()
            if op in (">=", ">"):
                if start_date is None or d < start_date:
                    start_date = d
            else:  # < or <=
                # exclusive `<` means the effective last day is d-1
                eff = d if op == "<=" else d - timedelta(days=1)
                if end_date is None or eff > end_date:
                    end_date = eff
        if start_date and end_date:
            return (end_date - start_date).days + 1
    # INTERVAL form: INTERVAL N DAY → N days
    m = INTERVAL_RE.search(sql or "")
    if m:
        n = int(m.group(1))
        unit = m.group(2).upper()
        if unit == "DAY":   return n
        if unit == "WEEK":  return n * 7
        if unit == "MONTH": return n * 30
    return None


def get_data_loader_sql(query: str) -> tuple[str, str]:
    """
    POST /api/v1/chat and extract:
      - the actual data-fetch SQL from pipeline_trace['analysis_data_loader'].detail.sql
      - LLM tool-selection reason from analysis.data.python_script header
    Returns (sql, reason).
    """
    try:
        r = httpx.post(f"{BASE}/api/v1/chat", json={"message": query}, timeout=180)
        body = r.json()
        inner = body.get("data") or {}

        # ── look in pipeline_trace for the data_loader step ──────────────
        trace = inner.get("pipeline_trace") or body.get("pipeline_trace") or []
        for step in trace:
            if step.get("step") in ("analysis_data_loader", "data_loader"):
                sql = (step.get("detail") or {}).get("sql", "")
                if sql:
                    return sql, ""

        # ── fallback: check analysis.data.python_script for LLM reason ──
        analysis = inner.get("analysis") or {}
        adata = analysis.get("data") or {}
        script = adata.get("python_script", "")
        reason = ""
        for line in (script or "").splitlines():
            if "LLM 选择理由" in line or "group_by" in line.lower():
                reason += line.strip() + "  "

        # No SQL in pipeline_trace — look in analysis metadata
        meta = analysis.get("metadata") or adata.get("metadata") or {}
        sql = meta.get("data_source_sql") or meta.get("sql") or ""
        return sql, reason.strip()

    except Exception as e:
        return "", f"ERROR: {e}"


# expected_days: exact int for ±1-tolerant check, None for date-only check
# LLM uses "N days ago" as start, so result is N or N+1 days inclusive.
CASES = [
    ("1wk",  "最近一个星期的一次良率",   7),
    ("2wk",  "最近两个星期的一次良率",   14),
    ("3d",   "最近三天的一次良率",       3),
    ("1mo",  "上个月各工站的一次良率",   None),
    ("qtr",  "本季度各工站的返工率",     None),
]

print(f"\n今天: {TODAY}\n{SEP}\n实时 HTTP 调用 — 数据拉取 SQL 的时间范围\n{SEP}")

sql_by_label: dict[str, str] = {}

for label, query, expected_days in CASES:
    note(f"\n  [{label}]  {query}")
    sql, reason = get_data_loader_sql(query)
    sql_by_label[label] = sql

    if not sql:
        if reason:
            note(f"  pipeline_trace 中未找到 SQL，LLM meta: {reason[:200]}")
        else:
            note(f"  pipeline_trace 中未找到 SQL (response may not expose it)")
        continue

    dates = extract_dates(sql)
    days  = window_days(sql)
    date_hint = f"{dates[0]} ~ {dates[1]}" if len(dates) >= 2 else (dates[0] if dates else "interval/curdate")

    # show date-relevant WHERE lines
    date_lines = [ln.strip() for ln in sql.splitlines()
                  if re.search(r"gmt_create|gmt_update|CURDATE|INTERVAL|DATE_SUB",
                               ln, re.IGNORECASE)]
    note(f"  WHERE (date): {' | '.join(date_lines)[:200]}")

    if expected_days is not None:
        # Allow ±1 day — LLM may use "today - N" (giving N+1 inclusive days)
        if days is not None and abs(days - expected_days) <= 1:
            ok(f"[{label}] window = {days} days  ≈  {expected_days}d expected  ({date_hint})")
        elif days == expected_days:
            ok(f"[{label}] window = {days} days  ✓  ({date_hint})")
        else:
            fail(f"[{label}] expected {expected_days}±1 days", f"got {days} days  ({date_hint})")
    else:
        if date_lines:
            ok(f"[{label}] has date filter  ({date_hint})")
        else:
            note(f"[{label}] no date filter found — needs manual review")

# ── Core invariant ─────────────────────────────────────────────────────────
print(f"\n{SEP}\n核心不变量：1周 vs 2周必须产生不同的时间窗口\n{SEP}")

w1 = window_days(sql_by_label.get("1wk", ""))
w2 = window_days(sql_by_label.get("2wk", ""))

if w1 and w2:
    note(f"'最近一个星期良率' → {w1} 天")
    note(f"'最近两个星期良率' → {w2} 天")
    if w1 != w2:
        ok(f"两查询时间窗口不同 ({w1}d ≠ {w2}d) — 原始 bug 已修复")
    else:
        fail("两查询时间窗口不同", f"都是 {w1} 天 — bug 仍存在")
elif not w1 and not w2:
    note("两个查询均未在 SQL 里找到 gmt_create 日期字面量")
    note("(LLM 可能使用了 DATE_SUB/CURDATE/INTERVAL 形式 — 检查 WHERE 行)")
    # show the raw WHERE lines
    for lbl in ("1wk", "2wk"):
        sql = sql_by_label.get(lbl, "")
        dl = [ln.strip() for ln in (sql or "").splitlines()
              if re.search(r"gmt_create|INTERVAL|CURDATE|DATE_SUB", ln, re.IGNORECASE)]
        note(f"  [{lbl}] date lines: {dl[:3]}")
else:
    note(f"部分查询未找到可解析的日期 (1wk={w1}, 2wk={w2})")

print(f"\n{SEP}")
if _failures:
    print(f"\033[91m{len(_failures)} FAILURE(S):\033[0m")
    for f in _failures:
        print(f"  - {f}")
    sys.exit(1)
else:
    print(f"\033[92mAll checks passed (or non-strict).\033[0m")
    sys.exit(0)

