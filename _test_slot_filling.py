"""
Smoke test: Slot Filling upgrade validation
验证意图槽 → context_builder 定向匹配路径
"""
import sys
sys.path.insert(0, "/Users/fupeggy/NL2SQL")

from app.models.intent_slots import IntentSlots
from app.ontology.context_builder import build_semantic_context

print("=== 测试1: 统计各仓库的库存分布 ===")
slots = IntentSlots(
    subject="库存",
    action="统计聚合",
    dimension_by="仓库",
    metric="库存数量",
)
ctx = build_semantic_context("统计各仓库的库存分布", intent_slots=slots)
print("  matched_classes:", [m.logic_class for m in ctx.matched_classes])
print("  physical_tables:", ctx.physical_tables)
assert len(ctx.matched_classes) > 0, "FAIL: 0 matched classes!"
print("  PASS")

print()
print("=== 测试2: 统计入库数量排名Top3的物料 ===")
slots2 = IntentSlots(
    subject="入库记录",
    action="统计聚合",
    dimension_by="物料",
    metric="入库数量",
    sort_order="DESC",
    limit_n=3,
)
ctx2 = build_semantic_context("统计入库数量排名Top3的物料", intent_slots=slots2)
print("  matched_classes:", [m.logic_class for m in ctx2.matched_classes])
print("  physical_tables:", ctx2.physical_tables)
assert len(ctx2.matched_classes) > 0, "FAIL: 0 matched classes!"
assert "semi:InboundEventRecord" in [m.logic_class for m in ctx2.matched_classes], \
    "FAIL: InboundEventRecord not matched!"
print("  PASS")

print()
print("=== 测试3: No slots (baseline) ===")
ctx3 = build_semantic_context("查询片篮列表", intent_slots=None)
print("  matched_classes:", [m.logic_class for m in ctx3.matched_classes])
print("  physical_tables:", ctx3.physical_tables)
assert len(ctx3.matched_classes) > 0, "FAIL: 0 matched classes!"
print("  PASS")

print()
print("=== 测试4: IntentSlots helpers ===")
s = IntentSlots(action="统计聚合", dimension_by="物料", metric="数量", limit_n=5)
assert s.is_aggregate(), "FAIL: should be aggregate"
assert s.has_ranking(), "FAIL: should have ranking"
d = s.to_dict()
s2 = IntentSlots.from_dict(d)
assert s2.limit_n == 5
print("  PASS")

print()
print("ALL TESTS PASSED")
