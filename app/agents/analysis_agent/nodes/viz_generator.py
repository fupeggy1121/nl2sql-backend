"""
viz_generator + response_builder 节点

组装最终的自然语言回答和标准化响应（与 Query Agent 格式兼容）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.agents.analysis_agent.state import AnalysisState

logger = logging.getLogger(__name__)


def viz_generator_node(state: AnalysisState) -> dict:
    """
    节点：可视化生成 + 最终响应组装。

    输入: analysis_success, analysis_summary, analysis_data,
          analysis_charts, suggested_method, method_reason
    输出: answer, response
    """
    success = state.get("analysis_success", False)
    summary = state.get("analysis_summary", "")
    data = state.get("analysis_data") or {}
    charts = state.get("analysis_charts") or []
    method = state.get("suggested_method", "")
    reason = state.get("method_reason", "")
    error = state.get("analysis_error")

    if not success:
        answer = f"分析执行失败：{error or '未知错误'}"
        response: Dict[str, Any] = {
            "success": False,
            "answer": answer,
            "analysis": None,
            "charts": [],
        }
    else:
        # 构建自然语言答复
        lines = [f"**{method} 分析结果**"]
        if reason:
            lines.append(f"（{reason}）")
        lines.append("")
        if summary:
            lines.append(summary)
        if data:
            # 附加关键数值（最多显示 5 条）
            for i, (k, v) in enumerate(data.items()):
                if i >= 5:
                    break
                if isinstance(v, (int, float)):
                    lines.append(f"- {k}: {v}")
        answer = "\n".join(lines)

        response = {
            "success": True,
            "answer": answer,
            "analysis": {
                "method": method,
                "summary": summary,
                "data": data,
            },
            "charts": charts,
        }

    logger.info(f"[viz_generator] success={success}, charts={len(charts)}")
    return {"answer": answer, "response": response}
