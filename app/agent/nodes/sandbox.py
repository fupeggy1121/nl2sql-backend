"""
Sandbox — 安全执行 DataProcessor 后处理步骤

校验步骤：
1. operation 必须在 ALLOWED_OPERATIONS 白名单内
2. params 只允许基本类型（str/int/float/bool/list/dict），禁止嵌套函数/模块引用
3. 执行超时 10s，DataFrame 行数上限 100000
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

import pandas as pd

from app.agent.nodes.data_processor import DataProcessor, ALLOWED_OPERATIONS

logger = logging.getLogger(__name__)

MAX_ROWS = 100_000
TIMEOUT_SECONDS = 10


class SandboxError(Exception):
    pass


def validate_postprocess_steps(steps: List[Dict[str, Any]]) -> None:
    """校验后处理步骤列表，抛出 SandboxError 表示不合法。"""
    for step in steps:
        op = step.get("operation", "")
        if op not in ALLOWED_OPERATIONS:
            raise SandboxError(
                f"不允许的操作: '{op}'，合法操作: {sorted(ALLOWED_OPERATIONS)}"
            )
        _validate_params(step.get("params", {}))


def _validate_params(params: Any, depth: int = 0) -> None:
    """递归校验 params，禁止函数对象、模块引用等危险类型。"""
    if depth > 5:
        raise SandboxError("params 嵌套层级过深（最大 5 层）")
    if isinstance(params, (str, int, float, bool, type(None))):
        return
    if isinstance(params, list):
        for item in params:
            _validate_params(item, depth + 1)
        return
    if isinstance(params, dict):
        for k, v in params.items():
            if not isinstance(k, str):
                raise SandboxError(f"params key 必须是字符串，got {type(k).__name__}")
            _validate_params(v, depth + 1)
        return
    raise SandboxError(f"params 包含不允许的类型: {type(params).__name__}")


def execute_postprocess(
    df: pd.DataFrame,
    steps: List[Dict[str, Any]],
) -> pd.DataFrame:
    """
    安全执行后处理步骤列表。
    每步操作都调用 DataProcessor 的对应静态方法。
    """
    if len(df) > MAX_ROWS:
        raise SandboxError(
            f"DataFrame 行数 {len(df)} 超过上限 {MAX_ROWS}，请在 SQL 层先过滤"
        )

    # 前置校验（全量，失败快速中止）
    validate_postprocess_steps(steps)

    processor = DataProcessor()
    t0 = time.time()

    for step in steps:
        if time.time() - t0 > TIMEOUT_SECONDS:
            raise SandboxError(f"后处理执行超时（>{TIMEOUT_SECONDS}s）")

        op = step["operation"]
        params = step.get("params", {})
        logger.info(f"[sandbox] executing {op} params={params}")

        method = getattr(processor, op)
        try:
            df = method(df, **params)
        except SandboxError:
            raise
        except Exception as e:
            raise SandboxError(f"执行 {op} 失败: {e}") from e

        logger.info(f"[sandbox] {op} done, shape={df.shape}")

    return df
