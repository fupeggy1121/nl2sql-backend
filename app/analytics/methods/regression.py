"""
回归分析方法

支持简单线性回归、多元线性回归。
输出：模型系数、R²、RMSE、MAE、残差分析图、特征重要性。
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

from app.analytics.models import AnalysisResult
from app.analytics.registry import register_method


def _residual_chart(y_true: np.ndarray, y_pred: np.ndarray, title: str) -> Dict[str, Any]:
    """残差分析散点图。"""
    residuals = (y_true - y_pred).tolist()
    y_pred_list = y_pred.tolist()
    return {
        "type": "scatter",
        "title": title,
        "data": [{
            "type": "scatter",
            "mode": "markers",
            "x": y_pred_list,
            "y": residuals,
            "name": "残差",
            "marker": {"size": 6, "opacity": 0.6},
        }, {
            "type": "line",
            "x": [min(y_pred_list), max(y_pred_list)],
            "y": [0, 0],
            "name": "零线",
            "line": {"dash": "dash", "color": "red"},
        }],
        "layout": {
            "title": title,
            "xaxis": {"title": "预测值"},
            "yaxis": {"title": "残差"},
        },
    }


def _actual_vs_predicted_chart(
    y_true: np.ndarray, y_pred: np.ndarray, target: str
) -> Dict[str, Any]:
    """实际值 vs 预测值对比图。"""
    vals = y_true.tolist()
    preds = y_pred.tolist()
    lo, hi = min(min(vals), min(preds)), max(max(vals), max(preds))
    return {
        "type": "scatter",
        "title": f"实际值 vs 预测值 ({target})",
        "data": [
            {
                "type": "scatter",
                "mode": "markers",
                "x": vals,
                "y": preds,
                "name": "样本点",
                "marker": {"size": 6, "opacity": 0.6},
            },
            {
                "type": "scatter",
                "mode": "lines",
                "x": [lo, hi],
                "y": [lo, hi],
                "name": "理想预测线",
                "line": {"dash": "dash", "color": "gray"},
            },
        ],
        "layout": {
            "title": f"实际值 vs 预测值 ({target})",
            "xaxis": {"title": "实际值"},
            "yaxis": {"title": "预测值"},
        },
    }


def _feature_importance_chart(
    features: List[str], coefs: List[float]
) -> Dict[str, Any]:
    """回归系数柱状图（特征重要性）。"""
    paired = sorted(zip(features, coefs), key=lambda x: abs(x[1]), reverse=True)
    feats, coef_vals = zip(*paired) if paired else ([], [])
    colors = ["#d62728" if c < 0 else "#1f77b4" for c in coef_vals]
    return {
        "type": "bar",
        "title": "回归系数（特征重要性）",
        "data": [{
            "type": "bar",
            "x": list(feats),
            "y": list(coef_vals),
            "marker": {"color": colors},
            "name": "回归系数",
        }],
        "layout": {
            "title": "回归系数（特征重要性）",
            "xaxis": {"title": "特征"},
            "yaxis": {"title": "系数值"},
        },
    }


@register_method(
    "regression",
    label="回归分析",
    description="线性回归/多元线性回归：模型系数、R²、RMSE、MAE、残差图、特征重要性",
    params_schema={
        "target_column": {
            "type": "string",
            "description": "目标（因变量）列名（必填）",
        },
        "feature_columns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "特征（自变量）列名列表（空=全部其他数值列）",
        },
        "fit_intercept": {
            "type": "boolean",
            "default": True,
            "description": "是否拟合截距",
        },
        "cv_folds": {
            "type": "integer",
            "default": 5,
            "description": "交叉验证折数（0 = 不做交叉验证）",
        },
        "standardize": {
            "type": "boolean",
            "default": False,
            "description": "对特征做标准化（StandardScaler）",
        },
    },
)
def run_regression(df: pd.DataFrame, params: Dict[str, Any]) -> AnalysisResult:
    """执行线性回归分析。"""
    target_col = params.get("target_column")
    feature_cols = params.get("feature_columns") or []
    fit_intercept = params.get("fit_intercept", True)
    cv_folds = params.get("cv_folds", 5)
    standardize = params.get("standardize", False)

    if not target_col:
        return AnalysisResult(
            success=False, method="regression",
            summary="回归分析需要 target_column 参数",
            error="缺少必要参数: target_column",
        )
    if target_col not in df.columns:
        return AnalysisResult(
            success=False, method="regression",
            summary=f"目标列 '{target_col}' 不在数据中",
            error=f"列 '{target_col}' 不存在",
        )

    # 选择特征列
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if feature_cols:
        feat_cols = [c for c in feature_cols if c in df.columns and c != target_col]
    else:
        feat_cols = [c for c in numeric_cols if c != target_col]

    if len(feat_cols) == 0:
        return AnalysisResult(
            success=False, method="regression",
            summary="没有可用的特征列",
            error="特征列为空",
        )

    # 清洗：删含 NaN 行
    sub = df[feat_cols + [target_col]].dropna()
    if len(sub) < max(len(feat_cols) + 2, 5):
        return AnalysisResult(
            success=False, method="regression",
            summary=f"有效样本量不足 ({len(sub)} 行)",
            error=f"样本量 {len(sub)} 过少",
        )

    X = sub[feat_cols].values
    y = sub[target_col].values

    if standardize:
        scaler = StandardScaler()
        X = scaler.fit_transform(X)

    model = LinearRegression(fit_intercept=fit_intercept)
    model.fit(X, y)
    y_pred = model.predict(X)

    r2 = float(r2_score(y, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y, y_pred)))
    mae = float(mean_absolute_error(y, y_pred))

    coefs = {feat: round(float(c), 6) for feat, c in zip(feat_cols, model.coef_)}
    intercept = round(float(model.intercept_), 6) if fit_intercept else 0.0

    cv_r2_mean, cv_r2_std = None, None
    if cv_folds and cv_folds >= 2 and len(sub) >= cv_folds * 2:
        X_cv = sub[feat_cols].values
        if standardize:
            X_cv = StandardScaler().fit_transform(X_cv)
        cv_scores = cross_val_score(
            LinearRegression(fit_intercept=fit_intercept),
            X_cv, y, cv=cv_folds, scoring="r2",
        )
        cv_r2_mean = round(float(cv_scores.mean()), 4)
        cv_r2_std = round(float(cv_scores.std()), 4)

    summary = (
        f"线性回归: R²={round(r2, 4)}, RMSE={round(rmse, 4)}, MAE={round(mae, 4)}"
    )
    if cv_r2_mean is not None:
        summary += f"; {cv_folds}-折CV R²={cv_r2_mean}±{cv_r2_std}"

    charts = [
        _actual_vs_predicted_chart(y, y_pred, target_col),
        _residual_chart(y, y_pred, f"残差分析 ({target_col})"),
        _feature_importance_chart(feat_cols, model.coef_.tolist()),
    ]

    return AnalysisResult(
        success=True,
        method="regression",
        summary=summary,
        data={
            "r2": round(r2, 6),
            "rmse": round(rmse, 6),
            "mae": round(mae, 6),
            "intercept": intercept,
            "coefficients": coefs,
            "n_samples": len(sub),
            "n_features": len(feat_cols),
            "feature_columns": feat_cols,
            "target_column": target_col,
            "cv_r2_mean": cv_r2_mean,
            "cv_r2_std": cv_r2_std,
        },
        charts=charts,
        metadata={
            "n_samples": len(sub),
            "n_features": len(feat_cols),
            "standardized": standardize,
        },
    )
