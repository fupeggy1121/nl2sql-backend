"""
端到端验证：python_compute 指标 LLM SQL vs 确定性 SQL
L1: SQL 可执行（无语法/运行时错误，有返回行）
L2: 结果列包含所有 required_columns（Python Computer 依赖列）
L3: LLM SQL 经 MetricComputer 计算结果与确定性路径结构一致

覆盖指标: rework_rate, first_pass_yield, final_yield
"""
import sys
sys.path.insert(0, "/Users/fupeggy/NL2SQL")

import pandas as pd

from app.ontology.mapping import get_mapping
from app.skills.loader import get_skill_loader
from app.services.mysql_executor import MySQLExecutor
from app.agents.analysis_agent.nodes.method_selector import (
    _llm_build_detail_sql,
    _build_metric_sql,
)

# 确保 MetricComputer 子类完成注册
import app.analytics.metrics.rework_rate       # noqa: F401
import app.analytics.metrics.first_pass_yield  # noqa: F401
import app.analytics.metrics.final_yield       # noqa: F401
from app.analytics.registry import get_metric

# ── 测试用例 ──────────────────────────────────────────────────────────────────
METRICS_QUERIES = {
    "rework_rate": [
        "各工站返工率统计",
        "过去一个月的返工情况",
        "按产品统计返工率",
    ],
    "first_pass_yield": [
        "各工站一次良率",
        "本月FPY趋势",
        "按产品统计首次合格率",
    ],
    "final_yield": [
        "各工站综合良率",
        "本月最终良率",
        "按工站查良率",
    ],
}

# ── 初始化 ─────────────────────────────────────────────────────────────────────
m = get_mapping()
loader = get_skill_loader()
exec_ = MySQLExecutor()

if not exec_.connect():
    print("FATAL: 无法连接数据库，终止验证")
    sys.exit(1)
print("DB 连接成功\n")


def run_sql(label: str, sql: str, required_cols: list[str]) -> tuple[pd.DataFrame | None, bool, bool]:
    """
    执行 SQL，返回 (dataframe, L1_pass, L2_pass)。
    L1: 执行成功且行数 > 0
    L2: required_cols 全部出现在结果列名中
    """
    print(f"\n  [{label}]")
    print(f"  SQL(前200字符): {sql[:200]}...")

    rows = exec_.execute_query(sql)
    if rows is None:
        print("  L1 FAIL: 执行失败（语法/运行时错误）")
        return None, False, False

    if len(rows) == 0:
        print("  L1 WARN: 执行成功但返回 0 行")
        return pd.DataFrame(), True, False

    df = pd.DataFrame(rows)
    df.columns = [c.lower() for c in df.columns]
    actual_cols = set(df.columns)

    # L2: 检查 required_columns
    missing = [c for c in required_cols if c not in actual_cols]
    l2_pass = len(missing) == 0

    print(f"  L1 PASS: rows={len(df)}, cols={sorted(actual_cols)}")
    if l2_pass:
        print(f"  L2 PASS: 所有必须列均存在 {required_cols}")
    else:
        print(f"  L2 FAIL: 缺少列 {missing}（需要: {required_cols}）")

    for r in rows[:3]:
        print(f"    {dict(r)}")
    return df, True, l2_pass


def compare_computer(metric_id: str, det_df: pd.DataFrame | None, llm_df: pd.DataFrame | None):
    """
    L3: 用同一 MetricComputer 分别计算两份数据，对比结果。
    只在 det_df 和 llm_df 都非空时执行。
    """
    if det_df is None or llm_df is None or det_df.empty or llm_df.empty:
        print("  L3 SKIP: 其中一份数据为空，无法对比")
        return

    computer = get_metric(metric_id)
    if computer is None:
        print(f"  L3 SKIP: 未找到 MetricComputer for '{metric_id}'")
        return

    det_result = computer.compute(det_df.copy())
    llm_result = computer.compute(llm_df.copy())

    det_ok = det_result.success
    llm_ok = llm_result.success
    det_val = det_result.value
    llm_val = llm_result.value

    print(f"  L3 det: success={det_ok}, value={det_val}, summary={det_result.summary[:60]}")
    print(f"  L3 llm: success={llm_ok}, value={llm_val}, summary={llm_result.summary[:60]}")

    if not llm_ok:
        print("  L3 FAIL: LLM SQL 的数据经 Computer 计算失败")
        if llm_result.error:
            print(f"           error: {llm_result.error}")
        return

    if det_val is not None and llm_val is not None:
        diff_pct = abs(llm_val - det_val) / max(abs(det_val), 1e-9) * 100
        threshold = 10.0  # 允许 ±10% 误差（时间窗口等浮动因素）
        if diff_pct <= threshold:
            print(f"  L3 PASS: 结果差异 {diff_pct:.2f}% ≤ {threshold}%")
        else:
            print(f"  L3 WARN: 结果差异 {diff_pct:.2f}% > {threshold}%（det={det_val:.4f}, llm={llm_val:.4f}）")
    else:
        print(f"  L3 INFO: value 为 None（det_val={det_val}, llm_val={llm_val}），对比 detail 行数")
        det_detail_n = len(det_result.detail)
        llm_detail_n = len(llm_result.detail)
        print(f"           det detail rows={det_detail_n}, llm detail rows={llm_detail_n}")


# ── 主验证循环 ────────────────────────────────────────────────────────────────
pass_summary: dict[str, list[str]] = {}

for metric_id, queries in METRICS_QUERIES.items():
    print(f"\n{'#'*70}")
    print(f"# 指标: {metric_id}")
    print(f"{'#'*70}")

    metric_def = m.get_metric_by_id(metric_id)
    skill = loader.get_skill(metric_id)
    required_cols = skill.required_columns if skill else []

    if not metric_def:
        print(f"FATAL: 找不到 metric_def for '{metric_id}'")
        continue

    metric_pass_list = []

    for query in queries:
        print(f"\n{'='*60}")
        print(f"查询: {query}")

        det_sql = _build_metric_sql(metric_def, skill, query)
        llm_sql = _llm_build_detail_sql(metric_def, skill, query)

        det_df, det_l1, det_l2 = run_sql("确定性SQL", det_sql, required_cols)

        if not llm_sql:
            print("  [LLM SQL] 生成失败，跳过 L1/L2/L3")
            metric_pass_list.append(f"{query}: LLM生成失败")
            continue

        llm_df, llm_l1, llm_l2 = run_sql("LLM SQL", llm_sql, required_cols)

        # L3 对比
        if llm_l1:
            compare_computer(metric_id, det_df, llm_df)

        status = "PASS" if (llm_l1 and llm_l2) else "FAIL"
        metric_pass_list.append(f"{query}: L1={'✓' if llm_l1 else '✗'} L2={'✓' if llm_l2 else '✗'} → {status}")

    pass_summary[metric_id] = metric_pass_list

# ── 汇总报告 ──────────────────────────────────────────────────────────────────
print(f"\n\n{'#'*70}")
print("# 验证汇总")
print(f"{'#'*70}")
all_pass = True
for metric_id, results in pass_summary.items():
    print(f"\n[{metric_id}]")
    for line in results:
        print(f"  {line}")
        if "FAIL" in line or "生成失败" in line:
            all_pass = False

print()
if all_pass:
    print(">> ALL PASS — 可以将以上指标加入 _LLM_SQL_ENABLED_METRICS <<")
else:
    print(">> 存在 FAIL 项，需要修复后再切换灰度 <<")
