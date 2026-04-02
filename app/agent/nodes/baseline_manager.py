"""
baseline_manager — 预警基线管理节点

处理 intent == "set_baseline" 分支：
  1. 用 LLM 从自然语言中提取基线参数
  2. 调用 BaselineService 执行 create / update / delete
  3. 返回结构化执行结果供 response_builder 格式化

支持的操作:
  - create: "针对库存数量设置上限 1000，目标 800"
  - update: "修改库存预警，将上限改为 1200"
  - delete: "删除库存预警基线"
  - toggle: "禁用良率预警"
"""

import json
import logging
import time
from typing import Any, Dict, Optional

from app.agent.state import AgentState
from app.agent.trace import trace_step

logger = logging.getLogger(__name__)

# 默认阈值颜色
_LEVEL_COLORS = {
    "target": "#10b981",    # emerald-500
    "warning": "#f59e0b",   # amber-500
    "critical": "#ef4444",  # red-500
}

# LLM 提取提示词
_EXTRACT_PROMPT = """\
你是工厂MES系统中的"预警基线"配置助手。
用户想要设定、修改或删除一个业务预警基线。

请从用户输入中提取以下信息，并以 JSON 格式输出：
{{
  "op": "create" | "update" | "delete" | "toggle",  // 操作类型
  "label": "...",          // 基线名称（简短描述，如"库存上限"）
  "field": "...",          // 对应 ECharts y轴字段名（如 inventory_qty, yield_rate, output_qty）
  "keywords": ["...", ...], // 触发关键词列表，用于 NL 查询时匹配
  "direction": "below" | "above",  // below=值低于阈值时预警, above=值高于阈值时预警
  "thresholds": [
    {{"value": <数值>, "level": "target"|"warning"|"critical", "label": "目标"|"警告"|"临界", "color": "<hex颜色>"}}
  ],
  "scope": {{...}},        // 可选，限定范围（如 {{"product_line": "A线"}}）
  "baseline_id": "...",    // 若是 update/delete/toggle，尽量提供已有基线 ID（用户可能提供）
  "created_by": "user"
}}

规则：
- 如果用户没提到具体数值，则 thresholds 为空数组 []
- level 从大到小: target（理想目标）< warning（预警）< critical（严重/触发立即处理）
- below 表示值低于阈值时触发（如库存少于...），above 表示值高于阈值时触发（如温度超过...）
- field 名称用下划线英文格式（参考: yield_rate 良率, output_qty 产量, inventory_qty 库存数量）
- 只输出 JSON，不要任何额外解释

用户输入: {user_input}
"""


def _get_llm():
    """获取 LLM Provider"""
    try:
        from app.services.llm_provider_manager import get_active_llm_provider
        return get_active_llm_provider()
    except Exception as e:
        logger.warning(f"[baseline_manager] get_llm failed: {e}")
        return None


def _extract_params(user_input: str) -> Dict[str, Any]:
    """使用 LLM 从用户输入中提取基线参数"""
    llm = _get_llm()
    if not llm:
        logger.warning("[baseline_manager] No LLM available, using fallback extraction")
        return _fallback_extract(user_input)

    try:
        prompt = _EXTRACT_PROMPT.format(user_input=user_input)
        raw = llm.complete(prompt)
        # 从响应中提取 JSON
        text = raw if isinstance(raw, str) else (raw.text if hasattr(raw, "text") else str(raw))
        # 截取第一个 JSON 对象
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        logger.warning(f"[baseline_manager] LLM extraction failed: {e}")

    return _fallback_extract(user_input)


def _fallback_extract(user_input: str) -> Dict[str, Any]:
    """规则兜底：解析常见的基线设定表达"""
    import re
    result: Dict[str, Any] = {
        "op": "create",
        "label": "自定义基线",
        "field": "",
        "keywords": [],
        "direction": "below",
        "thresholds": [],
        "scope": {},
        "created_by": "user",
    }

    # 判断操作类型
    if re.search(r"删除|移除|取消", user_input):
        result["op"] = "delete"
    elif re.search(r"禁用|关闭|停用", user_input):
        result["op"] = "toggle"
    elif re.search(r"修改|更新|调整|更改", user_input):
        result["op"] = "update"

    # 判断字段
    field_map = [
        (r"库存", "inventory_qty"),
        (r"良率|良品率|合格率", "yield_rate"),
        (r"产量|产出|产能", "output_qty"),
        (r"缺陷|不良", "defect_count"),
        (r"设备|稼动|OEE", "equipment_oee"),
    ]
    for pattern, field in field_map:
        if re.search(pattern, user_input):
            result["field"] = field
            result["keywords"].append(pattern.split("|")[0])
            break

    # 判断方向
    if re.search(r"上限|不超过|最多|高于.*预警|超过.*告警", user_input):
        result["direction"] = "above"
    else:
        result["direction"] = "below"

    # 提取数值 → 生成 thresholds
    numbers = re.findall(r"(\d+(?:\.\d+)?)\s*(%|%|百分|个|件|片|台)?", user_input)
    threshold_levels = ["critical", "warning", "target"]
    for i, (val, unit) in enumerate(numbers[:3]):
        level = threshold_levels[i] if i < len(threshold_levels) else "warning"
        result["thresholds"].append({
            "value": float(val),
            "level": level,
            "label": {"critical": "临界", "warning": "警告", "target": "目标"}[level],
            "color": _LEVEL_COLORS[level],
        })

    # 生成 label
    field_labels = {
        "inventory_qty": "库存预警",
        "yield_rate": "良率预警",
        "output_qty": "产量预警",
        "defect_count": "缺陷预警",
        "equipment_oee": "设备稼动率预警",
    }
    if result["field"]:
        result["label"] = field_labels.get(result["field"], result["field"] + "预警")

    return result


def _build_text_response(op: str, params: Dict[str, Any], saved: Optional[Dict[str, Any]]) -> str:
    """组装用户可读的文字回复"""
    label = params.get("label") or (saved or {}).get("label") or "基线"
    op_labels = {
        "create": f"✅ 已成功创建预警基线「{label}」",
        "update": f"✅ 已成功更新预警基线「{label}」",
        "delete": f"✅ 已成功删除预警基线「{label}」",
        "toggle": f"✅ 已切换预警基线「{label}」的启用状态",
    }
    base_msg = op_labels.get(op, f"✅ 基线操作成功")
    thresholds = params.get("thresholds") or (saved or {}).get("thresholds") or []
    if thresholds and op in ("create", "update"):
        lines = []
        for t in thresholds:
            lines.append(f"  - {t.get('label','')}: {t.get('value', '')} ({t.get('level','')})")
        base_msg += "\n阈值配置:\n" + "\n".join(lines)
    base_msg += "\n下次生成相关图表时，系统将自动在图上标注预警基线。"
    return base_msg


def baseline_manager_node(state: AgentState) -> dict:
    """
    基线设定节点。
    输入: user_input, intent_data
    输出: baseline_action, response
    """
    t0 = time.perf_counter()
    trace = list(state.get("pipeline_trace", []))
    user_input = state.get("resolved_input") or state.get("user_input", "")

    logger.info(f"[baseline_manager] Processing: {user_input[:100]}")

    # Step 1: 提取参数
    params = _extract_params(user_input)
    op = params.get("op", "create")
    logger.info(f"[baseline_manager] Extracted params: op={op}, field={params.get('field')}, "
                f"thresholds={len(params.get('thresholds', []))}")

    # 补充颜色
    for t in params.get("thresholds", []):
        if not t.get("color"):
            t["color"] = _LEVEL_COLORS.get(t.get("level", ""), "#6b7280")

    # Step 2: 调用 BaselineService
    saved: Optional[Dict[str, Any]] = None
    error_msg: Optional[str] = None

    try:
        from app.services.baseline_service import baseline_service as svc

        if op == "create":
            data = {
                "label": params.get("label", "自定义基线"),
                "field": params.get("field", ""),
                "keywords": params.get("keywords", []),
                "scope": params.get("scope") or {},
                "thresholds": params.get("thresholds", []),
                "direction": params.get("direction", "below"),
                "enabled": True,
                "created_by": params.get("created_by", "user"),
            }
            if params.get("metric_id"):
                data["metric_id"] = params["metric_id"]
            saved = svc.create_baseline(data)

        elif op == "update":
            baseline_id = params.get("baseline_id")
            if not baseline_id:
                # 尝试按 label/field 查找
                rows = svc.list_baselines(q=params.get("label", ""))
                if rows:
                    baseline_id = rows[0]["id"]
            if baseline_id:
                updates = {k: v for k, v in params.items()
                           if k not in ("op", "baseline_id", "created_by") and v is not None}
                saved = svc.update_baseline(baseline_id, updates)
            else:
                # 找不到则转 create
                op = "create"
                saved = svc.create_baseline(params)

        elif op == "delete":
            baseline_id = params.get("baseline_id")
            if not baseline_id:
                rows = svc.list_baselines(q=params.get("label", "") or params.get("field", ""))
                if rows:
                    baseline_id = rows[0]["id"]
            if baseline_id:
                svc.delete_baseline(baseline_id)
                saved = {"id": baseline_id, "label": params.get("label", "")}
            else:
                error_msg = f"未找到匹配的基线: {params.get('label', params.get('field', ''))}"

        elif op == "toggle":
            baseline_id = params.get("baseline_id")
            if not baseline_id:
                rows = svc.list_baselines(q=params.get("label", "") or params.get("field", ""))
                if rows:
                    baseline_id = rows[0]["id"]
            if baseline_id:
                saved = svc.toggle_baseline(baseline_id)
            else:
                error_msg = f"未找到匹配的基线: {params.get('label', params.get('field', ''))}"

    except Exception as e:
        logger.error(f"[baseline_manager] Service error: {e}", exc_info=True)
        error_msg = str(e)

    # Step 3: 组装 response
    if error_msg:
        text_response = f"❌ 基线设定失败: {error_msg}\n请检查输入或联系管理员。"
        success = False
    else:
        text_response = _build_text_response(op, params, saved)
        success = True

    baseline_action = {
        "op": op,
        "success": success,
        "params": params,
        "saved": saved,
        "error": error_msg,
    }

    trace_step(trace, "baseline_manager", t0,
               summary=f"基线操作: op={op}, success={success}",
               detail={"op": op, "field": params.get("field"), "success": success})

    return {
        "baseline_action": baseline_action,
        "response": {
            "success": success,
            "intent": "set_baseline",
            "text": text_response,
            "data": saved,
            "visualization": None,
            "chartConfig": None,
            "baseline_action": baseline_action,
        },
        "pipeline_trace": trace,
    }
