"""
SPC 控制图分析方法

支持 X-bar/R 控制图、单值控制图 (I-MR)、Cpk/Ppk 计算及 Nelson 规则判异。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.analytics.models import AnalysisResult
from app.analytics.registry import register_method

# ---------------------------------------------------------------------------
# 控制图常数表 (n = 2 ~ 10)
# A2: X-bar 图系数, D3/D4: R 图系数, d2: 极差均值与σ的比值
# ---------------------------------------------------------------------------
_SPC_CONSTANTS: Dict[int, Dict[str, float]] = {
    2:  {"A2": 1.880, "D3": 0.000, "D4": 3.267, "d2": 1.128},
    3:  {"A2": 1.023, "D3": 0.000, "D4": 2.575, "d2": 1.693},
    4:  {"A2": 0.729, "D3": 0.000, "D4": 2.282, "d2": 2.059},
    5:  {"A2": 0.577, "D3": 0.000, "D4": 2.115, "d2": 2.326},
    6:  {"A2": 0.483, "D3": 0.000, "D4": 2.004, "d2": 2.534},
    7:  {"A2": 0.419, "D3": 0.076, "D4": 1.924, "d2": 2.704},
    8:  {"A2": 0.373, "D3": 0.136, "D4": 1.864, "d2": 2.847},
    9:  {"A2": 0.337, "D3": 0.184, "D4": 1.816, "d2": 2.970},
    10: {"A2": 0.308, "D3": 0.223, "D4": 1.777, "d2": 3.078},
}


# ---------------------------------------------------------------------------
# Nelson 规则 (1-4)
# ---------------------------------------------------------------------------

def _nelson_rule_1(values: np.ndarray, cl: float, sigma: float) -> List[int]:
    """规则 1: 单个点超出 3σ。"""
    ucl = cl + 3 * sigma
    lcl = cl - 3 * sigma
    return [int(i) for i in range(len(values)) if values[i] > ucl or values[i] < lcl]


def _nelson_rule_2(values: np.ndarray, cl: float, _sigma: float) -> List[int]:
    """规则 2: 连续 9 个点在中心线同侧。"""
    violations: List[int] = []
    n = len(values)
    if n < 9:
        return violations
    sides = np.sign(values - cl)
    for i in range(n - 8):
        window = sides[i : i + 9]
        if np.all(window > 0) or np.all(window < 0):
            violations.extend(range(i, i + 9))
    return sorted(set(violations))


def _nelson_rule_3(values: np.ndarray, _cl: float, _sigma: float) -> List[int]:
    """规则 3: 连续 6 个点递增或递减。"""
    violations: List[int] = []
    n = len(values)
    if n < 6:
        return violations
    diffs = np.diff(values)
    for i in range(n - 5):
        window = diffs[i : i + 5]
        if np.all(window > 0) or np.all(window < 0):
            violations.extend(range(i, i + 6))
    return sorted(set(violations))


def _nelson_rule_4(values: np.ndarray, _cl: float, _sigma: float) -> List[int]:
    """规则 4: 连续 14 个点交替上下波动。"""
    violations: List[int] = []
    n = len(values)
    if n < 14:
        return violations
    diffs = np.diff(values)
    signs = np.sign(diffs)
    for i in range(n - 13):
        window = signs[i : i + 13]
        # 相邻差值符号交替 → 乘积均为负
        products = window[:-1] * window[1:]
        if np.all(products < 0):
            violations.extend(range(i, i + 14))
    return sorted(set(violations))


_NELSON_FUNCS = {
    1: _nelson_rule_1,
    2: _nelson_rule_2,
    3: _nelson_rule_3,
    4: _nelson_rule_4,
}


def _run_nelson_rules(
    values: np.ndarray, cl: float, sigma: float, rules: List[int]
) -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    for r in rules:
        func = _NELSON_FUNCS.get(r)
        if func is not None:
            indices = func(values, cl, sigma)
            results[f"rule_{r}"] = indices
    return results


# ---------------------------------------------------------------------------
# Cpk / Ppk
# ---------------------------------------------------------------------------

def _calc_capability(
    values: np.ndarray,
    usl: Optional[float],
    lsl: Optional[float],
    within_sigma: float,
    overall_sigma: float,
) -> Dict[str, Any]:
    mean = float(np.mean(values))
    result: Dict[str, Any] = {"mean": mean}

    # Cp / Cpk (within‑subgroup σ)
    if within_sigma > 0:
        if usl is not None and lsl is not None:
            result["Cp"] = round((usl - lsl) / (6 * within_sigma), 4)
        cpu = (usl - mean) / (3 * within_sigma) if usl is not None else None
        cpl = (mean - lsl) / (3 * within_sigma) if lsl is not None else None
        caps = [v for v in (cpu, cpl) if v is not None]
        if caps:
            result["Cpk"] = round(min(caps), 4)
        if cpu is not None:
            result["CPU"] = round(cpu, 4)
        if cpl is not None:
            result["CPL"] = round(cpl, 4)

    # Pp / Ppk (overall σ)
    if overall_sigma > 0:
        if usl is not None and lsl is not None:
            result["Pp"] = round((usl - lsl) / (6 * overall_sigma), 4)
        ppu = (usl - mean) / (3 * overall_sigma) if usl is not None else None
        ppl = (mean - lsl) / (3 * overall_sigma) if lsl is not None else None
        pcaps = [v for v in (ppu, ppl) if v is not None]
        if pcaps:
            result["Ppk"] = round(min(pcaps), 4)

    return result


# ---------------------------------------------------------------------------
# X-bar / R 控制图
# ---------------------------------------------------------------------------

def _build_subgroups(
    series: pd.Series, subgroup_size: int, group_col: Optional[pd.Series]
) -> List[np.ndarray]:
    if group_col is not None:
        groups = []
        for _, grp in series.groupby(group_col):
            arr = grp.dropna().values.astype(float)
            if len(arr) >= 2:
                groups.append(arr)
        return groups

    vals = series.dropna().values.astype(float)
    n_full = len(vals) // subgroup_size
    return [vals[i * subgroup_size : (i + 1) * subgroup_size] for i in range(n_full)]


def _xbar_r_analysis(
    subgroups: List[np.ndarray], subgroup_size: int
) -> Dict[str, Any]:
    xbars = np.array([g.mean() for g in subgroups])
    ranges = np.array([g.max() - g.min() for g in subgroups])
    xbar_bar = float(np.mean(xbars))
    r_bar = float(np.mean(ranges))

    n = min(subgroup_size, 10)
    n = max(n, 2)
    consts = _SPC_CONSTANTS[n]

    # X-bar 控制限
    xbar_ucl = xbar_bar + consts["A2"] * r_bar
    xbar_lcl = xbar_bar - consts["A2"] * r_bar

    # R 控制限
    r_ucl = consts["D4"] * r_bar
    r_lcl = consts["D3"] * r_bar

    # within‑subgroup σ 估计
    within_sigma = r_bar / consts["d2"] if consts["d2"] > 0 else 0.0

    return {
        "xbars": xbars,
        "ranges": ranges,
        "xbar_bar": xbar_bar,
        "r_bar": r_bar,
        "xbar_ucl": xbar_ucl,
        "xbar_lcl": xbar_lcl,
        "r_ucl": r_ucl,
        "r_lcl": r_lcl,
        "within_sigma": within_sigma,
    }


def _make_xbar_chart(stats: Dict[str, Any]) -> Dict[str, Any]:
    xbars = stats["xbars"]
    indices = list(range(1, len(xbars) + 1))
    return {
        "type": "xbar",
        "title": "X-bar 控制图（均值控制图）",
        "data": [
            {"x": indices, "y": xbars.tolist(), "mode": "lines+markers", "name": "X̄"},
            {"x": indices, "y": [stats["xbar_ucl"]] * len(indices), "mode": "lines", "name": "UCL", "line": {"dash": "dash", "color": "red"}},
            {"x": indices, "y": [stats["xbar_bar"]] * len(indices), "mode": "lines", "name": "CL", "line": {"dash": "solid", "color": "green"}},
            {"x": indices, "y": [stats["xbar_lcl"]] * len(indices), "mode": "lines", "name": "LCL", "line": {"dash": "dash", "color": "red"}},
        ],
        "layout": {
            "title": "X-bar 控制图",
            "xaxis": {"title": "子组序号"},
            "yaxis": {"title": "均值"},
        },
    }


def _make_r_chart(stats: Dict[str, Any]) -> Dict[str, Any]:
    ranges = stats["ranges"]
    indices = list(range(1, len(ranges) + 1))
    return {
        "type": "r_chart",
        "title": "R 控制图（极差控制图）",
        "data": [
            {"x": indices, "y": ranges.tolist(), "mode": "lines+markers", "name": "R"},
            {"x": indices, "y": [stats["r_ucl"]] * len(indices), "mode": "lines", "name": "UCL", "line": {"dash": "dash", "color": "red"}},
            {"x": indices, "y": [stats["r_bar"]] * len(indices), "mode": "lines", "name": "CL", "line": {"dash": "solid", "color": "green"}},
            {"x": indices, "y": [stats["r_lcl"]] * len(indices), "mode": "lines", "name": "LCL", "line": {"dash": "dash", "color": "red"}},
        ],
        "layout": {
            "title": "R 控制图",
            "xaxis": {"title": "子组序号"},
            "yaxis": {"title": "极差"},
        },
    }


# ---------------------------------------------------------------------------
# I-MR 单值控制图
# ---------------------------------------------------------------------------

def _individual_mr_analysis(values: np.ndarray) -> Dict[str, Any]:
    mean = float(np.mean(values))
    mrs = np.abs(np.diff(values))
    mr_bar = float(np.mean(mrs))
    # d2 for n=2 (moving range of 2 consecutive points)
    d2 = _SPC_CONSTANTS[2]["d2"]
    sigma = mr_bar / d2 if d2 > 0 else float(np.std(values, ddof=1))

    i_ucl = mean + 3 * sigma
    i_lcl = mean - 3 * sigma

    mr_ucl = _SPC_CONSTANTS[2]["D4"] * mr_bar
    mr_lcl = 0.0

    anomalies = [int(i) for i in range(len(values)) if values[i] > i_ucl or values[i] < i_lcl]

    return {
        "values": values,
        "mrs": mrs,
        "mean": mean,
        "mr_bar": mr_bar,
        "sigma": sigma,
        "i_ucl": i_ucl,
        "i_lcl": i_lcl,
        "mr_ucl": mr_ucl,
        "mr_lcl": mr_lcl,
        "anomalies": anomalies,
    }


def _make_individual_chart(stats: Dict[str, Any]) -> Dict[str, Any]:
    values = stats["values"]
    indices = list(range(1, len(values) + 1))
    anomaly_idx = stats["anomalies"]

    traces = [
        {"x": indices, "y": values.tolist(), "mode": "lines+markers", "name": "个体值"},
        {"x": indices, "y": [stats["i_ucl"]] * len(indices), "mode": "lines", "name": "UCL", "line": {"dash": "dash", "color": "red"}},
        {"x": indices, "y": [stats["mean"]] * len(indices), "mode": "lines", "name": "CL", "line": {"dash": "solid", "color": "green"}},
        {"x": indices, "y": [stats["i_lcl"]] * len(indices), "mode": "lines", "name": "LCL", "line": {"dash": "dash", "color": "red"}},
    ]
    if anomaly_idx:
        traces.append({
            "x": [i + 1 for i in anomaly_idx],
            "y": [float(values[i]) for i in anomaly_idx],
            "mode": "markers",
            "name": "异常点",
            "marker": {"color": "red", "size": 10, "symbol": "x"},
        })

    return {
        "type": "individual",
        "title": "I 控制图（单值控制图）",
        "data": traces,
        "layout": {
            "title": "I 控制图",
            "xaxis": {"title": "观测序号"},
            "yaxis": {"title": "测量值"},
        },
    }


def _make_mr_chart(stats: Dict[str, Any]) -> Dict[str, Any]:
    mrs = stats["mrs"]
    indices = list(range(2, len(mrs) + 2))
    return {
        "type": "mr_chart",
        "title": "MR 控制图（移动极差控制图）",
        "data": [
            {"x": indices, "y": mrs.tolist(), "mode": "lines+markers", "name": "MR"},
            {"x": indices, "y": [stats["mr_ucl"]] * len(indices), "mode": "lines", "name": "UCL", "line": {"dash": "dash", "color": "red"}},
            {"x": indices, "y": [stats["mr_bar"]] * len(indices), "mode": "lines", "name": "CL", "line": {"dash": "solid", "color": "green"}},
            {"x": indices, "y": [stats["mr_lcl"]] * len(indices), "mode": "lines", "name": "LCL", "line": {"dash": "dash", "color": "red"}},
        ],
        "layout": {
            "title": "MR 控制图",
            "xaxis": {"title": "观测序号"},
            "yaxis": {"title": "移动极差"},
        },
    }


# ---------------------------------------------------------------------------
# 注册方法
# ---------------------------------------------------------------------------

@register_method(
    "spc",
    label="SPC 控制图",
    description="统计过程控制：X-bar/R 控制图、单值控制图 (I-MR)、过程能力 Cpk/Ppk、Nelson 判异规则",
    params_schema={
        "value_column": {
            "type": "string",
            "description": "测量值列名",
            "required": True,
        },
        "group_column": {
            "type": "string",
            "description": "子组分组列（可选，若提供则按此列分组）",
        },
        "subgroup_size": {
            "type": "integer",
            "default": 5,
            "minimum": 2,
            "maximum": 50,
            "description": "子组大小（无分组列时按顺序分组）",
        },
        "usl": {
            "type": "number",
            "description": "规格上限 (Upper Specification Limit)",
        },
        "lsl": {
            "type": "number",
            "description": "规格下限 (Lower Specification Limit)",
        },
        "nelson_rules": {
            "type": "array",
            "items": {"type": "integer"},
            "default": [1, 2, 3, 4],
            "description": "启用的 Nelson 判异规则编号",
        },
        "chart_type": {
            "type": "string",
            "enum": ["xbar_r", "individual"],
            "default": "xbar_r",
            "description": "控制图类型: xbar_r=均值-极差, individual=单值",
        },
    },
)
def run_spc(df: pd.DataFrame, params: Dict[str, Any]) -> AnalysisResult:
    """执行 SPC 控制图分析。"""
    value_column: str = params.get("value_column", "")
    group_column: Optional[str] = params.get("group_column")
    subgroup_size: int = params.get("subgroup_size", 5)
    usl: Optional[float] = params.get("usl")
    lsl: Optional[float] = params.get("lsl")
    nelson_rules: List[int] = params.get("nelson_rules", [1, 2, 3, 4])
    chart_type: str = params.get("chart_type", "xbar_r")

    # ---- 参数校验 ----
    if not value_column:
        return AnalysisResult(
            success=False, method="spc", summary="",
            error="请指定测量值列名 (value_column)",
        )

    if value_column not in df.columns:
        return AnalysisResult(
            success=False, method="spc", summary="",
            error=f"数据中不存在列「{value_column}」",
        )

    if not pd.api.types.is_numeric_dtype(df[value_column]):
        return AnalysisResult(
            success=False, method="spc", summary="",
            error=f"列「{value_column}」不是数值类型，无法进行 SPC 分析",
        )

    all_values = df[value_column].dropna().values.astype(float)
    if len(all_values) < 10:
        return AnalysisResult(
            success=False, method="spc", summary="",
            error=f"数据量不足：至少需要 10 个有效数据点，当前仅 {len(all_values)} 个",
        )

    if group_column and group_column not in df.columns:
        return AnalysisResult(
            success=False, method="spc", summary="",
            error=f"分组列「{group_column}」不存在于数据中",
        )

    subgroup_size = max(2, min(subgroup_size, 50))

    # ---- 分析 ----
    charts: List[Dict[str, Any]] = []
    data: Dict[str, Any] = {"chart_type": chart_type, "n_total": len(all_values)}
    overall_sigma = float(np.std(all_values, ddof=0))

    if chart_type == "xbar_r":
        group_series = df[group_column] if group_column else None
        subgroups = _build_subgroups(df[value_column], subgroup_size, group_series)
        if len(subgroups) < 2:
            return AnalysisResult(
                success=False, method="spc", summary="",
                error="子组数量不足：至少需要 2 个子组，请检查数据量或子组大小设置",
            )

        effective_n = min(max(len(subgroups[0]), 2), 10)
        stats = _xbar_r_analysis(subgroups, effective_n)
        charts.append(_make_xbar_chart(stats))
        charts.append(_make_r_chart(stats))

        data.update({
            "n_subgroups": len(subgroups),
            "subgroup_size": effective_n,
            "xbar_bar": round(stats["xbar_bar"], 4),
            "r_bar": round(stats["r_bar"], 4),
            "xbar_ucl": round(stats["xbar_ucl"], 4),
            "xbar_lcl": round(stats["xbar_lcl"], 4),
            "r_ucl": round(stats["r_ucl"], 4),
            "r_lcl": round(stats["r_lcl"], 4),
            "within_sigma": round(stats["within_sigma"], 4),
        })
        within_sigma = stats["within_sigma"]
        nelson_values = stats["xbars"]
        nelson_cl = stats["xbar_bar"]
        nelson_sigma = (stats["xbar_ucl"] - stats["xbar_bar"]) / 3 if stats["xbar_ucl"] != stats["xbar_bar"] else within_sigma

    else:  # individual
        stats = _individual_mr_analysis(all_values)
        charts.append(_make_individual_chart(stats))
        charts.append(_make_mr_chart(stats))

        data.update({
            "mean": round(stats["mean"], 4),
            "mr_bar": round(stats["mr_bar"], 4),
            "sigma": round(stats["sigma"], 4),
            "i_ucl": round(stats["i_ucl"], 4),
            "i_lcl": round(stats["i_lcl"], 4),
            "mr_ucl": round(stats["mr_ucl"], 4),
            "anomalies": stats["anomalies"],
        })
        within_sigma = stats["sigma"]
        nelson_values = all_values
        nelson_cl = stats["mean"]
        nelson_sigma = stats["sigma"]

    # ---- Nelson 规则 ----
    nelson_results = _run_nelson_rules(nelson_values, nelson_cl, nelson_sigma, nelson_rules)
    data["nelson_rules"] = nelson_results
    total_violations = sum(len(v) for v in nelson_results.values())

    # ---- Cpk / Ppk ----
    if usl is not None or lsl is not None:
        capability = _calc_capability(all_values, usl, lsl, within_sigma, overall_sigma)
        data["capability"] = capability

    # ---- 摘要 ----
    summary_parts = []
    if chart_type == "xbar_r":
        summary_parts.append(
            f"X̄-R 控制图：{data['n_subgroups']} 个子组，"
            f"X̄={data['xbar_bar']:.4f}，R̄={data['r_bar']:.4f}"
        )
    else:
        summary_parts.append(
            f"I-MR 控制图：{len(all_values)} 个观测，"
            f"均值={data['mean']:.4f}，σ={data['sigma']:.4f}"
        )
        if stats["anomalies"]:
            summary_parts.append(f"发现 {len(stats['anomalies'])} 个异常点")

    if total_violations > 0:
        violated = [k for k, v in nelson_results.items() if v]
        summary_parts.append(f"Nelson 判异触发: {', '.join(violated)}")

    if "capability" in data:
        cap = data["capability"]
        cap_items = []
        if "Cpk" in cap:
            cap_items.append(f"Cpk={cap['Cpk']}")
        if "Ppk" in cap:
            cap_items.append(f"Ppk={cap['Ppk']}")
        if cap_items:
            summary_parts.append("过程能力: " + ", ".join(cap_items))

    summary = "；".join(summary_parts)

    return AnalysisResult(
        success=True,
        method="spc",
        summary=summary,
        data=data,
        charts=charts,
        metadata={
            "value_column": value_column,
            "chart_type": chart_type,
            "subgroup_size": subgroup_size,
            "usl": usl,
            "lsl": lsl,
            "nelson_rules": nelson_rules,
        },
    )
