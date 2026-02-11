"""
Chart Tools — 封装现有 ChartRecommender
"""

import logging
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from app.services.chart_recommender import get_chart_recommender
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)

_recommender = None


def _get_recommender():
    global _recommender
    if _recommender is None:
        _recommender = get_chart_recommender(llm_provider=get_llm_provider())
    return _recommender


@tool
def recommend_chart(
    sql: str,
    data: List[Dict[str, Any]],
    natural_language: str = "",
    intent_type: str = "",
) -> dict:
    """Analyze query result data and recommend the best chart type for visualization.
    Returns dict with: type, title, xAxisField, yAxisField, seriesField, confidence, reason."""
    try:
        recommender = _get_recommender()
        intent_dict = {}
        if natural_language:
            intent_dict["natural_language"] = natural_language
        if intent_type:
            intent_dict["intent"] = intent_type
        result = recommender.recommend(sql=sql, data=data, query_intent=intent_dict)
        return result
    except Exception as e:
        logger.error(f"Chart recommendation error: {e}")
        return {
            "type": "table",
            "title": "",
            "xAxisField": None,
            "yAxisField": None,
            "seriesField": None,
            "confidence": 0.0,
            "reason": f"Error: {e}",
        }
