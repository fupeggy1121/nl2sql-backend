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

@router.post("/api/query/process")
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

        # ── 通过 supervisor 路由（支持 query / analyze / report 三路） ──
        try:
            from app.agents.supervisor import route_to_agent
            result = await route_to_agent(
                natural_language,
                session_id,
                conversation_history,
            )
        except ImportError:
            # 回退到直接调用 Query Agent
            agent = get_agent_app()
            initial_state = {
                "user_input": natural_language,
                "session_id": session_id,
                "conversation_history": conversation_history,
                "sql_retry_count": 0,
            }
            result = await agent.ainvoke(initial_state)

        logger.info(
            f"[compat/process] session={session_id}, "
            f"input='{natural_language[:60]}...', mode={execution_mode}"
        )

        response_data = result.get("response", {})
        is_followup = result.get("is_followup", False)
        # pipeline_trace: analysis_agent 写在 response 内；query_agent 写在顶层 result
        pipeline_trace = (
            response_data.get("pipeline_trace")
            or result.get("pipeline_trace")
            or []
        )

        return JSONResponse({
            "success": response_data.get("success", False),
            "session_id": session_id,
            "is_followup": is_followup,
            "execution_mode": execution_mode,
            "query_plan": response_data.get("query_plan"),
            "query_result": response_data.get("query_result"),
            "visualization": response_data.get("visualization"),
            "pipeline_trace": pipeline_trace,
            # 分析报表类响应额外字段（良率/OEE 等）
            "analysis": response_data.get("analysis"),
            "charts": response_data.get("charts"),
            "answer": response_data.get("answer"),
            # 基线设定类响应额外字段（baseline_manager 返回）
            "intent": response_data.get("intent"),
            "text": response_data.get("text"),
            "data": response_data.get("data"),
            "baseline_action": response_data.get("baseline_action"),
        })

    except Exception as e:
        logger.error(f"[compat/process] Error: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500,
        )


@router.post("/api/query/execute")
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

        # 统一走 Agent 流水线，返回 pipeline_trace
        agent = get_agent_app()
        # user_input: 优先用前端传来的 natural_language；若缺失则用 SQL 本身作为占位
        # （必须非空，否则 intent_router 用空串调 LLM 可能错误路由到 chat）
        user_input = (
            query_intent_data.get("natural_language", "").strip()
            or f"执行SQL: {sql_query[:80]}"
        )
        initial_state = {
            "user_input": user_input,
            "session_id": str(uuid.uuid4()),
            "conversation_history": [],
            "sql_retry_count": 0,
            "approved_sql": sql_query,
            "sql_edited": bool(body.get("sql_edited", False)),  # 前端手动编辑过 SQL 时为 True
            # 保留上一轮 query 的 query_type，供 result_analyzer 规则引擎使用
            "intent_data": {
                "query_type": query_intent_data.get("query_type", ""),
            },
        }
        result = await agent.ainvoke(initial_state)
        response_data = result.get("response", {})
        return JSONResponse({
            "success": response_data.get("success", False),
            "query_plan": response_data.get("query_plan"),
            "query_result": response_data.get("query_result"),
            "visualization": response_data.get("visualization"),
            "pipeline_trace": response_data.get("pipeline_trace", []),
        })
    except Exception as e:
        logger.error(f"[compat/execute] Error: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500,
        )


@router.post("/api/query/explain")
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
@router.get("/api/query/unified/health")
async def compat_health():
    """健康检查"""
    import os
    return JSONResponse({
        "status": "healthy",
        "service": "ai-agent",
        "version": "2.0.0",
        "llm_provider": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        "db_backend": os.getenv("DB_BACKEND", "supabase"),  # 'mysql' | 'supabase'
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
async def compat_get_synonyms(target_uri: Optional[str] = None, table_name: Optional[str] = None, status: Optional[str] = None):
    """获取同义词列表（target_uri 或向后兼容的 table_name 参数）"""
    try:
        from app.services.synonym_manager import synonym_manager
        is_active_filter = None if status is None else (status == 'active')
        uri_filter = target_uri or table_name  # backward compat
        result = synonym_manager.get_all_synonyms(
            target_uri=uri_filter, is_active=is_active_filter
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
            synonyms_list = body if isinstance(body, list) else body.get("synonyms", [])
            # 批量：{target_uri, synonym} 列表
            target_uri = body.get("target_uri") or body.get("table_name") if not isinstance(body, list) else None
            results = []
            for s in synonyms_list:
                uri = s.get("target_uri") or s.get("table_name") or target_uri
                syn = s.get("synonym") or s.get("keyword") or (s if isinstance(s, str) else None)
                if uri and syn:
                    r = synonym_manager.add_synonym(target_uri=uri, synonym=syn)
                    results.append(r)
            return JSONResponse({"success": True, "data": results})
        else:
            uri = body.get("target_uri") or body.get("table_name")
            syn = body.get("synonym") or body.get("keyword")
            if not uri or not syn:
                return JSONResponse({"success": False, "error": "target_uri 和 synonym 为必填项"}, status_code=400)
            r = synonym_manager.add_synonym(target_uri=uri, synonym=syn)
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


@router.get("/api/synonyms/unmatched")
async def compat_list_unmatched(
    status: str = "pending",
    min_frequency: int = 1,
    limit: int = 100,
):
    """获取未匹配查询词列表"""
    try:
        from app.services.synonym_manager import synonym_manager
        data = synonym_manager.get_unmatched_terms(status, min_frequency, limit)
        return JSONResponse({"success": True, "data": data, "total": len(data)})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/api/synonyms/unmatched/{term_id}/approve")
async def compat_approve_unmatched(term_id: int, request: Request):
    """审批未匹配词 → 自动创建同义词映射"""
    try:
        from app.services.synonym_manager import synonym_manager
        body = await request.json()
        target_uri = body.get("target_uri") or body.get("table_name")
        if not target_uri:
            return JSONResponse({"success": False, "error": "target_uri 必填"}, status_code=400)
        result = synonym_manager.approve_unmatched_term(
            term_id, target_uri,
            reviewed_by=body.get("reviewed_by", "admin"),
        )
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/api/synonyms/unmatched/{term_id}/reject")
async def compat_reject_unmatched(term_id: int):
    """拒绝未匹配词"""
    try:
        from app.services.synonym_manager import synonym_manager
        result = synonym_manager.reject_unmatched_term(term_id, reviewed_by="admin")
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/api/synonyms/unmatched/{term_id}/ignore")
async def compat_ignore_unmatched(term_id: int):
    """忽略未匹配词"""
    try:
        from app.services.synonym_manager import synonym_manager
        result = synonym_manager.ignore_unmatched_term(term_id)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/api/synonyms/audit-log")
async def compat_audit_log(limit: int = 50):
    """操作审计日志"""
    try:
        from app.services.synonym_manager import synonym_manager
        data = synonym_manager.get_audit_log(limit)
        return JSONResponse({"success": True, "data": data})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ═══════════════════════════════════════════════════════════════
#   /api/skills/* — Skill 文件管理（读写 app/skills/metrics/*.md）
# ═══════════════════════════════════════════════════════════════

_SKILLS_METRICS_DIR = None

def _get_skills_dir():
    global _SKILLS_METRICS_DIR
    if _SKILLS_METRICS_DIR is None:
        from pathlib import Path
        _SKILLS_METRICS_DIR = Path(__file__).parent.parent / "skills" / "metrics"
    return _SKILLS_METRICS_DIR


@router.get("/api/skills")
async def list_skills():
    """列出所有 skill 文件（含解析后的 skill_name / zh_names 摘要）"""
    try:
        from app.skills.loader import get_skill_loader
        loader = get_skill_loader()
        skills = loader.list_skills()
        return JSONResponse({
            "success": True,
            "data": [
                {
                    "skill_name": s.skill_name,
                    "zh_names": s.zh_names,
                    "compute_mode": s.compute_mode,
                    "anchor_table": s.anchor_table,
                    "standard_definition": s.standard_definition,
                    "source_file": s.source_file,
                }
                for s in skills
            ],
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/api/skills/{skill_name}/raw")
async def get_skill_raw(skill_name: str):
    """返回 skill 的原始 Markdown 文本"""
    try:
        skills_dir = _get_skills_dir()
        md_file = skills_dir / f"{skill_name}.md"
        if not md_file.exists():
            return JSONResponse({"success": False, "error": "skill 文件不存在"}, status_code=404)
        content = md_file.read_text(encoding="utf-8")
        return JSONResponse({"success": True, "skill_name": skill_name, "content": content})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.put("/api/skills/{skill_name}")
async def save_skill(skill_name: str, request: Request):
    """保存（覆写）skill 的 Markdown 文本"""
    try:
        body = await request.json()
        content = body.get("content", "")
        if not content.strip():
            return JSONResponse({"success": False, "error": "content 不能为空"}, status_code=400)

        skills_dir = _get_skills_dir()
        skills_dir.mkdir(parents=True, exist_ok=True)

        # 基础安全检查：skill_name 不允许路径穿越
        safe_name = skill_name.replace("/", "_").replace("..", "_")
        md_file = skills_dir / f"{safe_name}.md"
        md_file.write_text(content, encoding="utf-8")

        # 重置 loader 缓存，使修改立即生效
        import app.skills.loader as _loader_mod
        _loader_mod._default_loader = None

        return JSONResponse({"success": True, "skill_name": safe_name})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/api/skills")
async def create_skill(request: Request):
    """新建 skill 文件"""
    try:
        body = await request.json()
        skill_name = (body.get("skill_name") or "").strip()
        content = (body.get("content") or "").strip()
        if not skill_name:
            return JSONResponse({"success": False, "error": "skill_name 必填"}, status_code=400)

        safe_name = skill_name.replace("/", "_").replace("..", "_")
        skills_dir = _get_skills_dir()
        skills_dir.mkdir(parents=True, exist_ok=True)
        md_file = skills_dir / f"{safe_name}.md"
        if md_file.exists():
            return JSONResponse({"success": False, "error": "skill 已存在，请使用 PUT 更新"}, status_code=409)

        if not content:
            content = f"---\nskill_name: {safe_name}\nzh_names:\n  - \ncompute_mode: python_compute\nstandard_definition: \"\"\nformula: \"\"\ngranularity: []\n---\n\n## 指标说明\n\n{safe_name} 指标定义。\n"

        md_file.write_text(content, encoding="utf-8")
        import app.skills.loader as _loader_mod
        _loader_mod._default_loader = None

        return JSONResponse({"success": True, "skill_name": safe_name})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.delete("/api/skills/{skill_name}")
async def delete_skill(skill_name: str):
    """删除 skill 文件"""
    try:
        skills_dir = _get_skills_dir()
        safe_name = skill_name.replace("/", "_").replace("..", "_")
        md_file = skills_dir / f"{safe_name}.md"
        if not md_file.exists():
            return JSONResponse({"success": False, "error": "文件不存在"}, status_code=404)
        md_file.unlink()
        import app.skills.loader as _loader_mod
        _loader_mod._default_loader = None
        return JSONResponse({"success": True})
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
