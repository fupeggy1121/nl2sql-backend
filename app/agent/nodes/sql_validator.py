"""
sql_validator — SQL 验证节点

在 SQL 执行前进行结构化验证：
1. 检查表名/列名是否存在于真实 Schema
2. 如果发现错误，直接修正（不走重试循环，减少 LLM 调用）
3. 如果无法自动修正，将问题写入 state 供 self-correction 使用
"""

import re
import logging
import time
from app.agent.state import AgentState
from app.agent.tools.schema_tools import validate_sql, _find_closest_table, _get_schema_metadata
from app.agent.trace import trace_step

logger = logging.getLogger(__name__)


def sql_validator_node(state: AgentState) -> dict:
    """
    SQL 验证节点。

    输入: sql
    输出: sql (可能被修正), sql_validation (验证详情)

    放在 sql_generator 和 data_executor 之间，减少无意义的执行失败。
    """
    _t0 = time.perf_counter()
    sql = state.get("sql", "")

    # approved_sql 模式：SQL 在上一轮 /api/v1/query 时已经过验证，前端 Review 后才提交
    # 直接跳过重复验证，节省一次 schema 检查开销
    # 但如果前端对 SQL 进行了人工编辑（sql_edited=True），则必须重新验证
    if state.get("approved_sql") and not state.get("sql_error") and not state.get("sql_edited"):
        logger.info("[sql_validator] approved_sql 模式: 跳过验证，直接转交 data_executor")
        trace = list(state.get("pipeline_trace", []))
        trace_step(trace, "sql_validator", _t0,
                   summary="approved_sql 模式: 跳过验证（SQL 已在上一轮 query 中验证）",
                   detail={"approved_sql_mode": True, "skipped": True})
        return {
            "sql_validation": {"valid": True, "skipped": True, "reason": "approved_sql_mode"},
            "pipeline_trace": trace,
        }

    if not sql:
        logger.warning("[sql_validator] No SQL to validate")
        return {}

    # ── 路径B: decomposed multi_sql — 对每条子查询独立验证 ──
    execution_plan = state.get("execution_plan") or {}
    if execution_plan.get("_decomposed"):
        sub_sqls = [
            (s["id"], s["sql"])
            for s in execution_plan.get("sqls", [])
            if s.get("sql")
        ]
        errors = []
        for sid, sub_sql in sub_sqls:
            clean = sub_sql.strip()
            if clean.startswith("```"):
                first_nl = clean.find("\n")
                clean = clean[first_nl + 1:].rstrip().rstrip("```").strip()
            v = validate_sql.invoke({"sql": clean})
            if not v["valid"]:
                errors.append(f"[{sid}] {'; '.join(v['errors'])}")
        trace = list(state.get("pipeline_trace", []))
        if errors:
            error_msg = " | ".join(errors)
            logger.warning(f"[sql_validator] decomposed multi_sql validation errors: {error_msg}")
            trace_step(trace, "sql_validator", _t0,
                       summary=f"multi_sql 验证失败 ({len(errors)}个子查询)",
                       status="error", detail={"errors": errors})
            return {"sql_error": f"[VALIDATION] {error_msg}", "pipeline_trace": trace}
        logger.info(f"[sql_validator] decomposed multi_sql: {len(sub_sqls)} sub-queries all valid")
        trace_step(trace, "sql_validator", _t0,
                   summary=f"multi_sql 验证通过 ({len(sub_sqls)} 个子查询)",
                   detail={"valid": True, "sub_queries": len(sub_sqls)})
        return {"pipeline_trace": trace}

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
        # ── Pipeline Trace ──
        trace = list(state.get("pipeline_trace", []))
        trace_step(trace, "sql_validator", _t0, summary=(
            "SQL 验证通过" + (f" (警告: {len(validation.get('warnings', []))})" if validation.get('warnings') else "")
        ), detail={
            "valid": True,
            "warnings": validation.get("warnings", []),
        })
        # If we cleaned fences, return the cleaned SQL
        original_sql = state.get("sql", "")
        result = {"pipeline_trace": trace}
        if sql != original_sql:
            result["sql"] = sql
        return result

    # ── SQL 无效，尝试自动修正 ──
    logger.warning(f"[sql_validator] ❌ Validation errors: {validation['errors']}")

    corrected_sql = _auto_correct_sql(sql, validation)

    if corrected_sql and corrected_sql != sql:
        # 再验证一次修正后的 SQL
        re_validation = validate_sql.invoke({"sql": corrected_sql})
        if re_validation["valid"]:
            logger.info(f"[sql_validator] ✅ Auto-corrected SQL: "
                        f"{corrected_sql[:100]}...")
            trace = list(state.get("pipeline_trace", []))
            trace_step(trace, "sql_validator", _t0, summary="SQL 自动修正成功", detail={
                "original_sql": sql[:200],
                "corrected_sql": corrected_sql[:200],
                "errors_fixed": validation["errors"],
            })
            return {
                "sql": corrected_sql,
                "sql_confidence": max(
                    state.get("sql_confidence", 0.0) - 0.1, 0.3
                ),
                "pipeline_trace": trace,
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

    trace = list(state.get("pipeline_trace", []))
    trace_step(trace, "sql_validator", _t0, summary=f"SQL 验证失败: {error_details[:80]}",
              status="error", detail={"errors": validation["errors"], "missing_tables": validation.get("missing_tables", [])})
    return {
        "sql_error": f"[VALIDATION] {error_details}",
        "pipeline_trace": trace,
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
