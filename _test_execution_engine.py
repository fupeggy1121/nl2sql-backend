"""
ExecutionEngine 单元测试（无需后端，使用 mock DB 适配器）

测试范围：
  1. sql_only  — 向后兼容的单条 SQL 执行
  2. multi_sql_merge — 同名 key / 异名 key
  3. sql_then_python — pivot / drop_nulls
  4. sandbox 白名单拦截
  5. sandbox 参数校验
  6. sandbox 行数上限
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import pytest

from app.agent.nodes.execution_engine import (
    ExecutionEngine,
    ExecutionPlan,
    SqlStep,
    MergeStep,
    PostprocessStep,
)
from app.agent.nodes.sandbox import (
    SandboxError,
    validate_postprocess_steps,
    execute_postprocess,
)


# ── Mock DB 适配器 ────────────────────────────────────────────────────────────

class MockDB:
    """用预设 DataFrame 响应 SQL 调用的测试适配器。"""

    def __init__(self, responses: dict):
        """responses: {sql_keyword: pd.DataFrame}  按关键字匹配"""
        self._responses = responses

    def execute(self, sql: str) -> pd.DataFrame:
        for keyword, df in self._responses.items():
            if keyword.lower() in sql.lower():
                return df.copy()
        raise ValueError(f"MockDB: no response for SQL: {sql[:80]}")


# ── 准备测试数据 ──────────────────────────────────────────────────────────────

def make_lot_df():
    return pd.DataFrame({
        "lot_id": ["L001", "L002", "L003"],
        "product_name": ["GaAs-A", "GaAs-B", "GaAs-A"],
        "wafer_count": [25, 50, 25],
    })


def make_process_df():
    return pd.DataFrame({
        "current_lot_id": ["L001", "L002", "L004"],
        "process_code": ["PROC-X", "PROC-Y", "PROC-Z"],
        "station": ["ST-01", "ST-02", "ST-03"],
    })


def make_wide_df():
    return pd.DataFrame({
        "date": ["2024-01-01", "2024-01-01", "2024-01-02"],
        "product": ["A", "B", "A"],
        "value": [100.0, 200.0, 110.0],
    })


def make_nullable_df():
    return pd.DataFrame({
        "lot_id": ["L001", None, "L003"],
        "value": [1.0, 2.0, None],
    })


# ── 测试 1: sql_only 向后兼容 ─────────────────────────────────────────────────

def test_sql_only_basic():
    db = MockDB({"lot": make_lot_df()})
    engine = ExecutionEngine(db)
    plan = ExecutionPlan.sql_only_fallback("SELECT * FROM lot_table")
    result = engine.run(plan)

    assert result["success"] is True
    assert result["rows_count"] == 3
    assert isinstance(result["data"], pd.DataFrame)
    assert "lot_id" in result["data"].columns
    assert len(result["trace"]) == 1
    print("[PASS] test_sql_only_basic")


def test_sql_only_from_dict():
    db = MockDB({"lot": make_lot_df()})
    engine = ExecutionEngine(db)
    plan = ExecutionPlan.from_dict({
        "mode": "sql_only",
        "sqls": [{"id": "s1", "sql": "SELECT * FROM lot_table", "purpose": "test"}],
        "primary_result": "s1",
    })
    result = engine.run(plan)

    assert result["success"] is True
    assert result["rows_count"] == 3
    print("[PASS] test_sql_only_from_dict")


# ── 测试 2: multi_sql_merge 同名 key ─────────────────────────────────────────

def test_multi_sql_merge_same_key():
    """两个 SQL 结果用同名列 lot_id 合并。"""
    lot_df = pd.DataFrame({
        "lot_id": ["L001", "L002"],
        "product": ["A", "B"],
    })
    wip_df = pd.DataFrame({
        "lot_id": ["L001", "L002"],
        "station": ["ST-01", "ST-02"],
    })
    db = MockDB({"lot_base": lot_df, "lot_wip": wip_df})
    engine = ExecutionEngine(db)

    plan = ExecutionPlan.from_dict({
        "mode": "multi_sql_merge",
        "sqls": [
            {"id": "s1", "sql": "SELECT * FROM lot_base", "purpose": "基础信息"},
            {"id": "s2", "sql": "SELECT * FROM lot_wip", "purpose": "WIP状态"},
        ],
        "merges": [
            {"id": "m1", "left": "s1", "right": "s2", "on": ["lot_id"], "how": "inner"},
        ],
        "primary_result": "m1",
    })
    result = engine.run(plan)

    assert result["success"] is True
    assert result["rows_count"] == 2
    df = result["data"]
    assert "product" in df.columns
    assert "station" in df.columns
    assert "lot_id" in df.columns
    # 合并后不应出现 lot_id_r 之类的重复键
    assert "lot_id_r" not in df.columns
    print("[PASS] test_multi_sql_merge_same_key")


def test_multi_sql_merge_different_key_names():
    """左表 lot_id，右表 current_lot_id，使用异名 key 合并。"""
    lot_df = pd.DataFrame({
        "lot_id": ["L001", "L002", "L003"],
        "product": ["A", "B", "A"],
    })
    process_df = pd.DataFrame({
        "current_lot_id": ["L001", "L002", "L004"],
        "process_code": ["PROC-X", "PROC-Y", "PROC-Z"],
    })
    db = MockDB({"lot_base": lot_df, "current_lot": process_df})
    engine = ExecutionEngine(db)

    plan = ExecutionPlan.from_dict({
        "mode": "multi_sql_merge",
        "sqls": [
            {"id": "s1", "sql": "SELECT * FROM lot_base", "purpose": "lot"},
            {"id": "s2", "sql": "SELECT * FROM current_lot", "purpose": "process"},
        ],
        "merges": [
            {
                "id": "m1", "left": "s1", "right": "s2",
                "on": [{"left": "lot_id", "right": "current_lot_id"}],
                "how": "inner",
            },
        ],
        "primary_result": "m1",
    })
    result = engine.run(plan)

    assert result["success"] is True
    assert result["rows_count"] == 2   # L001, L002 匹配
    df = result["data"]
    # 右表的 key 列应被删除（避免重复）
    assert "current_lot_id" not in df.columns
    assert "lot_id" in df.columns
    assert "process_code" in df.columns
    print("[PASS] test_multi_sql_merge_different_key_names")


# ── 测试 3: sql_then_python — pivot ─────────────────────────────────────────

def test_sql_then_python_pivot():
    db = MockDB({"wide": make_wide_df()})
    engine = ExecutionEngine(db)

    plan = ExecutionPlan.from_dict({
        "mode": "sql_then_python",
        "sqls": [{"id": "s1", "sql": "SELECT * FROM wide_table", "purpose": "日报数据"}],
        "postprocess": [
            {
                "operation": "pivot",
                "params": {
                    "index": "date",
                    "columns": "product",
                    "values": "value",
                    "aggfunc": "first",
                },
            }
        ],
        "primary_result": "s1",
    })
    result = engine.run(plan)

    assert result["success"] is True
    df = result["data"]
    # pivot 后 date 应作为列而非 index
    assert "date" in df.columns
    # 产品名称应成为列
    assert "A" in df.columns
    assert "B" in df.columns
    print("[PASS] test_sql_then_python_pivot")


def test_sql_then_python_drop_nulls():
    db = MockDB({"nullable": make_nullable_df()})
    engine = ExecutionEngine(db)

    plan = ExecutionPlan.from_dict({
        "mode": "sql_then_python",
        "sqls": [{"id": "s1", "sql": "SELECT * FROM nullable_table", "purpose": "含空值"}],
        "postprocess": [
            {"operation": "drop_nulls", "params": {}},
        ],
        "primary_result": "s1",
    })
    result = engine.run(plan)

    assert result["success"] is True
    df = result["data"]
    assert len(df) == 1   # 只有 L001 两列都有值
    assert df.iloc[0]["lot_id"] == "L001"
    print("[PASS] test_sql_then_python_drop_nulls")


# ── 测试 4: sandbox 白名单拦截非法操作 ────────────────────────────────────────

def test_sandbox_whitelist_blocks_illegal_op():
    df = make_lot_df()
    with pytest.raises(SandboxError, match="不允许的操作"):
        execute_postprocess(df, [{"operation": "eval", "params": {}}])
    print("[PASS] test_sandbox_whitelist_blocks_illegal_op")


def test_sandbox_whitelist_blocks_exec():
    df = make_lot_df()
    with pytest.raises(SandboxError, match="不允许的操作"):
        execute_postprocess(df, [{"operation": "exec", "params": {"code": "import os"}}])
    print("[PASS] test_sandbox_whitelist_blocks_exec")


# ── 测试 5: sandbox 参数类型校验 ─────────────────────────────────────────────

def test_sandbox_param_rejects_callable():
    """params 不应允许包含函数对象。"""
    df = make_lot_df()
    with pytest.raises(SandboxError):
        validate_postprocess_steps([
            {"operation": "drop_nulls", "params": {"subset": lambda x: x}}
        ])
    print("[PASS] test_sandbox_param_rejects_callable")


def test_sandbox_param_deep_nesting():
    """超过 5 层嵌套应抛出 SandboxError。"""
    deep = {"a": {"b": {"c": {"d": {"e": {"f": "too deep"}}}}}}
    with pytest.raises(SandboxError, match="嵌套层级过深"):
        validate_postprocess_steps([
            {"operation": "drop_nulls", "params": deep}
        ])
    print("[PASS] test_sandbox_param_deep_nesting")


# ── 测试 6: sandbox 行数上限 ─────────────────────────────────────────────────

def test_sandbox_row_limit():
    import numpy as np
    large_df = pd.DataFrame({"x": np.arange(100_001)})
    with pytest.raises(SandboxError, match="超过上限"):
        execute_postprocess(large_df, [{"operation": "drop_nulls", "params": {}}])
    print("[PASS] test_sandbox_row_limit")


# ── 测试 7: ExecutionEngine 错误传播 ─────────────────────────────────────────

def test_execution_engine_propagates_db_error():
    """DB 执行失败时 Engine 应返回 success=False。"""
    class FailDB:
        def execute(self, sql):
            raise RuntimeError("connection refused")

    engine = ExecutionEngine(FailDB())
    plan = ExecutionPlan.sql_only_fallback("SELECT 1")
    result = engine.run(plan)

    assert result["success"] is False
    assert "connection refused" in result["error"]
    print("[PASS] test_execution_engine_propagates_db_error")


# ── 测试 8: python_orchestrated 降级 ─────────────────────────────────────────

def test_python_orchestrated_fallback():
    """python_orchestrated 应降级为 multi_sql_merge 并成功执行。"""
    db = MockDB({"lot": make_lot_df()})
    engine = ExecutionEngine(db)
    plan = ExecutionPlan.from_dict({
        "mode": "python_orchestrated",
        "sqls": [{"id": "s1", "sql": "SELECT * FROM lot_table", "purpose": "test"}],
        "primary_result": "s1",
    })
    result = engine.run(plan)

    assert result["success"] is True
    assert result["rows_count"] == 3
    print("[PASS] test_python_orchestrated_fallback")


# ── 入口 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_sql_only_basic,
        test_sql_only_from_dict,
        test_multi_sql_merge_same_key,
        test_multi_sql_merge_different_key_names,
        test_sql_then_python_pivot,
        test_sql_then_python_drop_nulls,
        test_sandbox_whitelist_blocks_illegal_op,
        test_sandbox_whitelist_blocks_exec,
        test_sandbox_param_rejects_callable,
        test_sandbox_param_deep_nesting,
        test_sandbox_row_limit,
        test_execution_engine_propagates_db_error,
        test_python_orchestrated_fallback,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"[FAIL] {t.__name__}: {e}")

    print(f"\n{'='*50}")
    print(f"Results: {passed} PASS, {failed} FAIL / {len(tests)} total")
    sys.exit(0 if failed == 0 else 1)
