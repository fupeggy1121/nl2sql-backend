// ============================================================
// 操作日志服务 — 查询操作历史
// Phase 5: 统一从 batch_events 表读取（batch_operation_logs 已删除）
// ============================================================

import supabase from '../config/supabaseClient';
import { BatchOperationLog, BatchEvent } from '../types/batch.types';
import { BatchServiceError } from '../middleware/errorHandler';

/**
 * 将 BatchEvent 转换为前端兼容的操作日志格式
 */
function eventToLog(event: BatchEvent): BatchOperationLog {
  return {
    id: event.id,
    batch_id: event.target_id,
    batch_code: event.payload?.batch_code || null,
    operation_type: event.event_type as any,
    from_station: event.payload?.from_station || null,
    to_station: event.payload?.to_station || null,
    operator_id: event.operator_id || '',
    remarks: event.payload?.remarks || null,
    good_qty_before: event.payload?.good_qty_before ?? null,
    defect_qty_before: event.payload?.defect_qty_before ?? null,
    good_qty_after: event.payload?.good_qty_after ?? null,
    defect_qty_after: event.payload?.defect_qty_after ?? null,
    details: event.payload || {},
    created_at: event.created_at,
  };
}

export const operationLogService = {
  /**
   * 查询批次的操作历史
   */
  async getOperationHistory(
    batchId: string,
    limit: number = 50
  ): Promise<BatchOperationLog[]> {
    const { data, error } = await supabase
      .from('batch_events')
      .select('*')
      .eq('target_id', batchId)
      .order('created_at', { ascending: false })
      .limit(limit);

    if (error) {
      throw new BatchServiceError('Failed to query operation history', 500, error);
    }

    return ((data || []) as BatchEvent[]).map(eventToLog);
  },

  /**
   * 按操作类型查询日志
   */
  async getLogsByType(
    operationType: string,
    limit: number = 50
  ): Promise<BatchOperationLog[]> {
    const { data, error } = await supabase
      .from('batch_events')
      .select('*')
      .eq('event_type', operationType)
      .order('created_at', { ascending: false })
      .limit(limit);

    if (error) {
      throw new BatchServiceError('Failed to query logs by type', 500, error);
    }

    return ((data || []) as BatchEvent[]).map(eventToLog);
  },

  /**
   * 查询最近的操作日志
   */
  async getRecentLogs(limit: number = 100): Promise<BatchOperationLog[]> {
    const { data, error } = await supabase
      .from('batch_events')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(limit);

    if (error) {
      throw new BatchServiceError('Failed to query recent logs', 500, error);
    }

    return ((data || []) as BatchEvent[]).map(eventToLog);
  },
};

export default operationLogService;
