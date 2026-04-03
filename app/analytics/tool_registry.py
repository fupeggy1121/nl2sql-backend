"""
Compute Tool Registry — LLM-callable tool wrappers around MetricComputer classes.

Each tool wraps a MetricComputer with:
  - name: unique identifier (used in skill frontmatter `compute_tool`)
  - description: natural-language summary for LLM prompt injection
  - input_schema: columns the tool expects to find in the DataFrame
  - params_schema: parameters LLM can pass (e.g. group_by)

Registration is done via @register_compute_tool decorator applied to the
MetricComputer subclass.  The existing @register_metric decorator is NOT removed
— both registries coexist so existing code calling get_metric() keeps working.

Usage:
    from app.analytics.tool_registry import get_compute_tool, describe_all_tools

    # LLM selects tool name; executor calls it:
    tool = get_compute_tool("first_pass_yield_computer")
    result = tool.call(df, group_by=["process_code"])
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

import pandas as pd

from app.analytics.metrics.base import MetricComputer, MetricResult

logger = logging.getLogger(__name__)

# ── Registry storage ─────────────────────────────────────────────────────────

@dataclass
class ComputeToolSpec:
    """Metadata + callable wrapper for a single compute tool."""
    name: str
    description: str
    input_schema: List[str]          # expected DataFrame columns (for LLM reference)
    params_schema: Dict[str, Any]    # JSON-schema style param descriptions
    computer: MetricComputer         # underlying computer instance

    def call(
        self,
        df: pd.DataFrame,
        group_by: Optional[List[str]] = None,
        **kwargs,
    ) -> MetricResult:
        """Invoke the underlying computer."""
        return self.computer.compute(df, group_by=group_by, **kwargs)


# name → ComputeToolSpec
_TOOL_REGISTRY: Dict[str, ComputeToolSpec] = {}


def register_compute_tool(
    *,
    name: str,
    description: str,
    input_schema: Optional[List[str]] = None,
    params_schema: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Class decorator — registers a MetricComputer subclass as a compute tool.

    Usage:
        @register_compute_tool(
            name="first_pass_yield_computer",
            description="Calculate First Pass Yield (FPY) ...",
            input_schema=["wafer_id", "process_code", "wafer_type", "ng_code", "rn"],
        )
        class FirstPassYieldComputer(MetricComputer):
            ...
    """
    def decorator(cls: Type[MetricComputer]) -> Type[MetricComputer]:
        instance = cls()
        spec = ComputeToolSpec(
            name=name,
            description=description,
            input_schema=input_schema or [],
            params_schema=params_schema or {
                "group_by": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "分组维度列名，如 ['process_code', 'report_date']。不传时自动推断。",
                },
            },
            computer=instance,
        )
        if name in _TOOL_REGISTRY:
            logger.warning(f"[tool_registry] tool '{name}' already registered, overwriting")
        _TOOL_REGISTRY[name] = spec
        logger.debug(f"[tool_registry] registered compute tool: {name}")
        return cls
    return decorator


# ── Lookup helpers ────────────────────────────────────────────────────────────

def get_compute_tool(name: str) -> Optional[ComputeToolSpec]:
    """Return the ComputeToolSpec for a given tool name, or None."""
    return _TOOL_REGISTRY.get(name)


def list_compute_tools() -> List[ComputeToolSpec]:
    """Return all registered tools."""
    return list(_TOOL_REGISTRY.values())


def describe_all_tools() -> str:
    """
    Render a compact, human-readable description of every registered tool
    for injection into an LLM prompt.

    Example output:
        Available compute tools:
        1. first_pass_yield_computer
           说明: 计算一次良率(FPY)...
           期望列: wafer_id, process_code, wafer_type, ng_code, rn
           参数:   group_by (array) — 分组维度列名
        ...
    """
    if not _TOOL_REGISTRY:
        return "（无已注册工具）"

    lines = ["可用计算工具："]
    for i, spec in enumerate(_TOOL_REGISTRY.values(), 1):
        lines.append(f"{i}. {spec.name}")
        lines.append(f"   说明: {spec.description}")
        if spec.input_schema:
            lines.append(f"   期望列: {', '.join(spec.input_schema)}")
        for pname, pmeta in spec.params_schema.items():
            pdesc = pmeta.get("description", "")
            ptype = pmeta.get("type", "any")
            lines.append(f"   参数:   {pname} ({ptype}) — {pdesc}")
    return "\n".join(lines)
