"""
NL2SQL Tools — 封装现有 EnhancedNL2SQLConverter
"""

import logging
from langchain_core.tools import tool
from app.services.nl2sql_enhanced import get_enhanced_nl2sql_converter

logger = logging.getLogger(__name__)


@tool
def generate_sql(natural_language: str, error_context: str = "") -> str:
    """Generate SQL from natural language query using LLM + schema annotations.
    If error_context is provided, the LLM will attempt to fix the previous SQL error.
    Returns the generated SQL string."""
    try:
        converter = get_enhanced_nl2sql_converter()

        if error_context:
            # 自我修正模式：将错误信息注入提示
            corrected_nl = (
                f"{natural_language}\n\n"
                f"[IMPORTANT] 上一次生成的 SQL 执行失败，错误信息如下，请修正：\n"
                f"{error_context}\n"
                f"请避免相同的错误，生成正确的 SQL。"
            )
            sql = converter.convert(corrected_nl)
        else:
            sql = converter.convert(natural_language)

        if sql:
            logger.info(f"SQL generated: {sql[:100]}...")
            return sql
        else:
            return ""
    except Exception as e:
        logger.error(f"SQL generation error: {e}")
        return ""
