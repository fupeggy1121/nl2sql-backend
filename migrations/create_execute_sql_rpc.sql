-- ============================================================
-- Supabase RPC 函数: execute_sql
-- 用于执行 PostgREST 无法处理的复杂 SQL（JOIN / CTE / 窗口函数等）
--
-- 运行方式:
--   在 Supabase SQL Editor 或 psql 中执行此脚本
--
-- 安全说明:
--   SECURITY DEFINER 会以创建者权限执行 SQL
--   仅限 SELECT 查询，拒绝写入操作
-- ============================================================

CREATE OR REPLACE FUNCTION execute_sql(query text)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    result json;
    trimmed text;
    first_keyword text;
BEGIN
    -- 去除前后空白
    trimmed := btrim(query);

    -- 提取第一个关键字（大写）
    first_keyword := upper(split_part(trimmed, ' ', 1));
    -- 处理 WITH\n 或 WITH\t 等情况
    IF first_keyword = '' OR first_keyword IS NULL THEN
        first_keyword := upper(left(trimmed, 6));
    END IF;

    -- 安全检查: 仅允许 SELECT 和 WITH (CTE) 查询
    IF first_keyword NOT IN ('SELECT', 'WITH') THEN
        RAISE EXCEPTION 'Only SELECT/WITH queries are allowed (received: %)', left(trimmed, 20);
    END IF;

    -- 拒绝危险语句（排除 CTE 中的 SELECT 子句，仅检测写入/DDL）
    IF trimmed ~* '\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE)\b' THEN
        RAISE EXCEPTION 'Write / DDL operations are not permitted';
    END IF;

    -- CTE 查询必须最终包含 SELECT
    IF first_keyword = 'WITH' AND trimmed !~* '\bSELECT\b' THEN
        RAISE EXCEPTION 'WITH (CTE) queries must contain a SELECT statement';
    END IF;

    -- 执行并返回 JSON 数组
    EXECUTE format('SELECT json_agg(row_to_json(t)) FROM (%s) t', trimmed)
    INTO result;

    -- 空结果返回空数组而非 null
    RETURN COALESCE(result, '[]'::json);
END;
$$;

-- 允许匿名用户通过 PostgREST 调用
GRANT EXECUTE ON FUNCTION execute_sql(text) TO anon;
GRANT EXECUTE ON FUNCTION execute_sql(text) TO authenticated;

COMMENT ON FUNCTION execute_sql(text) IS
  'Execute read-only SQL and return result as JSON. Used by NL2SQL backend for complex queries (JOINs, CTEs, window functions) that cannot be expressed via PostgREST.';
