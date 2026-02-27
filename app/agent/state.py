"""
AgentState — LangGraph 工作流的全局状态定义

整个工作流的"共享内存"，类比产线上的"工单"。
每个 Node 只更新自己负责的字段，职责清晰，互不干扰。
"""

from typing import TypedDict, Optional, List, Dict, Any, Literal


class AgentState(TypedDict, total=False):
    """AI Agent 全局状态"""

    # ── 输入 ──
    user_input: str                              # 原始用户输入
    session_id: str                              # 会话 ID（用于多轮对话）
    conversation_history: List[Dict[str, str]]   # 对话历史 [{"role": "user/assistant", "content": "..."}]

    # ── 意图路由 ──
    intent: str                                  # 意图分类: query / chat / alert / schedule
    intent_data: Dict[str, Any]                  # 意图识别完整结果（含 entities, confidence 等）

    # ── 语义解析 (Phase 3: 本体引擎) ──
    semantic_context: Dict[str, Any]             # 本体语义上下文 (SemanticContext.to_dict())

    # ── 查询规划 ──
    query_plan: Dict[str, Any]                   # 结构化查询参数（table, metrics, time_range 等）
    rag_context: str                             # RAG 检索到的 schema 上下文

    # ── SQL 生成 ──
    sql: str                                     # 生成的 SQL 语句
    sql_confidence: float                        # SQL 生成置信度
    sql_variants: List[str]                      # SQL 变体建议

    # ── 执行与重试 ──
    query_result: Dict[str, Any]                 # 查询结果 {"success": bool, "data": [...], ...}
    sql_retry_count: int                         # SQL 重试次数（自我修正计数器）
    sql_error: str                               # SQL 执行错误信息（用于自我修正）
    sql_validation: Dict[str, Any]               # SQL 验证结果 (Phase B)

    # ── 结果分析 ──
    chart_type: str                              # 推荐图表类型
    chart_config: Dict[str, Any]                 # ECharts option JSON 配置
    visualization: Dict[str, Any]                # 图表推荐详情（type, title, xAxisField, yAxisField 等）

    # ── 响应 ──
    response: Dict[str, Any]                     # 最终组装的完整响应
    error: str                                   # 全局错误信息

    # ── 对话记忆 (Phase C) ──
    memory_context: Dict[str, Any]               # 记忆模块注入的上下文
    is_followup: bool                            # 是否为追问/指代查询
    resolved_input: str                          # 指代消解后的输入

    # ── 执行时间 ──
    start_time: float                            # 请求开始时间戳

    # ── 执行模式 ──
    approved_sql: str                            # 前端已批准的 SQL（/execute 接口传入，跳过 LLM 生成）

    # ── Fast Path (Phase B1) ──
    fast_path: bool                              # True 时由 semantic_resolver 直接提供 SQL，跳过规划/生成节点
    fast_sql_source: str                         # fast_path SQL 来源描述 (e.g. "business_rule:wip_by_station")

    # ── 管道追踪 (Pipeline Trace) ──
    pipeline_trace: List[Dict[str, Any]]         # 各步骤的执行追踪记录
