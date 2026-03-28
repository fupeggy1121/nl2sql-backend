"""
viz_generator + response_builder 节点

组装最终的自然语言回答和标准化响应（与 Query Agent 格式兼容）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.agents.analysis_agent.state import AnalysisState

logger = logging.getLogger(__name__)


def _build_pipeline_trace(state: AnalysisState) -> list:
    """
    从终态汇总分析全链路追踪步骤，供前端 QueryTrace 组件展示。
    每条 trace 包含：step（步骤名）、status、detail（详细内容，可含 SQL / Python 描述）。
    """
    trace = []

    # Step 1: 意图识别 + 方法选择
    method = state.get("suggested_method", "")
    reason = state.get("method_reason", "")
    if method:
        trace.append({
            "step": "analysis_method_selector",
            "status": "ok",
            "elapsed_ms": 0,
            "summary": f"分析方法识别：{method}（{reason}）",
            "detail": {"method": method, "reason": reason},
        })

    # Step 2: 数据加载 SQL
    config = state.get("data_source_config") or {}
    if config.get("type") == "sql" and config.get("sql"):
        load_ok = not state.get("data_load_error")
        trace.append({
            "step": "analysis_data_loader",
            "status": "ok" if load_ok else "error",
            "elapsed_ms": 0,
            "summary": "数据加载成功" if load_ok else f"数据加载失败：{state.get('data_load_error')}",
            "detail": {
                "sql": config["sql"],
                "error": state.get("data_load_error"),
            },
        })
    elif config.get("type") == "data":
        trace.append({
            "step": "analysis_data_loader",
            "status": "ok",
            "elapsed_ms": 0,
            "summary": "使用内存数据（无 SQL 查询）",
            "detail": {"source": "memory"},
        })

    # Step 3: 预处理
    preprocess_log = state.get("preprocess_log") or []
    preprocess_steps = state.get("preprocess_steps") or []
    if preprocess_steps:
        trace.append({
            "step": "analysis_preprocessor",
            "status": "ok",
            "elapsed_ms": 0,
            "summary": f"预处理：{len(preprocess_steps)} 步",
            "detail": {"steps": preprocess_steps, "log": preprocess_log},
        })

    # Step 4: Python 分析逻辑说明
    if method:
        method_desc = {
            "yield_report": (
                "Python 聚合逻辑：\n"
                "1. 按 report_date + process_code 分组汇总 input_wafers / ng_wafers\n"
                "2. yield_rate = (input - ng) / input × 100%\n"
                "3. 与目标良率对比，标注低于目标的工站\n"
                "4. 生成趋势折线图 + 各工站良率水平柱状图"
            ),
            "oee_report": (
                "Python 配对逻辑：\n"
                "1. 按 lot_code + process_code 匹配进站（op=8）与出站（op=9）事件\n"
                "2. run_minutes = 出站时间 − 进站时间（过滤负值和 >7天异常对）\n"
                "3. A（可用率）= run_minutes / (计划时长 * 60) × 100%\n"
                "4. P（性能效率）= 实际 wafer_num / 标准产能\n"
                "5. Q（合格率）= 参数传入，默认 98%\n"
                "6. OEE = A × P × Q\n"
                "7. 生成 OEE 趋势图 + 设备 OEE 排名柱状图"
            ),
            "spc": (
                "Python SPC 计算：\n"
                "1. 计算均值 X̄ 和标准差 σ\n"
                "2. 控制限 UCL=X̄+3σ, LCL=X̄-3σ\n"
                "3. Cpk = min((USL-X̄)/3σ, (X̄-LSL)/3σ)"
            ),
        }.get(method, f"使用 {method} 方法对数据进行统计分析（pandas/numpy）")
        trace.append({
            "step": "analysis_executor",
            "status": "error" if state.get("analysis_error") else "ok",
            "elapsed_ms": 0,
            "summary": state.get("analysis_error") or f"{method} 分析完成",
            "detail": {
                "method": method,
                "logic": method_desc,
                "error": state.get("analysis_error"),
            },
        })

    # Step 5: 图表生成
    charts = state.get("analysis_charts") or []
    if charts:
        chart_titles = [c.get("title", c.get("type", "图表")) for c in charts]
        trace.append({
            "step": "analysis_viz_generator",
            "status": "ok",
            "elapsed_ms": 0,
            "summary": f"生成 {len(charts)} 张图表：" + "、".join(chart_titles),
            "detail": {"chart_titles": chart_titles},
        })

    return trace


def viz_generator_node(state: AnalysisState) -> dict:
    """
    节点：可视化生成 + 最终响应组装。

    输入: analysis_success, analysis_summary, analysis_data,
          analysis_charts, suggested_method, method_reason
    输出: answer, response, pipeline_trace
    """
    success = state.get("analysis_success", False)
    summary = state.get("analysis_summary", "")
    data = state.get("analysis_data") or {}
    charts = state.get("analysis_charts") or []
    method = state.get("suggested_method", "")
    reason = state.get("method_reason", "")
    error = state.get("analysis_error")

    if not success:
        answer = f"分析执行失败：{error or '未知错误'}"
        response: Dict[str, Any] = {
            "success": False,
            "answer": answer,
            "analysis": None,
            "charts": [],
        }
    else:
        # 构建自然语言答复
        lines = [f"**{method} 分析结果**"]
        if reason:
            lines.append(f"（{reason}）")
        lines.append("")
        if summary:
            lines.append(summary)
        if data:
            # 附加关键数值（最多显示 5 条）
            for i, (k, v) in enumerate(data.items()):
                if i >= 5:
                    break
                if isinstance(v, (int, float)):
                    lines.append(f"- {k}: {v}")
        answer = "\n".join(lines)

        response = {
            "success": True,
            "answer": answer,
            "analysis": {
                "method": method,
                "summary": summary,
                "data": data,
            },
            "charts": charts,
        }

    pipeline_trace = _build_pipeline_trace(state)
    response["pipeline_trace"] = pipeline_trace

    logger.info(f"[viz_generator] success={success}, charts={len(charts)}, trace_steps={len(pipeline_trace)}")
    return {"answer": answer, "response": response, "pipeline_trace": pipeline_trace}
