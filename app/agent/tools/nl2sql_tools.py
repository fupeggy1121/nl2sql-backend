"""
NL2SQL Tools — 封装现有 EnhancedNL2SQLConverter
"""

import logging
from langchain_core.tools import tool
from app.services.nl2sql_enhanced import get_enhanced_nl2sql_converter

logger = logging.getLogger(__name__)


def _strip_sql_fences(sql: str) -> str:
    """Strip markdown code fences (```sql ... ```) from LLM output."""
    s = sql.strip()
    # Remove opening fence
    if s.startswith("```"):
        # Find end of first line
        first_newline = s.find("\n")
        if first_newline != -1:
            s = s[first_newline + 1:]
        else:
            s = s[3:]  # Just remove ```
    # Remove closing fence
    if s.rstrip().endswith("```"):
        s = s.rstrip()[:-3]
    return s.strip()


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
                f"请避免相同的错误，生成正确的 SQL。\n"
                f"仅输出纯 SQL 语句，不要包含 ```sql 等 markdown 代码块标记。"
            )
            sql = converter.convert(corrected_nl)
        else:
            sql = converter.convert(natural_language)

        if sql:
            # Strip markdown code fences that LLM may include
            sql = _strip_sql_fences(sql)
            logger.info(f"SQL generated: {sql[:100]}...")
            return sql
        else:
            return ""
    except Exception as e:
        logger.error(f"SQL generation error: {e}")
        return ""
