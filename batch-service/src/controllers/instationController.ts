// ============================================================
// 进站确认控制器
// 通过 Supabase RPC 原子性执行进站操作
// ============================================================

import { Request, Response } from 'express';
import supabase from '../config/supabaseClient';
import { ConfirmInstationRequest, ApiResponse } from '../types/batch.types';
import { BatchServiceError } from '../middleware/errorHandler';

/**
 * POST /api/batch/confirm-instation
 *
 * 请求体:
 * {
 *   batchId: string,
 *   subBatchIds: string[],
 *   equipmentCode?: string,
 *   equipmentName?: string,
 *   equipmentChamber?: string,
 *   operator?: string
 * }
 *
 * 业务逻辑（在 RPC 中原子执行）:
 * 1. 校验批次状态为 '待进站' 且非 HOLD
 * 2. 更新主批次: status='加工中', 设置设备信息, current_station_id
 * 3. 更新子批次: status='加工中', equipment_id, next_station_id (v2)
 * 4. 写入 batch_events
 */
export async function confirmInstation(req: Request, res: Response): Promise<void> {
  const body = req.body as ConfirmInstationRequest;

  // 参数校验
  if (!body.batchId) {
    throw new BatchServiceError('Missing required field: batchId', 400);
  }
  if (!body.subBatchIds || !Array.isArray(body.subBatchIds) || body.subBatchIds.length === 0) {
    throw new BatchServiceError('Missing or invalid field: subBatchIds', 400);
  }

  // 调用 Supabase RPC
  const { data, error } = await supabase.rpc('batch_confirm_instation', {
    p_batch_id: body.batchId,
    p_sub_batch_ids: body.subBatchIds,
    p_equipment_code: body.equipmentCode || null,
    p_equipment_name: body.equipmentName || null,
    p_equipment_chamber: body.equipmentChamber || null,
    p_operator: body.operator || 'system',
  });

  if (error) {
    console.error('[instation] RPC error:', error);

    // 根据错误消息映射 HTTP 状态码
    let statusCode = 500;
    if (error.message?.includes('not found')) statusCode = 404;
    if (error.message?.includes('must be') || error.message?.includes('HOLD')) statusCode = 409;

    throw new BatchServiceError(
      error.message || 'Failed to confirm instation',
      statusCode,
      error
    );
  }

  const response: ApiResponse = {
    success: true,
    data,
    message: 'Instation confirmed successfully',
  };
  res.status(200).json(response);
}
