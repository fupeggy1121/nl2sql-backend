// ============================================================
// 批次作业 TypeScript 类型定义
// 基于 Supabase 数据库表结构 + CIM Schema v2 本体模型
// ============================================================

// ─── 数据库实体类型 ─────────────────────────────────────────

/** 主批次 — 对应 batches 表 (含 v2 新列) */
export interface Batch {
  id: string;
  batch_code: string;
  product_code: string;
  product_name: string;
  total_qty: number;
  good_qty: number;
  defect_qty: number;
  status: BatchStatus;
  current_station_code: string;
  current_station_name: string | null;
  equipment_code: string | null;
  equipment_name: string | null;
  equipment_chamber: string | null;
  next_station_code: string | null;
  next_station_name: string | null;
  product_version: number;
  recipe_code: string;
  ingot_id: string;
  is_small_batch: boolean;
  is_hold: boolean;
  created_at: string;
  updated_at: string;
  // ── v2 新列 ──
  current_station_id: string | null;
  work_order_id: string | null;
}

/** 子批次 — 对应 sub_batches 表 (含 v2 新列) */
export interface SubBatch {
  id: string;
  batch_id: string;
  sub_batch_code: string;
  current_carrier_id: string;
  current_station_id: string;
  total_qty: number;
  good_qty: number;
  defect_qty: number;
  status: BatchStatus;
  created_at: string;
  updated_at: string;
  // ── v2 新列 ──
  lot_id: string | null;
  equipment_id: string | null;
  next_station_id: string | null;
}

/** 晶圆 — 对应 wafers 表 (含 v2 新列) */
export interface Wafer {
  id: string;
  wafer_id_code: string;
  batch_id: string;
  initial_product_version: string | null;
  created_at: string;
  updated_at: string;
  // ── v2 新列 (已由 wafer_carrier_contents 反规范化) ──
  lot_id: string | null;
  sublot_id: string | null;
  carrier_id: string | null;
  slot_number: number | null;
  wafer_type: string | null;
  ingot_id: string | null;
  work_order_id: string | null;
  wafer_id: string | null;
}

/** @deprecated wafer_carrier_contents 表已在 Phase 5 删除，数据已反规范化到 wafers 表 */
export type WaferCarrierContent = Wafer;

/** 载具 — 对应 carriers 表 */
export interface Carrier {
  id: string;
  carrier_code: string;
  capacity: number;
  status: string;
  created_at: string;
  updated_at: string;
}

/** 批次事件 — 对应 batch_events 表 (v2 新增, 替代 batch_operation_logs) */
export interface BatchEvent {
  id: string;
  event_type: string;
  target_type: 'batch' | 'sublot' | 'wafer' | 'carrier';
  target_id: string;
  payload: Record<string, any>;
  triggered_by: string | null;
  created_at: string;
}

/** 站点 — 对应 stations 表 (27 列, 精简) */
export interface Station {
  id: string;
  code: string;
  name: string;
  description: string;
  workshop: string;
  station_type: string;
  auto_entry: boolean | null;
  auto_exit: boolean | null;
  entry_form_config: any[];
  exit_form_config: any[];
  process_rules: Record<string, any>;
  status: string;
  processing_unit: string;
  entry_basket_group: string;
  exit_basket_group: string;
  basket_change_mode: string;
  parameter_group_ids: string[];
  recipe_id: string | null;
  equipment_group_ids: string[];
  created_at: string;
  updated_at: string;
}

/** 工艺路线站点 — 对应 process_route_stations 表 */
export interface ProcessRouteStation {
  id: string;
  route_id: string;
  station_id: string;
  sequence: number;
  created_at: string;
}

/** 操作日志 — Phase 5 后统一从 batch_events 表读取，此类型用于 API 响应兼容 */
export interface BatchOperationLog {
  id: string;
  batch_id: string;
  batch_code: string | null;
  operation_type: OperationType;
  from_station: string | null;
  to_station: string | null;
  operator_id: string;
  remarks: string | null;
  good_qty_before: number | null;
  defect_qty_before: number | null;
  good_qty_after: number | null;
  defect_qty_after: number | null;
  details: Record<string, any>;
  created_at: string;
}

// ─── 枚举 / 联合类型 ────────────────────────────────────────

export type BatchStatus = '待进站' | '加工中' | '待出站' | '已完成' | '暂停' | string;

export type OperationType =
  | 'instation'
  | 'outstation'
  | 'split'
  | 'merge'
  | 'cancel_entry'
  | 'carrier_change'
  | 'rework'
  | 'transfer'
  | 'accumulate';

// ─── 请求类型 ────────────────────────────────────────────────

/** 前端传入的晶圆检测结果（对应前端 WaferData 的关键字段） */
export interface WaferResult {
  wafer_id: string;
  type: 'GOOD' | 'GoodSample' | 'REJECT';
  sublot_id: string;               // 对应前端 wafer.sublotId
  defect_code?: string | null;
  defect_type?: string | null;
}

/** 出站确认请求 — 对应 handleConfirmOutstation */
export interface ConfirmOutstationRequest {
  batchId: string;
  waferResults: WaferResult[];
  subBatches: Array<{ id: string; sublot_id: string }>;
}

/** 进站确认请求 — 对应 handleInstation 的 confirm 逻辑 */
export interface ConfirmInstationRequest {
  batchId: string;
  subBatchIds: string[];
  equipmentCode?: string;
  equipmentName?: string;
  equipmentChamber?: string;
  operator?: string;
}

/** 拆批确认请求 — 对应 handleConfirmSplit */
export interface ConfirmSplitRequest {
  batchId: string;
  splitConfig: {
    new_sub_batches: Array<{
      sub_batch_code: string;
      wafer_ids: string[];
      carrier_id: string;
    }>;
  };
}

/** 并批确认请求 — 对应 handleConfirmMergeBatch */
export interface ConfirmMergeRequest {
  targetBatchId: string;
  sourceSubBatchIds: string[];
}

// ─── 响应类型 ────────────────────────────────────────────────

/** 统一 API 响应格式 */
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

/** 批次详情响应（含子批次和晶圆） */
export interface BatchDetailResponse {
  batch: Batch;
  subBatches: SubBatch[];
  wafers?: Wafer[];
  events?: BatchEvent[];
}
