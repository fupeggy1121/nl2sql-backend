"""
app.analytics — 数据分析引擎核心包

提供统计分析、预测建模、可视化等能力。
被 Analysis Agent 和 /api/v1/analytics/ 端点共同调用。
"""

from app.analytics.engine import AnalysisEngine  # noqa: F401
from app.analytics.registry import get_method, list_methods  # noqa: F401
