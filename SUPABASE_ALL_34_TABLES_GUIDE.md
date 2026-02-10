# Supabase 完整表列表查询指南

## 获取所有表的SQL查询

### 1. 获取表计数 (验证总数)
```sql
SELECT count(*) 
FROM pg_catalog.pg_tables
WHERE schemaname = 'public';
-- 结果: 34
```

### 2. 获取所有表名和基本信息
```sql
SELECT 
    tablename,
    schemaname,
    tableowner
FROM pg_catalog.pg_tables 
WHERE schemaname = 'public'
ORDER BY tablename;
```

### 3. 获取每个表的行数
```sql
SELECT 
    schemaname,
    tablename,
    n_live_tup as row_count
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_live_tup DESC;
```

### 4. 获取每个表的列数和详细信息
```sql
SELECT 
    t.tablename,
    COUNT(a.attname) as column_count,
    ARRAY_AGG(a.attname ORDER BY a.attnum) as columns
FROM pg_catalog.pg_tables t
LEFT JOIN pg_catalog.pg_attribute a 
    ON (SELECT oid FROM pg_catalog.pg_class WHERE relname = t.tablename) = a.attrelid
    AND a.attnum > 0 
    AND NOT a.attisdropped
WHERE t.schemaname = 'public'
GROUP BY t.tablename
ORDER BY column_count DESC;
```

### 5. 获取所有表的完整概览 (推荐)
```sql
SELECT 
    t.tablename,
    COALESCE(s.n_live_tup, 0) as row_count,
    COUNT(a.attname) as column_count
FROM pg_catalog.pg_tables t
LEFT JOIN pg_catalog.pg_attribute a 
    ON (SELECT oid FROM pg_catalog.pg_class WHERE relname = t.tablename) = a.attrelid
    AND a.attnum > 0 
    AND NOT a.attisdropped
LEFT JOIN pg_stat_user_tables s 
    ON t.tablename = s.relname
WHERE t.schemaname = 'public'
GROUP BY t.tablename, s.n_live_tup
ORDER BY row_count DESC;
```

## 为什么Python客户端只找到11张表?

可能的原因：

1. **权限限制**: 某些表可能不允许通过REST API访问
2. **表类型**: 某些系统表、视图或特殊表可能被过滤
3. **REST API限制**: Supabase 的 PostgREST API 可能不公开所有表
4. **表名列表**: REST API 可能只列出已授权的表

## 解决方案

在 Supabase 仪表板 → SQL 编辑器中：
1. 运行上面的 SQL 查询 #5
2. 会看到所有34张表的完整列表
3. 导出结果为 CSV/JSON
4. 这给出了真实的完整数据库结构

## 已验证的表 (通过Python REST API)

- quality_records (6,200 行)
- oee_records (465 行)
- sub_batches (102 行)
- parameters (89 行)
- stations (64 行)
- products (31 行)
- batches (20 行)
- production_orders (6 行)
- equipment (5 行)
- equipment_groups (3 行)
- annotation_audit_log (0 行)

## 未验证的表 (23 张 - 通过SQL发现)

这些表存在于数据库中，但通过REST API不可访问。需要在Supabase SQL编辑器中查询以获取完整列表。
