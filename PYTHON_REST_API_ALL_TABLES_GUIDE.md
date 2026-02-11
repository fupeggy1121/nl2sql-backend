# 通过 Python REST API 找到所有 Supabase 表的完整指南

## 📊 最新发现

通过组合使用 **Supabase REST API** 和 **直接 PostgreSQL 连接**，我们成功发现了数据库中的**所有 34 张表**：

### 对比总结

| 方案 | 表数量 | 行数 | 优点 | 缺点 |
|------|-------|------|------|------|
| **REST API** | 11 | 6,985 | 无需密码，安全 | 权限限制，发现不了所有表 |
| **PostgreSQL 直接连接** ⭐ | 34 | 20,322 | 完整数据库访问 | 需要密码，不够安全 |
| **组合方案** ⭐⭐ | 34+ | 完整 | 两者结合优势 | 需要谨慎管理凭证 |

---

## 🎯 三种方案详解

### 方案 1: 使用 Supabase REST API (当前实现)

```python
from app.services.supabase_client import SupabaseClient

client = SupabaseClient()

# 查询已知表
possible_tables = ['equipment', 'products', 'batches', ...]

for table_name in possible_tables:
    try:
        result = client.client.table(table_name).select('*', count='exact').limit(0).execute()
        row_count = result.count if hasattr(result, 'count') else 0
        print(f"{table_name}: {row_count} 行")
    except Exception:
        pass
```

**优点:**
- ✅ 无需数据库密码
- ✅ 可通过 Supabase 权限控制
- ✅ 安全性高

**缺点:**
- ❌ 只发现 11 张表
- ❌ 无法发现系统表
- ❌ 权限限制

---

### 方案 2: 直接 PostgreSQL 连接 (推荐)

```python
import psycopg2

# 从 .env 读取连接信息
db_config = {
    'host': os.getenv('SUPABASE_DB_HOST'),        # db.xxx.supabase.co
    'database': os.getenv('SUPABASE_DB_NAME'),    # postgres
    'user': os.getenv('SUPABASE_DB_USER'),        # postgres
    'password': os.getenv('SUPABASE_DB_PASSWORD'),# 你的数据库密码
    'port': 5432
}

# 连接数据库
conn = psycopg2.connect(**db_config)
cursor = conn.cursor()

# 查询所有表
query = """
SELECT 
    t.tablename,
    COALESCE(s.n_live_tup, 0) as row_count
FROM pg_catalog.pg_tables t
LEFT JOIN pg_stat_user_tables s ON t.tablename = s.relname
WHERE t.schemaname = 'public'
ORDER BY row_count DESC
"""

cursor.execute(query)
results = cursor.fetchall()

for tablename, row_count in results:
    print(f"{tablename}: {row_count:,} 行")

cursor.close()
conn.close()
```

**优点:**
- ✅ 访问所有 34 张表
- ✅ 完整的 SQL 查询能力
- ✅ 可获取系统信息

**缺点:**
- ❌ 需要数据库密码
- ❌ 安全性需谨慎管理
- ❌ 网络依赖

---

### 方案 3: 综合方案 (推荐使用)

结合两种方式的优势：

```python
#!/usr/bin/env python3
"""综合方案：REST API + PostgreSQL"""

from app.services.supabase_client import SupabaseClient
import psycopg2
import os

class SuperbaseTableDiscovery:
    def __init__(self):
        self.rest_client = SupabaseClient()
        self.pg_config = {
            'host': os.getenv('SUPABASE_DB_HOST'),
            'database': os.getenv('SUPABASE_DB_NAME'),
            'user': os.getenv('SUPABASE_DB_USER'),
            'password': os.getenv('SUPABASE_DB_PASSWORD'),
            'port': 5432
        }
    
    def get_rest_api_tables(self):
        """通过 REST API 获取表"""
        tables = []
        # ... 实现代码 ...
        return tables
    
    def get_postgres_tables(self):
        """通过 PostgreSQL 获取所有表"""
        conn = psycopg2.connect(**self.pg_config)
        cursor = conn.cursor()
        
        query = """
        SELECT tablename, COALESCE(n_live_tup, 0) as row_count
        FROM pg_catalog.pg_tables t
        LEFT JOIN pg_stat_user_tables s ON t.tablename = s.relname
        WHERE t.schemaname = 'public'
        ORDER BY row_count DESC
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return results
    
    def get_all_tables(self):
        """获取所有表 (优先使用 PostgreSQL)"""
        try:
            return self.get_postgres_tables()
        except Exception as e:
            print(f"PostgreSQL 失败，降级使用 REST API: {e}")
            return self.get_rest_api_tables()
```

---

## 📦 当前状态

### 已发现的完整表列表 (34 张表，355 列)

#### 大数据表 (>1000 行)
| 表名 | 行数 | 用途 |
|------|------|------|
| **wafer_inspection_results** | 7,113 | 晶圆检测结果 |
| **quality_records** | 6,200 | 质量检测记录 |
| **wafers** | 2,180 | 晶圆信息 |
| **wafer_carrier_contents** | 2,180 | 晶圆籍子内容 |
| **production_events** | 930 | 生产事件 |

#### 中等数据表 (100-1000 行)
- oee_records (465)
- chat_messages (329)
- carriers (276)
- parameter_group_parameters (120)
- sub_batches (102)
- parameters (89)
- stations (64)
- process_route_stations (60)
- parameter_groups (55)
- process_routes (43)

#### 小数据表 (<100 行)
- products (31)
- batches (20)
- parameter_equipment (18)
- product_boms (12)
- chat_sessions (8)
- production_orders (6)
- schema_column_annotations (5)
- equipment (5)
- custom_process_rules (5)
- equipment_groups (3)
- schema_table_annotations (2)
- feedback (1)

#### 空表 (0 行)
- sub_batch_process_log
- intent_feedback
- schema_relation_annotations
- query_result_feedback
- annotation_audit_log
- saved_reports
- batch_remarks

---

## 🚀 快速开始

### 安装依赖

```bash
pip install psycopg2-binary
```

### 运行工具

```bash
# 使用综合工具 (推荐)
python find_all_tables_comprehensive.py

# 或手动运行 PostgreSQL 查询
python3 << 'EOF'
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('SUPABASE_DB_HOST'),
    database=os.getenv('SUPABASE_DB_NAME'),
    user=os.getenv('SUPABASE_DB_USER'),
    password=os.getenv('SUPABASE_DB_PASSWORD'),
    port=5432
)
cursor = conn.cursor()
cursor.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public' ORDER BY tablename")
for row in cursor.fetchall():
    print(row[0])
cursor.close()
conn.close()
EOF
```

---

## 📋 文件清单

| 文件 | 说明 |
|------|------|
| `find_all_tables_comprehensive.py` | 主要工具脚本 - 实现三种方案 |
| `database_complete_tables_list.json` | 完整表列表 JSON 格式 |
| `SUPABASE_ALL_34_TABLES_GUIDE.md` | SQL 查询指南 |

---

## ⚠️ 安全建议

1. **不要在代码中硬编码密码**
   ```python
   # ❌ 不好
   password = "fyhxxy1121616"
   
   # ✅ 好
   password = os.getenv('SUPABASE_DB_PASSWORD')
   ```

2. **限制 PostgreSQL 连接范围**
   - 只在必要时连接
   - 连接后立即断开
   - 使用连接池管理

3. **分离 REST API 和数据库凭证**
   - REST API: 使用 SUPABASE_ANON_KEY (无需密码)
   - PostgreSQL: 仅在后端服务器中使用

4. **监控和日志**
   ```python
   import logging
   logging.basicConfig(level=logging.INFO)
   logger = logging.getLogger(__name__)
   
   logger.info(f"连接到数据库 {db_config['host']}")
   logger.info(f"找到 {len(results)} 张表")
   ```

---

## 📝 常见问题

### Q: 为什么 REST API 只能发现 11 张表?

A: Supabase 通过 PostgREST 自动生成 REST API，并应用了行级安全策略 (RLS)。某些内部表或系统表被隐藏。

### Q: 是否可以通过 REST API 访问所有 34 张表?

A: 可以，但需要在 Supabase 中配置 RLS 策略。默认情况下，REST API 只暴露已授权的表。

### Q: PostgreSQL 连接的性能如何?

A: 非常好，直接连接比 REST API 快 10-100 倍。推荐用于数据分析和大批量操作。

### Q: 如何在生产环境中使用?

A: 
1. 使用环境变量管理凭证
2. 使用连接池 (e.g., pgBouncer)
3. 限制连接数量
4. 添加连接超时
5. 监控和告警

---

## 🎓 总结

| 场景 | 推荐方案 |
|------|---------|
| 前端应用 | REST API + ANON_KEY |
| 数据分析 | PostgreSQL 直接连接 |
| 后端服务 | 组合方案 (REST API + PostgreSQL) |
| 系统管理 | SQL 编辑器或 psql CLI |
| 学习探索 | 此综合工具 |

---

希望这个完整指南对你有帮助！🚀
