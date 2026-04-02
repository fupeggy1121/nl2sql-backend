"""
分析方法注册表 — 策略模式

使用 @register_method 装饰器注册分析方法，新增方法零侵入。

Usage:
    from app.analytics.registry import register_method

    @register_method("spc", label="SPC 控制图", description="...")
    def run_spc(df: pd.DataFrame, params: dict) -> AnalysisResult:
        ...
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from app.analytics.models import AnalysisResult

logger = logging.getLogger(__name__)

# 全局注册表: name → {func, label, description, params_schema}
_REGISTRY: Dict[str, Dict[str, Any]] = {}

# 指标计算器注册表: metric_name → MetricComputer instance
_METRIC_REGISTRY: Dict[str, Any] = {}


def register_method(
    name: str,
    *,
    label: str = "",
    description: str = "",
    params_schema: Optional[Dict[str, Any]] = None,
) -> Callable:
    """
    装饰器 — 注册分析方法到全局注册表。

    :param name: 方法唯一标识（如 "spc", "anova", "descriptive"）
    :param label: 前端显示的中文标签
    :param description: 方法说明
    :param params_schema: 参数 JSON Schema（用于前端动态表单）
    """

    def decorator(func: Callable[[pd.DataFrame, dict], AnalysisResult]) -> Callable:
        if name in _REGISTRY:
            logger.warning(f"[registry] method '{name}' already registered, overwriting")
        _REGISTRY[name] = {
            "func": func,
            "label": label or name,
            "description": description,
            "params_schema": params_schema or {},
        }
        logger.debug(f"[registry] registered method: {name}")
        return func

    return decorator


def get_method(name: str) -> Optional[Callable[[pd.DataFrame, dict], AnalysisResult]]:
    """获取已注册的分析方法函数。"""
    entry = _REGISTRY.get(name)
    return entry["func"] if entry else None


def list_methods() -> List[Dict[str, Any]]:
    """列出所有已注册的分析方法（不含函数引用）。"""
    return [
        {
            "name": name,
            "label": entry["label"],
            "description": entry["description"],
            "params_schema": entry["params_schema"],
        }
        for name, entry in _REGISTRY.items()
    ]


def has_method(name: str) -> bool:
    return name in _REGISTRY


# ── 指标计算器注册 ──

def register_metric(computer_cls: type) -> type:
    """
    装饰器 — 注册 MetricComputer 子类到指标注册表。

    Usage:
        @register_metric
        class FirstPassYieldComputer(MetricComputer):
            metric_name = "first_pass_yield"
            ...
    """
    name = getattr(computer_cls, "metric_name", "")
    if not name:
        raise ValueError(f"MetricComputer class {computer_cls.__name__} missing metric_name")
    if name in _METRIC_REGISTRY:
        logger.warning(f"[registry] metric '{name}' already registered, overwriting")
    instance = computer_cls()
    _METRIC_REGISTRY[name] = instance
    logger.debug(f"[registry] registered metric: {name}")
    return computer_cls


def get_metric(name: str) -> Optional[Any]:
    """获取已注册的 MetricComputer 实例"""
    return _METRIC_REGISTRY.get(name)


def list_metrics() -> List[Dict[str, str]]:
    """列出所有已注册的指标计算器"""
    return [
        {"metric_name": name, "class": type(inst).__name__}
        for name, inst in _METRIC_REGISTRY.items()
    ]


def has_metric(name: str) -> bool:
    return name in _METRIC_REGISTRY
