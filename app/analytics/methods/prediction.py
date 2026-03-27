"""
质量预测方法

支持 Random Forest 和 Gradient Boosting，用于分类（良/不良）和回归（预测数值）任务。
输出：准确率/R²、特征重要性、混淆矩阵（分类）、ROC 曲线（分类）。
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder

from app.analytics.models import AnalysisResult
from app.analytics.registry import register_method


def _feature_importance_chart(features: List[str], importances: List[float]) -> Dict[str, Any]:
    paired = sorted(zip(features, importances), key=lambda x: x[1], reverse=True)
    feats, imps = zip(*paired) if paired else ([], [])
    return {
        "type": "bar",
        "title": "特征重要性",
        "data": [{
            "type": "bar",
            "x": list(feats),
            "y": list(imps),
            "name": "重要性",
            "marker": {"color": "#1f77b4"},
        }],
        "layout": {
            "title": "特征重要性",
            "xaxis": {"title": "特征"},
            "yaxis": {"title": "重要性得分"},
        },
    }


def _confusion_matrix_chart(cm: np.ndarray, labels: List[str]) -> Dict[str, Any]:
    return {
        "type": "heatmap",
        "title": "混淆矩阵",
        "data": [{
            "type": "heatmap",
            "z": cm.tolist(),
            "x": [str(l) for l in labels],
            "y": [str(l) for l in labels],
            "colorscale": "Blues",
            "showscale": True,
        }],
        "layout": {
            "title": "混淆矩阵",
            "xaxis": {"title": "预测类别"},
            "yaxis": {"title": "真实类别"},
        },
    }


def _roc_chart(fpr: np.ndarray, tpr: np.ndarray, auc: float) -> Dict[str, Any]:
    return {
        "type": "line",
        "title": f"ROC 曲线 (AUC={round(auc, 4)})",
        "data": [
            {
                "type": "scatter",
                "mode": "lines",
                "x": fpr.tolist(),
                "y": tpr.tolist(),
                "name": f"ROC (AUC={round(auc, 4)})",
                "line": {"color": "#1f77b4"},
            },
            {
                "type": "scatter",
                "mode": "lines",
                "x": [0, 1],
                "y": [0, 1],
                "name": "随机分类器",
                "line": {"dash": "dash", "color": "gray"},
            },
        ],
        "layout": {
            "title": f"ROC 曲线 (AUC={round(auc, 4)})",
            "xaxis": {"title": "假正率 (FPR)"},
            "yaxis": {"title": "真正率 (TPR)"},
        },
    }


@register_method(
    "prediction",
    label="质量预测",
    description="Random Forest / Gradient Boosting 分类或回归预测，含特征重要性、混淆矩阵（分类）、ROC（分类）",
    params_schema={
        "target_column": {
            "type": "string",
            "description": "目标列（必填）",
        },
        "feature_columns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "特征列（空=全部其他数值列）",
        },
        "task": {
            "type": "string",
            "enum": ["auto", "classification", "regression"],
            "default": "auto",
            "description": "任务类型：auto=自动判断（目标列唯一值≤10视为分类）",
        },
        "model": {
            "type": "string",
            "enum": ["random_forest", "gradient_boosting"],
            "default": "random_forest",
            "description": "模型类型",
        },
        "test_size": {
            "type": "number",
            "default": 0.2,
            "description": "测试集比例",
        },
        "n_estimators": {
            "type": "integer",
            "default": 100,
            "description": "树的数量",
        },
        "cv_folds": {
            "type": "integer",
            "default": 5,
            "description": "交叉验证折数（0=不做）",
        },
    },
)
def run_prediction(df: pd.DataFrame, params: Dict[str, Any]) -> AnalysisResult:
    """执行质量预测分析。"""
    target_col = params.get("target_column")
    feature_cols = params.get("feature_columns") or []
    task = params.get("task", "auto")
    model_type = params.get("model", "random_forest")
    test_size = float(params.get("test_size", 0.2))
    n_estimators = int(params.get("n_estimators", 100))
    cv_folds = int(params.get("cv_folds", 5))

    if not target_col:
        return AnalysisResult(
            success=False, method="prediction",
            summary="质量预测需要 target_column 参数",
            error="缺少必要参数: target_column",
        )
    if target_col not in df.columns:
        return AnalysisResult(
            success=False, method="prediction",
            summary=f"目标列 '{target_col}' 不在数据中",
            error=f"列 '{target_col}' 不存在",
        )

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if feature_cols:
        feat_cols = [c for c in feature_cols if c in df.columns and c != target_col]
    else:
        feat_cols = [c for c in numeric_cols if c != target_col]

    if not feat_cols:
        return AnalysisResult(
            success=False, method="prediction",
            summary="没有可用的特征列",
            error="特征列为空",
        )

    # 确定任务类型
    y_raw = df[target_col].dropna()
    n_unique = y_raw.nunique()
    if task == "auto":
        is_classification = n_unique <= 10 or not pd.api.types.is_numeric_dtype(y_raw)
    else:
        is_classification = task == "classification"

    sub = df[feat_cols + [target_col]].dropna()
    if len(sub) < 20:
        return AnalysisResult(
            success=False, method="prediction",
            summary=f"有效样本量不足 ({len(sub)} 行，至少需 20 行)",
            error=f"样本量 {len(sub)} 过少",
        )

    X = sub[feat_cols].values

    if is_classification:
        le = LabelEncoder()
        y = le.fit_transform(sub[target_col].astype(str).values)
        labels = le.classes_.tolist()
    else:
        y = sub[target_col].values.astype(float)
        labels = []

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42,
        stratify=y if is_classification else None,
    )

    # 选模型
    if is_classification:
        if model_type == "gradient_boosting":
            clf = GradientBoostingClassifier(n_estimators=n_estimators, random_state=42)
        else:
            clf = RandomForestClassifier(n_estimators=n_estimators, random_state=42, n_jobs=-1)
    else:
        if model_type == "gradient_boosting":
            clf = GradientBoostingRegressor(n_estimators=n_estimators, random_state=42)
        else:
            clf = RandomForestRegressor(n_estimators=n_estimators, random_state=42, n_jobs=-1)

    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)
    importances = clf.feature_importances_.tolist()

    charts = [_feature_importance_chart(feat_cols, importances)]
    result_data: Dict[str, Any] = {
        "model": model_type,
        "task": "classification" if is_classification else "regression",
        "n_train": len(X_train),
        "n_test": len(X_test),
        "feature_columns": feat_cols,
        "target_column": target_col,
        "feature_importances": {f: round(imp, 6) for f, imp in zip(feat_cols, importances)},
    }

    if is_classification:
        acc = float(accuracy_score(y_test, y_pred))
        cm = confusion_matrix(y_test, y_pred)
        charts.append(_confusion_matrix_chart(cm, labels))

        # ROC (仅二分类)
        auc_score = None
        if len(labels) == 2:
            try:
                y_prob = clf.predict_proba(X_test)[:, 1]
                fpr, tpr, _ = roc_curve(y_test, y_prob)
                auc_score = float(roc_auc_score(y_test, y_prob))
                charts.append(_roc_chart(fpr, tpr, auc_score))
            except Exception:
                pass

        cv_score = None
        if cv_folds >= 2 and len(sub) >= cv_folds * 2:
            cv_scores = cross_val_score(clf, X, y, cv=cv_folds, scoring="accuracy")
            cv_score = round(float(cv_scores.mean()), 4)

        summary = f"分类预测 ({model_type}): 准确率={round(acc, 4)}"
        if auc_score is not None:
            summary += f", AUC={round(auc_score, 4)}"
        if cv_score is not None:
            summary += f", {cv_folds}-折CV={cv_score}"

        result_data.update({
            "accuracy": round(acc, 6),
            "auc": round(auc_score, 6) if auc_score else None,
            "cv_accuracy": cv_score,
            "confusion_matrix": cm.tolist(),
            "labels": labels,
        })
    else:
        r2 = float(r2_score(y_test, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        mae = float(mean_absolute_error(y_test, y_pred))

        cv_r2 = None
        if cv_folds >= 2 and len(sub) >= cv_folds * 2:
            cv_scores = cross_val_score(clf, X, y, cv=cv_folds, scoring="r2")
            cv_r2 = round(float(cv_scores.mean()), 4)

        summary = f"回归预测 ({model_type}): R²={round(r2, 4)}, RMSE={round(rmse, 4)}"
        if cv_r2 is not None:
            summary += f", {cv_folds}-折CV R²={cv_r2}"

        result_data.update({
            "r2": round(r2, 6),
            "rmse": round(rmse, 6),
            "mae": round(mae, 6),
            "cv_r2": cv_r2,
        })

    return AnalysisResult(
        success=True,
        method="prediction",
        summary=summary,
        data=result_data,
        charts=charts,
        metadata={"n_samples": len(sub), "n_features": len(feat_cols)},
    )
