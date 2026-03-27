"""
ECharts 兼容转换层

将 app.analytics 产出的 Plotly JSON 转为 ECharts option JSON，
使前端能用已有的 ECharts 渲染器展示分析图表。

策略：
  前端首选 Plotly.js 渲染分析图表（交互性更好）。
  对于已有 ECharts 组件的场景，可通过此适配器转换。
  不支持的图表类型直接返回 None，前端 fallback 到 Plotly。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def plotly_to_echarts(plotly_chart: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    将单个 Plotly chart dict 转换为 ECharts option dict。

    返回 None 表示当前图表类型不支持转换。
    """
    chart_type = plotly_chart.get("type", "")
    traces = plotly_chart.get("data", [])
    layout = plotly_chart.get("layout", {})
    title = plotly_chart.get("title", layout.get("title", {}).get("text", ""))

    if not traces:
        return None

    if chart_type == "histogram" or _all_traces_type(traces, "bar"):
        return _bar_to_echarts(traces, title, layout)

    if chart_type == "scatter" or _all_traces_type(traces, "scatter"):
        return _scatter_to_echarts(traces, title, layout)

    if chart_type == "line" or _all_traces_type(traces, "line"):
        return _line_to_echarts(traces, title, layout)

    if chart_type == "heatmap" or _all_traces_type(traces, "heatmap"):
        return _heatmap_to_echarts(traces, title, layout)

    if chart_type == "box" or _all_traces_type(traces, "box"):
        return _box_to_echarts(traces, title, layout)

    return None


def _all_traces_type(traces: List[Dict], t: str) -> bool:
    return bool(traces) and all(tr.get("type") == t for tr in traces)


# ── 柱状图 ──

def _bar_to_echarts(
    traces: List[Dict], title: str, layout: Dict
) -> Dict[str, Any]:
    series = []
    x_data: List[Any] = []
    for tr in traces:
        x = tr.get("x", [])
        y = tr.get("y", [])
        if not x_data:
            x_data = [str(v) for v in x]
        series.append({
            "name": tr.get("name", ""),
            "type": "bar",
            "data": list(y),
        })

    return {
        "title": {"text": title},
        "tooltip": {"trigger": "axis"},
        "legend": {"data": [s["name"] for s in series if s["name"]]},
        "xAxis": {"type": "category", "data": x_data},
        "yAxis": {"type": "value", "name": _axis_name(layout, "yaxis")},
        "series": series,
    }


# ── 折线图 ──

def _line_to_echarts(
    traces: List[Dict], title: str, layout: Dict
) -> Dict[str, Any]:
    series = []
    x_data: List[Any] = []
    for tr in traces:
        x = tr.get("x", [])
        y = tr.get("y", [])
        if not x_data:
            x_data = [str(v) for v in x]
        series.append({
            "name": tr.get("name", ""),
            "type": "line",
            "data": list(y),
            "smooth": False,
        })

    return {
        "title": {"text": title},
        "tooltip": {"trigger": "axis"},
        "legend": {"data": [s["name"] for s in series if s["name"]]},
        "xAxis": {"type": "category", "data": x_data, "name": _axis_name(layout, "xaxis")},
        "yAxis": {"type": "value", "name": _axis_name(layout, "yaxis")},
        "series": series,
    }


# ── 散点图 ──

def _scatter_to_echarts(
    traces: List[Dict], title: str, layout: Dict
) -> Dict[str, Any]:
    series = []
    for tr in traces:
        x = tr.get("x", [])
        y = tr.get("y", [])
        data = [[xi, yi] for xi, yi in zip(x, y)]
        series.append({
            "name": tr.get("name", ""),
            "type": "scatter",
            "data": data,
        })

    return {
        "title": {"text": title},
        "tooltip": {"trigger": "item", "formatter": "{a}: ({c})"},
        "legend": {"data": [s["name"] for s in series if s["name"]]},
        "xAxis": {"type": "value", "name": _axis_name(layout, "xaxis")},
        "yAxis": {"type": "value", "name": _axis_name(layout, "yaxis")},
        "series": series,
    }


# ── 热力图（相关矩阵）──

def _heatmap_to_echarts(
    traces: List[Dict], title: str, layout: Dict
) -> Dict[str, Any]:
    tr = traces[0]
    z = tr.get("z", [])
    x_labels = tr.get("x", [])
    y_labels = tr.get("y", [])

    # 展平 z 矩阵 → ECharts [[col, row, val], ...]
    data_flat = []
    for row_i, row in enumerate(z):
        for col_i, val in enumerate(row):
            data_flat.append([col_i, row_i, round(val, 4) if val is not None else 0])

    return {
        "title": {"text": title},
        "tooltip": {"position": "top"},
        "grid": {"height": "60%", "top": "10%"},
        "xAxis": {"type": "category", "data": [str(v) for v in x_labels], "splitArea": {"show": True}},
        "yAxis": {"type": "category", "data": [str(v) for v in y_labels], "splitArea": {"show": True}},
        "visualMap": {"min": -1, "max": 1, "calculable": True, "orient": "horizontal", "left": "center", "bottom": "15%"},
        "series": [{
            "name": title,
            "type": "heatmap",
            "data": data_flat,
            "label": {"show": True},
            "emphasis": {"itemStyle": {"shadowBlur": 10}},
        }],
    }


# ── 箱线图 ──

def _box_to_echarts(
    traces: List[Dict], title: str, layout: Dict
) -> Dict[str, Any]:
    import numpy as np

    series = []
    categories = []
    for tr in traces:
        name = str(tr.get("name", ""))
        categories.append(name)
        values = [float(v) for v in tr.get("y", []) if v is not None]
        if values:
            q1 = float(np.percentile(values, 25))
            q3 = float(np.percentile(values, 75))
            series.append([
                round(min(values), 4),
                round(q1, 4),
                round(float(np.median(values)), 4),
                round(q3, 4),
                round(max(values), 4),
            ])
        else:
            series.append([0, 0, 0, 0, 0])

    return {
        "title": {"text": title},
        "tooltip": {"trigger": "item", "axisPointer": {"type": "shadow"}},
        "xAxis": {"type": "category", "data": categories},
        "yAxis": {"type": "value", "name": _axis_name(layout, "yaxis")},
        "series": [{"name": title, "type": "boxplot", "data": series}],
    }


def _axis_name(layout: Dict, axis_key: str) -> str:
    axis = layout.get(axis_key, {})
    if isinstance(axis, dict):
        title = axis.get("title", {})
        if isinstance(title, dict):
            return title.get("text", "")
        return str(title)
    return ""


def convert_charts(plotly_charts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    批量将 Plotly chart list 转为 ECharts option list。
    无法转换的项保留原始 Plotly JSON 并附加 `_renderer: "plotly"` 标记。
    """
    result = []
    for chart in plotly_charts:
        echarts_option = plotly_to_echarts(chart)
        if echarts_option is not None:
            result.append({"_renderer": "echarts", "option": echarts_option})
        else:
            result.append({"_renderer": "plotly", **chart})
    return result
