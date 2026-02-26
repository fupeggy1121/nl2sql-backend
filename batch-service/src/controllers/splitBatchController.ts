// ============================================================
// 拆批确认控制器
// 通过 Supabase RPC 原子性执行拆批操作
// ============================================================

import { Request, Response } from 'express';
import supabase from '../config/supabaseClient';
import { ConfirmSplitRequest, ApiResponse } from '../types/batch.types';
import { BatchServiceError } from '../middleware/errorHandler';

/**
 * POST /api/batch/confirm-split
 *
 * 请求体:
 * {
 *   batchId: string,
 *   splitConfig: {
 *     new_sub_batches: [
 *       { sub_batch_code: string, wafer_ids: string[], carrier_id: string }
 *     ]
 *   }
 * }
 *
 * 业务逻辑（在 RPC 中原子执行）:
 * 1. 校验源批次非 HOLD
 * 2. 为每组晶圆创建新子批次 (含 lot_id)
 * 3. 更新 wafers.sublot_id + carrier_id
 * 4. 写入 batch_events
 */
export async function confirmSplit(req: Request, res: Response): Promise<void> {
  const { batchId, splitConfig } = req.body as ConfirmSplitRequest;

  // 参数校验
  if (!batchId) {
    throw new BatchServiceError('Missing required field: batchId', 400);
  }
  if (!splitConfig?.new_sub_batches || !Array.isArray(splitConfig.new_sub_batches)) {
    throw new BatchServiceError('Missing or invalid field: splitConfig.new_sub_batches', 400);
  }
  if (splitConfig.new_sub_batches.length === 0) {
    throw new BatchServiceError('splitConfig.new_sub_batches must not be empty', 400);
  }

  // 校验每个新子批次的必填字段
  for (const sub of splitConfig.new_sub_batches) {
    if (!sub.sub_batch_code) {
      throw new BatchServiceError('Each new sub-batch must have a sub_batch_code', 400);
    }
    if (!sub.wafer_ids || sub.wafer_ids.length === 0) {
      throw new BatchServiceError(
        `Sub-batch ${sub.sub_batch_code} must have at least one wafer_id`,
        400
      );
    }
    if (!sub.carrier_id) {
      throw new BatchServiceError(
        `Sub-batch ${sub.sub_batch_code} must have a carrier_id`,
        400
      );
    }
  }

  // 调用 Supabase RPC
  const { data, error } = await supabase.rpc('batch_confirm_split', {
    p_batch_id: batchId,
    p_split_config: splitConfig,
  });

  if (error) {
    console.error('[split] RPC error:', error);

    let statusCode = 500;
    if (error.message?.includes('not found')) statusCode = 404;
    if (error.message?.includes('HOLD')) statusCode = 409;

    throw new BatchServiceError(
      error.message || 'Failed to confirm split',
      statusCode,
      error
    );
  }

  const response: ApiResponse = {
    success: true,
    data,
    message: 'Batch split confirmed successfully',
  };
  res.status(200).json(response);
}
