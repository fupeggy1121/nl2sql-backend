#!/usr/bin/env python3
"""
量测参数查询测试

真实数据基准（来自 process_measure_data）：
  批次+工站:
    SJ026C00010  几何参数检验(8200)   18片  1参数  1次录入
    SJ026C00009  几何参数检验(8200)   25片  1参数  1次录入
    SP026C00089  脱胶-晶向检测         1片  3参数  1次录入
    SJ026C00006  抛光前分选            100片 1参数  1次录入
  常见参数: TTV(μm)、厚度(μm)、Bow(μm)、WARP(μm)、RES-CEN(ohm·cm)

覆盖场景：
  M01 — 查某批次在某工站的所有量测参数
  M02 — 查某批次某参数项的值
  M03 — 查某工站最近的量测数据
  M04 — 查多片 wafer 的 TTV 参数
  M05 — 查某批次所有量测参数的录入记录（按 trace_code 聚合）
  M06 — 查参数值超出范围的 wafer（基于具体阈值）
  M07 — 查某工站最近录入的量测数据条数
  M08 — 模糊表达：查批次测量情况
  M09 — 路由边界：不应触发 skill 路径
  M10 — 英文表达：measurement data query
"""

import httpx
import json
import time
import os
import sys
import re

for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(k, None)

ENDPOINT = "http://localhost:8000/api/v1/chat"
TIMEOUT = 120

# ── 真实数据基准 ──────────────────────────────────────────────────────────────
LOT_GEO      = "SJ026C00010"   # 几何参数检验，18片，1参数
LOT_GEO2     = "SJ026C00009"   # 几何参数检验，25片，1参数
LOT_ORIENT   = "SP026C00089"   # 脱胶-晶向检测，1片，3参数
LOT_SORT     = "SJ026C00006"   # 抛光前分选，100片，1参数
PROCESS_GEO  = "几何参数检验"
PROCESS_ORI  = "脱胶-晶向检测"
PROCESS_SORT = "抛光前分选"
PARAM_TTV    = "TTV"
PARAM_BOW    = "Bow"
PARAM_THICK  = "厚度"

CASES = [
    # ── 批次+工站 维度 ──────────────────────────────────────────────────────────
    {
        "id": "M01",
        "group": "批次+工站查询",
        "desc": "查某批次在某工站的所有量测参数",
        "query": f"批次 {LOT_GEO} 在{PROCESS_GEO}的量测数据",
        "expect_route": "adhoc",
        "checks": {
            "has_sql":    lambda r: bool(r["sql"]),
            "has_answer": lambda r: r["answer_len"] > 0,
            "hits_table": lambda r: "process_measure_data" in r["sql"].lower(),
            "filters_lot": lambda r: LOT_GEO.lower() in r["sql"].lower(),
        },
    },
    {
        "id": "M02",
        "group": "批次+工站查询",
        "desc": "查某批次某具体参数项的值",
        "query": f"批次 {LOT_ORIENT} 在{PROCESS_ORI}的晶向偏离参数值",
        "expect_route": "adhoc",
        "checks": {
            "has_sql":    lambda r: bool(r["sql"]),
            "hits_table": lambda r: "process_measure_data" in r["sql"].lower(),
            "filters_lot": lambda r: LOT_ORIENT.lower() in r["sql"].lower(),
        },
    },
    {
        "id": "M03",
        "group": "批次+工站查询",
        "desc": "查含有100片的批次在抛光前分选的量测结果",
        "query": f"批次 {LOT_SORT} 抛光前分选量测结果",
        "expect_route": "adhoc",
        "checks": {
            "has_sql":    lambda r: bool(r["sql"]),
            "hits_table": lambda r: "process_measure_data" in r["sql"].lower(),
        },
    },
    # ── 参数项维度 ──────────────────────────────────────────────────────────────
    {
        "id": "M04",
        "group": "参数项查询",
        "desc": "查某批次所有wafer的TTV值",
        "query": f"批次 {LOT_GEO} 每片wafer的TTV测量值",
        "expect_route": "adhoc",
        "checks": {
            "has_sql":     lambda r: bool(r["sql"]),
            "hits_table":  lambda r: "process_measure_data" in r["sql"].lower(),
            "filters_ttv": lambda r: "ttv" in r["sql"].lower() or "TTV" in r["sql"],
        },
    },
    {
        "id": "M05",
        "group": "参数项查询",
        "desc": "查几何参数检验工站最常见参数",
        "query": f"几何参数检验工站都有哪些量测参数项",
        "expect_route": "adhoc",
        "checks": {
            "has_sql":    lambda r: bool(r["sql"]),
            "hits_table": lambda r: "process_measure_data" in r["sql"].lower(),
        },
    },
    {
        "id": "M06",
        "group": "参数项查询",
        "desc": "查TTV超过某阈值的wafer",
        "query": f"批次 {LOT_GEO2} 中TTV大于5μm的wafer有哪些",
        "expect_route": "adhoc",
        "checks": {
            "has_sql":    lambda r: bool(r["sql"]),
            "hits_table": lambda r: "process_measure_data" in r["sql"].lower(),
            "has_filter": lambda r: "5" in r["sql"],
        },
    },
    # ── 录入事件维度（trace_code 聚合）─────────────────────────────────────────
    {
        "id": "M07",
        "group": "录入事件查询",
        "desc": "查某批次共有几次量测录入",
        "query": f"批次 {LOT_GEO} 共进行了几次量测数据录入",
        "expect_route": "adhoc",
        "checks": {
            "has_sql":    lambda r: bool(r["sql"]),
            "hits_table": lambda r: "process_measure_data" in r["sql"].lower(),
            "has_trace":  lambda r: "trace_code" in r["sql"].lower(),
        },
    },
    {
        "id": "M08",
        "group": "录入事件查询",
        "desc": "查最近录入的量测数据（工站维度）",
        "query": "最近录入的量测数据按工站统计各有多少条",
        "expect_route": "adhoc",
        "checks": {
            "has_sql":    lambda r: bool(r["sql"]),
            "hits_table": lambda r: "process_measure_data" in r["sql"].lower(),
        },
    },
    # ── 语义覆盖与路由边界 ───────────────────────────────────────────────────────
    {
        "id": "M09",
        "group": "路由边界",
        "desc": "模糊表达：查批次测量情况",
        "query": f"批次 {LOT_GEO} 的测量情况",
        "expect_route": "adhoc",
        "checks": {
            "not_skill":  lambda r: r["route"] != "skill",
            "has_answer": lambda r: r["answer_len"] > 0,
        },
    },
    {
        "id": "M10",
        "group": "路由边界",
        "desc": "英文表达：measurement data query",
        "query": f"show measurement data for lot {LOT_GEO} at {PROCESS_GEO}",
        "expect_route": "adhoc",
        "checks": {
            "has_sql":    lambda r: bool(r["sql"]),
            "hits_table": lambda r: "process_measure_data" in r["sql"].lower(),
        },
    },
]


def probe(query: str, timeout: int = TIMEOUT) -> dict:
    t0 = time.time()
    try:
        r = httpx.post(ENDPOINT, json={"message": query}, timeout=timeout)
        elapsed = time.time() - t0
        body = r.json()
        data = body.get("data", {})
        pt = data.get("pipeline_trace", [])
        steps = [s.get("step", "") for s in pt]

        # 路由判断
        if "multi_skill_merge" in steps:
            route = "multi_skill"
        elif "analysis_method_selector" in steps:
            route = "skill"
        elif "intent_router" in steps:
            route = "adhoc"
        elif "clarification_node" in steps:
            route = "clarification"
        else:
            route = "unknown"

        # SQL 提取（取第一条非空 SQL）
        sql = ""
        for s in pt:
            candidate = s.get("detail", {}).get("sql", "")
            if candidate:
                sql = candidate
                break

        # rows
        rows = 0
        for s in pt:
            rc = s.get("detail", {}).get("rows_count")
            if rc is not None:
                rows = rc
                break

        # answer 可能在 data.answer 或 data.query_result.summary
        answer = (
            data.get("answer")
            or (data.get("query_result") or {}).get("summary")
            or ""
        )

        return {
            "ok":          True,
            "route":       route,
            "sql":         sql,
            "rows":        rows,
            "answer":      answer,
            "answer_len":  len(answer),
            "steps":       steps,
            "elapsed":     elapsed,
        }

    except httpx.TimeoutException:
        elapsed = time.time() - t0
        return {
            "ok": False, "error": f"TIMEOUT after {elapsed:.0f}s",
            "route": "timeout", "sql": "", "rows": 0,
            "answer": "", "answer_len": 0, "steps": [], "elapsed": elapsed,
        }
    except Exception as e:
        return {
            "ok": False, "error": str(e),
            "route": "error", "sql": "", "rows": 0,
            "answer": "", "answer_len": 0, "steps": [], "elapsed": time.time() - t0,
        }


def run_checks(case: dict, result: dict) -> tuple:
    errors, warnings = [], []

    if not result["ok"]:
        errors.append(f"请求失败: {result.get('error')}")
        return False, errors, warnings

    # 路由检查
    if result["route"] != case["expect_route"]:
        errors.append(f"路由错误: 期望 {case['expect_route']}，实际 {result['route']}")

    # 自定义 checks
    for name, fn in case.get("checks", {}).items():
        try:
            if not fn(result):
                errors.append(f"check 失败: {name}")
        except Exception as e:
            warnings.append(f"check 异常: {name} — {e}")

    # 数据为空提示（不算失败，只 warning）
    if result["rows"] == 0 and result["ok"]:
        warnings.append("SQL 执行返回 0 行（可能是测试数据库无近期数据）")

    if result["elapsed"] > 60:
        warnings.append(f"响应时间 {result['elapsed']:.0f}s 超过 60s")

    return len(errors) == 0, errors, warnings


def main():
    print("=" * 65)
    print("量测参数查询测试")
    print("=" * 65)

    total = len(CASES)
    passed_count = 0
    results_summary = []
    current_group = ""

    for case in CASES:
        if case["group"] != current_group:
            current_group = case["group"]
            print(f"\n── {current_group} ──")

        print(f"\n[{case['id']}] {case['desc']}")
        print(f"  查询: {case['query']}")

        result = probe(case["query"])
        passed, errors, warnings = run_checks(case, result)

        if passed:
            passed_count += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"

        print(f"  {status}  route={result['route']}  rows={result['rows']}  {result['elapsed']:.1f}s")

        if result["sql"]:
            print(f"  SQL: {result['sql'][:200]}")

        if result["answer_len"] > 0:
            print(f"  answer: {result['answer'][:120].replace(chr(10),' ')!r}...")

        for e in errors:
            print(f"  ⛔ {e}")
        for w in warnings:
            print(f"  ⚠  {w}")

        results_summary.append({
            "id":       case["id"],
            "group":    case["group"],
            "desc":     case["desc"],
            "passed":   passed,
            "route":    result["route"],
            "rows":     result["rows"],
            "sql":      result["sql"][:300] if result["sql"] else "",
            "elapsed":  round(result["elapsed"], 1),
            "errors":   errors,
            "warnings": warnings,
        })

    # ── 汇总 ──────────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print(f"整体汇总: {passed_count}/{total} 通过")
    print("=" * 65)

    groups: dict = {}
    for r in results_summary:
        g = r["group"]
        groups.setdefault(g, {"total": 0, "passed": 0})
        groups[g]["total"] += 1
        if r["passed"]:
            groups[g]["passed"] += 1

    print("\n分组统计:")
    for g, stat in groups.items():
        mark = "✅" if stat["passed"] == stat["total"] else "⚠ "
        print(f"  {mark} {g}: {stat['passed']}/{stat['total']}")

    failed = [r for r in results_summary if not r["passed"]]
    if failed:
        print("\n失败用例:")
        for r in failed:
            print(f"  ❌ [{r['id']}] {r['desc']}")
            for e in r["errors"]:
                print(f"      ⛔ {e}")
    else:
        print("\n全部通过 🎉")

    report_path = "/tmp/measurement_query_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(
            {"total": total, "passed": passed_count, "results": results_summary},
            f, ensure_ascii=False, indent=2,
        )
    print(f"\n详细报告: {report_path}")
    sys.exit(0 if passed_count == total else 1)


if __name__ == "__main__":
    main()
