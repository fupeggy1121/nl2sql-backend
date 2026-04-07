#!/usr/bin/env python3
"""
一次良率 vs 综合良率对比查询测试

覆盖场景：
  Y01 — 基础对比：7天两指标同时查询（multi_skill 路径）
  Y02 — 基础对比：上月各工站两指标
  Y03 — 时间维度：30天趋势对比
  Y04 — 时间维度：本月每天变化
  Y05 — 工站维度：各工站两指标对比
  Y06 — 工站维度：差值最大的工站
  Y07 — 边界验证：综合良率低于一次良率的工站（正常为空）
  Y08 — 单指标：一次良率独立查询（不触发 multi_skill）
  Y09 — 单指标：综合良率独立查询（不触发 multi_skill）
  Y10 — 英文查询：FPY and final yield comparison

路由判断依据（实测 pipeline_trace 结构）：
  - multi_skill：steps 中有 "multi_skill_merge"
  - skill：steps 中有 "analysis_method_selector" 但无 "multi_skill_merge"
  - adhoc：steps 中有 "intent_router" 但无以上两者
skill 名从 multi_skill_merge.detail.skill_names（list）或
analysis_method_selector.detail.reason（含 "'skill_name'" 模式）提取
"""

import httpx
import json
import re
import time
import os
import sys

for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(k, None)

ENDPOINT = "http://localhost:8000/api/v1/chat"
TIMEOUT = 120

CASES = [
    # ── 基础对比（multi_skill 路径）────────────────────────────────────────────
    {
        "id": "Y01",
        "group": "基础对比",
        "desc": "最近7天两指标同时查询",
        "query": "最近7天一次良率和综合良率对比",
        "expect_route": "multi_skill",
        "expect_skills": ["first_pass_yield", "final_yield"],
        "expect_has_answer": True,
        "checks": {
            "multi_skill": lambda r: r["route"] == "multi_skill",
            "skills_both": lambda r: "first_pass_yield" in r["skills_hit"] and "final_yield" in r["skills_hit"],
        },
    },
    {
        "id": "Y02",
        "group": "基础对比",
        "desc": "上个月各工站一次良率和综合良率",
        "query": "上个月各工站一次良率和综合良率",
        "expect_route": "multi_skill",
        "expect_skills": ["first_pass_yield", "final_yield"],
        "expect_has_answer": True,
        "checks": {
            "multi_skill": lambda r: r["route"] == "multi_skill",
            "skills_both": lambda r: "first_pass_yield" in r["skills_hit"] and "final_yield" in r["skills_hit"],
        },
    },
    # ── 时间维度 ───────────────────────────────────────────────────────────────
    {
        "id": "Y03",
        "group": "时间维度",
        "desc": "最近30天趋势对比",
        "query": "最近30天一次良率和综合良率趋势对比",
        "expect_route": "multi_skill",
        "expect_skills": ["first_pass_yield", "final_yield"],
        "expect_has_answer": True,
        "checks": {
            "multi_skill": lambda r: r["route"] == "multi_skill",
            "skills_both": lambda r: "first_pass_yield" in r["skills_hit"] and "final_yield" in r["skills_hit"],
        },
    },
    {
        "id": "Y04",
        "group": "时间维度",
        "desc": "本月每天变化",
        "query": "本月每天的一次良率和综合良率变化",
        "expect_route": "multi_skill",
        "expect_skills": ["first_pass_yield", "final_yield"],
        "expect_has_answer": True,
        "checks": {
            "multi_skill": lambda r: r["route"] == "multi_skill",
            "skills_both": lambda r: "first_pass_yield" in r["skills_hit"] and "final_yield" in r["skills_hit"],
        },
    },
    # ── 工站/产品维度 ──────────────────────────────────────────────────────────
    {
        "id": "Y05",
        "group": "工站/产品维度",
        "desc": "各产品一次良率和综合良率对比",
        "query": "各产品的一次良率和综合良率对比",
        "expect_route": "multi_skill",
        "expect_skills": ["first_pass_yield", "final_yield"],
        "expect_has_answer": True,
        "checks": {
            "multi_skill": lambda r: r["route"] == "multi_skill",
            "skills_both": lambda r: "first_pass_yield" in r["skills_hit"] and "final_yield" in r["skills_hit"],
        },
    },
    {
        "id": "Y06",
        "group": "工站/产品维度",
        "desc": "各工站差值最大的工站",
        "query": "各工站一次良率和综合良率差值最大的是哪些",
        "expect_route": "multi_skill",
        "expect_skills": ["first_pass_yield", "final_yield"],
        "expect_has_answer": True,
        "checks": {
            "multi_skill": lambda r: r["route"] == "multi_skill",
            "skills_both": lambda r: "first_pass_yield" in r["skills_hit"] and "final_yield" in r["skills_hit"],
        },
    },
    # ── 边界验证 ───────────────────────────────────────────────────────────────
    {
        "id": "Y07",
        "group": "边界验证",
        "desc": "综合良率低于一次良率的工站（正常为空）",
        "query": "有哪些工站综合良率低于一次良率",
        "expect_route": "multi_skill",
        "expect_skills": ["first_pass_yield", "final_yield"],
        "expect_has_answer": True,
        "checks": {
            "routed": lambda r: r["route"] in ("multi_skill", "skill"),
        },
        "note": "正常情况下综合良率 >= 一次良率，若返回具体工站名则需人工确认数据",
    },
    # ── 单指标独立查询（不应触发 multi_skill）────────────────────────────────
    {
        "id": "Y08",
        "group": "单指标",
        "desc": "一次良率独立查询",
        "query": "最近一周各工站一次良率",
        "expect_route": "skill",
        "expect_skills": ["first_pass_yield"],
        "expect_has_answer": True,
        "checks": {
            "single_skill": lambda r: r["route"] == "skill",
            "correct_skill": lambda r: "first_pass_yield" in r["skills_hit"],
        },
    },
    {
        "id": "Y09",
        "group": "单指标",
        "desc": "综合良率独立查询",
        "query": "本月综合良率趋势",
        "expect_route": "skill",
        "expect_skills": ["final_yield"],
        "expect_has_answer": True,
        "checks": {
            "single_skill": lambda r: r["route"] == "skill",
            "correct_skill": lambda r: "final_yield" in r["skills_hit"],
        },
    },
    # ── 英文查询 ───────────────────────────────────────────────────────────────
    {
        "id": "Y10",
        "group": "英文查询",
        "desc": "FPY and final yield comparison",
        "query": "FPY and final yield comparison for last week",
        "expect_route": "multi_skill",
        "expect_skills": ["first_pass_yield", "final_yield"],
        "expect_has_answer": True,
        "checks": {
            "multi_skill": lambda r: r["route"] == "multi_skill",
            "skills_both": lambda r: "first_pass_yield" in r["skills_hit"] and "final_yield" in r["skills_hit"],
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

        # ── 路由判断（基于实测 trace 结构）──────────────────────────
        if "multi_skill_merge" in steps:
            route = "multi_skill"
        elif "analysis_method_selector" in steps:
            route = "skill"
        elif "intent_router" in steps:
            # 进一步区分 clarification
            for s in pt:
                if s.get("step") == "intent_router":
                    if s.get("detail", {}).get("route") == "clarification":
                        route = "clarification"
                        break
            else:
                route = "adhoc"
        else:
            route = "unknown"

        # ── skill 名提取 ──────────────────────────────────────────────
        # 优先从 multi_skill_merge.detail.skill_names（直接 list）
        skills_hit = []
        for s in pt:
            if s.get("step") == "multi_skill_merge":
                skills_hit = s.get("detail", {}).get("skill_names", [])
                break

        # 回退：从 analysis_method_selector reason 中正则提取 'skill_name'
        if not skills_hit:
            for s in pt:
                if s.get("step") == "analysis_method_selector":
                    reason = s.get("detail", {}).get("reason", "")
                    m = re.search(r"'([a-z_]+)'", reason)
                    if m and m.group(1) not in skills_hit:
                        skills_hit.append(m.group(1))

        answer = data.get("answer", "") or data.get("message", "") or ""
        charts = data.get("charts") or []

        # 记录 data_loader 错误（用于诊断数据为空）
        data_errors = []
        for s in pt:
            if s.get("step") == "analysis_data_loader":
                err = s.get("detail", {}).get("error")
                if err:
                    data_errors.append(err)

        return {
            "ok": True,
            "route": route,
            "skills_hit": skills_hit,
            "answer": answer,
            "answer_len": len(answer),
            "charts_count": len(charts),
            "steps": steps,
            "data_errors": data_errors,
            "elapsed": elapsed,
        }

    except httpx.TimeoutException:
        elapsed = time.time() - t0
        return {"ok": False, "error": f"TIMEOUT after {elapsed:.0f}s", "route": "timeout",
                "skills_hit": [], "answer": "", "answer_len": 0, "charts_count": 0,
                "steps": [], "data_errors": [], "elapsed": elapsed}
    except Exception as e:
        return {"ok": False, "error": str(e), "route": "error",
                "skills_hit": [], "answer": "", "answer_len": 0, "charts_count": 0,
                "steps": [], "data_errors": [], "elapsed": time.time() - t0}


def run_checks(case: dict, result: dict) -> tuple:
    errors = []
    warnings = []

    if not result["ok"]:
        errors.append(f"请求失败: {result.get('error', '未知错误')}")
        return False, errors, warnings

    # 路由检查
    if result["route"] != case["expect_route"]:
        errors.append(f"路由错误: 期望 {case['expect_route']}，实际 {result['route']}")

    # skill 命中检查
    for skill in case.get("expect_skills", []):
        if skill not in result["skills_hit"]:
            errors.append(f"skill 未命中: {skill}（实际 {result['skills_hit']}）")

    # answer 非空检查（数据为空时 answer 也有说明文字，不应为空）
    if case.get("expect_has_answer") and result["answer_len"] == 0:
        errors.append("answer 字段为空")

    # 自定义 checks
    for name, fn in case.get("checks", {}).items():
        try:
            if not fn(result):
                errors.append(f"check 失败: {name}")
        except Exception as e:
            warnings.append(f"check 异常: {name} — {e}")

    # 数据为空警告（路由正确但无生产数据）
    if result["data_errors"]:
        for err in result["data_errors"]:
            warnings.append(f"数据层: {err}")

    # Y07 边界验证特殊说明
    if case["id"] == "Y07" and result["answer_len"] > 0:
        if any(kw in result["answer"] for kw in ["工站", "station", "process"]):
            warnings.append("answer 含工站名，可能存在综合良率 < 一次良率的异常数据，请人工确认")

    # multi_skill charts 提示（数据为空时 0 图表是正常的）
    if case["expect_route"] == "multi_skill" and result["charts_count"] == 0 and not result["data_errors"]:
        warnings.append(f"multi_skill 但 charts=0（有数据时期望 >= 2）")

    # 延迟警告
    if result["elapsed"] > 60:
        warnings.append(f"响应时间 {result['elapsed']:.0f}s 超过 60s")

    return len(errors) == 0, errors, warnings


def main():
    print("=" * 70)
    print("一次良率 vs 综合良率对比查询测试")
    print("=" * 70)

    total = len(CASES)
    passed_count = 0
    results_summary = []
    current_group = ""

    for case in CASES:
        if case["group"] != current_group:
            current_group = case["group"]
            print(f"\n── {current_group} ──────────────────────────────────────")

        print(f"\n[{case['id']}] {case['desc']}")
        print(f"  查询: {case['query']}")

        result = probe(case["query"])
        passed, errors, warnings = run_checks(case, result)

        if passed:
            passed_count += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"

        print(
            f"  {status}  route={result['route']}  "
            f"skills={result['skills_hit']}  "
            f"charts={result['charts_count']}  "
            f"{result['elapsed']:.1f}s"
        )

        if result["answer_len"] > 0:
            preview = result["answer"][:180].replace("\n", " ")
            print(f"  answer: {preview!r}")
        else:
            print("  answer: (空)")

        if case.get("note"):
            print(f"  ℹ  {case['note']}")

        for e in errors:
            print(f"  ⛔ {e}")
        for w in warnings:
            print(f"  ⚠  {w}")

        results_summary.append({
            "id": case["id"], "group": case["group"], "desc": case["desc"],
            "passed": passed, "route": result["route"], "skills": result["skills_hit"],
            "charts": result["charts_count"], "elapsed": round(result["elapsed"], 1),
            "data_errors": result["data_errors"], "errors": errors, "warnings": warnings,
        })

    # ── 汇总 ─────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"整体汇总: {passed_count}/{total} 通过")
    print("=" * 70)

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
                print(f"       ⛔ {e}")
    else:
        print("\n全部通过 🎉")

    # 数据为空汇总（辅助诊断）
    empty_data = [r for r in results_summary if r["data_errors"]]
    if empty_data:
        print(f"\n注：{len(empty_data)} 个用例数据层返回空（路由正确，查询时段内无生产数据）:")
        for r in empty_data:
            print(f"  [{r['id']}] {'; '.join(set(r['data_errors']))}")

    report_path = "/tmp/yield_comparison_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({"total": total, "passed": passed_count, "results": results_summary},
                  f, ensure_ascii=False, indent=2)
    print(f"\n详细报告: {report_path}")
    sys.exit(0 if passed_count == total else 1)


if __name__ == "__main__":
    main()
