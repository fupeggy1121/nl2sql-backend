"""
AnalysisState — Analysis Agent 的状态定义

与 Query Agent 的 AgentState 完全独立，字段针对分析流程设计。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from typing_extensions import TypedDict


class AnalysisState(TypedDict, total=False):
    # ── 输入 ──
    user_input: str          # 用户原始输入（自然语言）
    session_id: str          # 会话 ID

    # ── 数据加载 ──
    data_source_config: Dict[str, Any]   # DataSourceConfig dict（由 method_selector 或前端提供）
    raw_data: List[Dict[str, Any]]       # 原始行数据
    dataframe_json: str                  # DataFrame 的 JSON 序列化（传递给后续节点）
    raw_dataframe_json: str              # 预处理前的原始 DataFrame JSON（供 metric_compute 等使用）
    data_load_error: Optional[str]

    # ── 预处理 ──
    preprocess_steps: List[str]          # 执行了哪些预处理步骤
    preprocess_log: List[str]            # 预处理日志

    # ── 方法选择 ──
    suggested_method: str                # 自动推荐的分析方法名
    method_reason: str                   # 推荐理由（给用户看）
    method_params: Dict[str, Any]        # 分析参数
    method_select_error: Optional[str]

    # ── 分析执行 ──
    analysis_success: bool
    analysis_summary: str
    analysis_data: Dict[str, Any]        # 分析数值结果
    analysis_charts: List[Dict[str, Any]]  # Plotly chart JSON 列表
    analysis_error: Optional[str]

    # ── 技能上下文 ──
    skill_context: Optional[Dict[str, Any]]  # 匹配到的 Skill 业务定义（供下游节点及 LLM 使用）

    # ── 路由决策 ──
    route_decision: str   # "skill" | "adhoc" | "analysis" | "out_of_scope" | "fallback"
    adhoc_context: Optional[str]  # 即席路径 LLM CoT 推理摘要

    # ── 最终输出 ──
    answer: str                          # 自然语言回答文本
    response: Dict[str, Any]             # 标准化响应（与 Query Agent 格式兼容）
    pipeline_trace: List[Dict[str, Any]] # 全链路追踪步骤（供前端展示）
