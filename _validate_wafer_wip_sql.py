"""
端到端验证：wafer_wip sql_aggregate LLM SQL vs 确定性 SQL
L1: 语法（EXPLAIN）
L2: 执行结构（行数、列名）
"""
import sys
sys.path.insert(0, "/Users/fupeggy/NL2SQL")

from app.ontology.mapping import get_mapping
from app.skills.loader import get_skill_loader
from app.services.mysql_executor import MySQLExecutor
from app.agents.analysis_agent.nodes.method_selector import (
    _llm_build_aggregate_sql,
    _build_metric_sql,
)

m = get_mapping()
loader = get_skill_loader()
metric_def = m.get_metric_by_id("wafer_wip")
skill = loader.get_skill("wafer_wip")

TEST_QUERIES = [
    "各工站当前在制品数量",
    "查各工序在制wafer数",
    "统计当前WIP分布",
]

exec_ = MySQLExecutor()
connected = exec_.connect()
if not connected:
    print("FATAL: 无法连接数据库，终止验证")
    sys.exit(1)
print("DB 连接成功\n")


def validate_sql(label: str, sql: str):
    print(f"\n{'='*60}")
    print(f"[{label}]")
    print(f"SQL:\n{sql}\n")

    # L1: 直接执行，用异常判断语法合法性
    # (DictCursor: EXPLAIN 走 DML 分支返回 None，所以直接执行 SELECT)
    rows = exec_.execute_query(sql)
    if rows is None:
        print("L1 FAIL: 执行失败（语法错误或运行时错误）")
        return None, None

    row_count = len(rows)
    cols = set(rows[0].keys()) if rows else set()
    print(f"L1+L2 PASS: rows={row_count}, cols={sorted(cols)}")
    for r in rows[:5]:
        print(f"  {r}")
    return row_count, cols


for query in TEST_QUERIES:
    print(f"\n{'#'*60}")
    print(f"用户问题: {query}")

    det_sql = _build_metric_sql(metric_def, skill, query)
    llm_sql = _llm_build_aggregate_sql(metric_def, skill, query)

    det_rows, det_cols = validate_sql("确定性SQL", det_sql)
    if llm_sql:
        llm_rows, llm_cols = validate_sql("LLM SQL", llm_sql)

        # L2 结构对比
        if det_rows is not None and llm_rows is not None:
            row_diff_pct = abs(llm_rows - det_rows) / max(det_rows, 1) * 100
            col_match = (det_cols == llm_cols) if (det_cols and llm_cols) else "N/A"
            print(f"\n[L2对比] 行数差={row_diff_pct:.1f}% (det={det_rows}, llm={llm_rows}), 列名一致={col_match}")
            if isinstance(col_match, bool) and not col_match:
                print(f"  det列: {det_cols}")
                print(f"  llm列: {llm_cols}")
    else:
        print("LLM SQL 生成失败，fallback 到确定性 SQL")
