"""
AnalysisResult — 统一的分析结果数据类
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AnalysisResult:
    """所有分析方法的统一返回格式。"""

    success: bool
    method: str
    summary: str  # 一句话结论
    data: Dict[str, Any] = field(default_factory=dict)  # 结构化数据（统计量等）
    charts: List[Dict[str, Any]] = field(default_factory=list)  # Plotly JSON 列表
    metadata: Dict[str, Any] = field(default_factory=dict)  # 运行耗时、参数等
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "method": self.method,
            "summary": self.summary,
            "data": self.data,
            "charts": self.charts,
            "metadata": self.metadata,
            "error": self.error,
        }
