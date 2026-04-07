#!/usr/bin/env python3
"""
multi_skill 并行路径验证脚本

覆盖场景：
  M01 — 两个同类指标对比（已知可用）
  M02 — 跨类指标组合
  M03 — 三个指标
  M04 — 边界：单指标，不应触发 multi_skill
  M05 — 边界：adhoc查询，不应触发 multi_skill
  M06 — 带时间范围的多指标
"""

import httpx
import json
import time
import os
import sys

for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(k, None)

ENDPOINT = "http://localhost:8000/api/v1/chat"
TIMEOUT = 120

# ── 测试用例定义 ──────────────────────────────────────────────────────────────
CASES = [
    {
        "id": "M01",
        "desc": "两个同类指标对比（基准验证）",
        "query": "返工率和良率对比",
        "expect_route": "multi_skill",
        "expect_min_skills": 2,
        "expect_has_answer": True,
    },
    {
        "id": "M02",
        "desc": "跨类指标：WIP数量和一次良率",
        "query": "最近一个月WIP数量和一次良率的关系",
        "expect_route": "multi_skill",
        "expect_min_skills": 2,
        "expect_has_answer": True,
    },
    {
        "id": "M03",
        "desc": "三个指标同时查询",
        "query": "比较一次良率、综合良率和返工率",
        "expect_route": "multi_skill",
        "expect_min_skills": 3,
        "expect_has_answer": True,
    },
    {
        "id": "M04",
        "desc": "边界：单指标，不应触发 multi_skill",
        "query": "最近7天返工率趋势",
        "expect_route": "skill",          # 应该走单 skill
        "expect_min_skills": 1,
        "expect_has_answer": True,
    },
    {
        "id": "M05",
        "desc": "边界：adhoc查询，不应触发 multi_skill",
        "query": "当前各工站有多少批次在加工",
        "expect_route": "adhoc",
        "expect_min_skills": 0,
        "expect_has_answer": True,
    },
    {
        "id": "M06",
        "desc": "带时间范围的多指标",
        "query": "上个月各工站的一次良率和返工率",
        "expect_route": "multi_skill",
        "expect_min_skills": 2,
        "expect_has_answer": True,
    },
]


# ── 工具函数 ──────────────────────────────────────────────────────────────────
def probe(query: str, timeout: int = TIMEOUT):
    """调用 chat API，返回解析后的结果字典。"""
    t0 = time.time()
    try:
        r = httpx.post(ENDPOINT, json={"message": query}, timeout=timeout)
        elapsed = time.time() - t0
        body = r.json()
        data = body.get("data", {})
        pt = data.get("pipeline_trace", [])

        # 判断路由类型
        steps = [s.get("step", "") for s in pt]
        if "multi_skill_merge" in steps:
            route = "multi_skill"
        elif "analysis_method_selector" in steps:
            route = "skill"
        elif "intent_router" in steps:
            route = "adhoc"
        else:
            route = "unknown"

        # 收集命中的 skill 列表
        # analysis_method_selector 的 detail.reason 格式: "[Skill路径] 'skill_name' — ..."
        import re as _re
        skills_hit = []
        for s in pt:
            if s.get("step") == "analysis_method_selector":
                reason = s.get("detail", {}).get("reason", "")
                m = _re.search(r"'(\w+)'", reason)
                if m:
                    skill = m.group(1)
                    if skill not in skills_hit:
                        skills_hit.append(skill)

        # charts 数量
        charts = data.get("charts") or []

        # analysis 字段（multi_skill 时是 dict of skill_name→result）
        analysis = data.get("analysis") or {}

        answer = data.get("answer", "") or ""
        # adhoc 路径无 answer 字段，检查 query_result 是否有内容
        if not answer:
            qr = data.get("query_result") or {}
            if qr.get("data") or qr.get("rows") or qr.get("total", 0) > 0:
                answer = f"[query_result] rows={qr.get('total', len(qr.get('data') or []))}"

        return {
            "ok": True,
            "route": route,
            "skills_hit": skills_hit,
            "answer": answer,
            "answer_len": len(answer),
            "charts_count": len(charts),
            "analysis_keys": list(analysis.keys()) if isinstance(analysis, dict) else [],
            "steps": steps,
            "elapsed": elapsed,
        }

    except httpx.TimeoutException:
        return {"ok": False, "error": f"TIMEOUT after {time.time()-t0:.0f}s",
                "route": "timeout", "skills_hit": [], "answer": "",
                "answer_len": 0, "charts_count": 0, "analysis_keys": [],
                "steps": [], "elapsed": time.time()-t0}
    except Exception as e:
        return {"ok": False, "error": str(e),
                "route": "error", "skills_hit": [], "answer": "",
                "answer_len": 0, "charts_count": 0, "analysis_keys": [],
                "steps": [], "elapsed": time.time()-t0}


def run_checks(case: dict, result: dict) -> tuple[bool, list[str], list[str]]:
    """返回 (passed, errors, warnings)。"""
    errors = []
    warnings = []

    if not result["ok"]:
        errors.append(f"请求失败: {result.get('error', '未知错误')}")
        return False, errors, warnings

    # 路由检查
    actual_route = result["route"]
    expect_route = case["expect_route"]
    if actual_route != expect_route:
        errors.append(f"路由错误: 期望 {expect_route}，实际 {actual_route}")

    # skill 数量检查
    min_skills = case["expect_min_skills"]
    actual_skills = len(result["skills_hit"])
    if actual_skills < min_skills:
        errors.append(
            f"skill 数量不足: 期望 >= {min_skills}，"
            f"实际 {actual_skills} {result['skills_hit']}"
        )

    # answer 检查
    if case["expect_has_answer"] and result["answer_len"] == 0:
        errors.append("answer 字段为空，用户将看到空白响应")

    # multi_skill 专项检查
    if expect_route == "multi_skill":
        if result["charts_count"] < 2:
            warnings.append(
                f"multi_skill 但 charts 只有 {result['charts_count']} 个（期望 >= 2）"
            )
        if len(result["analysis_keys"]) < 2:
            warnings.append(
                f"analysis 字段只有 {len(result['analysis_keys'])} 个 key: "
                f"{result['analysis_keys']}"
            )

    # 延迟警告
    if result["elapsed"] > 60:
        warnings.append(f"响应时间 {result['elapsed']:.0f}s 超过 60s")

    passed = len(errors) == 0
    return passed, errors, warnings


# ── 主流程 ───────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("multi_skill 并行路径验证")
    print("=" * 65)

    total = len(CASES)
    passed_count = 0
    results_summary = []

    for case in CASES:
        print(f"\n[{case['id']}] {case['desc']}")
        print(f"  查询: {case['query']}")

        result = probe(case["query"])
        passed, errors, warnings = run_checks(case, result)

        if passed:
            passed_count += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"

        # 打印详情
        print(f"  {status}  route={result['route']}  "
              f"skills={result['skills_hit']}  "
              f"charts={result['charts_count']}  "
              f"{result['elapsed']:.1f}s")
        print(f"  steps: {result['steps']}")

        if result["answer_len"] > 0:
            preview = result["answer"][:120].replace("\n", " ")
            print(f"  answer: {preview!r}...")
        else:
            print(f"  answer: (空)")

        if result["analysis_keys"]:
            print(f"  analysis keys: {result['analysis_keys']}")

        for e in errors:
            print(f"  ⛔ {e}")
        for w in warnings:
            print(f"  ⚠  {w}")

        results_summary.append({
            "id": case["id"],
            "desc": case["desc"],
            "passed": passed,
            "route": result["route"],
            "skills": result["skills_hit"],
            "charts": result["charts_count"],
            "elapsed": round(result["elapsed"], 1),
            "errors": errors,
            "warnings": warnings,
        })

    # ── 汇总 ──
    print("\n" + "=" * 65)
    print(f"整体汇总: {passed_count}/{total} 通过")
    print("=" * 65)

    failed = [r for r in results_summary if not r["passed"]]
    if failed:
        print("失败用例:")
        for r in failed:
            print(f"  ❌ [{r['id']}] {r['desc']}")
            for e in r["errors"]:
                print(f"      ⛔ {e}")
    else:
        print("全部通过 🎉")

    # 输出 JSON 报告
    report_path = "/tmp/multi_skill_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({"total": total, "passed": passed_count, "results": results_summary},
                  f, ensure_ascii=False, indent=2)
    print(f"\n详细报告: {report_path}")

    sys.exit(0 if passed_count == total else 1)


if __name__ == "__main__":
    main()
