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
      - ProcessStation 类：从 "XX站点" / "XX工站" 中提取 XX，生成 s.name LIKE '%XX%'

    如查询未指定特定实体（如"所有站点"），占位符替换为空字符串，SQL 返回全量数据。
    """
    # ── ProcessStation 实体过滤 ──────────────────────────────────────────────────
    station_filter = ""
    has_station_class = any(
        getattr(mc, "logic_class", "") == "semi:ProcessStation"
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
    # P2: 读取 intent_router 产出的 target_class_hints
    intent_data = state.get("intent_data", {})
    target_class_hints: list = intent_data.get("target_class_hints", [])

    # 追问时使用消解后的输入
    effective_input = resolved_input if is_followup else user_input

    if not effective_input:
        logger.warning("[semantic_resolver] Empty input, skipping")
        return {"semantic_context": {}}

    # 快速路径: approved_sql 模式——SQL已确定，语义解析结果不影响SQL生成
    if state.get("approved_sql") and not state.get("sql_error"):
        trace = list(state.get("pipeline_trace", []))
        t0_skip = time.perf_counter()
        trace_step(trace, "semantic_resolver", t0_skip,
                   summary="approved_sql 模式: 跳过语义解析，SQL已确定",
                   detail={"approved_sql_mode": True, "skipped": True})
        return {"semantic_context": {}, "pipeline_trace": trace}

    # ── B2: 语义缓存查找（追问不使用缓存，避免上下文依赖）──
    # v4: 本体类版本前缀——当规则/模板发生重大变更时更新版本号可立即淘汰旧缓存
    _SEMANTIC_CACHE_VERSION = "v30"  # v30: 不良原因统计默认改用NG_all(IN 2,9)，碎片也有ng_reason
    _cache_key = f"{_SEMANTIC_CACHE_VERSION}:{effective_input}"
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
            return {"semantic_context": _cached_ctx, "pipeline_trace": trace}

    try:
        t0 = time.perf_counter()

        from app.ontology.context_builder import build_semantic_context
        from app.models.intent_slots import IntentSlots

        # Slot Filling: 从 intent_data 提取语义槽，传给 context_builder 做定向匹配
        slots_dict = intent_data.get("intent_slots", {})
        slots = IntentSlots.from_dict(slots_dict) if slots_dict else None
        if slots and (slots.subject or slots.dimension_by):
            logger.info(
                "[semantic_resolver] Using intent_slots for directed matching: "
                "subject=%s dimension_by=%s", slots.subject, slots.dimension_by
            )

        ctx = build_semantic_context(effective_input, intent_slots=slots)

        # P2: hint 增强路径 — 如果 build_semantic_context 没有匹配到物理表，
        # 且 intent_router 提供了 target_class_hints，直接从映射字典补充。
        # 注意：physical_tables 是 @property（只读），必须向 ctx.matched_classes 追加
        # MatchedClass，而不是尝试直接赋值给 physical_tables。
        if not ctx.physical_tables and target_class_hints:
            try:
                from app.ontology.mapping import get_mapping
                from app.ontology.context_builder import MatchedClass
                mapping = get_mapping()
                seen_tables: set = set()
                for hint_class in target_class_hints:
                    pt = mapping.get_physical_table(hint_class)
                    if pt and pt.table_name and pt.table_name not in seen_tables:
                        seen_tables.add(pt.table_name)
                        mc = MatchedClass(
                            keyword=hint_class,
                            logic_class=pt.logic_class,
                            label_cn=getattr(pt, "label_cn", hint_class),
                            physical_table=pt.table_name,
                            primary_key=getattr(pt, "primary_key", "id"),
                            display_column=getattr(pt, "display_column", None),
                            key_columns=list(getattr(pt, "key_columns", []) or []),
                            properties=dict(getattr(pt, "properties", {}) or {}),
                            virtual=False,
                            filter_condition=getattr(pt, "filter_condition", None),
                        )
                        ctx.matched_classes.append(mc)
                if seen_tables:
                    logger.info(
                        f"[semantic_resolver] P2 hint补充 matched_classes: "
                        f"{list(seen_tables)} (来自 target_class_hints {target_class_hints})"
                    )
            except Exception as hint_err:
                logger.warning(f"[semantic_resolver] P2 hint增强失败(非关键): {hint_err}")
        ctx_dict = ctx.to_dict()

        # P3-bridge: 将 intent_router 语义过滤器注入 semantic_context.filters
        # semantic_resolver 的关键词引擎无法识别值语义（如"可用"→status=Available）
        # intent_router 的 LLM 已识别出 semantic_filters，此处做两件事：
        #   1. 通过 value_mappings 字典尝试解析为精确的 physical_condition
        #   2. 即使 mapping 尚未完善（TODO），也注入语义提示让 sql_generator 感知
        # 仅在 semantic_resolver 自身未产生过滤条件时注入（避免重复）
        intent_sfilters = intent_data.get("semantic_filters", [])
        if intent_sfilters and not ctx_dict.get("filters"):
            injected_filters = []
            try:
                from app.ontology.mapping import get_mapping
                mapping = get_mapping()
                physical_tables_set = set(ctx_dict.get("physical_tables", []))

                for sf in intent_sfilters:
                    attr = sf.get("attribute")   # e.g. "status"
                    sv   = sf.get("semantic_value")  # e.g. "Available"
                    if not attr or not sv:
                        continue

                    # 在所有值域中查找与 (applies_to_table ∈ physical_tables, applies_to_column = attr) 匹配的映射
                    resolved_vm = None
                    resolved_domain = None
                    # 第一轮：精确匹配列名（intent LLM 识别的 attribute 与 value_mapping applies_to_column 一致）
                    for domain in mapping.list_value_domains():
                        vm = mapping.map_value(domain, sv)
                        if (vm and vm.applies_to_column == attr
                                and vm.applies_to_table in physical_tables_set):
                            resolved_vm = vm
                            resolved_domain = domain
                            break
                    # 第二轮：宽松匹配（仅验证 applies_to_table；intent LLM 常混淆列名，
                    # 如把 sub_status 写成 status，但语义值 key 是正确的）
                    if resolved_vm is None:
                        for domain in mapping.list_value_domains():
                            vm = mapping.map_value(domain, sv)
                            if vm and vm.applies_to_table in physical_tables_set:
                                logger.info(
                                    f"[semantic_resolver] P3-bridge 列名修正: "
                                    f"intent attr='{attr}' → 正确列='{vm.applies_to_column}' "
                                    f"(domain={domain}, sv={sv}, table={vm.applies_to_table})"
                                )
                                resolved_vm = vm
                                resolved_domain = domain
                                break

                    if resolved_vm:
                        pc = resolved_vm.physical_condition
                        # 过滤掉 TODO 占位符，让 sql_generator 依赖 semantic_value 语义提示
                        if pc and "TODO" in pc:
                            pc = None
                        injected_filters.append({
                            "semantic_domain": resolved_domain,
                            "semantic_value": sv,
                            "description": resolved_vm.description or f"{attr}={sv}",
                            "physical_condition": pc,
                            "physical_values": resolved_vm.physical_values,
                            "applies_to_table": resolved_vm.applies_to_table,
                            "applies_to_column": resolved_vm.applies_to_column,
                            "count_target_table": resolved_vm.count_target_table,
                            "count_target_column": resolved_vm.count_target_column,
                            "_source": "intent_semantic_filter",
                        })
                    else:
                        # 未找到 value_mapping — 注入最小语义提示（表+列+语义值）
                        # sql_generator 可据此构造合理的 WHERE 条件
                        table_hint = next(iter(physical_tables_set), None)
                        injected_filters.append({
                            "semantic_domain": "intent",
                            "semantic_value": sv,
                            "description": f"{table_hint}.{attr} 应满足语义值 {sv}（需确认物理枚举）",
                            "physical_condition": None,
                            "physical_values": None,
                            "applies_to_table": table_hint,
                            "applies_to_column": attr,
                            "count_target_table": None,
                            "count_target_column": None,
                            "_source": "intent_semantic_filter",
                        })

            except Exception as filter_err:
                logger.warning(f"[semantic_resolver] 语义过滤器注入失败(非关键): {filter_err}")

            if injected_filters:
                ctx_dict["filters"] = injected_filters
                logger.info(
                    f"[semantic_resolver] 注入 {len(injected_filters)} 个语义过滤器"
                    f"（来自 intent_data.semantic_filters）"
                )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        n_classes = len(ctx.matched_classes)
        n_joins = len(ctx.joins)
        n_filters = len(ctx_dict.get("filters", []))   # 包含注入的 intent semantic_filters
        n_rules = len(ctx.business_rules)
        tables = ctx_dict.get("physical_tables", [])

        logger.info(
            f"[semantic_resolver] Resolved in {elapsed_ms:.1f}ms — "
            f"classes={n_classes}, joins={n_joins}, filters={n_filters}, "
            f"rules={n_rules}, tables={tables}"
        )

        # ── Pipeline Trace ──
        trace = list(state.get("pipeline_trace", []))
        trace_step(trace, "semantic_resolver", t0, summary=(
            f"匹配 {n_classes} 个本体类, {n_joins} 个JOIN, "
            f"{n_filters} 个过滤条件, 物理表: {tables}"
        ), detail={
            "matched_classes": ctx_dict.get("matched_classes", []),
            "joins": ctx_dict.get("joins", []),
            "filters": ctx_dict.get("filters", []),
            "business_rules": ctx_dict.get("business_rules", []),
            "metrics": ctx_dict.get("metrics", []),
            "physical_tables": tables,
        })

        # ── 写入语义缓存（追问不缓存）──
        if not is_followup:
            _summary = (
                f"匹配 {n_classes} 个本体类, {n_joins} 个JOIN, "
                f"{n_filters} 个过滤条件, 物理表: {tables}"
            )
            ctx_dict["_summary"] = _summary
            semantic_cache.set(_cache_key, ctx_dict)

        return {"semantic_context": ctx_dict, "pipeline_trace": trace}

    except Exception as e:
        logger.error(f"[semantic_resolver] Failed: {e}", exc_info=True)
        # Graceful fallback — 不阻塞后续节点
        trace = list(state.get("pipeline_trace", []))
        trace_step(trace, "semantic_resolver", t0, summary=f"语义解析失败: {e}", status="error")
        return {"semantic_context": {}, "pipeline_trace": trace}
