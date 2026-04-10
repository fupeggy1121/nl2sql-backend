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
    elif source_type == "multi_source":
        return _load_from_multi_source(config)
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
        if isinstance(result, str):
            sql = result.strip() or None
        elif isinstance(result, dict):
            sql = result.get("sql")
        else:
            sql = getattr(result, "sql", None)
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


def _load_from_multi_source(config: Dict[str, Any]) -> pd.DataFrame:
    """执行多数据源查询（type="multi_source"），返回生产数据 DataFrame。

    当前策略：
      - 执行 production_sql（MES 侧），返回产出事件 DataFrame
      - 若 downtime_source_id 已配置，执行 downtime_sql 并将聚合停机时长列
        左连接到 production df（按 report_date + equipment_code/eqp_id）
      - run_oee_report 可以读取 __downtime_minutes__ 列（若存在）来计算可用率
    """
    from app.services.multi_source_query_executor import MultiSourceQueryExecutor, SourceSqlTask

    production_sql = config.get("production_sql", "")
    downtime_sql = config.get("downtime_sql", "")
    production_source_id = config.get("production_source_id", "mes_prod")
    downtime_source_id = config.get("downtime_source_id", "equip_mgmt")
    limit = config.get("limit", _MAX_ROWS)

    if not production_sql:
        raise ValueError("multi_source 配置缺少 production_sql")

    executor = MultiSourceQueryExecutor()

    # ── 执行生产查询 ──────────────────────────────────────────────────────────
    prod_task = SourceSqlTask(
        source_id=production_source_id,
        sql=production_sql,
        result_name="production",
    )
    prod_df = executor.execute_single(prod_task)

    if prod_df.empty:
        logger.warning("[data_source] multi_source: 生产数据为空")
        return prod_df

    # 截断至 limit
    if len(prod_df) > limit:
        prod_df = prod_df.head(limit)

    # ── 尝试执行停机查询并附加 ────────────────────────────────────────────────
    if downtime_sql and downtime_source_id:
        try:
            from app.config.data_sources import DataSourceRegistry
            registry = DataSourceRegistry.get_instance()
            if registry.has(downtime_source_id):
                down_task = SourceSqlTask(
                    source_id=downtime_source_id,
                    sql=downtime_sql,
                    result_name="downtime",
                )
                down_df = executor.execute_single(down_task)
                if not down_df.empty and "report_date" in down_df.columns:
                    # 聚合到设备+日期维度，计算总停机分钟
                    agg_cols = [c for c in ["report_date", "equipment_code"] if c in down_df.columns]
                    if agg_cols and "downtime_minutes" in down_df.columns:
                        down_agg = (
                            down_df.groupby(agg_cols, as_index=False)["downtime_minutes"]
                            .sum()
                            .rename(columns={"downtime_minutes": "__downtime_minutes__"})
                        )
                        # 将 report_date 类型对齐后 LEFT JOIN 到生产数据
                        if "report_date" in prod_df.columns:
                            prod_df["report_date"] = prod_df["report_date"].astype(str)
                            down_agg["report_date"] = down_agg["report_date"].astype(str)
                            merge_on = [c for c in agg_cols if c in prod_df.columns]
                            if merge_on:
                                prod_df = pd.merge(prod_df, down_agg, on=merge_on, how="left")
                                logger.info("[data_source] multi_source: 停机数据已附加 (%d rows)", len(down_agg))
        except Exception as e:
            logger.warning("[data_source] multi_source: 停机数据加载失败（降级）: %s", e)

    return prod_df
