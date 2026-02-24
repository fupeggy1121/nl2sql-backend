// ============================================================
// 操作日志服务 — 查询操作历史
// ============================================================

import supabase from '../config/supabaseClient';
import { BatchOperationLog } from '../types/batch.types';
import { BatchServiceError } from '../middleware/errorHandler';

export const operationLogService = {
  /**
   * 查询批次的操作历史
   */
  async getOperationHistory(
    batchId: string,
    limit: number = 50
  ): Promise<BatchOperationLog[]> {
    const { data, error } = await supabase
      .from('batch_operation_logs')
      .select('*')
      .eq('batch_id', batchId)
      .order('created_at', { ascending: false })
      .limit(limit);

    if (error) {
      throw new BatchServiceError('Failed to query operation history', 500, error);
    }

    return (data || []) as BatchOperationLog[];
  },

  /**
   * 按操作类型查询日志
   */
  async getLogsByType(
    operationType: string,
    limit: number = 50
  ): Promise<BatchOperationLog[]> {
    const { data, error } = await supabase
      .from('batch_operation_logs')
      .select('*')
      .eq('operation_type', operationType)
      .order('created_at', { ascending: false })
      .limit(limit);

    if (error) {
      throw new BatchServiceError('Failed to query logs by type', 500, error);
    }

    return (data || []) as BatchOperationLog[];
  },

  /**
   * 查询最近的操作日志
   */
  async getRecentLogs(limit: number = 100): Promise<BatchOperationLog[]> {
    const { data, error } = await supabase
      .from('batch_operation_logs')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(limit);

    if (error) {
      throw new BatchServiceError('Failed to query recent logs', 500, error);
    }

    return (data || []) as BatchOperationLog[];
  },
};

export default operationLogService;
