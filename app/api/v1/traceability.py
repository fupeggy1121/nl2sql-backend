"""
追溯查询 API — 批次 / Wafer 生产履历追溯

GET /api/v1/traceability/lot/{lot_code}    — 批次谱系追溯（DAG + 过站记录）
GET /api/v1/traceability/wafer/{wafer_code} — Wafer 时序追溯（时间轴）

Demo 模式：lot_code = "DEMO-2026-A01" 或 wafer_code = "DEMO-W012" 返回模拟数据
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.query_executor import QueryExecutor
from app.services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/traceability", tags=["Traceability"])

# ── 延迟初始化执行器 ──
_executor: QueryExecutor | None = None


def _get_executor() -> QueryExecutor:
    global _executor
    if _executor is None:
        _executor = QueryExecutor(supabase_client=get_supabase_client())
    return _executor


def _run(sql: str) -> List[Dict[str, Any]]:
    try:
        result = _get_executor().execute_query(sql)
        if result.get("success"):
            return result.get("data") or []
        logger.warning(f"[Traceability] query returned error: {result.get('error')}")
    except Exception as e:
        logger.warning(f"[Traceability] query exception: {e}")
    return []


# ── Demo 模拟数据 ──────────────────────────────────────────────────
# 当 lot_code.upper().startswith("DEMO") 时触发，无需真实数据库连接。
# 可用 Demo 批次号：DEMO-2026-A01（父批次，25片），DEMO-2026-B01（子批次12片），
#                   DEMO-2026-B02（子批次13片）
# 可用 Demo Wafer号：DEMO-W012 或任意 DEMO-* 字符串

_DEMO_LOT_PARENT = "DEMO-2026-A01"
_DEMO_LOT_B01    = "DEMO-2026-B01"
_DEMO_LOT_B02    = "DEMO-2026-B02"

_WAFER_IDS_PARENT = [f"W-{i:03d}" for i in range(1, 26)]
_WAFER_IDS_B01    = [f"W-{i:03d}" for i in range(1, 13)]
_WAFER_IDS_B02    = [f"W-{i:03d}" for i in range(13, 26)]

_STATIONS = [
    {"id": "ST-INHO",  "name": "进料检验(INHO)",    "type": "测量", "eq": "EQ-CMM-01"},
    {"id": "ST-OXID",  "name": "热氧化(OXID)",      "type": "加工", "eq": "EQ-FURNACE-03"},
    {"id": "ST-LPCVD", "name": "低压CVD(LPCVD)",    "type": "加工", "eq": "EQ-CVD-02"},
    {"id": "ST-LITHO", "name": "光刻(LITHO)",        "type": "加工", "eq": "EQ-STEPPER-01"},
    {"id": "ST-ETCH",  "name": "干法刻蚀(ETCH)",    "type": "加工", "eq": "EQ-RIE-04"},
    {"id": "ST-MEAS",  "name": "膜厚量测(MEAS)",    "type": "测量", "eq": "EQ-ELLIP-02"},
    {"id": "ST-CMP",   "name": "化学机械研磨(CMP)", "type": "加工", "eq": "EQ-CMP-01"},
    {"id": "ST-FINAL", "name": "终测(FINAL)",        "type": "测量", "eq": "EQ-PROBE-03"},
]
_STATION_DURATIONS = [30, 90, 120, 60, 75, 25, 150, 20]


def _ts(base: datetime, minutes: int) -> str:
    return (base + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S")


def _build_pass_records(lot_code: str, wafer_ids: List[str], base: datetime) -> List[Dict[str, Any]]:
    records = []
    rec_id = 1
    for w_idx, wid in enumerate(wafer_ids):
        offset = w_idx * 15
        for s_idx, st in enumerate(_STATIONS):
            dur = _STATION_DURATIONS[s_idx]
            in_t  = _ts(base, offset + s_idx * 200)
            out_t = _ts(base, offset + s_idx * 200 + dur)
            records.append({
                "id":           f"PR-{lot_code[-3:]}-{rec_id:04d}",
                "station_id":   st["id"],
                "station_name": st["name"],
                "station_type": st["type"],
                "equipment_id": st["eq"],
                "lot_code":     lot_code,
                "wafer_id":     wid,
                "in_time":      in_t,
                "out_time":     out_t,
                "operator_id":  f"OP-{(w_idx % 3) + 1:03d}",
                "recipe_id":    f"RCP-{st['id']}-V3",
                "status":       "PASS" if (w_idx + s_idx) % 7 != 0 else "NG",
            })
            rec_id += 1
    return records


def _build_measurement_records(lot_code: str, wafer_ids: List[str], base: datetime) -> List[Dict[str, Any]]:
    import random
    rng = random.Random(42)
    meas_stations = [s for s in _STATIONS if s["type"] == "测量"]
    records = []
    rec_id = 1
    for wid in wafer_ids:
        for st in meas_stations:
            records.append({
                "id":                    f"MR-{lot_code[-3:]}-{rec_id:04d}",
                "station_id":            st["id"],
                "station_name":          st["name"],
                "equipment_id":          st["eq"],
                "lot_code":              lot_code,
                "wafer_id":              wid,
                "measure_time":          _ts(base, rec_id * 40),
                "param_thickness_nm":    round(rng.gauss(280.0, 4.5), 2),
                "param_uniformity_pct":  round(rng.gauss(1.2, 0.3), 3),
                "param_resistivity_ohm": round(rng.gauss(15.5, 0.8), 3),
                "result":                "PASS" if rng.random() > 0.08 else "NG",
                "operator_id":           f"OP-{(rec_id % 3) + 1:03d}",
            })
            rec_id += 1
    return records


def _build_state_transitions(lot_code: str, wafer_ids: List[str], base: datetime,
                             genealogy: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    构造「状态机追溯 DAG」的边列表。
    每条记录描述一次状态切换：
      from_node  — 批次在某操作「之前」的状态节点 ID
      to_node    — 批次在该操作「之后」的状态节点 ID
      event      — 驱动转移的操作标签（进站/出站/拆批/返工…）
      event_type — 机器可读类型（CHECKIN / CHECKOUT / SPLIT / REWORK / MERGE）
      lot_code   — 所属批次
      station    — 工序站点名
      time       — 发生时间
      wafer_count / operator_id / note 等附属信息

    节点 ID 规范：{lot_code}@{状态标签}，如 "DEMO-2026-A01@待检验"
    """
    transitions: List[Dict[str, Any]] = []
    seq_id = 1

    # ── 1. 从 pass_records 中按批次维度（所有 wafer 合并同工序）生成进/出站转移 ──
    # 状态序列：投料 → 进站1 → 出站1 → 进站2 → 出站2 → … → 完成
    # 节点粒度：批次级（不展开到单片，单片在时间轴中呈现）
    lot_short = lot_code.split("-")[-1]  # "A01"
    wafer_count = len(wafer_ids)

    # 初始节点：投料/待加工
    prev_node = f"{lot_code}@投料"

    for s_idx, st in enumerate(_STATIONS):
        dur = _STATION_DURATIONS[s_idx]
        checkin_time  = _ts(base, s_idx * 200)
        checkout_time = _ts(base, s_idx * 200 + dur)
        state_in  = f"{lot_code}@{st['name']}-进站"
        state_out = f"{lot_code}@{st['name']}-出站"

        # 进站事件
        transitions.append({
            "id":          f"ST-{lot_short}-{seq_id:03d}",
            "from_node":   prev_node,
            "to_node":     state_in,
            "event":       f"进站 → {st['name']}",
            "event_type":  "CHECKIN",
            "lot_code":    lot_code,
            "station":     st["name"],
            "station_id":  st["id"],
            "equipment":   st["eq"],
            "time":        checkin_time,
            "wafer_count": wafer_count,
            "operator_id": f"OP-{(s_idx % 3) + 1:03d}",
            "note":        f"{lot_code} 批次进入 {st['name']}",
        })
        seq_id += 1

        # ── 插入拆批/返工事件（如果发生在该站点出站之时）──
        for ge in genealogy:
            if ge.get("station_id") == st["id"] and ge.get("lot_id") == lot_code:
                op = ge["operation_type"]
                child = ge.get("child_lot_id", "")
                transitions.append({
                    "id":             f"ST-{lot_short}-{seq_id:03d}",
                    "from_node":      state_in,
                    "to_node":        f"{child}@投料",
                    "event":          f"{op} → {child.split('-')[-1]}",
                    "event_type":     op,
                    "lot_code":       lot_code,
                    "child_lot":      child,
                    "station":        st["name"],
                    "station_id":     st["id"],
                    "time":           ge["event_time"],
                    "wafer_count":    ge.get("wafer_count_out", 0),
                    "operator_id":    ge.get("operator_id", ""),
                    "note":           ge.get("note", ""),
                })
                seq_id += 1

        # 出站事件
        transitions.append({
            "id":          f"ST-{lot_short}-{seq_id:03d}",
            "from_node":   state_in,
            "to_node":     state_out,
            "event":       f"出站 ← {st['name']}",
            "event_type":  "CHECKOUT",
            "lot_code":    lot_code,
            "station":     st["name"],
            "station_id":  st["id"],
            "equipment":   st["eq"],
            "time":        checkout_time,
            "wafer_count": wafer_count,
            "operator_id": f"OP-{(s_idx % 3) + 1:03d}",
            "note":        f"{lot_code} 完成 {st['name']}，状态更新",
        })
        seq_id += 1
        prev_node = state_out

    # 末尾节点：完成
    transitions.append({
        "id":          f"ST-{lot_short}-{seq_id:03d}",
        "from_node":   prev_node,
        "to_node":     f"{lot_code}@完成",
        "event":       "完成入库",
        "event_type":  "DONE",
        "lot_code":    lot_code,
        "station":     "出货",
        "time":        _ts(base, len(_STATIONS) * 200 + 60),
        "wafer_count": wafer_count,
        "operator_id": "OP-001",
        "note":        "所有工序完成，批次流转完毕",
    })
    return transitions


def _build_genealogy_events(parent: str, b01: str, b02: str, base: datetime) -> List[Dict[str, Any]]:
    split_t   = _ts(base, 320)
    rework_t  = _ts(base, 580)
    return [
        {
            "id": "GE-0001", "operation_type": "SPLIT", "event_type": "SPLIT",
            "lot_id": parent, "parent_lot_id": parent, "child_lot_id": b01,
            "lot_code": parent, "result_lot_id": b01,
            "wafer_count_in": 25, "wafer_count_out": 12,
            "operator_id": "OP-002", "station_id": "ST-LITHO",
            "event_time": split_t,
            "note": "光刻前按工艺路径拆批：B01(优先流片) / B02(常规流片)",
        },
        {
            "id": "GE-0002", "operation_type": "SPLIT", "event_type": "SPLIT",
            "lot_id": parent, "parent_lot_id": parent, "child_lot_id": b02,
            "lot_code": parent, "result_lot_id": b02,
            "wafer_count_in": 25, "wafer_count_out": 13,
            "operator_id": "OP-002", "station_id": "ST-LITHO",
            "event_time": split_t,
            "note": "光刻前按工艺路径拆批：B01(优先流片) / B02(常规流片)",
        },
        {
            "id": "GE-0003", "operation_type": "REWORK", "event_type": "REWORK",
            "lot_id": b02, "parent_lot_id": b02, "child_lot_id": f"{b02}-RW1",
            "lot_code": b02, "result_lot_id": f"{b02}-RW1",
            "wafer_count_in": 3, "wafer_count_out": 3,
            "operator_id": "OP-003", "station_id": "ST-ETCH",
            "event_time": rework_t,
            "note": "刻蚀过刻3片NG片返工处理",
        },
    ]


def _mock_lot_response(lot_code: str) -> "LotTraceabilityResponse":
    uc = lot_code.upper()
    base = datetime(2026, 3, 1, 8, 0, 0)
    if uc == _DEMO_LOT_PARENT.upper():
        wafer_ids, lot = _WAFER_IDS_PARENT, _DEMO_LOT_PARENT
    elif uc == _DEMO_LOT_B01.upper():
        wafer_ids, lot = _WAFER_IDS_B01, _DEMO_LOT_B01
        base += timedelta(hours=8)
    elif uc == _DEMO_LOT_B02.upper():
        wafer_ids, lot = _WAFER_IDS_B02, _DEMO_LOT_B02
        base += timedelta(hours=8)
    else:
        wafer_ids = [f"W-{i:03d}" for i in range(1, 6)]
        lot = lot_code
        base += timedelta(hours=4)

    lot_info = {
        "lot_id":      lot,
        "lot_code":    lot,
        "product_id":  "PRD-CMOS-28NM",
        "recipe_id":   "RCP-MAIN-V3.2",
        "route_id":    "RT-STD-28NM-A",
        "wafer_count": len(wafer_ids),
        "status":      "在制" if lot == _DEMO_LOT_PARENT else "完成",
        "priority":    "高" if "B01" in lot else "正常",
        "operator_id": "OP-001",
        "customer":    "CC-SEMI",
        "created_at":  base.strftime("%Y-%m-%dT%H:%M:%S"),
        "updated_at":  (base + timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%S"),
    }
    genealogy_events = (
        _build_genealogy_events(_DEMO_LOT_PARENT, _DEMO_LOT_B01, _DEMO_LOT_B02, base)
        if lot == _DEMO_LOT_PARENT else []
    )
    pass_records        = _build_pass_records(lot, wafer_ids, base)
    measurement_records = _build_measurement_records(lot, wafer_ids, base)
    state_transitions   = _build_state_transitions(lot, wafer_ids, base, genealogy_events)
    return LotTraceabilityResponse(
        success=True,
        lot_code=lot,
        lot_info=lot_info,
        wafer_ids=wafer_ids,
        genealogy_events=genealogy_events,
        state_transitions=state_transitions,
        pass_records=pass_records,
        measurement_records=measurement_records,
    )


def _mock_wafer_response(wafer_code: str) -> "WaferTraceabilityResponse":
    base = datetime(2026, 3, 1, 8, 0, 0)
    # 从 wafer_code 中提取 W-xxx 部分（如 DEMO-W012 → W-012）
    parts = wafer_code.upper().replace("DEMO-", "").replace("DEMO", "")
    wid = parts if parts.startswith("W-") else "W-012"
    timeline = []
    for s_idx, st in enumerate(_STATIONS):
        dur = _STATION_DURATIONS[s_idx]
        timeline.append({
            "id":           f"TL-{s_idx+1:03d}",
            "station_id":   st["id"],
            "station_name": st["name"],
            "station_type": st["type"],
            "equipment_id": st["eq"],
            "lot_id":       _DEMO_LOT_PARENT,
            "wafer_id":     wid,
            "in_time":      _ts(base, s_idx * 200),
            "out_time":     _ts(base, s_idx * 200 + dur),
            "recipe_id":    f"RCP-{st['id']}-V3",
            "operator_id":  "OP-002",
            "status":       "PASS" if s_idx != 4 else "NG→REWORK",
        })
    return WaferTraceabilityResponse(
        success=True,
        wafer_code=wafer_code,
        timeline=timeline,
    )


# ── 响应模型 ──
class LotTraceabilityResponse(BaseModel):
    success: bool
    lot_code: str
    lot_info: Dict[str, Any] = {}
    wafer_ids: List[str] = []           # 该批次下所有 wafer_id 列表（用于前端下拉）
    genealogy_events: List[Dict[str, Any]] = []   # 原始谱系事件（SPLIT/MERGE/REWORK）
    state_transitions: List[Dict[str, Any]] = []  # 状态机转移边列表，用于 DAG 渲染
    pass_records: List[Dict[str, Any]] = []  # 每条记录含 wafer_id 字段
    measurement_records: List[Dict[str, Any]] = []
    error: str = ""


class WaferTraceabilityResponse(BaseModel):
    success: bool
    wafer_code: str
    timeline: List[Dict[str, Any]] = []
    error: str = ""


# ── 端点 ──

@router.get("/lot/{lot_code}", response_model=LotTraceabilityResponse)
async def get_lot_traceability(lot_code: str):
    """
    获取批次追溯信息：
      - lot_info: 批次基本信息
      - genealogy_events: SPLIT / MERGE / REWORK 谱系事件（用于 DAG 渲染）
      - pass_records: 工序过站记录
      - measurement_records: 量测记录
    Demo: lot_code 以 "DEMO" 开头时返回模拟数据（无需数据库）。
    """
    if lot_code.upper().startswith("DEMO"):
        return _mock_lot_response(lot_code)
    try:
        # ── 批次基本信息 ──
        lot_info_rows = _run(
            f"SELECT * FROM matrix_routerx_operation_lot "
            f"WHERE lot_code = '{lot_code}' LIMIT 1"
        )
        lot_info = lot_info_rows[0] if lot_info_rows else {}

        # ── 全部操作履历（主表）按时间排序 ──
        all_ops = _run(
            f"SELECT id, lot_id, lot_code, output_lot_id, output_lot_code, "
            f"  process_id, process_code, process_name, operation_type, "
            f"  before_state, after_state, create_user_id, create_user, "
            f"  extra, gmt_create "
            f"FROM matrix_routerx_operation_lot_batch_resume_log "
            f"WHERE lot_code = '{lot_code}' "
            f"ORDER BY gmt_create"
        )

        # ── 谱系事件：拆批(1)、并批(2)、返工(12)、拆父批(14)、攒批(16) ──
        _GENEALOGY_OPS = {1, 2, 12, 14, 16}
        _OP_TYPE_LABEL = {
            1: "SPLIT", 2: "MERGE", 3: "CarrierTransfer", 4: "Hold", 5: "Release",
            6: "NGRecording", 7: "CancelNG", 8: "CheckIn", 9: "CheckOut",
            10: "Return", 11: "Skip", 12: "Rework", 13: "CancelRework",
            14: "SplitParent", 15: "SwitchSubRoute", 16: "Accumulate",
            17: "CarrierChange", 18: "CreateLocalLot", 19: "OpenLot",
            20: "ExperimentSkip", 21: "CancelCreateLocalLot", 22: "CancelOpenLot",
            23: "CompleteLot",
        }
        genealogy_events = [
            {**row, "event_type": _OP_TYPE_LABEL.get(row.get("operation_type"), str(row.get("operation_type", "")))}
            for row in all_ops if row.get("operation_type") in _GENEALOGY_OPS
        ]

        # ── 状态机转移（全部操作构成 DAG 边）──
        state_transitions = []
        for idx, op in enumerate(all_ops):
            op_type = op.get("operation_type")
            op_label = _OP_TYPE_LABEL.get(op_type, str(op_type))
            before = op.get("before_state") or op.get("process_status_before") or f"状态{idx}"
            after = op.get("after_state") or op.get("process_status_after") or f"状态{idx + 1}"
            state_transitions.append({
                "id":          str(op.get("id", idx)),
                "from_node":   f"{lot_code}@{before}",
                "to_node":     f"{lot_code}@{after}",
                "event":       op_label,
                "event_type":  op_label,
                "lot_code":    lot_code,
                "operation_type": op_type,
                "process_code": op.get("process_code", ""),
                "process_name": op.get("process_name", ""),
                "operator":    op.get("create_user", ""),
                "time":        str(op.get("gmt_create", "")),
            })

        # ── 过站记录：进站(8) + 出站(9) ──
        pass_records = [r for r in all_ops if r.get("operation_type") in (8, 9)]

        # ── 量测记录（尝试查询，失败时置空） ──
        measurement_records: list = []
        try:
            measurement_records = _run(
                f"SELECT * FROM process_measure_data "
                f"WHERE lot_code = '{lot_code}' "
                f"ORDER BY gmt_create LIMIT 500"
            )
        except Exception:
            pass

        # ── Wafer ID 列表 ──
        wafer_ids = sorted(
            {str(r["wafer_code"]) for r in (lot_info_rows or []) if r.get("wafer_code")}
        )
        if not wafer_ids:
            wafer_rows = _run(
                f"SELECT DISTINCT wafer_code FROM matrix_routerx_operation_lot_wafer "
                f"WHERE lot_id = '{lot_info.get('id', '')}' LIMIT 200"
            ) if lot_info.get("id") else []
            wafer_ids = sorted({str(r["wafer_code"]) for r in wafer_rows if r.get("wafer_code")})

        return LotTraceabilityResponse(
            success=True,
            lot_code=lot_code,
            lot_info=lot_info,
            wafer_ids=wafer_ids,
            genealogy_events=genealogy_events,
            state_transitions=state_transitions,
            pass_records=pass_records,
            measurement_records=measurement_records,
        )

    except Exception as e:
        logger.error(f"[Traceability] lot {lot_code} error: {e}")
        return LotTraceabilityResponse(
            success=False,
            lot_code=lot_code,
            error=str(e),
        )


@router.get("/wafer/{wafer_code}", response_model=WaferTraceabilityResponse)
async def get_wafer_traceability(wafer_code: str):
    """
    获取 Wafer 追溯时间轴：
      - timeline: 按时间排序的过站记录
    Demo: wafer_code 以 "DEMO" 开头时返回模拟数据（无需数据库）。
    """
    if wafer_code.upper().startswith("DEMO"):
        return _mock_wafer_response(wafer_code)
    try:
        timeline = _run(
            f"SELECT spr.*, mol.lot_id, mol.wafer_id "
            f"FROM station_process_record spr "
            f"JOIN matrix_routerx_operation_lot mol ON mol.id = spr.sublot_id "
            f"WHERE mol.wafer_id = '{wafer_code}' "
            f"ORDER BY spr.in_time"
        )

        return WaferTraceabilityResponse(
            success=True,
            wafer_code=wafer_code,
            timeline=timeline,
        )

    except Exception as e:
        logger.error(f"[Traceability] wafer {wafer_code} error: {e}")
        return WaferTraceabilityResponse(
            success=False,
            wafer_code=wafer_code,
            error=str(e),
        )
