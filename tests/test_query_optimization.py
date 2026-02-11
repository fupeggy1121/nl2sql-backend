"""测试复杂SQL查询优化的所有新功能"""
import sys
sys.path.insert(0, '.')

from app.services.supabase_client import SupabaseClient
from app.services.query_cache import QueryCache

sc = SupabaseClient()

# === 1. SQL 复杂度分类 ===
assert sc.classify_sql_complexity('SELECT * FROM carriers') == 'simple'
assert sc.classify_sql_complexity("SELECT COUNT(*) FROM carriers WHERE status = 'available'") == 'aggregate'
assert sc.classify_sql_complexity('SELECT a.*, b.name FROM carriers a JOIN users b ON a.user_id=b.id') == 'complex'
assert sc.classify_sql_complexity('WITH cte AS (SELECT * FROM t) SELECT * FROM cte') == 'complex'
assert sc.classify_sql_complexity('SELECT SUM(qty), type FROM items GROUP BY type') == 'aggregate'
assert sc.classify_sql_complexity('SELECT ROW_NUMBER() OVER (PARTITION BY type ORDER BY id) FROM t') == 'complex'
print('✅ 1. SQL complexity classifier OK')

# === 2. WHERE 解析 — 基础操作符 ===
conds = sc._parse_where_conditions("SELECT * FROM t WHERE status = 'active' AND age > 18 AND name LIKE '%test%'")
assert len(conds) == 3
ops = {c['column']: c['op'] for c in conds}
assert ops['status'] == 'eq'
assert ops['age'] == 'gt'
assert ops['name'] == 'like'
print('✅ 2. WHERE parsing (basic operators) OK')

# === 3. WHERE 解析 — IN / IS NULL ===
conds2 = sc._parse_where_conditions("SELECT * FROM t WHERE id IN (1,2,3) AND deleted_at IS NULL")
ops2 = {c['column']: c['op'] for c in conds2}
assert ops2['id'] == 'in'
assert ops2['deleted_at'] == 'is_null'
print('✅ 3. WHERE parsing (IN / IS NULL) OK')

# === 4. WHERE 解析 — BETWEEN ===
conds3 = sc._parse_where_conditions("SELECT * FROM t WHERE price BETWEEN 10 AND 100")
assert len(conds3) == 1
assert conds3[0]['op'] == 'between'
assert conds3[0]['value'] == [10, 100]
print('✅ 4. WHERE parsing (BETWEEN) OK')

# === 5. WHERE 解析 — !=, <>, >=, <=, IS NOT NULL, ILIKE, NOT LIKE ===
conds4 = sc._parse_where_conditions("SELECT * FROM t WHERE a != 5 AND b >= 10 AND c IS NOT NULL")
ops4 = {c['column']: c['op'] for c in conds4}
assert ops4['a'] == 'neq'
assert ops4['b'] == 'gte'
assert ops4['c'] == 'is_not_null'
print('✅ 5. WHERE parsing (!=, >=, IS NOT NULL) OK')

# === 6. 解析辅助函数 ===
assert sc._parse_offset('SELECT * FROM t LIMIT 10 OFFSET 20') == 20
assert sc._parse_offset('SELECT * FROM t LIMIT 10') is None

orders = sc._parse_order_by_multi('SELECT * FROM t ORDER BY name ASC, age DESC LIMIT 10')
assert len(orders) == 2
assert orders[0] == {'column': 'name', 'desc': False}
assert orders[1] == {'column': 'age', 'desc': True}

gb = sc._parse_group_by('SELECT type, COUNT(*) FROM t GROUP BY type ORDER BY type')
assert gb == ['type']

assert sc._parse_limit('SELECT * FROM t LIMIT 50') == 50
print('✅ 6. Parse helpers (OFFSET / ORDER BY multi / GROUP BY / LIMIT) OK')

# === 7. SELECT 列解析 ===
cols = sc._parse_select_columns('SELECT DISTINCT name, type FROM carriers')
assert 'name' in cols
cols2 = sc._parse_select_columns('SELECT t.id, t.name FROM carriers t')
assert 'id' in cols2
print('✅ 7. SELECT columns parsing (DISTINCT, table prefix) OK')

# === 8. 客户端去重 ===
data = [{'a': 1, 'b': 2}, {'a': 1, 'b': 2}, {'a': 3, 'b': 4}]
deduped = SupabaseClient._client_distinct(data)
assert len(deduped) == 2
print('✅ 8. Client-side DISTINCT OK')

# === 9. 聚合查询检测 ===
agg1 = sc._detect_aggregate_query("SELECT COUNT(*) FROM carriers WHERE status = 'active'")
assert agg1 is not None
assert agg1['function'] == 'count'

agg2 = sc._detect_aggregate_query("SELECT type, COUNT(*), AVG(weight) FROM items GROUP BY type")
assert agg2 is not None
assert agg2.get('multi') is True
assert len(agg2['aggregates']) == 2
assert agg2['group_by'] == ['type']

agg3 = sc._detect_aggregate_query("SELECT * FROM carriers")
assert agg3 is None
print('✅ 9. Aggregate detection (single / multi / GROUP BY) OK')

# === 10. 查询缓存 ===
cache = QueryCache(max_size=10, default_ttl=60)
cache.set('SELECT 1', {'success': True, 'data': [1]})
assert cache.get('SELECT 1') == {'success': True, 'data': [1]}
assert cache.get('SELECT 2') is None
stats = cache.get_stats()
assert stats['hits'] == 1
assert stats['misses'] == 1

# SQL 指纹测试 — 带和不带多余空格的查询应该命中同一缓存
cache.set('SELECT * FROM  carriers  WHERE  id = 1', {'success': True, 'data': 'x'})
assert cache.get('SELECT *  FROM carriers WHERE id = 1') == {'success': True, 'data': 'x'}

cache.invalidate(table_name='carriers')
assert cache.get('SELECT 1') is not None  # 'carriers' 不在这个 SQL 里，不应被清除
assert cache.get('SELECT * FROM  carriers  WHERE  id = 1') is None  # 含 carriers 的应被清除
print('✅ 10. Query cache (set/get/stats/invalidate) OK')

# === 11. _cast_value 辅助 ===
assert SupabaseClient._cast_value('42') == 42
assert SupabaseClient._cast_value('3.14') == 3.14
assert SupabaseClient._cast_value('hello') == 'hello'
print('✅ 11. _cast_value helper OK')

print()
print('🎉 All 11 test groups passed!')
