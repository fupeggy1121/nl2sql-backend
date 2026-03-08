#!/usr/bin/env python3
"""
NL 语义查询端到端测试执行器

用法:
  python tests/nl_eval/runner.py                          # 跑全部用例
  python tests/nl_eval/runner.py --id wip_by_station      # 跑单条
  python tests/nl_eval/runner.py --id a,b --out /tmp/r.json  # 跑多条+JSON报告

依赖: pip install pyyaml requests
"""

import argparse
import difflib
import json
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import requests
import yaml

# ── 配置 ──────────────────────────────────────────────────────────────────────
BASE_URL   = "http://localhost:8000"
CHAT_URL   = f"{BASE_URL}/api/v1/chat"
TIMEOUT    = 90
CASES_FILE = Path(__file__).parent / "cases.yaml"

# ANSI 颜色
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def c(color: str, text: str) -> str:
    return f"{color}{text}{RESET}"


# ── 数据结构 ───────────────────────────────────────────────────────────────────
@dataclass
class RunResult:
    run_idx:         int
    sql:             str
    physical_tables: List[str]
    matched_classes: List[str]
    success:         bool
    failures:        List[str]
    error:           str = ""
    latency_ms:      float = 0.0
    sql_retry_count: int = 0


@dataclass
class CaseResult:
    case_id: str
    nl:      str
    intent:  str
    runs:    List[RunResult] = field(default_factory=list)


# ── HTTP 调用 ─────────────────────────────────────────────────────────────────
def call_api(nl: str) -> dict:
    session_id = str(uuid.uuid4())
    payload = {"message": nl, "session_id": session_id}
    resp = requests.post(CHAT_URL, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def extract_run_info(api_resp: dict) -> dict:
    """从 API 响应中提取 SQL、物理表、类匹配等关键字段"""
    data = api_resp.get("data", {})

    # SQL 可能在 data.query_plan.generated_sql 或 data.query_result.sql
    sql = (
        (data.get("query_plan") or {}).get("generated_sql")
        or (data.get("query_result") or {}).get("sql")
        or data.get("generated_sql")
        or data.get("sql")
        or ""
    )

    physical_tables: List[str] = []
    matched_classes: List[str] = []

    # pipeline_trace 中字段名为 "step"（不是 "node"）
    for step in data.get("pipeline_trace", []):
        if step.get("step") == "semantic_resolver":
            detail = step.get("detail", {})
            physical_tables = detail.get("physical_tables", [])
            matched_classes = [
                mc.get("logic_class", "")
                for mc in detail.get("matched_classes", [])
            ]
            break

    return {
        "sql":             sql,
        "physical_tables": physical_tables,
        "matched_classes": matched_classes,
        "success":         api_resp.get("success", False) or data.get("success", False),
        "error":           data.get("error", ""),
        "sql_retry_count": data.get("sql_retry_count", 0),
    }


# ── 断言检查 ──────────────────────────────────────────────────────────────────
def check_expected(
    sql: str,
    tables: List[str],
    expected: dict,
) -> Tuple[bool, List[str]]:
    failures: List[str] = []
    sql_up = sql.upper()

    for kw in expected.get("sql_contains", []):
        if kw.upper() not in sql_up:
            failures.append(f"sql_contains 缺失: '{kw}'")

    for kw in expected.get("sql_excludes", []):
        if kw.upper() in sql_up:
            failures.append(f"sql_excludes 出现了禁止词: '{kw}'")

    for tbl in expected.get("tables_present", []):
        if tbl not in tables:
            failures.append(
                f"tables_present 缺失: '{tbl}'  (实际: {tables or '无'})"
            )

    pattern = expected.get("sql_pattern")
    if pattern:
        try:
            if not re.search(pattern, sql, re.IGNORECASE | re.DOTALL):
                failures.append(f"sql_pattern 不匹配: /{pattern}/")
        except re.error as e:
            failures.append(f"sql_pattern 正则无效: {e}")

    return (len(failures) == 0), failures


# ── SQL 差异展示 ─────────────────────────────────────────────────────────────
def sql_diff(sqls: List[str]) -> str:
    if len(sqls) <= 1:
        return ""
    lines_a = sqls[0].splitlines(keepends=True)
    diffs = []
    for i, s in enumerate(sqls[1:], start=2):
        lines_b = s.splitlines(keepends=True)
        diff = list(
            difflib.unified_diff(
                lines_a, lines_b,
                fromfile="run-1", tofile=f"run-{i}", lineterm=""
            )
        )
        if diff:
            diffs.append(
                f"  diff run-1 vs run-{i}:\n"
                + "".join(f"    {l}" for l in diff)
            )
    return "\n".join(diffs)


# ── 单条用例执行 ──────────────────────────────────────────────────────────────
def run_case(case: dict) -> CaseResult:
    case_id   = case["id"]
    nl        = case["nl"]
    intent    = case.get("intent", "")
    run_count = case.get("run_count", 1)
    expected  = case.get("expected", {})

    result = CaseResult(case_id=case_id, nl=nl, intent=intent)

    print(f"\n{c(BOLD, '▶')} [{case_id}]  {c(CYAN, nl)}")
    print(f"  {c(DIM, intent)}")
    print(
        f"  runs={run_count}  "
        f"contains={expected.get('sql_contains',[])}  "
        f"excludes={expected.get('sql_excludes',[])}  "
        f"tables={expected.get('tables_present',[])}"
    )

    for i in range(1, run_count + 1):
        t0 = time.perf_counter()
        try:
            api_resp = call_api(nl)
            info     = extract_run_info(api_resp)
            latency  = (time.perf_counter() - t0) * 1000

            passed, failures = check_expected(
                info["sql"], info["physical_tables"], expected
            )

            run = RunResult(
                run_idx=i,
                sql=info["sql"],
                physical_tables=info["physical_tables"],
                matched_classes=info["matched_classes"],
                success=passed,
                failures=failures,
                error=info.get("error", ""),
                latency_ms=latency,
                sql_retry_count=info["sql_retry_count"],
            )
            result.runs.append(run)

            status_icon = c(GREEN, "✓") if passed else c(RED, "✗")
            retry_info  = f"  [retry×{run.sql_retry_count}]" if run.sql_retry_count else ""
            print(f"  run {i}/{run_count}  {status_icon}  {latency:.0f}ms{retry_info}")

            if not passed:
                for f in failures:
                    print(f"    {c(RED, '→')} {f}")

            if info["sql"]:
                sql_preview = info["sql"].replace("\n", " ")[:120]
                print(
                    f"    SQL: {c(DIM, sql_preview)}"
                    f"{'…' if len(info['sql']) > 120 else ''}"
                )
            if info["physical_tables"]:
                print(f"    tables: {c(DIM, str(info['physical_tables']))}")

        except requests.exceptions.Timeout:
            result.runs.append(
                RunResult(i, "", [], [], False, [f"TIMEOUT (>{TIMEOUT}s)"], "TIMEOUT")
            )
            print(f"  run {i}/{run_count}  {c(YELLOW, '⚠')}  TIMEOUT")
        except Exception as e:
            result.runs.append(
                RunResult(i, "", [], [], False, [str(e)], str(e))
            )
            print(f"  run {i}/{run_count}  {c(RED, '✗')}  ERROR: {e}")

    # 稳健性分析
    if run_count > 1:
        sqls   = [r.sql for r in result.runs if r.sql]
        unique = len(set(s.strip().upper() for s in sqls))
        stability  = "STABLE" if unique <= 1 else f"UNSTABLE ({unique} unique SQLs)"
        stab_color = GREEN if unique <= 1 else YELLOW
        print(f"  稳健性: {c(stab_color, stability)}")
        if unique > 1:
            diff_str = sql_diff(sqls)
            if diff_str:
                print(diff_str)

    pass_n  = sum(1 for r in result.runs if r.success)
    total   = len(result.runs)
    overall = (
        c(GREEN,  f"PASS {pass_n}/{total}")   if pass_n == total else
        c(YELLOW, f"PARTIAL {pass_n}/{total}") if pass_n > 0 else
        c(RED,    f"FAIL {pass_n}/{total}")
    )
    print(f"  结果: {c(BOLD, overall)}")

    return result


# ── 汇总报告 ──────────────────────────────────────────────────────────────────
def print_summary(results: List[CaseResult]) -> None:
    total_cases = len(results)
    full_pass   = sum(1 for r in results if all(run.success for run in r.runs))
    any_fail    = sum(1 for r in results if any(not run.success for run in r.runs))

    print(f"\n{'═'*64}")
    print(f"{c(BOLD, '  测试汇总')}")
    print(f"{'═'*64}")
    print(f"  用例总数:  {total_cases}")
    print(f"  全部通过:  {c(GREEN, str(full_pass))}")
    print(f"  存在失败:  {c(RED if any_fail else GREEN, str(any_fail))}")
    print(f"{'═'*64}")

    for r in results:
        runs_ok = sum(1 for run in r.runs if run.success)
        total   = len(r.runs)
        icon    = (
            c(GREEN,  "✓") if runs_ok == total else
            c(YELLOW, "△") if runs_ok > 0 else
            c(RED,    "✗")
        )
        avg_lat = sum(run.latency_ms for run in r.runs) / total if total else 0
        print(
            f"  {icon}  {r.case_id:<32s}  {runs_ok}/{total} pass  "
            f"avg {avg_lat:.0f}ms"
        )

    print(f"{'═'*64}\n")


def build_json_report(results: List[CaseResult]) -> dict:
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": {
            "total":     len(results),
            "full_pass": sum(
                1 for r in results if all(run.success for run in r.runs)
            ),
        },
        "cases": [
            {
                "id":     r.case_id,
                "nl":     r.nl,
                "intent": r.intent,
                "runs": [
                    {
                        "run":             run.run_idx,
                        "success":         run.success,
                        "latency_ms":      round(run.latency_ms),
                        "sql":             run.sql,
                        "physical_tables": run.physical_tables,
                        "matched_classes": run.matched_classes,
                        "sql_retry_count": run.sql_retry_count,
                        "failures":        run.failures,
                        "error":           run.error,
                    }
                    for run in r.runs
                ],
            }
            for r in results
        ],
    }


# ── 入口 ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="NL 语义查询端到端测试执行器")
    parser.add_argument("--id",    help="只跑指定 case id（逗号分隔）")
    parser.add_argument("--out",   help="输出 JSON 报告到文件")
    parser.add_argument("--url",   help=f"后端 base URL（默认 {BASE_URL}）")
    parser.add_argument("--cases", help=f"cases.yaml 路径（默认自动查找）")
    args = parser.parse_args()

    global BASE_URL, CHAT_URL
    if args.url:
        BASE_URL = args.url.rstrip("/")
        CHAT_URL = f"{BASE_URL}/api/v1/chat"

    # 查找 cases.yaml
    cases_path: Path
    if args.cases:
        cases_path = Path(args.cases)
    else:
        candidates = [
            CASES_FILE,
            Path(__file__).parent.parent.parent / "tests" / "nl_eval" / "cases.yaml",
        ]
        cases_path = next((p for p in candidates if p.exists()), CASES_FILE)

    if not cases_path.exists():
        print(f"{c(RED, '✗')} 找不到 cases.yaml: {cases_path}")
        sys.exit(1)

    with open(cases_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    cases = config.get("cases", [])
    if args.id:
        ids    = {s.strip() for s in args.id.split(",")}
        cases  = [c for c in cases if c["id"] in ids]
        if not cases:
            print(f"{c(RED, '✗')} 未找到 id={args.id} 的用例")
            sys.exit(1)

    # 健康检查
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        r.raise_for_status()
        print(f"{c(GREEN, '✓')} 后端健康: {r.json()}")
    except Exception as e:
        print(f"{c(RED, '✗')} 后端不可达: {e}")
        sys.exit(1)

    print(f"\n{c(BOLD, f'运行 {len(cases)} 条 NL 语义测试用例')}")

    results = [run_case(case) for case in cases]

    print_summary(results)

    if args.out:
        report = build_json_report(results)
        out_path = Path(args.out)
        out_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"JSON 报告已写入: {out_path}")

    all_pass = all(all(run.success for run in r.runs) for r in results)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
