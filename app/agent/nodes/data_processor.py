"""
DataProcessor — 即席路径数据后处理工具

所有方法均为纯函数（输入 DataFrame，输出 DataFrame），
无副作用，无外部 IO，供 sandbox 安全执行。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

# ── 白名单方法集合（sandbox 校验用）──────────────────────────────────────────
ALLOWED_OPERATIONS = {
    "drop_nulls",
    "pivot",
    "unpivot",
    "merge_dfs",
    "rename_columns",
    "filter_rows",
    "add_column",
    "sort_rows",
    "limit_rows",
}


class DataProcessor:
    """
    后处理工具类。所有方法均以 DataFrame 为输入输出。
    新增操作只需在此类添加静态方法，并加入 ALLOWED_OPERATIONS。
    """

    @staticmethod
    def drop_nulls(df: pd.DataFrame, subset: Optional[List[str]] = None) -> pd.DataFrame:
        """移除含空值的行。subset 指定检查的列，None 表示检查所有列。"""
        return df.dropna(subset=subset).reset_index(drop=True)

    @staticmethod
    def pivot(
        df: pd.DataFrame,
        index: str,
        columns: str,
        values: str,
        aggfunc: str = "first",
    ) -> pd.DataFrame:
        """行转列（宽表转换）。"""
        result = df.pivot_table(
            index=index,
            columns=columns,
            values=values,
            aggfunc=aggfunc,
        )
        result.columns.name = None
        return result.reset_index()

    @staticmethod
    def unpivot(
        df: pd.DataFrame,
        id_vars: List[str],
        value_vars: Optional[List[str]] = None,
        var_name: str = "variable",
        value_name: str = "value",
    ) -> pd.DataFrame:
        """列转行（长表转换）。"""
        return df.melt(
            id_vars=id_vars,
            value_vars=value_vars,
            var_name=var_name,
            value_name=value_name,
        ).reset_index(drop=True)

    @staticmethod
    def merge_dfs(
        left: pd.DataFrame,
        right: pd.DataFrame,
        on: List[str],
        how: str = "inner",
    ) -> pd.DataFrame:
        """合并两个 DataFrame。"""
        return left.merge(right, on=on, how=how).reset_index(drop=True)

    @staticmethod
    def rename_columns(df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
        """重命名列。mapping = {"旧列名": "新列名"}"""
        return df.rename(columns=mapping)

    @staticmethod
    def filter_rows(df: pd.DataFrame, column: str, op: str, value: Any) -> pd.DataFrame:
        """
        过滤行。op 支持: eq, ne, gt, lt, gte, lte, isin, notnull。
        """
        ops = {
            "eq":      lambda s: s == value,
            "ne":      lambda s: s != value,
            "gt":      lambda s: s > value,
            "lt":      lambda s: s < value,
            "gte":     lambda s: s >= value,
            "lte":     lambda s: s <= value,
            "isin":    lambda s: s.isin(value),
            "notnull": lambda s: s.notna(),
        }
        if op not in ops:
            raise ValueError(f"不支持的操作符: '{op}'，支持: {sorted(ops.keys())}")
        return df[ops[op](df[column])].reset_index(drop=True)

    @staticmethod
    def add_column(df: pd.DataFrame, name: str, expr: str) -> pd.DataFrame:
        """
        添加派生列。expr 是 pandas eval 表达式。
        示例：add_column(df, "yield_pct", "good_count / total_count * 100")
        """
        df = df.copy()
        df[name] = df.eval(expr)
        return df

    @staticmethod
    def sort_rows(df: pd.DataFrame, by: List[str], ascending: bool = True) -> pd.DataFrame:
        """排序。"""
        return df.sort_values(by=by, ascending=ascending).reset_index(drop=True)

    @staticmethod
    def limit_rows(df: pd.DataFrame, n: int) -> pd.DataFrame:
        """取前 N 行。"""
        return df.head(n).reset_index(drop=True)
