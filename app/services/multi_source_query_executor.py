"""
多数据源查询执行器 (MultiSourceQueryExecutor)

支持同时向多个 MySQL 数据库发起查询，并将结果以 dict[result_name → DataFrame]
的形式返回，供上层 Python 层做 merge / compute。

核心设计：
  - SourceSqlTask:          描述"向哪个数据源运行哪条 SQL，结果叫什么名字"
  - MultiSourceExecutionPlan: 一批 SourceSqlTask + merge 规格
  - MultiSourceQueryExecutor: 并行执行 plan.tasks，返回 Dict[str, pd.DataFrame]

并行策略：使用 ThreadPoolExecutor（pymysql 是线程安全的），每个 task 用独立连接。
降级策略：若某数据源不可用，该 task 结果为空 DataFrame，并记录 WARNING；
         调用方可检查 result 是否为空 DataFrame 来决定是否降级。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    _PANDAS_AVAILABLE = True
except ImportError:
    _PANDAS_AVAILABLE = False
    pd = None  # type: ignore

try:
    import pymysql
    import pymysql.cursors
    _PYMYSQL_AVAILABLE = True
except ImportError:
    _PYMYSQL_AVAILABLE = False
    pymysql = None  # type: ignore


# ── 数据结构 ─────────────────────────────────────────────────────────────────

@dataclass
class SourceSqlTask:
    """向指定数据源执行单条 SQL 的任务描述。"""
    source_id: str          # 对应 DataSourceRegistry 中的 source_id
    sql: str                # 要执行的 SQL（已渲染，不含 %s 参数）
    result_name: str        # 结果 DataFrame 在返回字典中的键名
    params: tuple = ()      # 可选绑定参数（pymysql %s 风格）
    timeout_override: Optional[int] = None  # 覆盖默认 read_timeout（秒）


@dataclass
class MultiSourceExecutionPlan:
    """一次多数据源查询的完整执行规格。"""
    tasks: List[SourceSqlTask]
    # merge 规格（供调用方参考，执行器本身不执行 merge）
    merge_keys: List[str] = field(default_factory=list)   # e.g. ["equipment_code", "report_date"]
    merge_strategy: str = "outer"                          # "outer" | "inner" | "left"
    primary_result: str = ""                               # merge 时的左表 result_name


# ── 执行器 ────────────────────────────────────────────────────────────────────

class MultiSourceQueryExecutor:
    """并行向多个数据库源执行 SQL，返回 Dict[result_name, pd.DataFrame]。

    每次 execute() 调用都会新建连接（短连接模型），不维护连接池。
    这样可以避免跨数据库连接状态混淆，并保证线程安全。
    """

    def __init__(self, max_workers: int = 4):
        self._max_workers = max_workers

    # ── 公开 API ──────────────────────────────────────────────────────────────

    def execute(self, plan: MultiSourceExecutionPlan) -> Dict[str, "pd.DataFrame"]:
        """并行执行 plan 中的全部任务，返回 result_name → DataFrame 字典。

        若某任务失败或数据源不可用，对应值为空 DataFrame（不抛出异常）。
        """
        if not _PANDAS_AVAILABLE:
            raise RuntimeError("pandas 未安装，MultiSourceQueryExecutor 不可用")

        results: Dict[str, "pd.DataFrame"] = {}

        if not plan.tasks:
            return results

        with ThreadPoolExecutor(max_workers=min(self._max_workers, len(plan.tasks))) as pool:
            future_to_task = {
                pool.submit(self._run_task, task): task
                for task in plan.tasks
            }
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    df = future.result()
                    results[task.result_name] = df
                    logger.info("[MultiSourceExec] task='%s' source='%s' rows=%d",
                                task.result_name, task.source_id, len(df))
                except Exception as e:
                    logger.error("[MultiSourceExec] task='%s' 失败: %s", task.result_name, e)
                    results[task.result_name] = pd.DataFrame()

        return results

    def execute_single(self, task: SourceSqlTask) -> "pd.DataFrame":
        """执行单个 SourceSqlTask，返回 DataFrame（失败时返回空 DataFrame）。"""
        try:
            return self._run_task(task)
        except Exception as e:
            logger.error("[MultiSourceExec] single task='%s' 失败: %s", task.result_name, e)
            return pd.DataFrame()

    # ── 内部实现 ──────────────────────────────────────────────────────────────

    def _run_task(self, task: SourceSqlTask) -> "pd.DataFrame":
        """在独立连接中执行单个 SQL 任务，返回 DataFrame。"""
        from app.config.data_sources import DataSourceRegistry

        if not _PYMYSQL_AVAILABLE:
            raise RuntimeError("pymysql 未安装")

        registry = DataSourceRegistry.get_instance()
        cfg = registry.get(task.source_id)

        kwargs = cfg.to_pymysql_kwargs()
        if task.timeout_override is not None:
            kwargs["read_timeout"] = task.timeout_override

        conn = None
        try:
            conn = pymysql.connect(**kwargs, cursorclass=pymysql.cursors.DictCursor)
            with conn.cursor() as cursor:
                if task.params:
                    cursor.execute(task.sql, task.params)
                else:
                    cursor.execute(task.sql)
                rows = cursor.fetchall()
            return pd.DataFrame(rows) if rows else pd.DataFrame()
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass


def merge_results(
    results: Dict[str, "pd.DataFrame"],
    left_key: str,
    right_key: str,
    merge_on: List[str],
    strategy: str = "outer",
) -> "pd.DataFrame":
    """将两个结果 DataFrame 在 Python 层 merge。

    Args:
        results:    execute() 返回的字典
        left_key:   results 字典中左表的键名
        right_key:  results 字典中右表的键名
        merge_on:   用于 JOIN 的列名列表，e.g. ["equipment_code", "report_date"]
        strategy:   "outer" | "inner" | "left"

    Returns:
        合并后的 DataFrame；若任一表为空则直接返回另一方（outer 语义）。
    """
    if not _PANDAS_AVAILABLE:
        raise RuntimeError("pandas 未安装")

    left_df  = results.get(left_key,  pd.DataFrame())
    right_df = results.get(right_key, pd.DataFrame())

    if left_df.empty and right_df.empty:
        return pd.DataFrame()
    if left_df.empty:
        return right_df
    if right_df.empty:
        return left_df

    return pd.merge(left_df, right_df, on=merge_on, how=strategy)
