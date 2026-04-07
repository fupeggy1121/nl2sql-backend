#!/usr/bin/env python3
"""
NL2SQL 全流程验证脚本
====================
验证三层架构（Ontology+Mapping / Skill / LLM编排）的完整查询链路。

三个维度：
  A. Skill 路径 — 四个预定义指标的端到端验证
  B. 即席路径 — 无 skill 覆盖的多样化查询
  C. 路由准确性 — LLM 路由器的分类正确性

使用方式：
  # 需要后端运行在 localhost:8000
  python _validate_full_pipeline.py

  # 只跑某个维度
  python _validate_full_pipeline.py --dimension A
  python _validate_full_pipeline.py --dimension B
  python _validate_full_pipeline.py --dimension C

  # 输出 JSON 报告
  python _validate_full_pipeline.py --output /tmp/pipeline_report.json
"""

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
API_BASE = os.environ.get("NL2SQL_API", "http://localhost:8000")
CHAT_ENDPOINT = f"{API_BASE}/api/v1/chat"
TIMEOUT = 120  # 秒

# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class TestCase:
    id: str
    query: str
    dimension: str  # A / B / C
    # 期望
    expected_route: str = ""          # skill / adhoc / analysis
    expected_skill: str = ""          # skill_name（仅 skill 路径）
    expected_tables: List[str] = field(default_factory=list)
    expected_columns: List[str] = field(default_factory=list)
    should_have_data: bool = True     # 是否期望有返回数据
    time_sensitive: bool = False      # 是否涉及时间过滤
    expected_clarification: bool = False  # 期望返回引导性澄清问题而非 SQL
    notes: str = ""

@dataclass
class TestResult:
    id: str
    query: str
    dimension: str
    passed: bool = False
    # 实际结果
    route_decision: str = ""
    skill_matched: str = ""
    sql_generated: str = ""
    tables_used: List[str] = field(default_factory=list)
    has_data: bool = False
    row_count: int = 0
    latency_ms: float = 0.0
    # 检查结果
    checks: Dict[str, bool] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 测试用例定义
# ---------------------------------------------------------------------------

# 维度 A：Skill 路径端到端
SKILL_PATH_CASES = [
    # --- first_pass_yield ---
    TestCase(
        id="A01", dimension="A",
        query="最近7天一次良率",
        expected_route="skill",
        expected_skill="first_pass_yield",
        time_sensitive=True,
        notes="基本良率查询，验证完整 skill 链路",
    ),
    TestCase(
        id="A02", dimension="A",
        query="上周各工站的一次良率是多少",
        expected_route="skill",
        expected_skill="first_pass_yield",
        time_sensitive=True,
        notes="按工站分组 + 时间表达'上周'",
    ),
    TestCase(
        id="A03", dimension="A",
        query="最近两个星期FPY趋势",
        expected_route="skill",
        expected_skill="first_pass_yield",
        time_sensitive=True,
        notes="同义词FPY + 时间表达'两个星期'（曾经出过bug的场景）",
    ),

    # --- final_yield ---
    TestCase(
        id="A04", dimension="A",
        query="本月最终良率",
        expected_route="skill",
        expected_skill="final_yield",
        time_sensitive=True,
        notes="最终良率 vs 一次良率的路由区分",
    ),
    TestCase(
        id="A05", dimension="A",
        query="最近30天各产品的最终良率",
        expected_route="skill",
        expected_skill="final_yield",
        time_sensitive=True,
        notes="按产品分组的最终良率",
    ),

    # --- rework_rate ---
    TestCase(
        id="A06", dimension="A",
        query="最近一周返工率",
        expected_route="skill",
        expected_skill="rework_rate",
        time_sensitive=True,
        notes="返工率基本查询",
    ),
    TestCase(
        id="A07", dimension="A",
        query="上个月各工站返工比例",
        expected_route="skill",
        expected_skill="rework_rate",
        time_sensitive=True,
        notes="同义表达'返工比例' + 按工站分组",
    ),

    # --- wafer_wip ---
    TestCase(
        id="A08", dimension="A",
        query="当前在制品数量",
        expected_route="skill",
        expected_skill="wafer_wip",
        notes="WIP 查询，sql_agg 模式",
    ),
    TestCase(
        id="A09", dimension="A",
        query="各工站WIP分布",
        expected_route="skill",
        expected_skill="wafer_wip",
        notes="按工站的 WIP 分布",
    ),
    TestCase(
        id="A10", dimension="A",
        query="wafer在制品按站点统计",
        expected_route="skill",
        expected_skill="wafer_wip",
        notes="英文术语 wafer + 中文描述混合",
    ),
]

# 维度 B：即席路径
ADHOC_PATH_CASES = [
    # 单表简单聚合
    TestCase(
        id="B01", dimension="B",
        query="当前各工站有多少个批次在加工",
        expected_route="adhoc",
        notes="单表聚合 + 状态过滤",
    ),
    TestCase(
        id="B02", dimension="B",
        query="查一下carrier_info表里各状态的载具数量",
        expected_route="adhoc",
        notes="直接引用表名的即席查询",
    ),

    # 多表 JOIN
    TestCase(
        id="B03", dimension="B",
        query="查询最近3天各设备的加工批次数",
        expected_route="adhoc",
        time_sensitive=True,
        notes="需要 JOIN 设备表和批次表",
    ),

    # 状态码过滤
    TestCase(
        id="B04", dimension="B",
        query="查询所有状态为hold的批次",
        expected_route="adhoc",
        notes="状态枚举值过滤",
    ),

    # 时间维度
    TestCase(
        id="B05", dimension="B",
        query="上个月新建了多少个生产批次",
        expected_route="adhoc",
        time_sensitive=True,
        notes="时间范围 + COUNT 聚合",
    ),

    # 库存/仓库域
    TestCase(
        id="B06", dimension="B",
        query="当前各仓库库位的物料库存数量",
        expected_route="adhoc",
        notes="仓库域查询，验证跨域实体覆盖",
    ),

    # 复杂聚合
    TestCase(
        id="B07", dimension="B",
        query="最近7天每天新增的子批次数量趋势",
        expected_route="adhoc",
        time_sensitive=True,
        notes="按日分组的时间序列",
    ),

    # 边界模糊查询
    TestCase(
        id="B08", dimension="B",
        query="最近有异常的批次",
        expected_route="adhoc",
        should_have_data=False,
        expected_clarification=True,  # 正确产品行为：返回引导性问题
        notes="意图模糊，'异常'无明确本体映射，应返回澄清问题而非SQL",
    ),
]

# 维度 C：路由准确性
ROUTING_CASES = [
    # 应该走 skill 的
    TestCase(
        id="C01", dimension="C",
        query="一次良率",
        expected_route="skill",
        expected_skill="first_pass_yield",
        notes="最简的 skill 触发",
    ),
    TestCase(
        id="C02", dimension="C",
        query="首次通过率最近一个月",
        expected_route="skill",
        expected_skill="first_pass_yield",
        notes="同义表达'首次通过率'",
    ),
    TestCase(
        id="C03", dimension="C",
        query="yield rate for last week",
        expected_route="skill",
        notes="英文查询是否也能路由到 skill",
    ),
    TestCase(
        id="C04", dimension="C",
        query="返工率和良率对比",
        expected_route="skill",
        notes="多指标查询，至少匹配一个 skill",
    ),

    # 应该走 adhoc 的
    TestCase(
        id="C05", dimension="C",
        query="查一下有多少台设备",
        expected_route="adhoc",
        notes="明显的即席查询，不应匹配任何 skill",
    ),
    TestCase(
        id="C06", dimension="C",
        query="最近创建的10个批次的批次号",
        expected_route="adhoc",
        notes="具体数据查询，不是指标分析",
    ),
    TestCase(
        id="C07", dimension="C",
        query="载具使用率",
        expected_route="adhoc",
        notes="看起来像指标但没有对应 skill",
    ),

    # 边界场景
    TestCase(
        id="C08", dimension="C",
        query="帮我分析一下生产情况",
        expected_route="adhoc",
        should_have_data=False,
        expected_clarification=True,  # 正确产品行为：返回引导性问题
        notes="极度模糊的查询，应返回澄清问题引导用户细化意图",
    ),
]


# ---------------------------------------------------------------------------
# HTTP 调用
# ---------------------------------------------------------------------------
def call_api(query: str) -> Dict[str, Any]:
    """调用 NL2SQL API，返回完整响应"""
    try:
        import httpx
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx", "-q"])
        import httpx

    # 清除代理
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        os.environ.pop(k, None)

    t0 = time.time()
    try:
        r = httpx.post(CHAT_ENDPOINT, json={"message": query}, timeout=TIMEOUT)
        latency_ms = (time.time() - t0) * 1000
        body = r.json()
        body["_latency_ms"] = latency_ms
        return body
    except Exception as e:
        return {"error": str(e), "_latency_ms": (time.time() - t0) * 1000}


# ---------------------------------------------------------------------------
# 结果提取
# ---------------------------------------------------------------------------
def extract_result(response: Dict[str, Any], case: TestCase) -> TestResult:
    """从 API 响应中提取关键信息（适配实际响应结构）"""
    result = TestResult(
        id=case.id,
        query=case.query,
        dimension=case.dimension,
        latency_ms=response.get("_latency_ms", 0),
    )

    if "error" in response:
        result.errors.append(f"API调用失败: {response['error']}")
        return result

    data = response.get("data", {})
    pipeline_trace = data.get("pipeline_trace", [])
    # 将 pipeline_trace 转为 {step_name: detail} 字典，方便按名检索
    step_map: Dict[str, Dict[str, Any]] = {
        s["step"]: s.get("detail", {}) for s in pipeline_trace if "step" in s
    }

    answer = data.get("answer", "")

    if "analysis_method_selector" in step_map:
        # ── Skill 路径 ──────────────────────────────────────────────────────
        result.route_decision = "skill"

        selector_detail = step_map["analysis_method_selector"]
        reason = selector_detail.get("reason", "")
        # reason 格式: "[Skill路径] 'first_pass_yield' — ..."
        m = re.search(r"'(\w+)'", reason)
        result.skill_matched = m.group(1) if m else ""

        loader_detail = step_map.get("analysis_data_loader", {})
        result.sql_generated = loader_detail.get("sql", "")

        loader_error = loader_detail.get("error")
        result.has_data = (
            bool(answer.strip())
            and "数据为空" not in answer
            and loader_error is None
        )

    elif "intent_router" in step_map:
        # ── Adhoc 路径（包含澄清子路径） ─────────────────────────────────────────────────────────
        result.route_decision = "adhoc"

        if "clarification_node" in step_map:
            # 澄清子路径：意图模糊，返回引导性问题
            result.has_data = bool(answer.strip())
        else:
            gen_detail = step_map.get("sql_generator", {})
            result.sql_generated = gen_detail.get("sql", "")

            executor_detail = step_map.get("data_executor", {})
            rows = executor_detail.get("rows_count") or 0
            result.row_count = int(rows) if rows else 0
            result.has_data = result.row_count > 0 or bool(answer.strip())

    else:
        # ── 未知路径（兜底） ────────────────────────────────────────────────
        result.route_decision = "unknown"
        result.has_data = bool(answer.strip())
        # 尝试从任意步骤中找 SQL
        for step in pipeline_trace:
            sql = step.get("detail", {}).get("sql", "")
            if sql:
                result.sql_generated = sql
                break

    # 提取表名（从 SQL 中解析）
    if result.sql_generated:
        result.tables_used = extract_tables_from_sql(result.sql_generated)

    return result


def extract_tables_from_sql(sql: str) -> List[str]:
    """从 SQL 中提取引用的表名"""
    tables = set()
    # FROM / JOIN 后的表名
    for match in re.finditer(
        r'(?:FROM|JOIN)\s+`?(\w+)`?', sql, re.IGNORECASE
    ):
        table = match.group(1)
        # 排除子查询别名和关键字
        if table.upper() not in ("SELECT", "WHERE", "AS", "ON", "AND", "OR"):
            tables.add(table)
    return sorted(tables)


# ---------------------------------------------------------------------------
# 验证检查
# ---------------------------------------------------------------------------
def run_checks(result: TestResult, case: TestCase):
    """对结果执行各项检查"""

    # --- 通用检查 ---

    # C1: API 是否成功返回
    result.checks["api_success"] = len(result.errors) == 0

    # C2: 是否生成了 SQL
    result.checks["sql_generated"] = bool(result.sql_generated)

    # C3: SQL 语法基本检查（是否以 SELECT 开头）
    if result.sql_generated:
        sql_upper = result.sql_generated.strip().upper()
        result.checks["sql_syntax_basic"] = (
            sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")
        )
    else:
        result.checks["sql_syntax_basic"] = False

    # C4: 是否有返回数据
    if case.should_have_data:
        result.checks["has_data"] = result.has_data
        if not result.has_data:
            result.warnings.append("期望有返回数据但实际为空")
    else:
        result.checks["has_data"] = True  # 不强制要求

    # --- 路由检查 ---

    if case.expected_route:
        route_match = (
            result.route_decision == case.expected_route
            # 兼容可能的变体
            or (case.expected_route == "skill" and "skill" in result.route_decision.lower())
            or (case.expected_route == "adhoc" and "adhoc" in result.route_decision.lower())
        )
        result.checks["route_correct"] = route_match
        if not route_match:
            result.errors.append(
                f"路由错误: 期望={case.expected_route}, 实际={result.route_decision}"
            )

    # --- Skill 路径专项检查 ---

    if case.expected_skill:
        skill_match = (
            result.skill_matched == case.expected_skill
            or case.expected_skill in result.skill_matched
            or result.skill_matched in case.expected_skill
        )
        result.checks["skill_match"] = skill_match
        if not skill_match:
            result.warnings.append(
                f"Skill匹配: 期望={case.expected_skill}, 实际={result.skill_matched}"
            )

    # --- 时间过滤检查 ---

    if case.time_sensitive and result.sql_generated:
        has_time = bool(re.search(
            r'gmt_create|gmt_update|DATE_SUB|INTERVAL|BETWEEN.*\d{4}-\d{2}-\d{2}',
            result.sql_generated, re.IGNORECASE
        ))
        result.checks["time_filter_present"] = has_time
        if not has_time:
            result.warnings.append("时间敏感查询但 SQL 中未检测到时间过滤条件")

    # --- 表引用检查 ---

    if case.expected_tables:
        actual = set(result.tables_used)
        expected = set(case.expected_tables)
        overlap = actual & expected
        f1 = (2 * len(overlap) / (len(actual) + len(expected))) if (actual or expected) else 0
        result.checks["table_f1"] = f1 >= 0.5
        if f1 < 0.5:
            result.warnings.append(
                f"表引用 F1={f1:.2f}: 期望={expected}, 实际={actual}"
            )

    # --- 列检查 ---

    if case.expected_columns and result.sql_generated:
        sql_lower = result.sql_generated.lower()
        found = sum(1 for col in case.expected_columns if col.lower() in sql_lower)
        ratio = found / len(case.expected_columns)
        result.checks["column_coverage"] = ratio >= 0.7
        if ratio < 0.7:
            result.warnings.append(
                f"列覆盖率={ratio:.0%}: 缺少={[c for c in case.expected_columns if c.lower() not in sql_lower]}"
            )

    # --- 延迟检查 ---
    result.checks["latency_ok"] = result.latency_ms < 30000  # 30 秒上限
    if result.latency_ms >= 30000:
        result.warnings.append(f"延迟过高: {result.latency_ms:.0f}ms")

    # --- 澄清路径专项检查 ---
    if case.expected_clarification:
        # 正确产品行为是返回引导性问题，不需要 SQL
        result.checks["has_clarification"] = result.has_data  # answer 非空即通过
        if not result.has_data:
            result.errors.append("期望返回澄清问题但 answer 为空")

    # --- 综合判定 ---
    if case.expected_clarification:
        # 期望澄清：只检查 api_success + has_clarification
        critical_checks = ["api_success", "has_clarification"]
    else:
        critical_checks = ["api_success", "sql_generated", "sql_syntax_basic"]
        if case.expected_route:
            critical_checks.append("route_correct")

    result.passed = all(
        result.checks.get(c, False) for c in critical_checks
    )


# ---------------------------------------------------------------------------
# 报告输出
# ---------------------------------------------------------------------------
def print_dimension_report(dim_label: str, results: List[TestResult]):
    """打印某个维度的测试报告"""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    print(f"\n{'='*70}")
    print(f"  维度 {dim_label}  |  通过: {passed}/{total}  |  失败: {failed}")
    print(f"{'='*70}")

    for r in results:
        status = "✅ PASS" if r.passed else "❌ FAIL"
        print(f"\n  [{r.id}] {status}  {r.query}")
        print(f"       路由={r.route_decision or '?'}  skill={r.skill_matched or '-'}  "
              f"行数={r.row_count}  延迟={r.latency_ms:.0f}ms")

        if r.sql_generated:
            # 显示 SQL 的前 120 字符
            sql_preview = r.sql_generated.replace('\n', ' ')[:120]
            print(f"       SQL: {sql_preview}...")

        # 检查项
        check_str = "  ".join(
            f"{'✓' if v else '✗'}{k}" for k, v in r.checks.items()
        )
        print(f"       检查: {check_str}")

        if r.errors:
            for e in r.errors:
                print(f"       ⛔ {e}")
        if r.warnings:
            for w in r.warnings:
                print(f"       ⚠️  {w}")


def print_summary(all_results: List[TestResult]):
    """打印整体汇总"""
    total = len(all_results)
    passed = sum(1 for r in all_results if r.passed)

    # 按维度统计
    dims = {}
    for r in all_results:
        if r.dimension not in dims:
            dims[r.dimension] = {"total": 0, "passed": 0}
        dims[r.dimension]["total"] += 1
        if r.passed:
            dims[r.dimension]["passed"] += 1

    # 延迟统计
    latencies = [r.latency_ms for r in all_results if r.latency_ms > 0]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    p50 = sorted(latencies)[len(latencies) // 2] if latencies else 0
    p90 = sorted(latencies)[int(len(latencies) * 0.9)] if latencies else 0
    max_lat = max(latencies) if latencies else 0

    print(f"\n{'='*70}")
    print(f"  整体汇总  |  {passed}/{total} 通过  ({passed/total*100:.0f}%)")
    print(f"{'='*70}")

    for dim in sorted(dims.keys()):
        d = dims[dim]
        labels = {"A": "Skill路径", "B": "即席路径", "C": "路由准确性"}
        print(f"  维度{dim} ({labels.get(dim, '?')}): "
              f"{d['passed']}/{d['total']} 通过")

    print(f"\n  延迟统计:")
    print(f"    平均={avg_lat:.0f}ms  P50={p50:.0f}ms  P90={p90:.0f}ms  最大={max_lat:.0f}ms")

    # 路由混淆矩阵
    route_matrix = {}
    for r in all_results:
        case = next((c for c in ALL_CASES if c.id == r.id), None)
        if case and case.expected_route:
            key = (case.expected_route, r.route_decision or "unknown")
            route_matrix[key] = route_matrix.get(key, 0) + 1

    if route_matrix:
        print(f"\n  路由混淆矩阵 (期望 → 实际):")
        for (expected, actual), count in sorted(route_matrix.items()):
            marker = "✓" if expected == actual else "✗"
            print(f"    {marker} {expected:10s} → {actual:10s}  ({count}条)")

    # 失败用例列表
    failures = [r for r in all_results if not r.passed]
    if failures:
        print(f"\n  失败用例 ({len(failures)}条):")
        for r in failures:
            print(f"    [{r.id}] {r.query}")
            for e in r.errors:
                print(f"           ⛔ {e}")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
ALL_CASES = SKILL_PATH_CASES + ADHOC_PATH_CASES + ROUTING_CASES


def main():
    parser = argparse.ArgumentParser(description="NL2SQL 全流程验证")
    parser.add_argument("--dimension", choices=["A", "B", "C"],
                        help="只运行指定维度")
    parser.add_argument("--output", type=str, default="",
                        help="输出 JSON 报告路径")
    parser.add_argument("--ids", type=str, default="",
                        help="只运行指定 ID（逗号分隔）")
    args = parser.parse_args()

    # 筛选用例
    cases = ALL_CASES
    if args.dimension:
        cases = [c for c in cases if c.dimension == args.dimension]
    if args.ids:
        id_set = set(args.ids.split(","))
        cases = [c for c in cases if c.id in id_set]

    print(f"NL2SQL 全流程验证")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API: {CHAT_ENDPOINT}")
    print(f"用例数: {len(cases)}")

    # 检查后端连通性
    try:
        import httpx
        for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
            os.environ.pop(k, None)
        health = httpx.get(f"{API_BASE}/health", timeout=5)
        print(f"后端状态: {health.status_code}")
    except Exception as e:
        print(f"⛔ 后端连接失败: {e}")
        print(f"   请确保后端运行在 {API_BASE}")
        sys.exit(1)

    # 执行测试
    all_results: List[TestResult] = []

    for i, case in enumerate(cases):
        print(f"\n[{i+1}/{len(cases)}] {case.id}: {case.query} ...", end="", flush=True)
        response = call_api(case.query)
        result = extract_result(response, case)
        run_checks(result, case)
        all_results.append(result)

        status = "✅" if result.passed else "❌"
        print(f" {status} ({result.latency_ms:.0f}ms)")

    # 按维度输出报告
    for dim in sorted(set(c.dimension for c in cases)):
        dim_results = [r for r in all_results if r.dimension == dim]
        labels = {"A": "Skill 路径端到端", "B": "即席路径", "C": "路由准确性"}
        print_dimension_report(f"{dim} — {labels.get(dim, '?')}", dim_results)

    # 整体汇总
    print_summary(all_results)

    # 输出 JSON
    if args.output:
        report = {
            "timestamp": datetime.now().isoformat(),
            "api": CHAT_ENDPOINT,
            "total": len(all_results),
            "passed": sum(1 for r in all_results if r.passed),
            "results": [asdict(r) for r in all_results],
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n  JSON 报告已保存: {args.output}")

    # 退出码
    failures = sum(1 for r in all_results if not r.passed)
    sys.exit(min(failures, 1))


if __name__ == "__main__":
    main()
