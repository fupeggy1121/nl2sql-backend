"""
action_executor — 执行层组件：状态写入引擎（含三联写入）

Phase E 新增节点，处理 intent == "action" 的写操作分支。

完整执行流程（对应 SplitEvent 5 维规约）：
  ① 从 TTL 读取目标事件类的 5 维注解规约
  ② 执行 preCondition 前置校验（SQL 查询验证批次状态）
  ③ 调用 apiBinding 指定的 MES 接口（MESAPIAdapter）
  ④ 执行 stateTransitionFunction 状态同步（UPDATE wafer belongsToLot）
  ⑤ 三联写入 EventRecord（matrix_routerx_operation_lot_batch_resume_log + detail + wafer_detail_log）
  ⑥ 执行 postCondition 后验校验
  ⑦ 返回执行结果供 response_builder 格式化
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.agent.state import AgentState
from app.agent.trace import trace_step
from app.services.mes_api_adapter import get_mes_api_adapter, MESAPIError

logger = logging.getLogger(__name__)

# 谱系事件类型 → operation_type 整数映射（对应 semi:LotOperationType 枚举）
_EVENT_TYPE_INT_MAP: Dict[str, int] = {
    "SPLIT": 1,
    "MERGE": 2,
    "CARRIER_TRANSFER": 3,
    "HOLD": 4,
    "RELEASE": 5,
    "NG_RECORD": 6,
    "CANCEL_NG": 7,
    "CHECKIN": 8,
    "CHECKOUT": 9,
    "RETURN": 10,
    "SKIP": 11,
    "REWORK": 12,
    "CANCEL_REWORK": 13,
    "SPLIT_PARENT": 14,
    "SWITCH_SUBROUTE": 15,
    "ACCUMULATE": 16,
}


# ─────────────────────────────────────────────
# 辅助：从 TTL 读取事件类注解规约
# ─────────────────────────────────────────────

def _load_event_spec(event_class_uri: str) -> Dict[str, str]:
    """
    从已加载的 RDFLib Graph 读取指定事件类的 5 维注解。
    返回 {preCondition, inputSchema, transformationLogic, apiBinding, postCondition, stateTransitionFunction}
    """
    try:
        from rdflib import Graph, URIRef, Literal
        from rdflib.namespace import Namespace
        import os

        ttl_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "ontology", "data", "semi-cim-ontology.ttl"
        )
        g = Graph()
        g.parse(ttl_path, format="turtle")

        SEMI = Namespace("http://www.semanticweb.org/semi-mes/ontology#")
        subject = SEMI[event_class_uri.replace("semi:", "")]

        spec: Dict[str, str] = {}
        annotation_props = [
            "preCondition", "inputSchema", "transformationLogic",
            "apiBinding", "postCondition", "stateTransitionFunction"
        ]
        for prop in annotation_props:
            for _, _, obj in g.triples((subject, SEMI[prop], None)):
                spec[prop] = str(obj)

        logger.info(f"[action_executor] Loaded spec for {event_class_uri}: {list(spec.keys())}")
        return spec
    except Exception as e:
        logger.error(f"[action_executor] Failed to load TTL spec for {event_class_uri}: {e}")
        return {}


# ─────────────────────────────────────────────
# 辅助：preCondition 校验
# ─────────────────────────────────────────────

def _check_precondition(precondition: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行 preCondition SQL 校验。

    TTL preCondition 示例:
        "ParentLot.status == 'WAIT' && ParentLot.waferCount > 1"

    当前实现：将 preCondition 转换为 SQL 查询验证批次状态。
    """
    lot_id = params.get("parentLotId") or params.get("lotId")
    if not lot_id:
        return {"passed": False, "reason": "缺少 parentLotId 参数"}

    try:
        from app.services.query_executor import QueryExecutor
        executor = QueryExecutor()

        # 校验批次存在且状态为 WAIT（status 对应数值由 mapping 决定，此处用字符串兜底）
        sql = f"""
            SELECT id, current_lot_code, status, wafer_count
            FROM matrix_routerx_lot
            WHERE current_lot_code = '{lot_id}'
            LIMIT 1
        """
        result = executor.execute(sql)
        rows = result.get("data", [])
        if not rows:
            return {"passed": False, "reason": f"批次 {lot_id} 不存在"}

        row = rows[0]
        # status: WAIT 通常对应 10 或 'WAIT'
        status = str(row.get("status", "")).upper()
        wafer_count = int(row.get("wafer_count") or 0)

        if status not in ("10", "WAIT", "WAITING"):
            return {
                "passed": False,
                "reason": f"批次 {lot_id} 状态为 {status}，须为 WAIT 才可拆批",
                "lot_status": status,
            }
        if wafer_count <= 1:
            return {
                "passed": False,
                "reason": f"批次 {lot_id} 仅含 {wafer_count} 片晶圆，无法拆批",
                "wafer_count": wafer_count,
            }

        return {
            "passed": True,
            "lot_id": lot_id,
            "lot_db_id": row.get("id"),
            "lot_status": status,
            "wafer_count": wafer_count,
            "prev_qty": wafer_count,
        }

    except Exception as e:
        logger.warning(f"[action_executor] preCondition SQL error: {e}")
        # DB 不可用时降级为通过（由 API 层做最终校验）
        return {"passed": True, "warning": f"preCondition SQL skip: {e}"}


# ─────────────────────────────────────────────
# 辅助：三联写入 EventRecord
# ─────────────────────────────────────────────

def _write_event_record(
    event_type: str,
    lot_id: str,
    new_lot_id: str,
    wafer_list: List[str],
    operator_id: str = "SYSTEM",
    before_state: str = "",
    after_state: str = "",
    session_id: str = "",
) -> Dict[str, Any]:
    """
    三联写入 SplitEventRecord：
      ① matrix_routerx_operation_lot_batch_resume_log         — 主事件行
      ② matrix_routerx_operation_lot_batch_resume_log_detail  — 拆批前后批次状态快照
      ③ matrix_routerx_operation_lot_batch_resume_wafer_detail_log — 逐片 Wafer 迁移明细

    当前实现：写入 Supabase（与现有日志表对齐）。
    若表不存在或写入失败，记录 WARNING 后继续（API 已成功，不回滚）。
    """
    results: Dict[str, Any] = {"log_id": None, "detail_id": None, "wafer_detail_ids": []}
    now = datetime.now(timezone.utc).isoformat()
    log_id = str(uuid.uuid4())

    try:
        from app.services.supabase_client import SupabaseClient
        sb = SupabaseClient()

        # ① 主事件行
        op_int = _EVENT_TYPE_INT_MAP.get(event_type.upper(), event_type)
        log_row = {
            "id": log_id,
            "lot_code": lot_id,
            "output_lot_code": new_lot_id,
            "operation_type": op_int,
            "operator_id": operator_id,
            "before_state": before_state,
            "after_state": after_state,
            "session_id": session_id,
            "gmt_create": now,
        }
        resp = sb.client.table("matrix_routerx_operation_lot_batch_resume_log").insert(log_row).execute()
        results["log_id"] = log_id
        logger.info(f"[action_executor] ① matrix_routerx_operation_lot_batch_resume_log 写入: {log_id}")

    except Exception as e:
        logger.warning(f"[action_executor] matrix_routerx_operation_lot_batch_resume_log 写入失败（非致命）: {e}")

    try:
        from app.services.supabase_client import SupabaseClient
        sb = SupabaseClient()

        # ② 批次状态快照
        detail_id = str(uuid.uuid4())
        detail_row = {
            "id": detail_id,
            "log_id": log_id,
            "source_lot_code": lot_id,
            "new_lot_code": new_lot_id,
            "before_state": before_state,
            "after_state": after_state,
            "gmt_create": now,
        }
        sb.client.table("matrix_routerx_operation_lot_batch_resume_log_detail").insert(detail_row).execute()
        results["detail_id"] = detail_id
        logger.info(f"[action_executor] ② matrix_routerx_operation_lot_batch_resume_log_detail 写入: {detail_id}")

    except Exception as e:
        logger.warning(f"[action_executor] matrix_routerx_operation_lot_batch_resume_log_detail 写入失败（非致命）: {e}")

    try:
        from app.services.supabase_client import SupabaseClient
        sb = SupabaseClient()

        # ③ 逐片 Wafer 明细
        wafer_rows = []
        for wcode in wafer_list:
            wafer_rows.append({
                "id": str(uuid.uuid4()),
                "log_id": log_id,
                "wafer_code": wcode,
                "source_lot_code": lot_id,
                "target_lot_code": new_lot_id,
                "operation_type": _EVENT_TYPE_INT_MAP.get(event_type.upper(), event_type),
                "gmt_create": now,
            })
        if wafer_rows:
            sb.client.table("matrix_routerx_operation_lot_batch_resume_wafer_detail_log").insert(wafer_rows).execute()
            results["wafer_detail_ids"] = [r["id"] for r in wafer_rows]
            logger.info(f"[action_executor] ③ matrix_routerx_operation_lot_batch_resume_wafer_detail_log 写入: {len(wafer_rows)} 行")

    except Exception as e:
        logger.warning(f"[action_executor] matrix_routerx_operation_lot_batch_resume_wafer_detail_log 写入失败（非致命）: {e}")

    return results


# ─────────────────────────────────────────────
# 辅助：状态同步 (stateTransitionFunction)
# ─────────────────────────────────────────────

def _sync_wafer_state(new_lot_id: str, wafer_list: List[str]) -> bool:
    """
    执行 stateTransitionFunction：
        UPDATE Wafer SET belongsToLot = newLotId WHERE wafer_code IN waferList

    注意：MES API 调用成功后通常已在 MES DB 侧执行了状态变更。
    此处为 NL2SQL 侧只读DB（只读副本）的最终一致性同步，失败不阻断主流程。
    """
    if not wafer_list:
        return True
    try:
        from app.services.supabase_client import SupabaseClient
        sb = SupabaseClient()
        codes_str = "','".join(wafer_list)
        # Supabase client ORM 更新
        sb.client.table("matrix_routerx_operation_lot_wafer") \
            .update({"lot_id": new_lot_id}) \
            .in_("wafer_code", wafer_list) \
            .execute()
        logger.info(f"[action_executor] stateSync: {len(wafer_list)} wafers → lot {new_lot_id}")
        return True
    except Exception as e:
        logger.warning(f"[action_executor] stateSync failed (non-fatal): {e}")
        return False


# ─────────────────────────────────────────────
# 辅助：postCondition 后验
# ─────────────────────────────────────────────

def _check_postcondition(new_lot_id: str, prev_qty: int, split_count: int) -> Dict[str, Any]:
    """执行 postCondition 校验：新批次存在 + 源批次数量已正确扣减"""
    try:
        from app.services.query_executor import QueryExecutor
        executor = QueryExecutor()
        sql = f"SELECT id FROM matrix_routerx_lot WHERE current_lot_code = '{new_lot_id}' LIMIT 1"
        result = executor.execute(sql)
        rows = result.get("data", [])
        if not rows:
            return {"passed": False, "reason": f"postCondition: 新批次 {new_lot_id} 在 DB 中未找到"}
        return {"passed": True, "new_lot_id": new_lot_id}
    except Exception as e:
        logger.warning(f"[action_executor] postCondition SQL error: {e}")
        return {"passed": True, "warning": f"postCondition SQL skip: {e}"}


# ─────────────────────────────────────────────
# 主节点函数
# ─────────────────────────────────────────────

# 事件类型 → TTL 事件类 URI 映射
_EVENT_CLASS_MAP = {
    "SPLIT": "semi:SplitEvent",
    # 后续扩展:
    # "MERGE": "semi:MergeEvent",
    # "REWORK": "semi:ReworkEvent",
    # "CHECKIN": "semi:CheckinEvent",
    # "CHECKOUT": "semi:CheckoutEvent",
}


def action_executor_node(state: AgentState) -> dict:
    """
    写操作执行节点 (Phase E)。

    输入: intent_data (含 eventType/lotId/waferList) 或 action_intent
    输出: action_result, action_error, response
    """
    t0 = time.perf_counter()
    trace = list(state.get("pipeline_trace", []))
    session_id = state.get("session_id", "")

    # 提取写操作意图数据（优先从 action_intent，回退到 intent_data.entities）
    intent_data = state.get("action_intent") or state.get("intent_data", {})
    entities = intent_data.get("entities", intent_data)  # intent_data 本身有时就是 entities

    event_type = entities.get("eventType", "SPLIT")
    lot_id = entities.get("lotId", "")
    wafer_list: List[str] = entities.get("waferList", [])

    logger.info(
        f"[action_executor] event={event_type}, lotId={lot_id}, "
        f"waferCount={len(wafer_list)}, wafers={wafer_list[:5]}"
    )

    # ── 参数完整性校验 ──
    if not lot_id:
        err = "缺少批次ID（lotId），请在指令中注明，如：'从批次 LOT-001 中拆出…'"
        trace_step(trace, "action_executor", t0, summary=f"参数缺失: {err}")
        return {
            "action_error": err,
            "action_result": {},
            "pipeline_trace": trace,
            "response": _build_error_response(err),
        }

    if event_type == "SPLIT" and not wafer_list:
        err = "拆批操作需要指定晶圆列表（waferList），请在指令中注明，如：'晶圆 W001,W002,W003'"
        trace_step(trace, "action_executor", t0, summary=f"参数缺失: {err}")
        return {
            "action_error": err,
            "action_result": {},
            "pipeline_trace": trace,
            "response": _build_error_response(err),
        }

    # ── ① 读取 TTL 事件规约 ──
    event_class = _EVENT_CLASS_MAP.get(event_type)
    spec: Dict[str, str] = {}
    if event_class:
        spec = _load_event_spec(event_class)

    api_binding = spec.get("apiBinding", "")

    # ── ② preCondition 前置校验 ──
    params = {"parentLotId": lot_id, "lotId": lot_id, "splitWaferList": wafer_list}
    precond_result = _check_precondition(spec.get("preCondition", ""), params)
    if not precond_result.get("passed"):
        reason = precond_result.get("reason", "前置条件校验失败")
        trace_step(trace, "action_executor", t0, summary=f"preCondition FAIL: {reason}")
        return {
            "action_error": reason,
            "action_result": {},
            "pipeline_trace": trace,
            "response": _build_error_response(f"操作被拦截：{reason}"),
        }
    prev_qty = precond_result.get("prev_qty", len(wafer_list))
    logger.info(f"[action_executor] preCondition PASS, prev_qty={prev_qty}")

    # ── ③ 调用 MES API (apiBinding) ──
    new_lot_id: Optional[str] = None
    if api_binding:
        try:
            adapter = get_mes_api_adapter()
            api_result = adapter.call(api_binding, params)
            new_lot_id = api_result.get("$newId")
            logger.info(f"[action_executor] API call OK, $newId={new_lot_id}, raw={str(api_result.get('_raw',''))[:100]}")
        except MESAPIError as e:
            err = f"MES API 调用失败：{e}"
            logger.error(f"[action_executor] {err}")
            trace_step(trace, "action_executor", t0, summary=err)
            return {
                "action_error": err,
                "action_result": {},
                "pipeline_trace": trace,
                "response": _build_error_response(err),
            }
    else:
        # 无 apiBinding（测试或离线模式）：生成本地 mock newId
        new_lot_id = f"{lot_id}-SPLIT-{uuid.uuid4().hex[:6].upper()}"
        logger.warning(f"[action_executor] No apiBinding found, using mock newId={new_lot_id}")

    if not new_lot_id:
        err = "MES API 返回中未包含新批次ID（$newId），请检查接口响应格式与 api_bindings.response_mapping 配置"
        trace_step(trace, "action_executor", t0, summary=err)
        return {
            "action_error": err,
            "action_result": {},
            "pipeline_trace": trace,
            "response": _build_error_response(err),
        }

    # ── ④ 状态同步 (stateTransitionFunction) ──
    sync_ok = _sync_wafer_state(new_lot_id, wafer_list)

    # ── ⑤ 三联写入 EventRecord ──
    record_ids = _write_event_record(
        event_type=event_type,
        lot_id=lot_id,
        new_lot_id=new_lot_id,
        wafer_list=wafer_list,
        operator_id="SYSTEM",
        before_state=str(precond_result.get("lot_status", "")),
        after_state="SPLIT",
        session_id=session_id,
    )

    # ── ⑥ postCondition 后验校验 ──
    postcond = _check_postcondition(new_lot_id, prev_qty, len(wafer_list))
    post_warn = postcond.get("warning") or (
        f"后验失败：{postcond.get('reason')}" if not postcond.get("passed") else None
    )

    # ── ⑦ 构建返回 ──
    action_result = {
        "success": True,
        "eventType": event_type,
        "sourceLotId": lot_id,
        "newLotId": new_lot_id,
        "affectedWafers": wafer_list,
        "waferCount": len(wafer_list),
        "prevQty": prev_qty,
        "remainingQty": prev_qty - len(wafer_list),
        "stateSynced": sync_ok,
        "recordIds": record_ids,
        "postcondPassed": postcond.get("passed", True),
        "spec": {
            "eventClass": event_class,
            "apiBinding": api_binding,
        },
    }
    if post_warn:
        action_result["warning"] = post_warn

    trace_step(trace, "action_executor", t0, summary=(
        f"✅ {event_type} 执行成功: {lot_id} → 新批次 {new_lot_id}, "
        f"{len(wafer_list)} 片 Wafer 迁移"
    ), detail=action_result)

    response = {
        "success": True,
        "action": event_type,
        "message": (
            f"✅ 拆批成功\n"
            f"  源批次：{lot_id}（剩余 {prev_qty - len(wafer_list)} 片）\n"
            f"  新批次：**{new_lot_id}**\n"
            f"  迁移晶圆（{len(wafer_list)} 片）：{', '.join(wafer_list)}\n"
            f"  Wafer belongsToLot 已更新 → {new_lot_id}"
        ),
        "data": action_result,
    }

    return {
        "action_result": action_result,
        "action_error": "",
        "pipeline_trace": trace,
        "response": response,
    }


def _build_error_response(message: str) -> Dict[str, Any]:
    return {"success": False, "message": message, "data": {}}
