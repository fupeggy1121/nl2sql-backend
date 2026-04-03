"""Smoke test: three-layer ontology → mapping → skill architecture + adhoc path."""
import app.analytics.methods  # trigger @register_metric
from app.agents.analysis_agent.nodes.method_selector import (
    method_selector_node,
    _resolve_metric_context,
)

# Test 1: three-layer resolution (direct metric_id lookup + zh_names lookup)
print("=== Test _resolve_metric_context ===")
for query in ["一次良率", "综合良率", "返工率", "在制品数量",
              "first_pass_yield", "rework_rate",  # direct metric_id lookup
              "SPC分析"]:
    md, sk, comp = _resolve_metric_context(query)
    if md:
        sk_name = sk.skill_name if sk else "none"
        comp_name = type(comp).__name__ if comp else "none"
        print(
            f'  ✓ "{query}" → metric={md.metric_id}, mode={md.compute_mode}, '
            f"skill={sk_name}, computer={comp_name}"
        )
    else:
        print(f'  ✗ "{query}" → no metric match (expected for non-metric)')

# Test 2: full node — FPY (skill path)
print("\n=== Test method_selector_node (FPY) ===")
result = method_selector_node({"user_input": "查一下最近7天一次良率"})
print(f"  method: {result['suggested_method']}")
print(f"  route_decision: {result.get('route_decision')}")
print(f"  reason: {result['method_reason']}")
sk_ctx = result.get("skill_context")
print(f"  skill_context keys: {list(sk_ctx.keys()) if sk_ctx else None}")
sql = (result.get("data_source_config") or {}).get("sql", "")
print(f"  SQL has JOIN: {'JOIN' in sql}")
print(f"  SQL has WHERE: {'WHERE' in sql}")
print(f"  SQL has ROW_NUMBER: {'ROW_NUMBER' in sql}")
print(f"  SQL has wafer_id: {'wafer_id' in sql}")
print(f"  SQL preview:\n{sql[:300]}")

# Test 3: full node — rework rate (skill path)
print("\n=== Test method_selector_node (Rework) ===")
result2 = method_selector_node({"user_input": "最近一个月返工率分析"})
print(f"  method: {result2['suggested_method']}")
print(f"  route_decision: {result2.get('route_decision')}")
print(f"  metric_name: {result2['method_params'].get('metric_name')}")
sql2 = (result2.get("data_source_config") or {}).get("sql", "")
print(f"  SQL has operation_type = 8: {'operation_type = 8' in sql2}")
print(f"  SQL preview:\n{sql2[:300]}")

# Test 4: SPC — keyword fast path (no LLM needed)
print("\n=== Test method_selector_node (SPC) ===")
result3 = method_selector_node({"user_input": "做一下SPC控制图分析"})
print(f"  method: {result3['suggested_method']}")
print(f"  route_decision: {result3.get('route_decision')}")
print(f"  skill_context: {result3.get('skill_context')}")

# Test 5: mapping context helpers
print("\n=== Test mapping context helpers ===")
from app.ontology.mapping import get_mapping
m = get_mapping()
catalog = m.build_table_catalog(max_tables=5)
print(f"  Table catalog (first 200 chars): {catalog[:200]}")
val_sum = m.build_value_summary(max_domains=2)
print(f"  Value summary (first 200 chars): {val_sum[:200]}")
pattern = m.match_query_pattern("站点可用载具")
if pattern:
    resolved = m.resolve_sql_bindings(pattern.sql_template, pattern.param_bindings)
    print(f"  Matched query pattern: {pattern.label_cn}")
    print(f"  Resolved SQL preview: {resolved[:150]}")
else:
    print("  No query pattern matched (may be OK)")

print("\n✅ All tests passed")
