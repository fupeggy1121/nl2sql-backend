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
BEGIN
    -- 去除前后空白
    trimmed := btrim(query);

    -- 安全检查: 仅允许 SELECT 查询
    IF upper(left(trimmed, 6)) <> 'SELECT' THEN
        RAISE EXCEPTION 'Only SELECT queries are allowed (received: %)', left(trimmed, 20);
    END IF;

    -- 拒绝危险语句
    IF trimmed ~* '\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE)\b' THEN
        RAISE EXCEPTION 'Write / DDL operations are not permitted';
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
