"""
Multi-Agent 顶层包

Supervisor 路由分发，子 Agent 各自自治：
- query_agent: NL2SQL 查询（委托现有 app/agent/）
- analysis_agent: 数据分析（独立 LangGraph）
- report_agent: 报表生成（预留）
"""
