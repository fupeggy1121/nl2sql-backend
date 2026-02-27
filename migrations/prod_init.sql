-- ═══════════════════════════════════════════════════════════════════════════
-- migrations/prod_init.sql
-- 生产数据库初始化脚本（自托管 PostgreSQL）
--
-- 执行方式:
--   psql "$DATABASE_URL" -f migrations/prod_init.sql
--
-- 包含:
--   1. execute_sql RPC 函数（供 psycopg2 执行任意 SELECT）
--   2. table_annotations 表（表级注释，供 schema_tools 读取）
--   3. column_annotations 表（列级注释，供 schema_tools 读取）
--   4. 初始注释示例（请按实际生产表修改）
-- ═══════════════════════════════════════════════════════════════════════════

-- ─── 1. execute_sql 函数 ─────────────────────────────────────────────────────
-- 注意：生产环境使用 DB_BACKEND=postgres 时，backend 走 psycopg2 直连，
-- 此函数可保留供兼容或管理工具使用，但 NL2SQL 后端不调用它。
CREATE OR REPLACE FUNCTION execute_sql(query text)
RETURNS TABLE (result json)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY EXECUTE 'SELECT row_to_json(t) FROM (' || query || ') t';
END;
$$;

-- ─── 2. table_annotations 表 ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS table_annotations (
    id          SERIAL PRIMARY KEY,
    schema_name TEXT    NOT NULL DEFAULT 'public',
    table_name  TEXT    NOT NULL,
    label_cn    TEXT,            -- 中文名称，如 "晶圆"
    description TEXT,            -- 详细描述
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (schema_name, table_name)
);

CREATE INDEX IF NOT EXISTS idx_table_annotations_table
    ON table_annotations (schema_name, table_name);

-- ─── 3. column_annotations 表 ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS column_annotations (
    id          SERIAL PRIMARY KEY,
    schema_name TEXT    NOT NULL DEFAULT 'public',
    table_name  TEXT    NOT NULL,
    column_name TEXT    NOT NULL,
    label_cn    TEXT,            -- 中文字段名，如 "批次编号"
    description TEXT,            -- 字段用途描述
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (schema_name, table_name, column_name)
);

CREATE INDEX IF NOT EXISTS idx_column_annotations_table
    ON column_annotations (schema_name, table_name);

-- ─── 4. 示例注释数据（请修改为您的实际表/列名）─────────────────────────────
-- 表注释示例
INSERT INTO table_annotations (table_name, label_cn, description) VALUES
    ('your_table_1', '实体1', '请填写实际描述'),
    ('your_table_2', '实体2', '请填写实际描述')
ON CONFLICT (schema_name, table_name) DO UPDATE
    SET label_cn    = EXCLUDED.label_cn,
        description = EXCLUDED.description,
        updated_at  = NOW();

-- 列注释示例
INSERT INTO column_annotations (table_name, column_name, label_cn, description) VALUES
    ('your_table_1', 'id',         '主键',   '自增主键'),
    ('your_table_1', 'name',       '名称',   '实体名称'),
    ('your_table_1', 'status',     '状态',   '当前状态'),
    ('your_table_1', 'created_at', '创建时间', '记录创建时间'),
    ('your_table_2', 'id',         '主键',   '自增主键'),
    ('your_table_2', 'code',       '编码',   '业务编码'),
    ('your_table_2', 'entity1_id', '关联ID', '关联 your_table_1.id')
ON CONFLICT (schema_name, table_name, column_name) DO UPDATE
    SET label_cn    = EXCLUDED.label_cn,
        description = EXCLUDED.description,
        updated_at  = NOW();

-- ─── 完成 ────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    RAISE NOTICE '✅ prod_init.sql 执行完成';
    RAISE NOTICE '   table_annotations 条数: %', (SELECT COUNT(*) FROM table_annotations);
    RAISE NOTICE '   column_annotations 条数: %', (SELECT COUNT(*) FROM column_annotations);
END $$;
