"""
execution_engine_node — ExecutionEngine 的 LangGraph 节点包装

作为 graph 中的 "data_executor" 节点运行（名称保持不变以保证向后兼容）。

执行逻辑：
  1. 若 state["execution_plan"] 存在 → 用 ExecutionPlan.from_dict() 构造计划
  2. 否则 → 用 state["sql"] 构造 sql_only 兜底计划（与原 data_executor 行为完全一致）
  3. ExecutionEngine 执行计划
  4. 将 DataFrame 转为 List[dict] 写入 query_result（与原 data_executor 格式一致）

结果格式（query_result）：
  {
      "success": bool,
      "data": List[dict],
      "rows_count": int,
      "sql": str,          # 用于前端"查看 SQL"功能
      "source": str,       # "execution_engine"
      "engine_trace": List[dict],   # ExecutionEngine 的内部执行追踪
  }
"""

import logging
import time
from typing import Any, Dict, List, Optional

import pandas as pd

from app.agent.state import AgentState
from app.agent.trace import trace_step
from app.agent.cache import result_cache
from app.agent.tools.database_tools import execute_query
from app.agent.nodes.execution_engine import ExecutionEngine, ExecutionPlan

logger = logging.getLogger(__name__)


# ── DB 适配器 ──────────────────────────────────────────────────────────────────

class _QueryToolAdapter:
    """
    将 LangChain execute_query tool 包装成 ExecutionEngine 要求的接口：
      execute(sql: str) -> pd.DataFrame
    """

    def execute(self, sql: str) -> pd.DataFrame:
        result = execute_query.invoke({"sql": sql})
        if not result.get("success"):
            error = result.get("error", "Unknown DB error")
            is_conn_err = result.get("db_connection_error", False)
            if is_conn_err:
                raise ConnectionError(error)
            raise RuntimeError(error)
        data = result.get("data", [])
        if not data:
            return pd.DataFrame()
        return pd.DataFrame(data)


# 单例适配器（无状态，可安全重用）
_DB_ADAPTER = _QueryToolAdapter()


# ── 节点函数 ───────────────────────────────────────────────────────────────────

def execution_engine_node(state: AgentState) -> dict:
    """
    LangGraph 节点：ExecutionEngine 包装器。
    安装为 graph 中的 "data_executor" 节点（名称不变）。
    """
    _t0 = time.perf_counter()

    # ── 决定构造哪种 ExecutionPlan ────────────────────────────────────────────
    plan_dict: Optional[Dict[str, Any]] = state.get("execution_plan")
    sql: str = state.get("sql", "")
    approved_sql: str = state.get("approved_sql", "")

    if approved_sql and not state.get("sql_error"):
        # 前端已审核 SQL：直接用 approved_sql，忽略 execution_plan
        active_sql = approved_sql
        plan = ExecutionPlan.sql_only_fallback(active_sql)
        logger.info(f"[data_executor] approved_sql mode: {active_sql[:80]}...")
    elif plan_dict:
        try:
            plan = ExecutionPlan.from_dict(plan_dict)
            active_sql = plan.sqls[0].sql if plan.sqls else sql
            logger.info(
                f"[data_executor] ExecutionPlan mode={plan.mode}, "
                f"sqls={len(plan.sqls)}, merges={len(plan.merges)}"
            )
        except Exception as e:
            logger.warning(f"[data_executor] ExecutionPlan.from_dict failed: {e!r}, fallback to sql_only")
            plan = ExecutionPlan.sql_only_fallback(sql)
            active_sql = sql
    else:
        # 无 execution_plan → 兼容旧路径
        active_sql = sql
        plan = ExecutionPlan.sql_only_fallback(sql)
        logger.info(f"[data_executor] sql_only fallback: {sql[:80]}...")

    if not active_sql and plan.mode == "sql_only":
        logger.warning("[data_executor] No SQL to execute")
        return {
            "query_result": {
                "success": False, "data": [], "rows_count": 0,
                "error": "No SQL generated",
            },
            "sql_error": "No SQL was generated to execute",
        }

    # ── 缓存查找（仅 sql_only 模式启用缓存，多SQL合并结果不缓存）────────────────
    if plan.mode == "sql_only":
        _cache_result = result_cache.get(active_sql)
        if _cache_result is not None:
            logger.info("[data_executor] Cache HIT")
            data = _cache_result.get("data", [])
            rows = len(data) if isinstance(data, list) else 0
            trace = list(state.get("pipeline_trace", []))
            trace_step(trace, "data_executor", _t0,
                       summary=f"[缓存] 返回 {rows} 行数据",
                       detail={"rows_count": rows, "mode": "sql_only", "cache_hit": True,
                               "engine_trace": [{"step": "s1", "mode": "sql_only",
                                                 "purpose": "cache hit", "rows": rows}]})
            return {
                "query_result": _cache_result,
                "sql_error": "",
                "pipeline_trace": trace,
            }

    # ── 执行 ──────────────────────────────────────────────────────────────────
    engine = ExecutionEngine(_DB_ADAPTER)
    engine_result = engine.run(plan)

    trace = list(state.get("pipeline_trace", []))

    if engine_result["success"]:
        df: Optional[pd.DataFrame] = engine_result.get("data")
        rows: int = engine_result.get("rows_count", 0)

        # DataFrame → List[dict]（与原 data_executor 格式一致）
        data_list: List[dict] = []
        if df is not None and not df.empty:
            data_list = df.to_dict(orient="records")

        logger.info(f"[data_executor] Success: {rows} rows, mode={plan.mode}")
        trace_step(trace, "data_executor", _t0,
                   summary=f"执行成功, {rows} 行 (mode={plan.mode})",
                   detail={
                       "rows_count": rows,
                       "columns": list(df.columns.tolist()) if df is not None else [],
                       "mode": plan.mode,
                       "engine_trace": engine_result.get("trace", []),
                   })

        query_result = {
            "success": True,
            "data": data_list,
            "rows_count": rows,
            "sql": active_sql,
            "source": "execution_engine",
            "engine_trace": engine_result.get("trace", []),
        }

        # sql_only 模式写入缓存
        if plan.mode == "sql_only":
            result_cache.set(active_sql, query_result)

        return {
            "query_result": query_result,
            "sql_error": "",
            "pipeline_trace": trace,
        }

    else:
        error_msg: str = engine_result.get("error", "Unknown execution error")
        # 判断是否为 DB 连接错误
        is_conn_err = isinstance(error_msg, str) and (
            "connection" in error_msg.lower()
            or "refused" in error_msg.lower()
            or "timeout" in error_msg.lower()
        )
        logger.warning(
            f"[data_executor] Failed ({'db_conn' if is_conn_err else 'sql'}): {error_msg}"
        )
        trace_step(trace, "data_executor", _t0,
                   summary=f"{'DB连接错误' if is_conn_err else '执行失败'}: {error_msg[:60]}",
                   status="error",
                   detail={"error": error_msg, "sql": active_sql[:200], "mode": plan.mode})

        result_payload: dict = {
            "query_result": {
                "success": False, "data": [], "rows_count": 0,
                "sql": active_sql, "error": error_msg,
            },
            "pipeline_trace": trace,
        }
        if is_conn_err:
            result_payload["db_error"] = error_msg
            result_payload["sql_error"] = ""
        else:
            result_payload["sql_error"] = error_msg
        return result_payload
