"""
假设检验分析方法

支持 t 检验、ANOVA、卡方检验、正态性检验。
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd
from scipy import stats

from app.analytics.models import AnalysisResult
from app.analytics.registry import register_method


def _significance_text(p: float, alpha: float = 0.05) -> str:
    """根据 p 值返回显著性描述。"""
    if p < 0.001:
        return "极显著"
    if p < 0.01:
        return "高度显著"
    if p < alpha:
        return "显著"
    return "不显著"


def _cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    """计算 Cohen's d 效应量。"""
    n1, n2 = len(group1), len(group2)
    var1, var2 = group1.var(ddof=1), group2.var(ddof=1)
    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled_std == 0:
        return 0.0
    return float((group1.mean() - group2.mean()) / pooled_std)


def _eta_squared(groups: List[np.ndarray]) -> float:
    """计算 η² 效应量 (ANOVA)。"""
    all_data = np.concatenate(groups)
    grand_mean = all_data.mean()
    ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in groups)
    ss_total = np.sum((all_data - grand_mean) ** 2)
    if ss_total == 0:
        return 0.0
    return float(ss_between / ss_total)


def _cramers_v(contingency: np.ndarray, chi2: float, n: int) -> float:
    """计算 Cramér's V。"""
    min_dim = min(contingency.shape[0], contingency.shape[1]) - 1
    if min_dim == 0 or n == 0:
        return 0.0
    return float(np.sqrt(chi2 / (n * min_dim)))


def _box_plot_chart(df: pd.DataFrame, value_col: str, group_col: str, title: str) -> Dict[str, Any]:
    """生成分组箱线图 Plotly JSON。"""
    groups = df[group_col].dropna().unique()
    traces = []
    for g in sorted(groups, key=str):
        values = df.loc[df[group_col] == g, value_col].dropna().tolist()
        traces.append({
            "type": "box",
            "name": str(g),
            "y": values,
        })
    return {
        "type": "box",
        "title": title,
        "data": traces,
        "layout": {
            "title": title,
            "yaxis": {"title": value_col},
            "xaxis": {"title": group_col},
        },
    }


def _run_t_test(df: pd.DataFrame, params: Dict[str, Any]) -> AnalysisResult:
    """Welch's t 检验 (两独立样本)。"""
    value_col = params.get("value_column")
    group_col = params.get("group_column")
    alpha = params.get("alpha", 0.05)

    if not value_col or not group_col:
        return AnalysisResult(
            success=False, method="hypothesis",
            summary="t 检验需要 value_column 和 group_column 参数",
            error="缺少必要参数: value_column, group_column",
        )
    for col in (value_col, group_col):
        if col not in df.columns:
            return AnalysisResult(
                success=False, method="hypothesis",
                summary=f"列 '{col}' 不存在",
                error=f"列 '{col}' 不在数据中",
            )

    groups = df[group_col].dropna().unique()
    if len(groups) != 2:
        return AnalysisResult(
            success=False, method="hypothesis",
            summary=f"t 检验要求恰好 2 个分组，当前有 {len(groups)} 个",
            error=f"分组数量不正确: {len(groups)}",
        )

    g1 = df.loc[df[group_col] == groups[0], value_col].dropna().values
    g2 = df.loc[df[group_col] == groups[1], value_col].dropna().values

    if len(g1) < 2 or len(g2) < 2:
        return AnalysisResult(
            success=False, method="hypothesis",
            summary="每个分组至少需要 2 个数据点",
            error="数据点不足",
        )

    t_stat, p_value = stats.ttest_ind(g1, g2, equal_var=False)
    d = _cohens_d(g1, g2)
    sig = _significance_text(p_value, alpha)

    chart = _box_plot_chart(df, value_col, group_col, f"t 检验: {value_col} by {group_col}")

    return AnalysisResult(
        success=True,
        method="hypothesis",
        summary=f"Welch t 检验: t={round(t_stat, 4)}, p={round(p_value, 6)}, {sig}; Cohen's d={round(d, 4)}",
        data={
            "test_type": "t_test",
            "t_statistic": round(float(t_stat), 6),
            "p_value": round(float(p_value), 6),
            "cohens_d": round(d, 4),
            "significance": sig,
            "alpha": alpha,
            "group_stats": {
                str(groups[0]): {"n": len(g1), "mean": round(float(g1.mean()), 4), "std": round(float(g1.std(ddof=1)), 4)},
                str(groups[1]): {"n": len(g2), "mean": round(float(g2.mean()), 4), "std": round(float(g2.std(ddof=1)), 4)},
            },
        },
        charts=[chart],
    )


def _run_anova(df: pd.DataFrame, params: Dict[str, Any]) -> AnalysisResult:
    """单因素方差分析 (ANOVA)。"""
    value_col = params.get("value_column")
    group_col = params.get("group_column")
    alpha = params.get("alpha", 0.05)

    if not value_col or not group_col:
        return AnalysisResult(
            success=False, method="hypothesis",
            summary="ANOVA 需要 value_column 和 group_column 参数",
            error="缺少必要参数: value_column, group_column",
        )
    for col in (value_col, group_col):
        if col not in df.columns:
            return AnalysisResult(
                success=False, method="hypothesis",
                summary=f"列 '{col}' 不存在",
                error=f"列 '{col}' 不在数据中",
            )

    group_names = df[group_col].dropna().unique()
    if len(group_names) < 2:
        return AnalysisResult(
            success=False, method="hypothesis",
            summary=f"ANOVA 至少需要 2 个分组，当前有 {len(group_names)} 个",
            error=f"分组数量不足: {len(group_names)}",
        )

    groups = [df.loc[df[group_col] == g, value_col].dropna().values for g in group_names]
    if any(len(g) < 2 for g in groups):
        return AnalysisResult(
            success=False, method="hypothesis",
            summary="每个分组至少需要 2 个数据点",
            error="部分分组数据点不足",
        )

    f_stat, p_value = stats.f_oneway(*groups)
    eta2 = _eta_squared(groups)
    sig = _significance_text(p_value, alpha)

    chart = _box_plot_chart(df, value_col, group_col, f"ANOVA: {value_col} by {group_col}")

    group_stats = {}
    for name, g in zip(group_names, groups):
        group_stats[str(name)] = {
            "n": len(g),
            "mean": round(float(g.mean()), 4),
            "std": round(float(g.std(ddof=1)), 4),
        }

    return AnalysisResult(
        success=True,
        method="hypothesis",
        summary=f"ANOVA: F={round(float(f_stat), 4)}, p={round(float(p_value), 6)}, {sig}; η²={round(eta2, 4)}",
        data={
            "test_type": "anova",
            "f_statistic": round(float(f_stat), 6),
            "p_value": round(float(p_value), 6),
            "eta_squared": round(eta2, 4),
            "significance": sig,
            "alpha": alpha,
            "group_count": len(group_names),
            "group_stats": group_stats,
        },
        charts=[chart],
    )


def _run_chi_square(df: pd.DataFrame, params: Dict[str, Any]) -> AnalysisResult:
    """卡方独立性检验。"""
    category_columns = params.get("category_columns")
    alpha = params.get("alpha", 0.05)

    if not category_columns or len(category_columns) != 2:
        return AnalysisResult(
            success=False, method="hypothesis",
            summary="卡方检验需要 category_columns 参数（包含 2 列）",
            error="缺少或不正确的 category_columns（需要恰好 2 列）",
        )
    for col in category_columns:
        if col not in df.columns:
            return AnalysisResult(
                success=False, method="hypothesis",
                summary=f"列 '{col}' 不存在",
                error=f"列 '{col}' 不在数据中",
            )

    col1, col2 = category_columns
    contingency = pd.crosstab(df[col1], df[col2])

    if contingency.size == 0:
        return AnalysisResult(
            success=False, method="hypothesis",
            summary="交叉表为空，无法执行卡方检验",
            error="交叉表无数据",
        )

    chi2, p_value, dof, expected = stats.chi2_contingency(contingency)
    n = contingency.values.sum()
    v = _cramers_v(contingency.values, chi2, n)
    sig = _significance_text(p_value, alpha)

    # 热力图
    chart = {
        "type": "heatmap",
        "title": f"卡方检验交叉表: {col1} × {col2}",
        "data": [{
            "type": "heatmap",
            "z": contingency.values.tolist(),
            "x": [str(c) for c in contingency.columns.tolist()],
            "y": [str(r) for r in contingency.index.tolist()],
            "colorscale": "Blues",
        }],
        "layout": {
            "title": f"卡方检验交叉表: {col1} × {col2}",
            "xaxis": {"title": col2},
            "yaxis": {"title": col1},
        },
    }

    return AnalysisResult(
        success=True,
        method="hypothesis",
        summary=f"卡方检验: χ²={round(float(chi2), 4)}, p={round(float(p_value), 6)}, {sig}; Cramér's V={round(v, 4)}",
        data={
            "test_type": "chi_square",
            "chi2_statistic": round(float(chi2), 6),
            "p_value": round(float(p_value), 6),
            "degrees_of_freedom": int(dof),
            "cramers_v": round(v, 4),
            "significance": sig,
            "alpha": alpha,
            "contingency_table": contingency.to_dict(),
        },
        charts=[chart],
    )


def _run_normality(df: pd.DataFrame, params: Dict[str, Any]) -> AnalysisResult:
    """正态性检验 (Shapiro-Wilk)。"""
    alpha = params.get("alpha", 0.05)
    columns = params.get("columns") or []

    if columns:
        num_cols = [c for c in columns if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    else:
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    if not num_cols:
        return AnalysisResult(
            success=False, method="hypothesis",
            summary="未找到数值列，无法执行正态性检验",
            error="没有数值类型的列",
        )

    results = {}
    for col in num_cols:
        data = df[col].dropna().values
        if len(data) < 3:
            results[col] = {"error": "数据点不足 (< 3)"}
            continue
        sample = data[:5000] if len(data) > 5000 else data
        w_stat, p_value = stats.shapiro(sample)
        sig = _significance_text(p_value, alpha)
        results[col] = {
            "w_statistic": round(float(w_stat), 6),
            "p_value": round(float(p_value), 6),
            "is_normal": p_value >= alpha,
            "significance": sig,
            "n_samples": len(sample),
        }

    normal_count = sum(1 for v in results.values() if isinstance(v, dict) and v.get("is_normal", False))

    return AnalysisResult(
        success=True,
        method="hypothesis",
        summary=f"正态性检验 (Shapiro-Wilk): {normal_count}/{len(results)} 列符合正态分布 (α={alpha})",
        data={
            "test_type": "normality",
            "alpha": alpha,
            "results": results,
        },
    )


_TEST_DISPATCH = {
    "t_test": _run_t_test,
    "anova": _run_anova,
    "chi_square": _run_chi_square,
    "normality": _run_normality,
}


@register_method(
    "hypothesis",
    label="假设检验",
    description="支持 t 检验、ANOVA、卡方检验、正态性检验，自动计算效应量和显著性",
    params_schema={
        "test_type": {
            "type": "string",
            "enum": ["t_test", "anova", "chi_square", "normality"],
            "description": "检验类型",
        },
        "value_column": {
            "type": "string",
            "description": "数值列 (t 检验/ANOVA)",
        },
        "group_column": {
            "type": "string",
            "description": "分组列 (t 检验/ANOVA)",
        },
        "category_columns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "分类列 (卡方检验，需要 2 列)",
        },
        "alpha": {
            "type": "number",
            "default": 0.05,
            "description": "显著性水平",
        },
    },
)
def run_hypothesis(df: pd.DataFrame, params: Dict[str, Any]) -> AnalysisResult:
    """执行假设检验分析。"""
    test_type = params.get("test_type")
    if not test_type or test_type not in _TEST_DISPATCH:
        return AnalysisResult(
            success=False,
            method="hypothesis",
            summary=f"不支持的检验类型: {test_type}",
            error=f"test_type 必须是 {list(_TEST_DISPATCH.keys())} 之一",
        )
    return _TEST_DISPATCH[test_type](df, params)
