"""
数据源适配器 — 统一数据获取入口

支持三种数据来源，统一返回 pandas DataFrame：
1. sql — 执行 SQL 查询（复用 MySQLExecutor）
2. table + filters — 指定表名+筛选条件（参数化查询防注入）
3. data — 行内数据（来自上轮 NL2SQL 查询结果）
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# 表名白名单正则 — 仅允许合法 MySQL 标识符
_TABLE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")

# 单次查询最大行数限制
_MAX_ROWS = 100_000


def load_dataframe(config: Dict[str, Any]) -> pd.DataFrame:
    """
    根据数据源配置加载 DataFrame。

    :param config: DataSourceConfig.model_dump() 的字典
    :return: pd.DataFrame
    :raises ValueError: 配置无效
    :raises RuntimeError: 数据库查询失败
    """
    source_type = config.get("type", "")

    if source_type == "sql":
        return _load_from_sql(config["sql"], config.get("limit"))
    elif source_type == "table":
        return _load_from_table(
            config["table"],
            config.get("filters"),
            config.get("columns"),
            config.get("limit"),
        )
    elif source_type == "data":
        return _load_from_data(config["data"])
    elif source_type == "nlquery":
        return _load_from_nlquery(config["nlquery"], config.get("limit"))
    else:
        raise ValueError(f"不支持的数据源类型: {source_type}")


def _load_from_sql(sql: str, limit: Optional[int] = None) -> pd.DataFrame:
    """执行 SQL 查询，返回 DataFrame。"""
    if not sql or not sql.strip():
        raise ValueError("SQL 语句不能为空")

    # 安全检查: 仅允许 SELECT
    normalized = sql.strip().upper()
    if not normalized.startswith("SELECT"):
        raise ValueError("仅支持 SELECT 查询")

    # 应用行数限制
    effective_limit = min(limit or _MAX_ROWS, _MAX_ROWS)
    if "LIMIT" not in normalized:
        sql = f"{sql.rstrip().rstrip(';')} LIMIT {effective_limit}"

    rows = _execute_mysql(sql)
    if rows is None:
        raise RuntimeError("SQL 查询执行失败")
    return pd.DataFrame(rows)


def _load_from_table(
    table: str,
    filters: Optional[Dict[str, Any]] = None,
    columns: Optional[List[str]] = None,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """基于表名+筛选条件查询，使用参数化查询防止 SQL 注入。"""
    if not table or not _TABLE_NAME_RE.match(table):
        raise ValueError(f"非法表名: {table}")

    # 构建 SELECT 列
    if columns:
        for col in columns:
            if not _TABLE_NAME_RE.match(col):
                raise ValueError(f"非法列名: {col}")
        col_str = ", ".join(f"`{c}`" for c in columns)
    else:
        col_str = "*"

    # 构建 WHERE（参数化）
    where_parts: List[str] = []
    params: List[Any] = []
    if filters:
        for key, value in filters.items():
            if not _TABLE_NAME_RE.match(key):
                raise ValueError(f"非法筛选字段名: {key}")
            if isinstance(value, list):
                placeholders = ", ".join(["%s"] * len(value))
                where_parts.append(f"`{key}` IN ({placeholders})")
                params.extend(value)
            else:
                where_parts.append(f"`{key}` = %s")
                params.append(value)

    where_clause = f" WHERE {' AND '.join(where_parts)}" if where_parts else ""
    effective_limit = min(limit or _MAX_ROWS, _MAX_ROWS)

    sql = f"SELECT {col_str} FROM `{table}`{where_clause} LIMIT {effective_limit}"
    rows = _execute_mysql(sql, tuple(params) if params else None)
    if rows is None:
        raise RuntimeError(f"表 {table} 查询失败")
    return pd.DataFrame(rows)


def _load_from_nlquery(nl_text: str, limit: Optional[int] = None) -> pd.DataFrame:
    """将自然语言转换为 SQL，再执行查询返回 DataFrame。"""
    if not nl_text or not nl_text.strip():
        raise ValueError("自然语言描述不能为空")
    try:
        from app.services.nl2sql_enhanced import get_enhanced_nl2sql_converter
        converter = get_enhanced_nl2sql_converter()
        result = converter.convert(nl_text)
        sql = result.get("sql") if isinstance(result, dict) else getattr(result, "sql", None)
        if not sql:
            raise ValueError(f"NL→SQL 转换失败，未生成 SQL：{result}")
        logger.info(f"[data_source] nlquery → SQL: {sql[:120]}")
        return _load_from_sql(sql, limit)
    except ImportError:
        raise RuntimeError("NL2SQL 服务不可用，请检查后端配置")


def _load_from_data(data: Optional[List[Dict[str, Any]]]) -> pd.DataFrame:
    """从行内数据构建 DataFrame（来自上轮 NL2SQL 查询结果）。"""
    if not data:
        raise ValueError("data 字段不能为空")
    df = pd.DataFrame(data)
    # 自动将数值字符串列转换为数值类型（数据库 varchar 字段常以字符串存储数值）
    for col in df.select_dtypes(include=["object"]).columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        # 若超过 50% 的行能成功转换，则认为该列是数值列
        if converted.notna().sum() > len(df) * 0.5:
            df[col] = converted
    return df


def _execute_mysql(sql: str, params: tuple = None) -> Optional[List[Dict]]:
    """复用 MySQLExecutor 连接执行查询。"""
    from app.services.mysql_executor import MySQLExecutor

    executor = MySQLExecutor()
    if not executor.connect():
        raise RuntimeError("MySQL 连接失败")
    try:
        return executor.execute_query(sql, params)
    finally:
        if executor.conn:
            executor.conn.close()
