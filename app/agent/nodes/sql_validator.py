"""
sql_validator — SQL 验证节点

在 SQL 执行前进行结构化验证：
1. 检查表名/列名是否存在于真实 Schema
2. 如果发现错误，直接修正（不走重试循环，减少 LLM 调用）
3. 如果无法自动修正，将问题写入 state 供 self-correction 使用
"""

import re
import logging
from app.agent.state import AgentState
from app.agent.tools.schema_tools import validate_sql, _find_closest_table, _get_schema_metadata

logger = logging.getLogger(__name__)


def sql_validator_node(state: AgentState) -> dict:
    """
    SQL 验证节点。

    输入: sql
    输出: sql (可能被修正), sql_validation (验证详情)

    放在 sql_generator 和 data_executor 之间，减少无意义的执行失败。
    """
    sql = state.get("sql", "")

    if not sql:
        logger.warning("[sql_validator] No SQL to validate")
        return {}

    # Safety net: strip markdown code fences if present
    clean_sql = sql.strip()
    if clean_sql.startswith("```"):
        first_nl = clean_sql.find("\n")
        if first_nl != -1:
            clean_sql = clean_sql[first_nl + 1:]
        if clean_sql.rstrip().endswith("```"):
            clean_sql = clean_sql.rstrip()[:-3]
        clean_sql = clean_sql.strip()
        if clean_sql != sql:
            logger.info(f"[sql_validator] Stripped markdown fences from SQL")
            sql = clean_sql

    logger.info(f"[sql_validator] Validating: {sql[:100]}...")

    # 调用 validate_sql 工具
    validation = validate_sql.invoke({"sql": sql})

    if validation["valid"]:
        logger.info("[sql_validator] ✅ SQL valid")
        if validation.get("warnings"):
            logger.info(f"[sql_validator] Warnings: {validation['warnings']}")
        # If we cleaned fences, return the cleaned SQL
        original_sql = state.get("sql", "")
        if sql != original_sql:
            return {"sql": sql}
        return {}

    # ── SQL 无效，尝试自动修正 ──
    logger.warning(f"[sql_validator] ❌ Validation errors: {validation['errors']}")

    corrected_sql = _auto_correct_sql(sql, validation)

    if corrected_sql and corrected_sql != sql:
        # 再验证一次修正后的 SQL
        re_validation = validate_sql.invoke({"sql": corrected_sql})
        if re_validation["valid"]:
            logger.info(f"[sql_validator] ✅ Auto-corrected SQL: "
                        f"{corrected_sql[:100]}...")
            return {
                "sql": corrected_sql,
                "sql_confidence": max(
                    state.get("sql_confidence", 0.0) - 0.1, 0.3
                ),
            }
        else:
            logger.warning("[sql_validator] Auto-correction failed re-validation")

    # 无法自动修正 — 将验证信息写入 state 供 self-correction 使用
    error_details = "; ".join(validation["errors"])
    if validation.get("missing_tables"):
        schema = _get_schema_metadata()
        suggestions = []
        for mt in validation["missing_tables"]:
            closest = _find_closest_table(mt, schema["tables"])
            if closest:
                suggestions.append(f"'{mt}' → try '{closest}'")
        if suggestions:
            error_details += f". Table suggestions: {', '.join(suggestions)}"

    logger.info(f"[sql_validator] Writing validation errors to state for "
                f"self-correction: {error_details[:200]}")

    return {
        "sql_error": f"[VALIDATION] {error_details}",
    }


def _auto_correct_sql(sql: str, validation: dict) -> str:
    """
    尝试自动修正常见的 SQL 问题。

    目前支持:
    1. 表名替换（missing_tables → closest match）
    2. 移除 schema 前缀（public.xxx → xxx）
    """
    corrected = sql
    schema = _get_schema_metadata()

    # 1. 修正缺失的表名
    for missing_table in validation.get("missing_tables", []):
        closest = _find_closest_table(missing_table, schema["tables"])
        if closest:
            # 用正则全词替换
            corrected = re.sub(
                rf'\b{re.escape(missing_table)}\b',
                closest,
                corrected,
                flags=re.IGNORECASE,
            )
            logger.info(f"[sql_validator] Replaced table: "
                        f"{missing_table} → {closest}")

    # 2. 移除 public. 前缀（Supabase 不需要）
    corrected = re.sub(r'\bpublic\.', '', corrected, flags=re.IGNORECASE)

    # 3. 修正 COUNT(*) 的常见错误写法
    corrected = re.sub(r'\bCOUNT\s*\(\s*\)', 'COUNT(*)', corrected)

    return corrected
