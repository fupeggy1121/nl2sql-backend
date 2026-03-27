"""
method_selector 节点

利用 LLM + 本体元数据自动识别用户意图，推荐合适的分析方法，
并构建 data_source_config 和 method_params。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

from app.agents.analysis_agent.state import AnalysisState
from app.analytics.registry import list_methods

logger = logging.getLogger(__name__)

# ── 关键词 → 方法名 快速映射（无需 LLM）──
_KEYWORD_MAP = {
    r"SPC|控制图|Cpk|Ppk|制程能力|control chart": "spc",
    r"相关性|相关系数|correlation|热力图": "correlation",
    r"ANOVA|方差分析|差异显著|t[-\s]?test|t检验|卡方|正态性": "hypothesis",
    r"帕累托|pareto|80/20|80%-20%": "pareto",
    r"回归|regression|线性分析|影响因素": "regression",
    r"预测|predict|forecast|分类|良率预测|random forest|随机森林": "prediction",
    r"异常|anomaly|outlier|离群|孤立|3[σσ]|三倍标准差": "anomaly",
    r"描述性|分布|基础统计|均值|方差|直方图|descriptive": "descriptive",
}


def _quick_classify(user_input: str) -> str | None:
    """关键词快速分类，返回方法名或 None（须走 LLM）。"""
    for pattern, method in _KEYWORD_MAP.items():
        if re.search(pattern, user_input, re.IGNORECASE):
            return method
    return None


def _llm_classify(user_input: str) -> tuple[str, str, Dict[str, Any]]:
    """
    使用 LLM 从自然语言中提取分析意图。
    返回 (method_name, reason, params_hint)。
    """
    from app.agent.llm import get_llm

    available = [f"  - {m['name']}: {m['description']}" for m in list_methods()]
    methods_text = "\n".join(available)

    prompt = f"""你是一个数据分析专家，根据用户需求选择最合适的分析方法，并提取关键参数。

可用分析方法：
{methods_text}

用户需求："{user_input}"

请以 JSON 格式返回，示例：
{{
  "method": "spc",
  "reason": "用户提到控制图分析，SPC 最合适",
  "params": {{
    "value_column": "measurement_value",
    "usl": 10.5,
    "lsl": 9.5
  }}
}}

仅返回 JSON，不要其他内容。"""

    llm = get_llm()
    resp = llm.invoke(prompt)
    content = resp.content if hasattr(resp, "content") else str(resp)

    try:
        # 提取 JSON 块
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return (
                data.get("method", "descriptive"),
                data.get("reason", "LLM 推荐"),
                data.get("params", {}),
            )
    except Exception as e:
        logger.warning(f"[method_selector] LLM JSON parse error: {e}")

    return "descriptive", "默认使用描述性统计", {}


def method_selector_node(state: AnalysisState) -> dict:
    """
    节点：分析方法选择。

    输入: user_input
    输出: suggested_method, method_reason, method_params, data_source_config
    """
    user_input = state.get("user_input", "")
    logger.info(f"[method_selector] input={user_input[:80]}...")

    # 1. 尝试关键词快速分类
    method = _quick_classify(user_input)
    if method:
        reason = f"关键词匹配: '{method}'"
        params: Dict[str, Any] = {}
        logger.info(f"[method_selector] keyword match → {method}")
    else:
        # 2. 回退到 LLM
        try:
            method, reason, params = _llm_classify(user_input)
            logger.info(f"[method_selector] LLM suggest → {method}")
        except Exception as e:
            logger.error(f"[method_selector] LLM error: {e}")
            method, reason, params = "descriptive", "默认使用描述性统计", {}

    # 3. 构造 data_source_config（如果 state 中尚未有）
    data_source_config = state.get("data_source_config") or {
        "type": "data",
        "data": state.get("raw_data") or [],
    }

    return {
        "suggested_method": method,
        "method_reason": reason,
        "method_params": params,
        "data_source_config": data_source_config,
    }
