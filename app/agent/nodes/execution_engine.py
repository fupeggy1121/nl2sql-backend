"""
ExecutionEngine — 支持4种执行模式的即席查询引擎

替代 data_executor，向后兼容：sql_only 模式行为与原 data_executor 完全一致。

执行模式：
  mode 1 sql_only           — 单条 SQL 直接执行（默认，兼容旧路径）
  mode 2 sql_then_python    — SQL 取数 + Python 后处理（pivot / drop_nulls 等）
  mode 3 multi_sql_merge    — 多条 SQL 分别执行后 pandas merge（拆分复杂 JOIN）
  mode 4 python_orchestrated — 当前降级为 multi_sql_merge，后续单独迭代
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from app.agent.nodes.sandbox import execute_postprocess, SandboxError

logger = logging.getLogger(__name__)


# ── 数据结构 ──────────────────────────────────────────────────────────────────

@dataclass
class SqlStep:
    id: str
    sql: str
    purpose: str
    depends_on: List[str] = field(default_factory=list)


@dataclass
class MergeStep:
    id: str
    left: str
    right: str
    on: List[Any]   # List[str] 或 List[{"left": str, "right": str}]
    how: str = "inner"


@dataclass
class PostprocessStep:
    operation: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    mode: str                              # sql_only | sql_then_python | multi_sql_merge | python_orchestrated
    sqls: List[SqlStep]
    merges: List[MergeStep] = field(default_factory=list)
    postprocess: List[PostprocessStep] = field(default_factory=list)
    primary_result: str = "s1"

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExecutionPlan":
        return cls(
            mode=d.get("mode", "sql_only"),
            sqls=[SqlStep(**s) for s in d.get("sqls", [])],
            merges=[MergeStep(**m) for m in d.get("merges", [])],
            postprocess=[PostprocessStep(**p) for p in d.get("postprocess", [])],
            primary_result=d.get("primary_result", "s1"),
        )

    @classmethod
    def sql_only_fallback(cls, sql: str) -> "ExecutionPlan":
        """从单条 SQL 字符串构造最简 plan，用于兼容旧 data_executor 路径。"""
        return cls(
            mode="sql_only",
            sqls=[SqlStep(id="s1", sql=sql, purpose="adhoc query")],
            primary_result="s1",
        )


# ── 执行引擎 ──────────────────────────────────────────────────────────────────

class ExecutionEngine:
    """
    DB 层适配器接口：传入任意实现 execute(sql: str) -> pd.DataFrame 的对象。
    实际生产中传入封装了 execute_query tool 的适配器。
    """

    def __init__(self, db_executor: Any):
        self._db = db_executor

    def run(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """
        执行 ExecutionPlan，返回统一结构：
        {
            "success": bool,
            "data": pd.DataFrame | None,
            "rows_count": int,
            "error": str | None,
            "trace": List[dict],   # 每步执行的耗时和结果摘要
        }
        """
        trace: List[Dict[str, Any]] = []
        try:
            if plan.mode == "sql_only":
                return self._run_sql_only(plan, trace)
            elif plan.mode == "multi_sql_merge":
                return self._run_multi_sql_merge(plan, trace)
            elif plan.mode == "sql_then_python":
                return self._run_sql_then_python(plan, trace)
            elif plan.mode == "python_orchestrated":
                logger.warning(
                    "[execution_engine] python_orchestrated not yet implemented, "
                    "falling back to multi_sql_merge"
                )
                return self._run_multi_sql_merge(plan, trace)
            else:
                raise ValueError(f"未知执行模式: {plan.mode}")
        except Exception as e:
            logger.error(f"[execution_engine] run failed: {e}", exc_info=True)
            return {
                "success": False, "data": None, "rows_count": 0,
                "error": str(e), "trace": trace,
            }

    # ── mode 1: sql_only ──────────────────────────────────────────────────────

    def _run_sql_only(self, plan: ExecutionPlan, trace: list) -> Dict[str, Any]:
        step = plan.sqls[0]
        t0 = time.time()
        df = self._db.execute(step.sql)
        elapsed = time.time() - t0
        trace.append({
            "step": step.id, "mode": "sql_only",
            "purpose": step.purpose,
            "rows": len(df), "elapsed_ms": int(elapsed * 1000),
        })
        return {
            "success": True, "data": df, "rows_count": len(df),
            "error": None, "trace": trace,
        }

    # ── mode 3: multi_sql_merge ───────────────────────────────────────────────

    def _run_multi_sql_merge(self, plan: ExecutionPlan, trace: list) -> Dict[str, Any]:
        results: Dict[str, pd.DataFrame] = {}

        # 按顺序执行所有 SQL 步骤（依赖关系目前为顺序保证，无并行）
        for step in plan.sqls:
            t0 = time.time()
            df = self._db.execute(step.sql)
            elapsed = time.time() - t0
            results[step.id] = df
            trace.append({
                "step": step.id, "mode": "multi_sql_merge",
                "purpose": step.purpose,
                "rows": len(df), "elapsed_ms": int(elapsed * 1000),
            })
            logger.info(f"[execution_engine] sql {step.id} done: {len(df)} rows")

        # 按顺序执行 merge 步骤
        for merge in plan.merges:
            left_df = results[merge.left]
            right_df = results[merge.right]

            # 支持同名 List[str] 和异名 List[{"left": str, "right": str}] 两种格式
            on_pairs = merge.on
            if on_pairs and isinstance(on_pairs[0], dict):
                left_on = [p["left"] for p in on_pairs]
                right_on = [p["right"] for p in on_pairs]
            else:
                left_on = right_on = on_pairs

            t0 = time.time()
            merged = left_df.merge(
                right_df,
                left_on=left_on,
                right_on=right_on,
                how=merge.how,
                suffixes=("", "_r"),
            )
            # 删除右表重复的 key 列（仅在列名不同时）
            if left_on != right_on:
                cols_to_drop = [c for c in right_on if c in merged.columns and c not in left_on]
                merged = merged.drop(columns=cols_to_drop)

            elapsed = time.time() - t0
            results[merge.id] = merged
            trace.append({
                "step": merge.id, "mode": "merge",
                "purpose": f"merge {merge.left}×{merge.right} on {merge.on}",
                "rows": len(merged), "elapsed_ms": int(elapsed * 1000),
            })
            logger.info(f"[execution_engine] merge {merge.id} done: {len(merged)} rows")

        final_df = results[plan.primary_result]
        return {
            "success": True, "data": final_df, "rows_count": len(final_df),
            "error": None, "trace": trace,
        }

    # ── mode 2: sql_then_python ───────────────────────────────────────────────

    def _run_sql_then_python(self, plan: ExecutionPlan, trace: list) -> Dict[str, Any]:
        # 先执行 SQL（多条时走 _run_multi_sql_merge，单条走 _run_sql_only）
        sql_result = (
            self._run_multi_sql_merge(plan, trace)
            if len(plan.sqls) > 1 or plan.merges
            else self._run_sql_only(plan, trace)
        )
        if not sql_result["success"]:
            return sql_result

        df = sql_result["data"]
        postprocess_dicts = [
            {"operation": p.operation, "params": p.params}
            for p in plan.postprocess
        ]

        try:
            t0 = time.time()
            df = execute_postprocess(df, postprocess_dicts)
            elapsed = time.time() - t0
            trace.append({
                "step": "postprocess", "mode": "sql_then_python",
                "operations": [p.operation for p in plan.postprocess],
                "rows": len(df), "elapsed_ms": int(elapsed * 1000),
            })
        except SandboxError as e:
            return {
                "success": False, "data": None, "rows_count": 0,
                "error": f"后处理失败: {e}", "trace": trace,
            }

        return {
            "success": True, "data": df, "rows_count": len(df),
            "error": None, "trace": trace,
        }
