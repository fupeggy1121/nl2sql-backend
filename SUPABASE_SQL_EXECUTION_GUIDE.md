# 🔐 Supabase SQL 执行完整指南

## 📚 概念理解

### Supabase 的三种连接方式

```
┌─────────────────────────────────────────────────────────────┐
│                    Supabase 连接方式                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ 1️⃣  PostgREST API (推荐用于前端/数据操作)                   │
│     • 使用: SUPABASE_URL + ANON_KEY                         │
│     • 权限: 受限 (RLS 策略控制)                             │
│     • 功能: 表查询、实时订阅                               │
│     • SDK: supabase-py (table().select())                  │
│                                                              │
│ 2️⃣  直接 PostgreSQL 连接 (用于管理操作)                    │
│     • 使用: psycopg2 或 psycopg3                           │
│     • 认证: 数据库用户名 + 密码                             │
│     • 权限: 完全访问                                        │
│     • 功能: 执行 SQL、数据库迁移                           │
│                                                              │
│ 3️⃣  Supabase API + SERVICE_ROLE_KEY (后端管理)           │
│     • 使用: SUPABASE_URL + SERVICE_ROLE_KEY               │
│     • 权限: 跳过 RLS 策略                                  │
│     • 功能: 管理操作、批量导入                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔑 密钥和密码获取位置

### 1. 在 Supabase 控制台获取 SERVICE_ROLE_KEY

```
1. 打开 https://supabase.com
2. 选择您的项目
3. 左侧菜单 → Settings → API
4. 在 "Project API keys" 中找到:
   - anon key: 用于前端
   - service_role key: 用于后端 ⭐
5. 复制 service_role key
```

### 2. 在 Supabase 控制台获取数据库连接信息

```
1. 左侧菜单 → Settings → Database
2. 在 "Connection info" 中查看:
   - Host: db.[project-id].supabase.co
   - Port: 5432
   - Database: postgres
   - User: postgres
   - Password: ⭐ 您创建项目时设置的主密码
```

**如果忘记了密码：**
```
1. Settings → Database
2. 点击 "Reset database password"
3. 输入新密码
4. 系统会生成一个新的随机密码（请保存）
```

### 3. 在 .env 文件中配置

```bash
# 后端管理密钥
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# 直接数据库连接信息
SUPABASE_DB_HOST=db.kgmyhukvyygudsllypgv.supabase.co
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=your_secure_password_here
```

---

## 🛠️ 后端直接执行 SQL 的方式

### 方式 1️⃣ : 使用 psycopg2（最推荐）

```python
import psycopg2

# 连接字符串格式
conn_string = (
    "postgresql://postgres:password@"
    "db.xxx.supabase.co:5432/postgres"
)

conn = psycopg2.connect(conn_string)
cursor = conn.cursor()

# 执行 SQL
cursor.execute("CREATE TABLE test (id SERIAL PRIMARY KEY)")
conn.commit()

cursor.close()
conn.close()
```

**优点：**
- ✅ 支持原生 SQL 执行
- ✅ 支持事务处理
- ✅ 性能最好
- ✅ 安装简单: `pip install psycopg2-binary`

**缺点：**
- ❌ 需要数据库密码
- ❌ 连接时需要网络到数据库

### 方式 2️⃣ : 使用 Supabase Python SDK + SERVICE_ROLE_KEY

```python
from supabase import create_client
import os

client = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_SERVICE_ROLE_KEY')  # ⭐ 注意是 SERVICE_ROLE_KEY
)

# 执行表操作
result = client.table('my_table').insert({
    'name': 'test',
    'value': 123
}).execute()
```

**优点：**
- ✅ 使用 SERVICE_ROLE_KEY（不需要数据库密码）
- ✅ 不需要直接访问数据库
- ✅ 支持 RLS 策略跳过

**缺点：**
- ❌ 不能直接执行原生 SQL
- ❌ 只能通过 PostgREST API（表级操作）

### 方式 3️⃣ : 使用 psycopg3（现代异步）

```python
import asyncio
import psycopg

async def execute_sql():
    async with await psycopg.AsyncConnection.connect(
        "postgresql://postgres:password@db.xxx.supabase.co:5432/postgres"
    ) as conn:
        async with conn.cursor() as cur:
            await cur.execute("CREATE TABLE test (id SERIAL PRIMARY KEY)")
            await conn.commit()

asyncio.run(execute_sql())
```

**优点：**
- ✅ 现代异步 API
- ✅ 支持原生 SQL
- ✅ 高效并发

**缺点：**
- ❌ 需要数据库密码
- ❌ 学习曲线较陡

---

## 🚀 使用后端直接执行迁移

### 已创建的工具

我为您创建了两个执行脚本：

**1️⃣  `postgresql_executor.py`** - 通用的 PostgreSQL 执行服务

```python
from app.services.postgresql_executor import PostgreSQLExecutor

executor = PostgreSQLExecutor()
if executor.connect():
    # 执行 SQL 文件
    executor.execute_sql_file('migration.sql')
    
    # 检查表是否存在
    if executor.table_exists('schema_table_annotations'):
        print("✅ 表已创建")
    
    executor.close()
```

**2️⃣  `execute_migration_direct.py`** - 独立的迁移执行脚本

```bash
# 直接运行
.venv/bin/python execute_migration_direct.py
```

---

## 📋 最佳实践

### 1. 环境变量管理

```bash
# .env 文件
# 前端/公开操作
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...

# 后端管理操作
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# 数据库直接连接（用于 SQL 执行）
SUPABASE_DB_HOST=db.xxx.supabase.co
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=***

# 不要将 SUPABASE_DB_PASSWORD 提交到 Git!
```

### 2. 生产环境安全

```python
# ❌ 不要这样做
db_password = "hardcoded_password"

# ✅ 应该这样做
db_password = os.getenv('SUPABASE_DB_PASSWORD')

# ✅ 或者通过环境变量
from dotenv import load_dotenv
load_dotenv()
```

### 3. 错误处理

```python
try:
    executor = PostgreSQLExecutor()
    if executor.connect():
        executor.execute_sql_file('migration.sql')
    else:
        logger.error("数据库连接失败")
except psycopg2.Error as e:
    logger.error(f"数据库错误: {e}")
except Exception as e:
    logger.error(f"未预期的错误: {e}")
finally:
    executor.close()
```

---

## 🔧 执行迁移的完整步骤

### 步骤 1: 设置环境变量

在 `.env` 文件中添加数据库连接信息：

```bash
SUPABASE_DB_HOST=db.kgmyhukvyygudsllypgv.supabase.co
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=your_actual_password
```

### 步骤 2: 安装依赖

```bash
# 如果还没有安装 psycopg2
.venv/bin/pip install psycopg2-binary
```

### 步骤 3: 执行迁移

```bash
# 方法 A: 使用专用脚本
.venv/bin/python execute_migration_direct.py

# 方法 B: 在 Python 代码中
from app.services.postgresql_executor import PostgreSQLExecutor
executor = PostgreSQLExecutor()
if executor.connect():
    executor.execute_sql_file('migration.sql')
```

### 步骤 4: 验证

```bash
# 验证环境
.venv/bin/python verify_schema_annotation_setup.py

# 查看数据库中的表
.venv/bin/python app/services/postgresql_executor.py
```

---

## ❓ 常见问题

**Q: SERVICE_ROLE_KEY 和数据库密码的区别？**

```
SERVICE_ROLE_KEY:
  - JWT 令牌格式
  - 用于 Supabase API 认证
  - 绕过 RLS 策略
  - 用于 PostgREST API

数据库密码:
  - PostgreSQL 密码
  - 用于直接数据库连接
  - 完全数据库访问权限
  - 用于 SQL 执行
```

**Q: 哪种方式执行 SQL 迁移最好？**

```
推荐顺序：
1️⃣  psycopg2 + 数据库密码 (最好)
    - 直接、快速、支持所有 SQL
2️⃣  Supabase Python SDK + SERVICE_ROLE_KEY (可用)
    - 但不支持直接 SQL，只能表操作
3️⃣  手动在 Supabase 控制台 (最安全)
    - 避免在代码中存储密码
```

**Q: 如何安全地存储数据库密码？**

```
方案 1: 环境变量 (.env 文件)
  - 添加 .env 到 .gitignore
  - 只在本地或私密服务器上

方案 2: 密钥管理服务
  - AWS Secrets Manager
  - HashiCorp Vault
  - Supabase Vault

方案 3: 部署平台
  - Render
  - Railway
  - Heroku
  - 都有内置的环境变量管理
```

---

## 📌 总结

| 场景 | 推荐方式 | 所需认证 |
|------|---------|---------|
| 迁移和初始化 | psycopg2 | DB 密码 |
| 后端管理操作 | Supabase SDK | SERVICE_ROLE_KEY |
| 前端数据操作 | Supabase SDK | ANON_KEY |
| 安全第一 | Supabase 控制台 | Web UI |

---

## 🎯 下一步

1. ✅ 在 Supabase 中获取 DB 密码
2. ✅ 添加到 `.env` 文件
3. ✅ 运行 `execute_migration_direct.py`
4. ✅ 继续后续的 Schema 扫描和 LLM 标注
