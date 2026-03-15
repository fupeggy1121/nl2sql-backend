"""
Schema Tools — 数据库 Schema 查询与 SQL 验证工具

提供:
- get_schema_context: 获取与用户查询最相关的 Schema 信息（RAG 上下文）
- validate_sql: 验证 SQL 是否可执行（检查表名/列名/语法）
"""

import os
import re
import logging
from typing import Optional
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# 延迟初始化缓存
_schema_cache: Optional[dict] = None


def _get_schema_metadata_via_mysql() -> dict:
    """DB_BACKEND=mysql 时，直接从 MySQL information_schema 读取表/列中文注释。"""
    global _schema_cache
    try:
        import pymysql
        import pymysql.cursors
        kwargs = dict(
            host=os.getenv("MYSQL_HOST",     os.getenv("PROD_DB_HOST",     "10.60.120.33")),
            port=int(os.getenv("MYSQL_PORT", os.getenv("PROD_DB_PORT",     "3336"))),
            db=os.getenv("MYSQL_DB",         os.getenv("PROD_DB_NAME",     "cc_semi_mvp")),
            user=os.getenv("MYSQL_USER",     os.getenv("PROD_DB_USER",     "root")),
            password=os.getenv("MYSQL_PASSWORD", os.getenv("PROD_DB_PASSWORD", "")),
            connect_timeout=10, charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor
        )
        conn = pymysql.connect(**kwargs)
        cur  = conn.cursor()

        db_name = kwargs["db"]
        cur.execute("""
            SELECT TABLE_NAME, TABLE_COMMENT
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
        """, (db_name,))
        tables_raw = cur.fetchall()

        cur.execute("""
            SELECT TABLE_NAME, COLUMN_NAME, COLUMN_COMMENT, DATA_TYPE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME, ORDINAL_POSITION
        """, (db_name,))
        cols_raw = cur.fetchall()
        cur.close()
        conn.close()

        schema: dict = {"tables": {}, "cn_to_table": {}, "all_columns": set()}
        for row in tables_raw:
            tname   = row["TABLE_NAME"]
            comment = (row["TABLE_COMMENT"] or "").strip()
            schema["tables"][tname] = {
                "name_cn":           comment or tname,
                "description":       comment,
                "business_meaning":   "",
                "columns":           [],
            }
            if comment:
                schema["cn_to_table"][comment] = tname

        for row in cols_raw:
            tname   = row["TABLE_NAME"]
            col_cn  = (row["COLUMN_COMMENT"] or "").strip()
            if tname in schema["tables"]:
                schema["tables"][tname]["columns"].append({
                    "name":    row["COLUMN_NAME"],
                    "name_cn": col_cn,
                    "type":    row["DATA_TYPE"],
                })
            schema["all_columns"].add(row["COLUMN_NAME"].lower())

        _schema_cache = schema
        logger.info(
            "[schema_tools] mysql mode: %d tables, %d columns loaded",
            len(schema["tables"]), len(schema["all_columns"])
        )
        return schema

    except Exception as e:
        logger.error("[schema_tools] MySQL schema load failed: %s", e)
        return {"tables": {}, "cn_to_table": {}, "all_columns": set()}


def _get_schema_metadata_via_psycopg2() -> dict:
    """DB_BACKEND=postgres 时，通过 psycopg2 直连读取 annotation 表。
    与 Supabase 路径返回完全相同的 schema 结构。
    """
    global _schema_cache
    try:
        import psycopg2
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            logger.error("[schema_tools] DB_BACKEND=postgres but DATABASE_URL is not set")
            return {"tables": {}, "cn_to_table": {}, "all_columns": set()}

        conn = psycopg2.connect(database_url)
        cur = conn.cursor()

        cur.execute("""
            SELECT table_name, name_cn, description_cn, business_meaning
            FROM table_annotations WHERE is_active = true
        """)
        tables_raw = cur.fetchall()

        cur.execute("""
            SELECT table_name, column_name, column_name_cn, data_type
            FROM column_annotations WHERE is_active = true
        """)
        cols_raw = cur.fetchall()
        cur.close()
        conn.close()

        schema = {"tables": {}, "cn_to_table": {}, "all_columns": set()}

        for table_name, name_cn, desc, biz in tables_raw:
            schema["tables"][table_name] = {
                "name_cn": name_cn or "",
                "description": desc or "",
                "business_meaning": biz or "",
                "columns": [],
            }
            if name_cn:
                schema["cn_to_table"][name_cn] = table_name

        for tbl, col, col_cn, dtype in cols_raw:
            if tbl in schema["tables"]:
                schema["tables"][tbl]["columns"].append({
                    "name": col, "name_cn": col_cn or "", "type": dtype or ""
                })
            schema["all_columns"].add(col.lower())

        _schema_cache = schema
        logger.info(
            f"[schema_tools] postgres mode: {len(schema['tables'])} tables, "
            f"{len(schema['all_columns'])} columns loaded via psycopg2"
        )
        return schema

    except Exception as e:
        logger.error(f"[schema_tools] psycopg2 schema load failed: {e}")
        return {"tables": {}, "cn_to_table": {}, "all_columns": set()}


def _get_schema_metadata() -> dict:
    """获取完整的 schema 元数据（缓存）"""
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache

    # 直连模式：跳过 SupabaseClient
    db_backend = os.getenv("DB_BACKEND", "supabase")
    if db_backend == "mysql":
        return _get_schema_metadata_via_mysql()
    if db_backend == "postgres":
        return _get_schema_metadata_via_psycopg2()

    try:
        from app.services.nl2sql_enhanced import get_enhanced_nl2sql_converter
        converter = get_enhanced_nl2sql_converter()
        metadata = converter.annotation_metadata

        tables = metadata.get("tables", {})
        columns = metadata.get("columns", {})

        # 构建结构化的 schema 索引
        schema = {
            "tables": {},           # table_name → {name_cn, columns: [...]}
            "cn_to_table": {},      # 中文名 → table_name
            "all_columns": set(),   # 所有列名集合
        }

        for table_name, info in tables.items():
            cn_name = info.get("name_cn", "")
            table_cols = []
            for col in columns.values():
                if col.get("table_name") == table_name:
                    table_cols.append({
                        "name": col["column_name"],
                        "name_cn": col.get("column_name_cn", ""),
                        "type": col.get("data_type", ""),
                    })
                    schema["all_columns"].add(col["column_name"].lower())

            schema["tables"][table_name] = {
                "name_cn": cn_name,
                "description": info.get("description_cn", ""),
                "business_meaning": info.get("business_meaning", ""),
                "columns": table_cols,
            }
            if cn_name:
                schema["cn_to_table"][cn_name] = table_name

        _schema_cache = schema
        logger.info(f"Schema cache built: {len(schema['tables'])} tables, "
                     f"{len(schema['all_columns'])} columns")
        return schema

    except Exception as e:
        logger.error(f"Failed to load schema metadata: {e}")
        # 缓存空结果，避免每次请求都重试，导致30s 超时 × 重试次数
        _schema_cache = {"tables": {}, "cn_to_table": {}, "all_columns": set()}
        return _schema_cache


@tool
def get_schema_context(user_input: str) -> str:
    """Retrieve relevant database schema context for the user's query.
    Searches table names/descriptions and returns matching schema info.
    Use this to understand what tables and columns are available."""
    schema = _get_schema_metadata()
    if not schema["tables"]:
        return "Schema metadata not available."

    user_lower = user_input.lower()
    matched_tables = []

    # 1. 中文名精确匹配
    for cn_name, table_name in schema["cn_to_table"].items():
        if cn_name in user_input:
            matched_tables.append(table_name)

    # 2. 英文表名匹配
    for table_name in schema["tables"]:
        if table_name.lower() in user_lower or table_name.replace("_", " ") in user_lower:
            if table_name not in matched_tables:
                matched_tables.append(table_name)

    # 3. 关键词匹配（description / business_meaning）
    keywords = ["产量", "产线", "设备", "质量", "OEE", "载具", "订单",
                 "批次", "晶圆", "站点", "工序", "报警", "维护",
                 "production", "equipment", "quality", "carrier", "order"]
    for kw in keywords:
        if kw in user_input or kw in user_lower:
            for tname, tinfo in schema["tables"].items():
                desc = (tinfo.get("description", "") + " " +
                        tinfo.get("business_meaning", "") + " " +
                        tinfo.get("name_cn", ""))
                if kw in desc.lower() or kw in desc:
                    if tname not in matched_tables:
                        matched_tables.append(tname)

    # 如果没有匹配，返回最常用的表
    if not matched_tables:
        fallback = ["production_events", "equipment", "carriers",
                     "production_orders", "quality_inspections"]
        matched_tables = [t for t in fallback if t in schema["tables"]][:3]

    # 构建上下文字符串
    lines = ["[可用数据库 Schema]\n"]
    for tname in matched_tables[:6]:  # 最多 6 个表
        tinfo = schema["tables"].get(tname, {})
        cn = tinfo.get("name_cn", "")
        desc = tinfo.get("description", "")
        lines.append(f"表: {tname}" + (f" ({cn})" if cn else ""))
        if desc:
            lines.append(f"  描述: {desc}")
        for col in tinfo.get("columns", []):
            col_cn = f" ({col['name_cn']})" if col.get("name_cn") else ""
            lines.append(f"  - {col['name']}{col_cn}: {col['type']}")
        lines.append("")

    return "\n".join(lines)


@tool
def validate_sql(sql: str) -> dict:
    """Validate SQL against real database schema.
    Returns dict with: valid (bool), errors (list of error strings),
    warnings (list), tables_found (list), missing_tables (list),
    missing_columns (list)."""
    schema = _get_schema_metadata()
    errors = []
    warnings = []
    tables_found = []
    missing_tables = []
    missing_columns = []

    if not sql or not sql.strip():
        return {
            "valid": False,
            "errors": ["SQL is empty"],
            "warnings": [],
            "tables_found": [],
            "missing_tables": [],
            "missing_columns": [],
        }

    sql_upper = sql.upper().strip()

    # 1. 基本语法检查 — allow SELECT and WITH (CTE) queries
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        errors.append("Only SELECT queries allowed")

    # 2. 检查危险操作
    danger_kws = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"]
    for kw in danger_kws:
        if re.search(rf"\b{kw}\b", sql_upper):
            errors.append(f"Dangerous keyword '{kw}' found")

    # 3. 提取表名并验证
    valid_tables = {t.lower() for t in schema["tables"]}
    # 补充本体映射中的生产库表名（MySQL 生产表），避免将正确表名误判为 missing
    try:
        from app.ontology.mapping import get_mapping
        for _pt in get_mapping().list_physical_tables():
            if _pt.table_name:
                valid_tables.add(_pt.table_name.lower())
    except Exception:
        pass
    # FROM table, JOIN table
    # MySQL 内置表函数（出现在 JOIN 后面但不是真实表名）
    MYSQL_BUILTIN_TABLE_FUNCS = {'json_table', 'lateral', 'dual'}
    from_pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    found = re.findall(from_pattern, sql, re.IGNORECASE)
    for table in found:
        if table.lower() in MYSQL_BUILTIN_TABLE_FUNCS:
            continue  # JSON_TABLE 等是 MySQL 内置函数，不是表名
        if table.lower() in valid_tables:
            tables_found.append(table)
        else:
            missing_tables.append(table)
            # 尝试建议修正
            suggestion = _find_closest_table(table, schema["tables"])
            if suggestion:
                errors.append(
                    f"Table '{table}' not found. Did you mean '{suggestion}'?"
                )
            else:
                errors.append(f"Table '{table}' not found in schema")

    # 4. 检查列名（仅对已匹配的表做验证）
    if tables_found and schema["all_columns"]:
        # 先提取表别名: FROM table alias 或 JOIN table alias
        table_alias_pattern = r'(?:FROM|JOIN)\s+\w+\s+(\w+)'
        table_aliases = {
            m.lower() for m in re.findall(table_alias_pattern, sql, re.IGNORECASE)
        }
        # 提取 SELECT 中的列别名: ... AS alias_name
        col_alias_pattern = r'\bAS\s+(\w+)'
        col_aliases = {
            m.lower() for m in re.findall(col_alias_pattern, sql, re.IGNORECASE)
        }
        # 提取点引用前缀: alias.col → alias 是表别名，不算列名
        dot_prefixes = {
            m.lower() for m in re.findall(r'\b(\w+)\.\w+', sql)
        }
        # 合并所有应跳过的符号
        skip_identifiers = table_aliases | col_aliases | dot_prefixes

        select_match = re.search(
            r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL
        )
        if select_match:
            select_clause = select_match.group(1)
            if select_clause.strip() != "*":
                potential_cols = re.findall(
                    r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', select_clause
                )
                sql_keywords = {
                    "select", "as", "count", "sum", "avg", "min", "max",
                    "distinct", "case", "when", "then", "else", "end",
                    "coalesce", "cast", "concat", "null", "true", "false",
                    "asc", "desc", "limit", "offset", "between", "in",
                    "like", "is", "not", "and", "or", "json_agg",
                    "row_to_json", "extract", "date", "timestamp",
                    "round", "nullif", "over", "partition", "numeric",
                    "integer", "varchar", "text", "float", "double",
                }
                for col in potential_cols:
                    col_l = col.lower()
                    if (col_l not in sql_keywords
                            and col_l not in valid_tables
                            and col_l not in skip_identifiers):
                        if col_l not in schema["all_columns"]:
                            missing_columns.append(col)

    if missing_columns:
        warnings.append(
            f"Possibly invalid columns: {', '.join(missing_columns[:5])}"
        )

    valid = len(errors) == 0 and len(missing_tables) == 0
    return {
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "tables_found": tables_found,
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
    }


def _find_closest_table(name: str, tables: dict) -> Optional[str]:
    """Find closest matching table name."""
    from difflib import SequenceMatcher

    name_lower = name.lower()
    best, best_ratio = None, 0.55

    # 常见别名映射
    aliases = {
        "vehicles": "carriers", "vehicle": "carriers",
        "machines": "equipment", "machine": "equipment",
        "orders": "production_orders", "order": "production_orders",
        "events": "production_events", "event": "production_events",
        "inspections": "quality_inspections",
        "checks": "quality_inspections",
    }
    if name_lower in aliases:
        aliased = aliases[name_lower]
        if aliased in tables:
            return aliased

    for tname in tables:
        ratio = SequenceMatcher(None, name_lower, tname.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best = tname

    return best


def get_table_list() -> list:
    """返回所有可用表名列表"""
    schema = _get_schema_metadata()
    return list(schema["tables"].keys())


def get_columns_for_table(table_name: str) -> list:
    """返回指定表的所有列名"""
    schema = _get_schema_metadata()
    tinfo = schema["tables"].get(table_name, {})
    return [c["name"] for c in tinfo.get("columns", [])]
