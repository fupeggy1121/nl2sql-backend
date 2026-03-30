"""
preprocessor 节点

对加载的 DataFrame 执行自动预处理（缺失值处理 + 时间特征提取）。
"""

from __future__ import annotations

import io
import json
import logging

import pandas as pd

from app.agents.analysis_agent.state import AnalysisState
from app.analytics.preprocessing.pipeline import auto_preprocess

logger = logging.getLogger(__name__)


def preprocessor_node(state: AnalysisState) -> dict:
    """
    节点：数据预处理。

    输入: dataframe_json
    输出: dataframe_json (更新), preprocess_steps, preprocess_log
    """
    df_json = state.get("dataframe_json", "{}")
    if not df_json or df_json == "{}":
        return {"preprocess_steps": [], "preprocess_log": ["数据为空，跳过预处理"]}

    try:
        df = pd.read_json(io.StringIO(df_json), orient="records")
        df, logs = auto_preprocess(df)
        updated_json = df.to_json(orient="records", force_ascii=False, date_format="iso")
        steps = [s for s in logs]
        logger.info(f"[preprocessor] done, steps={len(steps)}, shape={df.shape}")
        return {
            "dataframe_json": updated_json,
            "preprocess_steps": steps,
            "preprocess_log": logs,
        }
    except Exception as e:
        logger.error(f"[preprocessor] error: {e}")
        return {"preprocess_steps": [], "preprocess_log": [f"预处理失败: {e}"]}
