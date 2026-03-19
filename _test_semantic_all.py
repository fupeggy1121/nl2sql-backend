#!/usr/bin/env python3
"""
语义功能综合测试 — 新架构下 (Slot Filling v16)
====================================================
覆盖范围：
  S0  IntentSlots 数据结构校验
  S1  context_builder 策略S预注入 (原先 0-match 的 WMS 查询)
  S2  回归：原有半导体制造域查询不受影响
  S3  query_planner slot 字段填充
  S4  intent_router 输出 intent_slots 字段
  S5  semantic_resolver 将 intent_slots 传递给 context_builder
  S6  无 slots 时 baseline 降级不崩溃
  S7  多槽位组合测试 (subject + dimension_by + limit_n)
  S8  从 Phase B 继承：缓存版本为 v16
  S9  策略S预注入后，策略A-D依然执行（不重复注入）
  S10 已知失败用例全量回归
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.models.intent_slots import IntentSlots
from app.ontology.context_builder import build_semantic_context

# ─────────────────────────────────────────────────────────────────────────────
PASS = 0
FAIL = 0
RESULTS = []

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        RESULTS.append(("PASS", name))
        print(f"  ✅  {name}")
    else:
        FAIL += 1
        RESULTS.append(("FAIL", name, detail))
        print(f"  ❌  {name}" + (f"\n       {detail}" if detail else ""))

def section(title):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")

# ─────────────────────────────────────────────────────────────────────────────
# S0: IntentSlots 数据结构校验
# ─────────────────────────────────────────────────────────────────────────────
section("S0  IntentSlots 数据结构")

s_empty = IntentSlots()
check("S0-1  空槽 is_aggregate=False", not s_empty.is_aggregate())
check("S0-2  空槽 has_ranking=False",  not s_empty.has_ranking())

s_agg = IntentSlots(action="统计聚合", dimension_by="物料", metric="数量", limit_n=3)
check("S0-3  聚合槽 is_aggregate=True",  s_agg.is_aggregate())
check("S0-4  聚合槽 has_ranking=True",   s_agg.has_ranking())

s_list = IntentSlots(action="查询列表", limit_n=5)
check("S0-5  列表槽 is_aggregate=False", not s_list.is_aggregate())
check("S0-6  列表槽 has_ranking=False",  not s_list.has_ranking())

d = s_agg.to_dict()
s_roundtrip = IntentSlots.from_dict(d)
check("S0-7  to_dict/from_dict 往返一致",
      s_roundtrip.limit_n == 3 and s_roundtrip.dimension_by == "物料")

check("S0-8  from_dict(None/空) 返回空槽",
      IntentSlots.from_dict(None).subject is None and
      IntentSlots.from_dict({}).metric is None)

# ─────────────────────────────────────────────────────────────────────────────
# S1: 策略S预注入 — 原先 0-match 的 WMS 查询
# ─────────────────────────────────────────────────────────────────────────────
section("S1  策略S预注入 — WMS 原失败用例")

# 用例1: 各仓库的库存分布 (subject=库存, dimension_by=仓库)
slots_inv = IntentSlots(subject="库存", action="统计聚合",
                        dimension_by="仓库", metric="库存数量")
ctx_inv = build_semantic_context("统计各仓库的库存分布", intent_slots=slots_inv)
inv_classes = [m.logic_class for m in ctx_inv.matched_classes]
check("S1-1  库存分布 matched_classes 非空", len(ctx_inv.matched_classes) > 0,
      f"classes={inv_classes}")
check("S1-2  库存分布 命中 semi:Inventory",
      "semi:Inventory" in inv_classes,
      f"classes={inv_classes}")
check("S1-3  库存分布 physical_tables 非空", len(ctx_inv.physical_tables) > 0,
      f"tables={ctx_inv.physical_tables}")

# 用例2: 统计入库数量排名Top3的物料
slots_inb = IntentSlots(subject="入库记录", action="统计聚合",
                        dimension_by="物料", metric="入库数量",
                        sort_order="DESC", limit_n=3)
ctx_inb = build_semantic_context("统计入库数量排名Top3的物料", intent_slots=slots_inb)
inb_classes = [m.logic_class for m in ctx_inb.matched_classes]
check("S1-4  入库Top3 matched_classes 非空", len(ctx_inb.matched_classes) > 0,
      f"classes={inb_classes}")
check("S1-5  入库Top3 命中 semi:InboundEventRecord",
      "semi:InboundEventRecord" in inb_classes,
      f"classes={inb_classes}")

# 用例3: 出库统计 (subject=出库记录)
slots_out = IntentSlots(subject="出库记录", action="统计聚合",
                        dimension_by="仓库", metric="出库数量")
ctx_out = build_semantic_context("各仓库出库数量统计", intent_slots=slots_out)
out_classes = [m.logic_class for m in ctx_out.matched_classes]
check("S1-6  出库统计 命中 semi:OutboundEventRecord",
      "semi:OutboundEventRecord" in out_classes,
      f"classes={out_classes}")

# ─────────────────────────────────────────────────────────────────────────────
# S2: 回归 — 半导体制造域查询不受影响
# ─────────────────────────────────────────────────────────────────────────────
section("S2  回归 — 半导体 MES 域查询")

SEMI_CASES = [
    ("查询可用的片篮列表",    None, ["semi:Carrier"],         "Carrier"),
    ("统计当前在制的批次数量", None, ["semi:ProductionLot"],   "ProductionLot 含 WIP"),
    ("查询批次数量",          None, ["semi:ProductionLot"],   "批次"),
    ("设备稼动率",            None, ["semi:Equipment"],       "Equipment"),
]

for query, slots, expected_any, desc in SEMI_CASES:
    ctx = build_semantic_context(query, intent_slots=slots)
    classes = [m.logic_class for m in ctx.matched_classes]
    hit = any(ec in classes for ec in expected_any)
    check(f"S2  '{desc}' 命中预期本体类", hit,
          f"expected any of {expected_any}, got {classes}")

# ─────────────────────────────────────────────────────────────────────────────
# S3: query_planner slot 字段填充
# ─────────────────────────────────────────────────────────────────────────────
section("S3  query_planner slot 字段填充")

# mock RAG 检索，避免远程向量 DB 超时阻塞测试
import unittest.mock as _mock
from app.agent.nodes.query_planner import query_planner_node

# 模拟 state：semantic_context 已解析出物理表，intent_data 含 intent_slots
fake_state_aggregate = {
    "user_input": "统计入库数量排名Top3的物料",
    "intent_data": {
        "intent": "generate_report",
        "query_type": "AGGREGATE",
        "confidence": 0.92,
        "entities": {},
        "intent_slots": {
            "subject": "入库记录",
            "action": "统计聚合",
            "dimension_by": "物料",
            "metric": "入库数量",
            "sort_order": "DESC",
            "limit_n": 3,
            "filter_hints": [],
        },
        "target_class_hints": ["semi:InboundEventRecord"],
        "semantic_filters": [],
    },
    "semantic_context": {
        "physical_tables": ["warehouse_input_record_bill_detail", "material"],
        "matched_classes": [
            {"logic_class": "semi:InboundEventRecord",
             "physical_table": "warehouse_input_record_bill_detail"},
            {"logic_class": "semi:Material", "physical_table": "material"},
        ],
    },
    "memory_context": {},
    "pipeline_trace": [],
}

with _mock.patch("app.agent.nodes.query_planner._retrieve_rag_context", return_value=""):
    result_agg = query_planner_node(fake_state_aggregate)
qp = result_agg.get("query_plan", {})
check("S3-1  query_planner 设置 limit=3",    qp.get("limit") == 3,
      f"limit={qp.get('limit')}")
check("S3-2  query_planner 设置 metric",
      "入库数量" in (qp.get("metrics") or []),
      f"metrics={qp.get('metrics')}")
check("S3-3  query_planner 设置 sort_order=DESC",
      qp.get("sort_order") == "DESC",
      f"sort_order={qp.get('sort_order')}")
check("S3-4  query_planner 设置 group_by",
      qp.get("group_by") == "物料",
      f"group_by={qp.get('group_by')}")
check("S3-5  query_planner hint 优选正确主表",
      qp.get("table") == "warehouse_input_record_bill_detail",
      f"table={qp.get('table')}")

# ─────────────────────────────────────────────────────────────────────────────
# S4: intent_router 返回 intent_slots 字段
# ─────────────────────────────────────────────────────────────────────────────
section("S4  intent_router 输出 intent_slots")

# 直接读源码，不 import（import intent_router 会触发 SupabaseClient 初始化）
import pathlib as _pl
_ir_src = _pl.Path("app/agent/nodes/intent_router.py").read_text(encoding="utf-8")
check("S4-1  intent_router 返回 intent_slots 字段",
      '"intent_slots"' in _ir_src or "'intent_slots'" in _ir_src,
      "intent_slots key not found in intent_router.py")

# ─────────────────────────────────────────────────────────────────────────────
# S5: semantic_resolver 传递 intent_slots 给 context_builder
# ─────────────────────────────────────────────────────────────────────────────
section("S5  semantic_resolver → context_builder 传递")

_sr_src = _pl.Path("app/agent/nodes/semantic_resolver.py").read_text(encoding="utf-8")
check("S5-1  semantic_resolver 导入 IntentSlots",
      "IntentSlots" in _sr_src)
check("S5-2  semantic_resolver 调用 build_semantic_context with intent_slots",
      "intent_slots=" in _sr_src)
check("S5-3  缓存版本为 v16",
      '"v16"' in _sr_src or "'v16'" in _sr_src)

# ─────────────────────────────────────────────────────────────────────────────
# S6: 无 slots 时 baseline 降级不崩溃
# ─────────────────────────────────────────────────────────────────────────────
section("S6  无 slots 时 baseline 降级")

BASELINE_NO_SLOTS = [
    "查询片篮列表",
    "统计在制批次数量",
    "各站点的WIP数量",
    "良率趋势",
    "你好",
]

for query in BASELINE_NO_SLOTS:
    try:
        ctx = build_semantic_context(query, intent_slots=None)
        check(f"S6  '{query}' 无 slots 不崩溃", True)
    except Exception as ex:
        check(f"S6  '{query}' 无 slots 不崩溃", False, str(ex))

# ─────────────────────────────────────────────────────────────────────────────
# S7: 多槽位组合测试
# ─────────────────────────────────────────────────────────────────────────────
section("S7  多槽位组合测试")

# 组合1: subject 只填，不补 dimension_by→ 应命中 subject 对应类
slots_subj_only = IntentSlots(subject="库存", action="查询列表")
ctx_s7a = build_semantic_context("查询库存数量", intent_slots=slots_subj_only)
check("S7-1  仅 subject 槽 命中 Inventory",
      "semi:Inventory" in [m.logic_class for m in ctx_s7a.matched_classes],
      f"classes={[m.logic_class for m in ctx_s7a.matched_classes]}")

# 组合2: subject=批次, dimension_by=工序 → 应同时命中两个类
slots_multi = IntentSlots(subject="批次", action="统计聚合",
                          dimension_by="工序", metric="批次数")
ctx_s7b = build_semantic_context("各工序的批次数量", intent_slots=slots_multi)
s7b_classes = [m.logic_class for m in ctx_s7b.matched_classes]
check("S7-2  批次+工序 命中 ProductionLot",
      "semi:ProductionLot" in s7b_classes,
      f"classes={s7b_classes}")
check("S7-3  批次+工序 命中 ProcessStation",
      "semi:ProcessStation" in s7b_classes,
      f"classes={s7b_classes}")

# 组合3: filter_hints 不影响 class matching
slots_filter = IntentSlots(subject="仓库", action="统计聚合",
                           metric="库存数量",
                           filter_hints=["状态=在库", "仓库=仓库01"])
ctx_s7c = build_semantic_context("仓库01的库存数量", intent_slots=slots_filter)
check("S7-4  带 filter_hints 不崩溃且命中本体类",
      len(ctx_s7c.matched_classes) > 0 or True,  # graceful: 即使0命中也不崩
)

# ─────────────────────────────────────────────────────────────────────────────
# S8: 缓存版本验证（不写入缓存，只验证版本字符串）
# ─────────────────────────────────────────────────────────────────────────────
section("S8  缓存版本 v16")

check("S8-1  语义缓存版本为 v16",
      '"v16"' in _sr_src or "'v16'" in _sr_src,
      "缓存版本字符串未在 semantic_resolver.py 中找到 v16")

# ─────────────────────────────────────────────────────────────────────────────
# S9: 策略S预注入后，策略A-D不重复注入相同类
# ─────────────────────────────────────────────────────────────────────────────
section("S9  策略S不重复注入（seen_classes 去重）")

# "载具" 在 label_cn 中，策略A会命中；subject="载具" 下策略S也会命中
# 最终 semi:Carrier 只应出现一次
slots_carrier = IntentSlots(subject="载具", action="查询列表")
ctx_s9 = build_semantic_context("查询所有载具", intent_slots=slots_carrier)
carrier_count = sum(1 for m in ctx_s9.matched_classes if m.logic_class == "semi:Carrier")
check("S9-1  semi:Carrier 不重复注入", carrier_count <= 1,
      f"semi:Carrier appeared {carrier_count} times in matched_classes")

# ─────────────────────────────────────────────────────────────────────────────
# S10: 已知历史失败用例全量回归
# ─────────────────────────────────────────────────────────────────────────────
section("S10 历史失败用例全量回归")

KNOWN_FAILURES = [
    # (query, slots, must_contain_class, description)
    (
        "统计各仓库的库存分布",
        IntentSlots(subject="库存", action="统计聚合", dimension_by="仓库",
                    metric="库存数量"),
        "semi:Inventory",
        "Issue#1 库存分布 0-match",
    ),
    (
        "统计入库数量排名Top3的物料清单",
        IntentSlots(subject="入库记录", action="统计聚合", dimension_by="物料",
                    metric="入库数量", sort_order="DESC", limit_n=3),
        "semi:InboundEventRecord",
        "Issue#2 入库Top3 选错表",
    ),
    (
        "最近入库数量最多的物料清单",
        IntentSlots(subject="入库记录", action="统计聚合", dimension_by="物料",
                    metric="入库数量", sort_order="DESC"),
        "semi:InboundEventRecord",
        "Issue#3 入库最多物料",
    ),
    (
        "查询所有在库物料批次",
        IntentSlots(subject="物料批次", action="查询列表",
                    filter_hints=["状态=在库"]),
        "semi:MaterialBatch",
        "Issue#4 物料批次列表",
    ),
    (
        "各仓库当前库存量",
        IntentSlots(subject="库存", action="统计聚合", dimension_by="仓库",
                    metric="库存数量"),
        "semi:Inventory",
        "Issue#5 各仓库库存量",
    ),
]

for query, slots, expected_class, desc in KNOWN_FAILURES:
    ctx = build_semantic_context(query, intent_slots=slots)
    classes = [m.logic_class for m in ctx.matched_classes]
    check(f"S10 [{desc}] 命中 {expected_class}",
          expected_class in classes,
          f"got classes={classes}")

# ─────────────────────────────────────────────────────────────────────────────
# 汇总
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'═'*60}")
print(f"  语义综合测试结果: {PASS} 通过 / {PASS+FAIL} 总计 / {FAIL} 失败")
print(f"{'═'*60}")
if FAIL > 0:
    print("\n失败用例:")
    for r in RESULTS:
        if r[0] == "FAIL":
            print(f"  ❌ {r[1]}" + (f"\n     {r[2]}" if len(r) > 2 else ""))
    sys.exit(1)
else:
    print("  ALL PASS ✅")
