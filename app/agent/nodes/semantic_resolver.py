"""
semantic_resolver — 语义解析节点 (Phase 3: 本体引擎集成)

在 intent_router → query_planner 之间插入，职责：
  1. 从用户输入提取关键词 → 匹配本体类
  2. 发现类间路径 → 翻译为物理 JOIN 条件
  3. 识别语义值 → 映射为 SQL 过滤条件
  4. 匹配业务规则
  5. 将 SemanticContext 注入 AgentState.semantic_context

设计原则：
  - 纯 Python 确定性规则引擎，0 LLM 调用
  - 快速（< 5ms）、稳定、可测试
  - 失败时 graceful fallback：写入空 {} 而不阻塞流程
"""

import logging
import re
import time
from typing import Dict, Any

from app.agent.state import AgentState
from app.agent.trace import trace_step
from app.agent.cache import semantic_cache

logger = logging.getLogger(__name__)

# 通用限定词，出现在"XX站点"/"XX设备"中时不作为实体名过滤
_GENERIC_QUALIFIERS = {"工艺", "生产", "所有", "各", "每个", "全部", "某", "该", "此", "其他", "任意"}
# 常见查询动词前缀，提取实体名时需去除
_QUERY_VERB_PREFIXES = ["查询", "统计", "获取", "计算", "显示", "查看", "对比", "比较", "查找", "搜索", "分析"]


def _extract_station_qualifier(user_input: str) -> str:
    """
    从用户输入中提取站点限定词。
    例: "查询包装站点的在制数量"    → "包装"
        "颗粒检测站点的良率"        → "颗粒检测"
        "统计双面研磨03站点的WIP"   → "双面研磨"
        "查询所有站点的在制数量"    → ""（通用词，跳过）
    """
    # 抓取若干 CJK/数字 字符后跟 "站点|工站" 的片段（允许中间有数字如"双面研磨03"）
    m = re.search(r'([\u4e00-\u9fff][\u4e00-\u9fff\d]*)(站点|工站)', user_input)
    if not m:
        return ""
    qualifier = m.group(1)
    # 去掉已知动词前缀（优先匹配最长）
    for verb in sorted(_QUERY_VERB_PREFIXES, key=len, reverse=True):
        if qualifier.startswith(verb):
            qualifier = qualifier[len(verb):]
            break
    # 去掉尾部数字/英文（如 "双面研磨03" → "双面研磨"）注意：\w 在 Python unicode 模式下包含 CJK，需用 ASCII 范围
    qualifier = re.sub(r'[0-9a-zA-Z]+$', '', qualifier).strip()
    if not qualifier or qualifier in _GENERIC_QUALIFIERS or len(qualifier) < 2:
        return ""
    return qualifier


def _inject_entity_filters(sql: str, ctx: Any, user_input: str) -> str:
    """
    从用户输入中提取实体名限定词，注入到 SQL 模板的 {station_filter} 等占位符中。

    当前支持：
      - stations 表：从 "XX站点" / "XX工站" 中提取 XX，生成 s.name LIKE '%XX%'

    如查询未指定特定实体（如"所有站点"），占位符替换为空字符串，SQL 返回全量数据。
    """
    # ── stations 实体过滤 ──────────────────────────────────────────────
    station_filter = ""
    has_station_class = any(
        getattr(mc, "physical_table", None) == "stations"
        for mc in getattr(ctx, "matched_classes", [])
    )
    if has_station_class:
        qualifier = _extract_station_qualifier(user_input)
        if qualifier:
            station_filter = f"AND s.name LIKE '%{qualifier}%' "
            logger.info(f"[semantic_resolver] Injecting station filter: {station_filter.strip()}")

    # 替换占位符（没有占位符也无副作用）
    sql = sql.replace("{station_filter}", station_filter)
    return sql


def semantic_resolver_node(state: AgentState) -> Dict[str, Any]:
    """
    语义解析节点。

    输入: user_input, resolved_input, is_followup
    输出: semantic_context (dict)
    """
    user_input = state.get("user_input", "")
    resolved_input = state.get("resolved_input", "") or user_input
    is_followup = state.get("is_followup", False)

    # 追问时使用消解后的输入
    effective_input = resolved_input if is_followup else user_input

    if not effective_input:
        logger.warning("[semantic_resolver] Empty input, skipping")
        return {"semantic_context": {}}

    # ── B2: 语义缓存查找（追问不使用缓存，避免上下文依赖）──
    _cache_key = effective_input
    _cache_hit = False
    if not is_followup:
        _cached_ctx = semantic_cache.get(_cache_key)
        if _cached_ctx is not None:
            _cache_hit = True
            logger.info(f"[semantic_resolver] Cache HIT for: {effective_input[:60]}")
            # 构建返回：不需要 trace，直接返回缓存值
            trace = list(state.get("pipeline_trace", []))
            t0_cache = time.perf_counter()
            trace_step(trace, "semantic_resolver", t0_cache, summary=(
                f"[缓存] " + _cached_ctx.get("_summary", "")
            ), detail={
                "cache_hit": True,
                "matched_classes": _cached_ctx.get("matched_classes", []),
                "physical_tables": _cached_ctx.get("physical_tables", []),
                "business_rules": _cached_ctx.get("business_rules", []),
            })
            extra: Dict[str, Any] = {}
            if _cached_ctx.get("_fast_path"):
                extra["sql"] = _cached_ctx["_fast_sql"]
                extra["fast_path"] = True
                extra["fast_sql_source"] = _cached_ctx.get("_fast_sql_source", "business_rule")
            return {"semantic_context": _cached_ctx, "pipeline_trace": trace, **extra}

    try:
        t0 = time.perf_counter()

        from app.ontology.context_builder import build_semantic_context

        ctx = build_semantic_context(effective_input)
        ctx_dict = ctx.to_dict()

        elapsed_ms = (time.perf_counter() - t0) * 1000
        n_classes = len(ctx.matched_classes)
        n_joins = len(ctx.joins)
        n_filters = len(ctx.filters)
        n_rules = len(ctx.business_rules)
        tables = ctx.physical_tables

        logger.info(
            f"[semantic_resolver] Resolved in {elapsed_ms:.1f}ms — "
            f"classes={n_classes}, joins={n_joins}, filters={n_filters}, "
            f"rules={n_rules}, tables={tables}"
        )

        # ── B1: Fast Path 检测 — 业务规则自带 SQL 模板 ──
        fast_path = False
        fast_sql = ""
        fast_sql_source = ""
        for rule in ctx.business_rules:
            if rule.physical_sql_template:
                # 若规则定义了触发关键词，用户输入必须包含其中至少一个
                trigger_kws = rule.trigger_keywords if rule.trigger_keywords else []
                if trigger_kws and not any(kw in effective_input for kw in trigger_kws):
                    logger.info(
                        f"[semantic_resolver] Skip fast path for rule '{rule.id}': "
                        f"trigger keywords {trigger_kws} not matched in query '{effective_input[:40]}'"
                    )
                    continue
                fast_path = True
                # 注入实体过滤条件（如"包装站点" → AND s.name LIKE '%包装%'）
                fast_sql = _inject_entity_filters(rule.physical_sql_template, ctx, effective_input)
                fast_sql_source = f"business_rule:{rule.id}"
                logger.info(
                    f"[semantic_resolver] Fast Path activated by rule '{rule.id}': "
                    f"{fast_sql[:80]}..."
                )
                break  # 取第一个匹配规则

        # ── Pipeline Trace ──
        trace = list(state.get("pipeline_trace", []))
        fast_note = " [★快速通道]" if fast_path else ""
        trace_step(trace, "semantic_resolver", t0, summary=(
            f"匹配 {n_classes} 个本体类, {n_joins} 个JOIN, "
            f"{n_filters} 个过滤条件, 物理表: {tables}{fast_note}"
        ), detail={
            "matched_classes": ctx_dict.get("matched_classes", []),
            "joins": ctx_dict.get("joins", []),
            "filters": ctx_dict.get("filters", []),
            "business_rules": ctx_dict.get("business_rules", []),
            "physical_tables": tables,
            "fast_path": fast_path,
            **({"+fast_sql_source": fast_sql_source} if fast_path else {}),
        })

        # ── B2: 写入语义缓存（追问不缓存）──
        # 将 fast_path 信息一并存进缓存，方便缓存命中时知道是否快速通道
        if not is_followup:
            _summary = (
                f"匹配 {n_classes} 个本体类, {n_joins} 个JOIN, "
                f"{n_filters} 个过滤条件, 物理表: {tables}{fast_note}"
            )
            ctx_dict["_summary"] = _summary
            ctx_dict["_fast_path"] = fast_path
            ctx_dict["_fast_sql"] = fast_sql
            ctx_dict["_fast_sql_source"] = fast_sql_source
            semantic_cache.set(_cache_key, ctx_dict)

        result: Dict[str, Any] = {"semantic_context": ctx_dict, "pipeline_trace": trace}
        if fast_path:
            result["sql"] = fast_sql
            result["fast_path"] = True
            result["fast_sql_source"] = fast_sql_source
        return result

    except Exception as e:
        logger.error(f"[semantic_resolver] Failed: {e}", exc_info=True)
        # Graceful fallback — 不阻塞后续节点
        trace = list(state.get("pipeline_trace", []))
        trace_step(trace, "semantic_resolver", t0, summary=f"语义解析失败: {e}", status="error")
        return {"semantic_context": {}, "pipeline_trace": trace}
