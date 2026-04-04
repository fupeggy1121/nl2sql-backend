"""
A/B 对比测试：build_metric_context() (A路径) vs build_metric_context_by_entity() (B路径)

目的：验证 B 路径（仅使用 ontology 实体名 + 实体级映射，不提供 anchor_table/join_path/auto_filter）
      能否产出质量相当的 SQL，为后续移除 MetricDefinition 物理定位字段提供数据依据。

覆盖指标: wafer_wip (sql_agg), first_pass_yield, final_yield, rework_rate (python_compute)

验证级别:
  L1: SQL 可执行，无语法/运行时错误，行数 > 0
  L2: 结果列包含 required_columns 中所有必须列（python_compute 指标）
  L3: MetricComputer 计算结果与 A 路径差异 ≤ 10%

输出: 每个指标每条查询打印 A/B 对比，最终汇总表。
"""
import json
import re
import sys
from datetime import datetime
from typing import Optional

sys.path.insert(0, "/Users/fupeggy/NL2SQL")

import pandas as pd

# 确保 MetricComputer 子类注册
import app.analytics.metrics.first_pass_yield   # noqa: F401
import app.analytics.metrics.final_yield         # noqa: F401
import app.analytics.metrics.rework_rate         # noqa: F401
from app.analytics.registry import get_metric

from app.ontology.mapping import get_mapping
from app.skills.loader import get_skill_loader
from app.services.mysql_executor import MySQLExecutor
from app.agents.analysis_agent.nodes.method_selector import _extract_date_range

# ─────────────────────────────────────────────────────────────────────────────
# LLM helpers (inline, to inject custom metric_context)
# ─────────────────────────────────────────────────────────────────────────────

def _call_llm_detail_sql(metric_def, skill, user_input: str, metric_context: str) -> Optional[str]:
    """与 _llm_build_detail_sql 相同 prompt，但 metric_context 由外部传入（用于 B 路径）。"""
    from app.agent.llm import get_llm
    mapping = get_mapping()
    value_summary = mapping.build_value_summary(max_domains=6)
    start_date, end_date = _extract_date_range(user_input)

    skill_block = ""
    if skill:
        skill_block = f"""## Skill 方法论
指标名称: {', '.join(skill.zh_names[:3])}
标准定义: {skill.standard_definition}
计算公式: {skill.formula}

{skill.body}
"""
    req_cols_block = ""
    if skill and skill.required_columns:
        col_lines = []
        for col in skill.required_columns:
            if col == "rn":
                order = skill.rn_order or "ASC"
                col_lines.append(
                    f"  - rn   （必须用 ROW_NUMBER() OVER "
                    f"(PARTITION BY wafer_id, process_code ORDER BY gmt_create {order}) AS rn）"
                )
            elif col == "report_date":
                col_lines.append("  - report_date   （必须用 DATE(gmt_create) AS report_date）")
            else:
                col_lines.append(f"  - {col}")
        req_cols_block = (
            "\n## Python Computer 必须列（SELECT 中必须包含，列名须完全一致）\n"
            + "\n".join(col_lines) + "\n"
        )

    prompt = f"""{skill_block}
{metric_context}
{req_cols_block}
## 业务值域（状态码枚举）
{value_summary}

## 时间上下文
查询时间范围: {start_date} 至 {end_date}

## 用户问题
"{user_input}"

## 任务
根据以上 Skill 方法论和数据物理结构，生成明细查询 SQL。
后续 Python 程序将读取这些明细行并完成指标计算，SQL 不做指标聚合。

要求：
- SELECT 中必须包含"Python Computer 必须列"中的所有列（列名须与列表完全一致）
- 返回计算所需的原始明细行（行级数据）
- 时间范围过滤用 gmt_create BETWEEN 或 >= / <=
- 加 LIMIT 100000
- **严禁**使用"涉及的物理表"的关键列列表以外的列名

输出 JSON（只返回 JSON）：
{{
  "sql": "SELECT ... FROM ... WHERE ... LIMIT 100000",
  "key_columns": ["col1", "col2"],
  "reason": "一句话说明返回了哪些字段，用于什么计算"
}}"""

    llm = get_llm()
    resp = llm.invoke(prompt)
    content = resp.content if hasattr(resp, "content") else str(resp)
    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        data = json.loads(match.group())
        return data.get("sql", "").strip() or None
    return None


def _call_llm_aggregate_sql(metric_def, skill, user_input: str, metric_context: str) -> Optional[str]:
    """与 _llm_build_aggregate_sql 相同 prompt，metric_context 由外部传入。"""
    from app.agent.llm import get_llm
    mapping = get_mapping()
    value_summary = mapping.build_value_summary(max_domains=6)
    today = datetime.now().date()
    fallback_start, fallback_end = _extract_date_range(user_input)

    skill_block = ""
    if skill:
        skill_block = f"""## Skill 方法论
指标名称: {', '.join(skill.zh_names[:3])}
标准定义: {skill.standard_definition}
计算公式: {skill.formula}
支持粒度: {', '.join(skill.granularity)}

{skill.body}
"""

    prompt = f"""{skill_block}
{metric_context}

## 业务值域（状态码枚举）
{value_summary}

## 时间上下文
当前日期: {today}
如果用户未明确提及时间，请使用 fallback 范围: {fallback_start} 至 {fallback_end}。

## 用户问题
"{user_input}"

## 任务
根据以上 Skill 方法论和数据物理结构，生成一条可执行的 MySQL 聚合查询 SQL。

要求：
- 使用聚合函数（COUNT / SUM / AVG）+ GROUP BY
- 必须包含时间范围的 WHERE 过滤
- 加 LIMIT 10000
- **严禁**使用关键列列表以外的列名

输出 JSON（只返回 JSON）：
{{
  "sql": "SELECT ... FROM ... WHERE ... GROUP BY ... LIMIT 10000",
  "groupby_dims": ["col1", "col2"],
  "reason": "一句话说明为什么这样写"
}}"""

    llm = get_llm()
    resp = llm.invoke(prompt)
    content = resp.content if hasattr(resp, "content") else str(resp)
    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        data = json.loads(match.group())
        return data.get("sql", "").strip() or None
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Test catalogue
# ─────────────────────────────────────────────────────────────────────────────

METRICS_QUERIES = {
    "wafer_wip": [
        "各工站当前在制品数量",
        "查各工序在制wafer数",
        "统计当前WIP分布",
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
    "rework_rate": [
        "各工站返工率统计",
        "过去一个月的返工情况",
        "按产品统计返工率",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────────────────────────
mapping = get_mapping()
loader = get_skill_loader()
exec_ = MySQLExecutor()

if not exec_.connect():
    print("FATAL: 无法连接数据库")
    sys.exit(1)
print("DB 连接成功\n")


def run_sql(label: str, sql: str, required_cols: list) -> tuple:
    """返回 (df|None, l1_pass, l2_pass)"""
    rows = exec_.execute_query(sql)
    if rows is None:
        return None, False, False
    if len(rows) == 0:
        return pd.DataFrame(), True, False
    df = pd.DataFrame(rows)
    df.columns = [c.lower() for c in df.columns]
    missing = [c for c in required_cols if c not in df.columns]
    return df, True, len(missing) == 0


def compare_computer(metric_id, df_a, df_b):
    """L3: run MetricComputer on both DataFrames, compare value."""
    if df_a is None or df_b is None or df_a.empty or df_b.empty:
        return None, None, "SKIP"
    computer = get_metric(metric_id)
    if not computer:
        return None, None, "NO_COMPUTER"
    ra = computer.compute(df_a.copy())
    rb = computer.compute(df_b.copy())
    if not ra.success or not rb.success:
        return ra.value, rb.value, f"FAIL(a_ok={ra.success},b_ok={rb.success})"
    va, vb = ra.value, rb.value
    if va is not None and vb is not None:
        diff_pct = abs(vb - va) / max(abs(va), 1e-9) * 100
        status = "PASS" if diff_pct <= 10.0 else f"WARN({diff_pct:.1f}%)"
    else:
        status = f"NO_VAL(a={va},b={vb})"
    return va, vb, status


# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────

# Results accumulator: {metric_id: [(query, a_l1,a_l2, b_l1,b_l2, l3_status), ...]}
results = {}

for metric_id, queries in METRICS_QUERIES.items():
    print(f"\n{'#'*70}")
    print(f"# 指标: {metric_id}")
    print(f"{'#'*70}")

    metric_def = mapping.get_metric_by_id(metric_id)
    skill = loader.get_skill(metric_id)
    required_cols = skill.required_columns if skill else []
    is_python = metric_def.compute_mode == "python_compute"

    ctx_a = mapping.build_metric_context(metric_def)
    ctx_b = mapping.build_entity_context(skill.required_entities if skill else [])

    print(f"\n[context sizes] A={len(ctx_a)} chars, B={len(ctx_b)} chars")

    metric_results = []
    for query in queries:
        print(f"\n{'='*60}")
        print(f"查询: {query}")

        # ── 生成 SQL ──────────────────────────────────────────────────
        try:
            sql_a = (_call_llm_detail_sql if is_python else _call_llm_aggregate_sql)(
                metric_def, skill, query, ctx_a
            )
        except Exception as e:
            print(f"  [A] LLM error: {e}")
            sql_a = None

        try:
            sql_b = (_call_llm_detail_sql if is_python else _call_llm_aggregate_sql)(
                metric_def, skill, query, ctx_b
            )
        except Exception as e:
            print(f"  [B] LLM error: {e}")
            sql_b = None

        # ── 执行 SQL ──────────────────────────────────────────────────
        df_a, a_l1, a_l2 = (None, False, False) if not sql_a else run_sql("A", sql_a, required_cols)
        df_b, b_l1, b_l2 = (None, False, False) if not sql_b else run_sql("B", sql_b, required_cols)

        print(f"  A: L1={'✓' if a_l1 else '✗'} L2={'✓' if a_l2 or not required_cols else '✗'}  "
              f"rows={len(df_a) if df_a is not None else 'N/A'}")
        print(f"  B: L1={'✓' if b_l1 else '✗'} L2={'✓' if b_l2 or not required_cols else '✗'}  "
              f"rows={len(df_b) if df_b is not None else 'N/A'}")

        if sql_a:
            print(f"  A SQL[:120]: {sql_a[:120]}")
        if sql_b:
            print(f"  B SQL[:120]: {sql_b[:120]}")

        # ── L3 (python_compute only) ──────────────────────────────────
        l3_status = "N/A"
        if is_python:
            val_a, val_b, l3_status = compare_computer(metric_id, df_a, df_b)
            print(f"  L3: A_val={val_a}, B_val={val_b} → {l3_status}")

        metric_results.append((
            query,
            a_l1, (a_l2 or not required_cols),
            b_l1, (b_l2 or not required_cols),
            l3_status,
        ))

    results[metric_id] = metric_results


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n\n{'#'*70}")
print("# A/B 对比汇总")
print(f"{'#'*70}")
print(f"{'指标':<20} {'查询':<20} {'A-L1':<5} {'A-L2':<5} {'B-L1':<5} {'B-L2':<5} {'L3'}")
print("-" * 80)

b_regressions = 0
for metric_id, rows in results.items():
    for (query, a_l1, a_l2, b_l1, b_l2, l3) in rows:
        a_ok = a_l1 and a_l2
        b_ok = b_l1 and b_l2
        if a_ok and not b_ok:
            b_regressions += 1
        flag = " ⚠" if (a_ok and not b_ok) else ""
        q_short = query[:18]
        print(f"{metric_id:<20} {q_short:<20} "
              f"{'✓' if a_l1 else '✗':<5} {'✓' if a_l2 else '✗':<5} "
              f"{'✓' if b_l1 else '✗':<5} {'✓' if b_l2 else '✗':<5} {l3}{flag}")

print()
if b_regressions == 0:
    print(">> B 路径与 A 路径质量相当 — ontology_entities 上下文可以替代物理定位字段 <<")
    print(">> 可以考虑将 anchor_table / join_path / auto_filter 标记 deprecated <<")
else:
    print(f">> B 路径有 {b_regressions} 处回归（A通过但B失败），暂不移除物理定位字段 <<")
