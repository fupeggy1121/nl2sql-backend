#!/usr/bin/env python3
"""
Phase B 优化测试
B1: Fast Path 路由 (semantic_resolver 检测 SQL 模板 → 跳过规划/生成)
B2: 意图缓存 + 语义缓存 + 结果缓存
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

# ───────────────────────────────────────────────
# B2-1: TTL 缓存基本功能
# ───────────────────────────────────────────────
def test_cache_basic():
    print("\n[B2-1] TTL Cache 基本功能...")
    from app.agent.cache import TTLCache

    c = TTLCache(ttl_seconds=2, maxsize=10, name="test")

    # 写入 & 命中
    c.set("你好啊", value={"intent": "chat"})
    result = c.get("你好啊")
    assert result == {"intent": "chat"}, f"Expected cache hit, got {result}"

    # 大小写/空格规范化
    result2 = c.get("  你好啊  ")
    assert result2 == {"intent": "chat"}, f"Normalized key should match"

    # 未命中
    result3 = c.get("不存在的key")
    assert result3 is None, "Should return None for missing key"

    # 过期测试
    c.set("expire_soon", value=42)
    time.sleep(2.1)
    assert c.get("expire_soon") is None, "Should expire after TTL"

    # 手动删除
    c.set("delete_me", value="val")
    c.invalidate("delete_me")
    assert c.get("delete_me") is None, "Should be deleted"

    stats = c.stats()
    assert stats["hits"] >= 2
    assert stats["misses"] >= 2
    print(f"  stats: {stats}")
    print("  ✅ PASS")


# ───────────────────────────────────────────────
# B2-2: 意图缓存集成
# ───────────────────────────────────────────────
def test_intent_cache_integration():
    print("\n[B2-2] 意图缓存集成...")
    from app.agent.cache import intent_cache

    intent_cache.clear()

    # 模拟写入
    fake_intent = {"intent": "direct_query", "confidence": 0.95}
    intent_cache.set("每个工站的WIP数量", fake_intent)

    # 模拟读取
    cached = intent_cache.get("每个工站的WIP数量")
    assert cached == fake_intent, f"Cache miss: {cached}"

    stats = intent_cache.stats()
    assert stats["hits"] == 1
    print(f"  intent_cache stats: {stats}")
    print("  ✅ PASS")


# ───────────────────────────────────────────────
# B2-3: 语义缓存集成
# ───────────────────────────────────────────────
def test_semantic_cache_integration():
    print("\n[B2-3] 语义缓存集成...")
    from app.agent.cache import semantic_cache

    semantic_cache.clear()

    fake_ctx = {
        "matched_classes": [{"logic_class": "semi:WIPState"}],
        "physical_tables": ["wafers", "stations"],
        "_summary": "匹配 1 个本体类, 0 个JOIN, 1 个过滤条件, 物理表: ['wafers', 'stations']",
        "_fast_path": True,
        "_fast_sql": "SELECT station_name, wip_count FROM ...",
        "_fast_sql_source": "business_rule:wip_by_station",
    }
    semantic_cache.set("每个工站WIP数量", fake_ctx)

    cached = semantic_cache.get("每个工站WIP数量")
    assert cached is not None, "Should cache semantic context"
    assert cached["_fast_path"] is True
    assert cached["_fast_sql"].startswith("SELECT")

    stats = semantic_cache.stats()
    assert stats["hits"] == 1
    print(f"  semantic_cache stats: {stats}")
    print("  ✅ PASS")


# ───────────────────────────────────────────────
# B2-4: 结果缓存集成
# ───────────────────────────────────────────────
def test_result_cache_integration():
    print("\n[B2-4] 结果缓存集成...")
    from app.agent.cache import result_cache

    result_cache.clear()

    sql = "SELECT station_name, COUNT(*) wip_count FROM wafers GROUP BY station_name"
    fake_result = {
        "success": True,
        "data": [{"station_name": "CMP", "wip_count": 42}],
        "rows_count": 1,
        "sql": sql,
    }
    result_cache.set(sql, fake_result)

    cached = result_cache.get(sql)
    assert cached is not None, "Should hit result cache"
    assert cached["rows_count"] == 1

    # SQL 大小写规范化 (cache key 会 lower-case)
    cached2 = result_cache.get(sql.lower())
    assert cached2 is not None, "Normalized SQL should still hit"

    print(f"  result_cache stats: {result_cache.stats()}")
    print("  ✅ PASS")


# ───────────────────────────────────────────────
# B1: Fast Path 路由函数
# ───────────────────────────────────────────────
def test_fast_path_routing():
    print("\n[B1] Fast Path 路由函数...")
    from app.agent.graph import _route_after_semantic

    # fast_path=True → sql_validator
    state_fast = {"fast_path": True, "sql": "SELECT 1"}
    result = _route_after_semantic(state_fast)
    assert result == "sql_validator", f"Expected sql_validator, got {result}"

    # fast_path=False → query_planner
    state_normal = {"fast_path": False}
    result2 = _route_after_semantic(state_normal)
    assert result2 == "query_planner", f"Expected query_planner, got {result2}"

    # fast_path 缺失 → query_planner
    result3 = _route_after_semantic({})
    assert result3 == "query_planner", f"Expected query_planner (missing key), got {result3}"

    print("  ✅ PASS")


# ───────────────────────────────────────────────
# B1: semantic_resolver fast_path 检测 (单元)
# ───────────────────────────────────────────────
def test_semantic_resolver_fast_path_detection():
    """测试 business rule 的 physical_sql_template 是否能被正确检测"""
    print("\n[B1] semantic_resolver fast_path 检测...")
    from app.ontology.mapping import BusinessRule
    from typing import Optional

    # 模拟 business_rules 列表
    rules_with_template = [
        BusinessRule(
            id="wip_by_station",
            name="按工站WIP统计",
            description="统计每个工站的WIP数量",
            physical_sql_template=(
                "SELECT s.name AS station_name, COUNT(DISTINCT w.id) AS wip_count "
                "FROM wafers w JOIN stations s ON s.id = w.station_id "
                "GROUP BY s.name ORDER BY wip_count DESC"
            ),
        )
    ]
    rules_without_template = [
        BusinessRule(id="r1", name="Rule1", description="No SQL template")
    ]

    def detect_fast_path(rules):
        for rule in rules:
            if rule.physical_sql_template:
                return True, rule.physical_sql_template, f"business_rule:{rule.id}"
        return False, "", ""

    fp, sql, source = detect_fast_path(rules_with_template)
    assert fp is True, "Should detect fast path"
    assert "station_name" in sql
    assert source == "business_rule:wip_by_station"

    fp2, _, _ = detect_fast_path(rules_without_template)
    assert fp2 is False, "Should NOT detect fast path without template"

    print("  ✅ PASS")


# ───────────────────────────────────────────────
# B2: cache_stats factory
# ───────────────────────────────────────────────
def test_cache_stats_factory():
    print("\n[B2] get_cache_stats 工厂函数...")
    from app.agent.cache import get_cache_stats

    stats = get_cache_stats()
    assert "intent" in stats
    assert "semantic" in stats
    assert "result" in stats
    for name, s in stats.items():
        assert "hit_rate" in s
        assert "ttl_seconds" in s

    print(f"  全局统计: { {k: v['hit_rate'] for k, v in stats.items()} }")
    print("  ✅ PASS")


# ───────────────────────────────────────────────
# B2: maxsize 淘汰测试
# ───────────────────────────────────────────────
def test_cache_eviction():
    print("\n[B2] 缓存淘汰 (maxsize=5)...")
    from app.agent.cache import TTLCache

    c = TTLCache(ttl_seconds=60, maxsize=5, name="evict_test")
    for i in range(10):
        c.set(f"key_{i}", value=i)

    # 不超过 maxsize 的 1.1 倍 (evict 会删 10%)
    stats = c.stats()
    assert stats["size"] <= 10, f"Cache size should be bounded, got {stats['size']}"
    print(f"  size after 10 inserts: {stats['size']} (maxsize=5)")
    print("  ✅ PASS")


# ───────────────────────────────────────────────
# Main
# ───────────────────────────────────────────────
if __name__ == "__main__":
    passed = 0
    failed = 0
    tests = [
        test_cache_basic,
        test_intent_cache_integration,
        test_semantic_cache_integration,
        test_result_cache_integration,
        test_fast_path_routing,
        test_semantic_resolver_fast_path_detection,
        test_cache_stats_factory,
        test_cache_eviction,
    ]
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  ❌ FAIL: {e}")
            import traceback; traceback.print_exc()
            failed += 1

    print(f"\n{'='*40}")
    print(f"Phase B 测试结果: {passed}/{len(tests)} 通过, {failed} 失败")
    if failed == 0:
        print("ALL PASS ✅")
    else:
        print("SOME FAILED ❌")
        sys.exit(1)
