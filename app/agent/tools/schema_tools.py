"""
Schema Tools — 数据库 Schema 查询与 SQL 验证工具

提供:
- get_schema_context: 获取与用户查询最相关的 Schema 信息（RAG 上下文）
- validate_sql: 验证 SQL 是否可执行（检查表名/列名/语法）
"""

import re
import logging
from typing import Optional
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# 延迟初始化缓存
_schema_cache: Optional[dict] = None


def _get_schema_metadata() -> dict:
    """获取完整的 schema 元数据（缓存）"""
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache

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
        return {"tables": {}, "cn_to_table": {}, "all_columns": set()}


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
    # FROM table, JOIN table
    from_pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    found = re.findall(from_pattern, sql, re.IGNORECASE)
    for table in found:
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
        # 提取 SELECT 子句和 WHERE 子句中的列名
        col_pattern = r'(?:SELECT|WHERE|ON|AND|OR|ORDER BY|GROUP BY|HAVING)\s+'
        # 简化方式：提取非函数的标识符
        select_match = re.search(
            r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL
        )
        if select_match:
            select_clause = select_match.group(1)
            if select_clause.strip() != "*":
                # 提取可能的列名
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
                }
                for col in potential_cols:
                    col_l = col.lower()
                    if col_l not in sql_keywords and col_l not in valid_tables:
                        if col_l not in schema["all_columns"]:
                            # 不确定是否是列名，只做 warning
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
