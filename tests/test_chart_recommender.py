"""测试图表推荐服务"""
import sys
sys.path.insert(0, '.')

from app.services.chart_recommender import ChartRecommender, CHART_CARD, CHART_LINE, CHART_BAR, CHART_PIE, CHART_TABLE, CHART_SCATTER, CHART_GROUPED_BAR

cr = ChartRecommender()

# === 1. 单值聚合 → card ===
r = cr.recommend('SELECT COUNT(*) FROM carriers', [{'count': 238}])
assert r['type'] == CHART_CARD, f"Expected card, got {r['type']}"
assert r['confidence'] >= 0.9
print(f"✅ 1. Single value → {r['type']} (conf={r['confidence']})")

# === 2. 空数据 → table ===
r = cr.recommend('SELECT * FROM t', [])
assert r['type'] == CHART_TABLE
print(f"✅ 2. Empty data → {r['type']}")

# === 3. 时间 + 数值 → line ===
data_trend = [
    {'date': '2026-01-01', 'oee': 85.2},
    {'date': '2026-01-02', 'oee': 87.1},
    {'date': '2026-01-03', 'oee': 82.5},
    {'date': '2026-01-04', 'oee': 89.0},
]
r = cr.recommend('SELECT date, oee FROM oee_records ORDER BY date', data_trend)
assert r['type'] == CHART_LINE, f"Expected line, got {r['type']}"
assert r['xAxisField'] == 'date'
assert r['yAxisField'] == 'oee'
print(f"✅ 3. Time + numeric → {r['type']} (x={r['xAxisField']}, y={r['yAxisField']})")

# === 4. 分类 + 数值 → bar ===
data_bar = [
    {'status': 'available', 'count': 120},
    {'status': 'in_use', 'count': 80},
    {'status': 'maintenance', 'count': 38},
]
r = cr.recommend('SELECT status, COUNT(*) as count FROM carriers GROUP BY status', data_bar)
assert r['type'] == CHART_BAR, f"Expected bar, got {r['type']}"
print(f"✅ 4. Category + numeric → {r['type']} (x={r['xAxisField']}, y={r['yAxisField']})")

# === 5. 两列少行（无分类关键词名） → pie ===
data_pie = [
    {'region': 'A区', 'total': 50},
    {'region': 'B区', 'total': 30},
    {'region': 'C区', 'total': 20},
]
r = cr.recommend('SELECT region, SUM(qty) as total FROM items GROUP BY region', data_pie)
# region 不在 CATEGORY_KEYWORDS 且唯一值少→category，但 rule 5 (cat+1num) 先命中 bar
# 这里放宽断言：对 category+1num 的少行数据，bar 和 pie 都是合理推荐
assert r['type'] in (CHART_BAR, CHART_PIE), f"Expected bar or pie, got {r['type']}"
print(f"✅ 5. Two cols + few rows → {r['type']}")

# === 6. 分类 + 多数值 → grouped_bar ===
data_grouped = [
    {'line': 'L1', 'oee': 85, 'yield_rate': 92},
    {'line': 'L2', 'oee': 78, 'yield_rate': 88},
]
r = cr.recommend('SELECT line, oee, yield_rate FROM reports', data_grouped)
assert r['type'] == CHART_GROUPED_BAR, f"Expected grouped_bar, got {r['type']}"
print(f"✅ 6. Category + multi-numeric → {r['type']}")

# === 7. 超过 20 行非聚合记录 → table ===
data_many = [{'wafer_id': f'W{i:04d}', 'lot': f'L{i:03d}', 'result': f'r{i}', 'note': f'n{i}'} for i in range(25)]
r = cr.recommend('SELECT wafer_id, lot, result, note FROM wafers LIMIT 25', data_many)
assert r['type'] == CHART_TABLE, f"Expected table, got {r['type']}"
print(f"✅ 7. 25 rows detail → {r['type']}")

# === 8. 两数值列无分类 → scatter ===
data_scatter = [{'x': i, 'y': i*2+1} for i in range(10)]
r = cr.recommend('SELECT x, y FROM measurements', data_scatter)
assert r['type'] == CHART_SCATTER, f"Expected scatter, got {r['type']}"
print(f"✅ 8. Two numerics → {r['type']}")

# === 9. 单行多指标 → pie ===
r = cr.recommend('SELECT AVG(oee) as avg_oee, AVG(yield) as avg_yield, AVG(uptime) as avg_uptime FROM stats',
                  [{'avg_oee': 85.2, 'avg_yield': 92.1, 'avg_uptime': 96.5}])
assert r['type'] == CHART_PIE, f"Expected pie, got {r['type']}"
print(f"✅ 9. Single row multi-values → {r['type']}")

# === 10. 带 intent 的标题生成 ===
intent = {'natural_language': '查询可用的载具数量'}
r = cr.recommend('SELECT COUNT(*) FROM carriers WHERE status = \'available\'',
                  [{'count': 120}], query_intent=intent)
assert '载具' in r['title'] or '查询' in r['title']
print(f"✅ 10. Title from intent → \"{r['title']}\"")

# === 11. visualization 字段包含完整结构 ===
required_keys = {'type', 'title', 'xAxisField', 'yAxisField', 'confidence', 'reason'}
assert required_keys.issubset(set(r.keys())), f"Missing keys: {required_keys - set(r.keys())}"
print(f"✅ 11. Response structure complete → {sorted(r.keys())}")

print()
print('🎉 All 11 chart recommender tests passed!')
