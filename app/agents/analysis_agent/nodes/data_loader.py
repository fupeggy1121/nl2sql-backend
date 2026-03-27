"""
data_loader 节点

从 data_source_config 加载数据到 DataFrame，
并将其 JSON 序列化存入 state（供后续节点使用）。
"""

from __future__ import annotations

import logging

from app.agents.analysis_agent.state import AnalysisState
from app.analytics.data_source import load_dataframe

logger = logging.getLogger(__name__)


def data_loader_node(state: AnalysisState) -> dict:
    """
    节点：数据加载。

    输入: data_source_config
    输出: dataframe_json, data_load_error
    """
    config = state.get("data_source_config") or {}
    logger.info(f"[data_loader] source type={config.get('type', 'unknown')}")

    try:
        df = load_dataframe(config)
        if df.empty:
            return {
                "dataframe_json": "{}",
                "data_load_error": "加载到的数据为空",
            }
        df_json = df.to_json(orient="records", force_ascii=False, date_format="iso")
        logger.info(f"[data_loader] loaded {len(df)} rows × {len(df.columns)} cols")
        return {"dataframe_json": df_json, "data_load_error": None}
    except Exception as e:
        logger.error(f"[data_loader] error: {e}")
        return {"dataframe_json": "{}", "data_load_error": str(e)}
