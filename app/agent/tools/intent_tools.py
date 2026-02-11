"""
意图识别 Tool — 封装现有 IntentRecognizer
"""

import logging
from langchain_core.tools import tool
from app.services.intent_recognizer import IntentRecognizer
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)

# 延迟初始化的全局实例
_recognizer = None


def _get_recognizer() -> IntentRecognizer:
    global _recognizer
    if _recognizer is None:
        _recognizer = IntentRecognizer(llm_provider=get_llm_provider())
    return _recognizer


@tool
def classify_intent(user_input: str) -> dict:
    """Analyze user natural language input and classify the intent.
    Returns intent type, entities, and confidence score."""
    try:
        recognizer = _get_recognizer()
        result = recognizer.recognize(user_input)
        return result
    except Exception as e:
        logger.error(f"Intent classification error: {e}")
        return {
            "intent": "direct_query",
            "confidence": 0.3,
            "entities": {},
            "error": str(e),
        }
