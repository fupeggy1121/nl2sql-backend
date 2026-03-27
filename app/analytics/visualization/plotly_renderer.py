"""
Plotly 可视化工具函数

提供图表标准化、合并、转换等辅助功能。
"""

from __future__ import annotations

from typing import Any, Dict, List


def standardize_chart(chart_dict: Dict[str, Any]) -> Dict[str, Any]:
    """确保图表字典包含必需字段 (type, title, data, layout)。"""
    return {
        "type": chart_dict.get("type", "unknown"),
        "title": chart_dict.get("title", ""),
        "data": chart_dict.get("data", []),
        "layout": chart_dict.get("layout", {}),
    }


def merge_charts(charts: List[Dict[str, Any]], title: str = "") -> Dict[str, Any]:
    """将多个图表的 traces 合并到一个 figure 中。"""
    merged_data: List[Dict[str, Any]] = []
    for c in charts:
        merged_data.extend(c.get("data", []))

    return {
        "type": "merged",
        "title": title,
        "data": merged_data,
        "layout": {"title": title},
    }


def to_plotly_json(fig: Any) -> Dict[str, Any]:
    """将 plotly.graph_objects.Figure 转为 JSON 可序列化字典。"""
    if hasattr(fig, "to_dict"):
        d = fig.to_dict()
        return {
            "type": "plotly",
            "title": d.get("layout", {}).get("title", {}).get("text", ""),
            "data": d.get("data", []),
            "layout": d.get("layout", {}),
        }
    # 已经是 dict 则直接标准化
    if isinstance(fig, dict):
        return standardize_chart(fig)
    return {"type": "unknown", "title": "", "data": [], "layout": {}}
