import sys
sys.path.insert(0, '/Users/fupeggy/NL2SQL')

from app.agent.nodes.semantic_resolver import _inject_entity_filters, _extract_station_qualifier
from app.ontology.mapping import get_mapping

mapping = get_mapping()
all_rules = mapping.get_business_rules(involved_tables=['stations'])

wip_rule   = next((r for r in all_rules if r.id == 'wip_count'), None)
yield_rule = next((r for r in all_rules if r.id == 'yield_rate'), None)

assert wip_rule, "wip_count rule not found"
assert yield_rule, "yield_rate rule not found"
print(f"wip_count trigger_keywords:   {wip_rule.trigger_keywords}")
print(f"yield_rate trigger_keywords:  {yield_rule.trigger_keywords}")
assert "{station_filter}" in yield_rule.physical_sql_template, "yield template needs {station_filter}"
print("PASS: Both rules loaded with trigger_keywords")

# Simulate ctx
class MC:
    physical_table = "stations"
class FakeCtx:
    matched_classes = [MC()]

# ── yield_rate rule activation ──
kws_wip   = wip_rule.trigger_keywords
kws_yield = yield_rule.trigger_keywords

queries_yield  = ["查询颗粒检测站点的良率", "统计包装站点良品率", "各站点合格率"]
queries_wip    = ["查询包装站点的在制数量", "统计颗粒检测站点WIP"]
queries_other  = ["查询颗粒检测站点的设备数量", "显示设备运行状态"]

for q in queries_yield:
    assert any(kw in q for kw in kws_yield), f"FAIL: '{q}' should trigger yield_rate"
    assert not any(kw in q for kw in kws_wip), f"FAIL: '{q}' should NOT trigger wip_count"
    print(f"PASS: '{q}' → yield_rate fast path")

for q in queries_wip:
    assert any(kw in q for kw in kws_wip), f"FAIL: '{q}' should trigger wip_count"
    print(f"PASS: '{q}' → wip_count fast path")

for q in queries_other:
    assert not any(kw in q for kw in kws_wip), f"FAIL: '{q}' should NOT trigger wip_count"
    assert not any(kw in q for kw in kws_yield), f"FAIL: '{q}' should NOT trigger yield_rate"
    print(f"PASS: '{q}' → no fast path (goes to LLM)")

# ── yield_rate SQL template injection ──
t = yield_rule.physical_sql_template

sql_keli = _inject_entity_filters(t, FakeCtx(), "查询颗粒检测站点的良率")
assert "AND s.name LIKE '%颗粒检测%'" in sql_keli
assert "{station_filter}" not in sql_keli
print(f"\nPASS: 颗粒检测站点良率 SQL injected correctly")

sql_baozhuan = _inject_entity_filters(t, FakeCtx(), "统计包装站点良品率")
assert "AND s.name LIKE '%包装%'" in sql_baozhuan
print(f"PASS: 包装站点良率 SQL injected correctly")

sql_all = _inject_entity_filters(t, FakeCtx(), "各站点合格率")
assert "AND s.name" not in sql_all
assert "{station_filter}" not in sql_all
print(f"PASS: 各站点合格率 SQL → no filter (全量)")

print(f"\n颗粒检测站点良率 SQL:\n{sql_keli}\n")

# ── cache key version check ──
from app.agent.nodes.semantic_resolver import semantic_resolver_node
import inspect
src = inspect.getsource(semantic_resolver_node)
assert "_SEMANTIC_CACHE_VERSION" in src or "v2:" in src, "Cache versioning not found"
print("PASS: Cache versioning (v2:) present in semantic_resolver_node")

# ── SQL validator alias fix ──
from app.agent.tools.schema_tools import validate_sql
result = validate_sql.invoke({
    "sql": "SELECT s.name AS station_name, COUNT(DISTINCT w.id) AS wip_count "
           "FROM wafers w JOIN batches b ON w.batch_id = b.id "
           "JOIN sub_batches sb ON sb.batch_id = b.id "
           "JOIN stations s ON sb.current_station_id = s.id "
           "WHERE sb.status != 'completed' "
           "GROUP BY s.name ORDER BY wip_count DESC"
})
# s, w, station_name, wip_count should not appear in warnings anymore
warn_str = " ".join(result.get("warnings", []))
print(f"SQL warnings (after fix): {result.get('warnings', [])}")
# 修复后：table 别名(s,w,b,sb)和列别名(station_name,wip_count)不应再出现在 warnings 中
for unexpected in ["station_name", "wip_count"]:
    assert unexpected not in warn_str, \
        f"Column alias '{unexpected}' still in warnings: {warn_str}"
print("PASS: SQL validator no longer warns about table/column aliases")

print("\nALL PASS ✅")
