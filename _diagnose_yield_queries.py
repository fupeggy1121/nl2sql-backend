"""
诊断：两条查询为何返回相同 SQL
"""
import sys
sys.path.insert(0, '/Users/fupeggy/NL2SQL')

from app.agents.analysis_agent.nodes.method_selector import (
    _build_yield_sql, _extract_station_filter, _extract_date_range
)
from app.agent.nodes.sql_generator import _apply_metric_sql_template
import json

Q1 = '查询\u201cPOL抛光\u201d工站最近7天按天统计的一次良率'   # 中文双引号
Q2 = '统计每个站点最近一周的一次良率'

print("=== 查询原文 ===")
print(f"Q1: {Q1}")
print(f"Q2: {Q2}")
print()

print("=== _extract_date_range ===")
print(f"Q1: {_extract_date_range(Q1)}")
print(f"Q2: {_extract_date_range(Q2)}")
print()

print("=== _extract_station_filter ===")
print(f"Q1: {repr(_extract_station_filter(Q1).strip())}")
print(f"Q2: {repr(_extract_station_filter(Q2).strip())}")
print()

print("=== 路由判断 (wants_fpy, use_dual_template) ===")
import re
for q, label in [(Q1, 'Q1'), (Q2, 'Q2')]:
    wants_fpy   = bool(re.search(r"一次良率|首次合格率|直通率|FPY|first.pass", q, re.IGNORECASE))
    wants_final = bool(re.search(r"综合良率|最终良率|累计良率", q, re.IGNORECASE))
    use_dual    = wants_fpy or wants_final or bool(re.search(r"良率趋势|yield.*trend|trend.*yield", q, re.IGNORECASE))
    print(f"{label}: wants_fpy={wants_fpy} wants_final={wants_final} use_dual_template={use_dual}")
print()

print("=== 生成的 SQL 差异 ===")
sql1 = _build_yield_sql(Q1)['sql']
sql2 = _build_yield_sql(Q2)['sql']
if sql1 == sql2:
    print("❌ 两条 SQL 完全相同！WHERE_EXTRA 段：")
    for line in sql1.split('\n'):
        if line.strip().startswith('AND') or '{WHERE' in line:
            print('  ' + line.strip())
else:
    print("✅ SQL 不同")
    lines1 = set(l.strip() for l in sql1.split('\n') if l.strip().startswith('AND'))
    lines2 = set(l.strip() for l in sql2.split('\n') if l.strip().startswith('AND'))
    print("仅Q1有:", lines1 - lines2)
    print("仅Q2有:", lines2 - lines1)

print()
print("=== sql_generator fast-path station test ===")
with open('/Users/fupeggy/NL2SQL/app/ontology/data/mapping_prod.json') as f:
    tmpl = json.load(f)['metric_definitions']['first_pass_yield']['sql_template']

for q, label in [(Q1, 'Q1'), (Q2, 'Q2')]:
    ctx = {'metrics': [{'metric_id': 'first_pass_yield', 'sql_template': tmpl}]}
    qp  = {'time_range': 'last_7_days'}
    sql = _apply_metric_sql_template(ctx, qp, q)
    conds = [l.strip() for l in sql.split('\n') if l.strip().startswith('AND') and 'process' in l.lower()]
    print(f"{label} process_code/name conditions: {conds}")
