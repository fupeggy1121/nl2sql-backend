"""
API 兼容层 — 保持旧 API 路径不变，前端零改动

将旧的 Flask API 路径映射到新 Agent，响应格式完全兼容：
- POST /api/query/unified/process → Agent 执行完整流水线
- POST /api/query/unified/execute → Agent 执行已批准 SQL
- POST /api/query/unified/explain → Agent 只生成 SQL 不执行
- GET  /api/query/health → 健康检查
- 同义词 CRUD、Schema 注解等保留原始实现
"""

import logging
import uuid
from typing import Optional, Dict, Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.agent.graph import get_agent_app

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Compat Layer"])


# ═══════════════════════════════════════════════════════════════
#   /api/query/unified/* — 核心查询接口（通过 Agent 处理）
# ═══════════════════════════════════════════════════════════════

@router.post("/api/query/unified/process")
async def compat_process_query(request: Request):
    """
    兼容旧 /process 接口（已支持多轮对话）。

    请求格式:
    {
        "natural_language": "查询今天的OEE数据",
        "execution_mode": "execute",  // "explain" or "execute"
        "session_id": "xxx",           // 可选，传入则启用多轮对话记忆
        "conversation_history": [],     // 可选，客户端对话历史
        "user_context": {}
    }

    响应格式:
    {
        "success": true,
        "session_id": "xxx",           // 返回 session_id，前端应保存用于下次请求
        "is_followup": false,
        "query_plan": {...},
        "query_result": {...},
        "visualization": {...}
    }
    """
    try:
        body = await request.json()
        natural_language = (body.get("natural_language") or "").strip()
        execution_mode = body.get("execution_mode", "explain")

        if not natural_language:
            return JSONResponse(
                {"success": False, "error": "natural_language 不能为空"},
                status_code=400,
            )

        if execution_mode not in ("explain", "execute"):
            execution_mode = "explain"

        # 支持多轮对话: 从请求中获取 session_id，没有则生成新的
        session_id = body.get("session_id") or str(uuid.uuid4())
        conversation_history = body.get("conversation_history", [])

        agent = get_agent_app()

        # 运行 Agent（携带 session_id 实现多轮记忆）
        initial_state = {
            "user_input": natural_language,
            "session_id": session_id,
            "conversation_history": conversation_history,
            "sql_retry_count": 0,
        }

        logger.info(
            f"[compat/process] session={session_id}, "
            f"input='{natural_language[:60]}...', mode={execution_mode}"
        )

        if execution_mode == "explain":
            result = await agent.ainvoke(initial_state)
            response_data = result.get("response", {})
            is_followup = result.get("is_followup", False)

            return JSONResponse({
                "success": True,
                "session_id": session_id,
                "is_followup": is_followup,
                "query_plan": response_data.get("query_plan"),
            })
        else:
            result = await agent.ainvoke(initial_state)
            response_data = result.get("response", {})
            is_followup = result.get("is_followup", False)

            return JSONResponse({
                "success": response_data.get("success", False),
                "session_id": session_id,
                "is_followup": is_followup,
                "query_plan": response_data.get("query_plan"),
                "query_result": response_data.get("query_result"),
                "visualization": response_data.get("visualization"),
            })

    except Exception as e:
        logger.error(f"[compat/process] Error: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500,
        )


@router.post("/api/query/unified/execute")
async def compat_execute_query(request: Request):
    """
    兼容旧 /execute 接口。

    请求格式:
    {
        "sql": "SELECT * FROM carriers WHERE ...",
        "query_intent": {...}
    }
    """
    try:
        body = await request.json()
        sql_query = (body.get("sql") or "").strip().rstrip(';').strip()
        query_intent_data = body.get("query_intent", {})

        if not sql_query:
            return JSONResponse(
                {"success": False, "error": "sql 不能为空"},
                status_code=400,
            )

        # 直接用 database tool 执行 SQL + chart recommender
        from app.agent.tools.database_tools import execute_query
        from app.agent.tools.chart_tools import recommend_chart

        exec_result = execute_query.invoke({"sql": sql_query})

        viz = None
        if exec_result.get("success"):
            data = exec_result.get("data", [])
            viz = recommend_chart.invoke({
                "sql": sql_query,
                "data": data,
                "natural_language": query_intent_data.get("natural_language", ""),
                "intent_type": query_intent_data.get("intent", ""),
            })

            from datetime import datetime
            return JSONResponse({
                "success": True,
                "query_result": {
                    "success": True,
                    "data": data,
                    "rows_count": len(data),
                    "sql": sql_query,
                    "summary": f"查询返回 {len(data)} 条记录",
                    "visualization_type": viz.get("type", "table") if viz else "table",
                    "actions": ["export", "refresh"],
                    "query_time_ms": 0,
                    "generated_at": datetime.now().isoformat(),
                },
                "visualization": viz,
            })
        else:
            return JSONResponse(
                {
                    "success": False,
                    "query_result": {
                        "success": False,
                        "data": [],
                        "rows_count": 0,
                        "sql": sql_query,
                        "error_message": exec_result.get("error", "Unknown error"),
                    },
                    "visualization": None,
                },
                status_code=400,
            )

    except Exception as e:
        logger.error(f"[compat/execute] Error: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500,
        )


@router.post("/api/query/unified/explain")
async def compat_explain_query(request: Request):
    """兼容旧 /explain 接口"""
    try:
        body = await request.json()
        natural_language = (body.get("natural_language") or "").strip()

        if not natural_language:
            return JSONResponse(
                {"success": False, "error": "natural_language 不能为空"},
                status_code=400,
            )

        agent = get_agent_app()
        result = await agent.ainvoke({
            "user_input": natural_language,
            "session_id": str(uuid.uuid4()),
            "conversation_history": [],
            "sql_retry_count": 0,
        })

        response_data = result.get("response", {})
        return JSONResponse({
            "success": True,
            "query_plan": response_data.get("query_plan"),
        })

    except Exception as e:
        logger.error(f"[compat/explain] Error: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500,
        )


# ═══════════════════════════════════════════════════════════════
#   /api/query/* — 辅助接口（直接迁移，不经过 Agent）
# ═══════════════════════════════════════════════════════════════

@router.get("/api/query/health")
async def compat_health():
    """健康检查"""
    import os
    return JSONResponse({
        "status": "healthy",
        "service": "ai-agent",
        "version": "2.0.0",
        "llm_provider": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    })


@router.post("/api/query/recognize-intent")
async def compat_recognize_intent(request: Request):
    """意图识别接口"""
    try:
        body = await request.json()
        user_input = (body.get("user_input") or body.get("natural_language") or "").strip()

        if not user_input:
            return JSONResponse(
                {"success": False, "error": "user_input 不能为空"},
                status_code=400,
            )

        from app.agent.tools.intent_tools import classify_intent
        result = classify_intent.invoke({"user_input": user_input})

        return JSONResponse({"success": True, "intent": result})

    except Exception as e:
        logger.error(f"[compat/intent] Error: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500,
        )


# ═══════════════════════════════════════════════════════════════
#   /api/synonyms/* — 同义词管理（直接调用现有服务）
# ═══════════════════════════════════════════════════════════════

@router.get("/api/synonyms")
async def compat_get_synonyms(table_name: Optional[str] = None, status: Optional[str] = None):
    """获取同义词列表"""
    try:
        from app.services.synonym_manager import synonym_manager
        result = synonym_manager.get_all_synonyms(
            table_name=table_name, status=status
        )
        return JSONResponse({"success": True, "data": result})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/api/synonyms/tables")
async def compat_get_synonym_tables():
    """获取按表分组的同义词"""
    try:
        from app.services.synonym_manager import synonym_manager
        result = synonym_manager.get_synonyms_by_table()
        return JSONResponse({"success": True, "data": result})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/api/synonyms")
async def compat_add_synonym(request: Request):
    """添加同义词"""
    try:
        body = await request.json()
        from app.services.synonym_manager import synonym_manager

        # 支持批量和单个
        if isinstance(body, list) or "synonyms" in body:
            synonyms = body if isinstance(body, list) else body.get("synonyms", [])
            results = []
            for s in synonyms:
                r = synonym_manager.add_synonym(
                    keyword=s.get("keyword"),
                    table_name=s.get("table_name"),
                    column_name=s.get("column_name"),
                    description=s.get("description", ""),
                )
                results.append(r)
            return JSONResponse({"success": True, "data": results})
        else:
            r = synonym_manager.add_synonym(
                keyword=body.get("keyword"),
                table_name=body.get("table_name"),
                column_name=body.get("column_name"),
                description=body.get("description", ""),
            )
            return JSONResponse({"success": True, "data": r})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.put("/api/synonyms/{synonym_id}")
async def compat_update_synonym(synonym_id: str, request: Request):
    """更新同义词"""
    try:
        body = await request.json()
        from app.services.synonym_manager import synonym_manager
        r = synonym_manager.update_synonym(synonym_id, body)
        return JSONResponse({"success": True, "data": r})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.delete("/api/synonyms/{synonym_id}")
async def compat_delete_synonym(synonym_id: str, hard: bool = False):
    """删除同义词"""
    try:
        from app.services.synonym_manager import synonym_manager
        if hard:
            r = synonym_manager.hard_delete_synonym(synonym_id)
        else:
            r = synonym_manager.delete_synonym(synonym_id)
        return JSONResponse({"success": True, "data": r})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/api/synonyms/map")
async def compat_synonym_map():
    """获取完整同义词映射"""
    try:
        from app.services.synonym_manager import synonym_manager
        r = synonym_manager.get_synonym_map()
        return JSONResponse({"success": True, "data": r})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/api/synonyms/lookup")
async def compat_synonym_lookup(keyword: str = ""):
    """查找特定关键词"""
    try:
        from app.services.synonym_manager import synonym_manager
        r = synonym_manager.lookup(keyword)
        return JSONResponse({"success": True, "data": r})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/api/synonyms/stats")
async def compat_synonym_stats():
    """同义词统计"""
    try:
        from app.services.synonym_manager import synonym_manager
        r = synonym_manager.get_stats()
        return JSONResponse({"success": True, "data": r})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/api/query/unified/query-recommendations")
async def compat_query_recommendations():
    """预设查询建议"""
    recommendations = [
        {"category": "生产数据", "queries": [
            "查询今天的生产产量",
            "显示最近一周的OEE趋势",
            "对比各产线的良品率",
        ]},
        {"category": "设备数据", "queries": [
            "查询可用的载具数量",
            "显示设备稼动率",
            "列出故障设备",
        ]},
        {"category": "质量数据", "queries": [
            "查询今天的良品率",
            "显示缺陷类型分布",
            "对比各工序的不良率",
        ]},
    ]
    return JSONResponse({"success": True, "recommendations": recommendations})
