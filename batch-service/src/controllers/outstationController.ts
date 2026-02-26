// ============================================================
// 出站确认控制器
// 对应前端 handleConfirmOutstation — 通过 Supabase RPC 原子性执行
// ============================================================

import { Request, Response } from 'express';
import supabase from '../config/supabaseClient';
import { ConfirmOutstationRequest, ApiResponse } from '../types/batch.types';
import { BatchServiceError } from '../middleware/errorHandler';

/**
 * POST /api/batch/confirm-outstation
 *
 * 请求体:
 * {
 *   batchId: string,
 *   waferResults: [{ wafer_id, type: 'GOOD'|'GoodSample'|'REJECT', sublot_id }],
 *   subBatches: [{ id, sublot_id }]
 * }
 *
 * 业务逻辑（在 RPC 中原子执行）:
 * 1. 统计良品/不良品数
 * 2. 通过 current_station_id + 工艺路线计算下一站点 (v2)
 * 3. 更新主批次: status='待进站', current_station_id=next, 清空设备
 * 4. 逐个更新子批次: status='待进站', 更新 wafers.wafer_type
 * 5. 双写 batch_events + batch_operation_logs
 */
export async function confirmOutstation(req: Request, res: Response): Promise<void> {
  const { batchId, waferResults, subBatches } = req.body as ConfirmOutstationRequest;

  // 参数校验
  if (!batchId) {
    throw new BatchServiceError('Missing required field: batchId', 400);
  }
  if (!waferResults || !Array.isArray(waferResults)) {
    throw new BatchServiceError('Missing or invalid field: waferResults', 400);
  }
  if (!subBatches || !Array.isArray(subBatches)) {
    throw new BatchServiceError('Missing or invalid field: subBatches', 400);
  }

  // 调用 Supabase RPC — 所有逻辑在 PL/pgSQL 事务中执行
  const { data, error } = await supabase.rpc('batch_confirm_outstation', {
    p_batch_id: batchId,
    p_wafer_results: waferResults,
    p_sub_batches: subBatches,
  });

  if (error) {
    console.error('[outstation] RPC error:', error);
    throw new BatchServiceError(
      error.message || 'Failed to confirm outstation',
      error.message?.includes('not found') ? 404 : 500,
      error
    );
  }

  const response: ApiResponse = {
    success: true,
    data,
    message: 'Outstation confirmed successfully',
  };
  res.status(200).json(response);
}
