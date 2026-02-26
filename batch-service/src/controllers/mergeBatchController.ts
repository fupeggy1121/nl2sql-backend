// ============================================================
// 并批确认控制器
// 通过 Supabase RPC 原子性执行并批操作
// ============================================================

import { Request, Response } from 'express';
import supabase from '../config/supabaseClient';
import { ConfirmMergeRequest, ApiResponse } from '../types/batch.types';
import { BatchServiceError } from '../middleware/errorHandler';

/**
 * POST /api/batch/confirm-merge
 *
 * 请求体:
 * {
 *   targetBatchId: string,
 *   sourceSubBatchIds: string[]
 * }
 *
 * 业务逻辑（在 RPC 中原子执行）:
 * 1. 校验所有源子批次在同一站点 (通过 current_station_id)
 * 2. 将源子批次的 batch_id + lot_id 更新为目标批次 (v2)
 * 3. 重算目标批次的 total_qty / good_qty / defect_qty
 * 4. 更新关联 wafers 的 lot_id / batch_id
 * 5. 写入 batch_events
 */
export async function confirmMerge(req: Request, res: Response): Promise<void> {
  const { targetBatchId, sourceSubBatchIds } = req.body as ConfirmMergeRequest;

  // 参数校验
  if (!targetBatchId) {
    throw new BatchServiceError('Missing required field: targetBatchId', 400);
  }
  if (!sourceSubBatchIds || !Array.isArray(sourceSubBatchIds) || sourceSubBatchIds.length === 0) {
    throw new BatchServiceError('Missing or invalid field: sourceSubBatchIds', 400);
  }

  // 调用 Supabase RPC
  const { data, error } = await supabase.rpc('batch_confirm_merge', {
    p_target_batch_id: targetBatchId,
    p_source_sub_batch_ids: sourceSubBatchIds,
  });

  if (error) {
    console.error('[merge] RPC error:', error);

    let statusCode = 500;
    if (error.message?.includes('not found')) statusCode = 404;
    if (error.message?.includes('same station')) statusCode = 409;

    throw new BatchServiceError(
      error.message || 'Failed to confirm merge',
      statusCode,
      error
    );
  }

  const response: ApiResponse = {
    success: true,
    data,
    message: 'Batch merge confirmed successfully',
  };
  res.status(200).json(response);
}
