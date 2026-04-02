"""Test yield SQL builder and station filter fixes."""
from app.agents.analysis_agent.nodes.method_selector import _extract_station_filter, _build_yield_sql

print("=== Station Extraction Tests ===")
tests = [
    ("查看CMP工站综合良率", "ci"),
    ("POL抛光工站一次良率", "ci"),
    ("想看这周各工站良率趋势", "ci"),
    ("所有工站良率", "ci"),
    ("分析CVD沉积工站良率", "ci"),
]
for q, alias in tests:
    s = _extract_station_filter(q, alias)
    result = s.strip() if s.strip() else "(no filter)"
    print(f"  {repr(q)} => {repr(result)}")

print()
print("=== Yield SQL Builder Tests ===")

r3 = _build_yield_sql("想看这周各工站良率趋势")
print("Q3 first_line:", r3["sql"].split("\n")[0])
has_station = any("process_code" in l for l in r3["sql"].split("\n") if l.strip().startswith("AND"))
print("Q3 has station filter:", has_station)

r4 = _build_yield_sql("POL抛光工站最近7天一次良率趋势")
andlines = [l.strip() for l in r4["sql"].split("\n") if l.strip().startswith("AND")]
print("Q4 AND conditions:")
for c in andlines:
    print("  ", c)

r5 = _build_yield_sql("查看CMP工站综合良率")
andlines5 = [l.strip() for l in r5["sql"].split("\n") if l.strip().startswith("AND")]
print("Q5 AND conditions:")
for c in andlines5:
    print("  ", c)

print("\nAll tests complete.")
