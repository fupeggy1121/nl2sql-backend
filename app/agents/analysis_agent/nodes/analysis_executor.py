"""
analysis_executor 节点

调用 AnalysisEngine 执行选定的分析方法。
"""

from __future__ import annotations

import io
import logging

import pandas as pd

from app.agents.analysis_agent.state import AnalysisState
from app.analytics.engine import AnalysisEngine
import app.analytics.methods  # noqa: F401 — 触发方法注册

logger = logging.getLogger(__name__)


def analysis_executor_node(state: AnalysisState) -> dict:
    """
    节点：分析执行。

    输入: dataframe_json, suggested_method, method_params
    输出: analysis_success, analysis_summary, analysis_data, analysis_charts, analysis_error
    """
    method = state.get("suggested_method", "descriptive")
    params = state.get("method_params") or {}

    # metric_compute 需要原始数据（NULL 有业务含义，不能被预处理器 drop 掉）
    if method == "metric_compute":
        df_json = state.get("raw_dataframe_json") or state.get("dataframe_json", "{}")
    else:
        df_json = state.get("dataframe_json", "{}")

    if not df_json or df_json == "{}":
        return {
            "analysis_success": False,
            "analysis_summary": "",
            "analysis_data": {},
            "analysis_charts": [],
            "analysis_error": "数据为空，无法执行分析",
        }

    try:
        # convert_dates=False 防止数值列（如 process_code=8200）被误判为日期
        df = pd.read_json(io.StringIO(df_json), orient="records", convert_dates=False)
    except Exception as e:
        return {
            "analysis_success": False,
            "analysis_summary": "",
            "analysis_data": {},
            "analysis_charts": [],
            "analysis_error": f"DataFrame 反序列化失败: {e}",
        }

    logger.info(f"[analysis_executor] method={method}, shape={df.shape}")
    result = AnalysisEngine.run(method, df, params)

    return {
        "analysis_success": result.success,
        "analysis_summary": result.summary or "",
        "analysis_data": result.data or {},
        "analysis_charts": result.charts or [],
        "analysis_error": result.error,
    }
