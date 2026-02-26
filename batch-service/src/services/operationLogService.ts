// ============================================================
// 操作日志服务 — 查询操作历史
// v2: 同时查询 batch_operation_logs (旧) 和 batch_events (新)
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
    operator_id: event.triggered_by || '',
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
   * 查询批次的操作历史（合并旧日志 + 新事件）
   */
  async getOperationHistory(
    batchId: string,
    limit: number = 50
  ): Promise<BatchOperationLog[]> {
    // 并发查询两个表
    const [logsResult, eventsResult] = await Promise.all([
      supabase
        .from('batch_operation_logs')
        .select('*')
        .eq('batch_id', batchId)
        .order('created_at', { ascending: false })
        .limit(limit),
      supabase
        .from('batch_events')
        .select('*')
        .eq('target_id', batchId)
        .order('created_at', { ascending: false })
        .limit(limit),
    ]);

    if (logsResult.error && eventsResult.error) {
      throw new BatchServiceError('Failed to query operation history', 500, logsResult.error);
    }

    const logs = (logsResult.data || []) as BatchOperationLog[];
    const events = (eventsResult.data || []).map(eventToLog);

    // 合并并按时间降序排列，去重（以 id 为准）
    const merged = [...logs, ...events];
    const seen = new Set<string>();
    const deduplicated = merged.filter(item => {
      if (seen.has(item.id)) return false;
      seen.add(item.id);
      return true;
    });

    deduplicated.sort((a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );

    return deduplicated.slice(0, limit);
  },

  /**
   * 按操作类型查询日志
   */
  async getLogsByType(
    operationType: string,
    limit: number = 50
  ): Promise<BatchOperationLog[]> {
    const [logsResult, eventsResult] = await Promise.all([
      supabase
        .from('batch_operation_logs')
        .select('*')
        .eq('operation_type', operationType)
        .order('created_at', { ascending: false })
        .limit(limit),
      supabase
        .from('batch_events')
        .select('*')
        .eq('event_type', operationType)
        .order('created_at', { ascending: false })
        .limit(limit),
    ]);

    if (logsResult.error && eventsResult.error) {
      throw new BatchServiceError('Failed to query logs by type', 500, logsResult.error);
    }

    const logs = (logsResult.data || []) as BatchOperationLog[];
    const events = (eventsResult.data || []).map(eventToLog);

    const merged = [...logs, ...events];
    merged.sort((a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );

    return merged.slice(0, limit);
  },

  /**
   * 查询最近的操作日志
   */
  async getRecentLogs(limit: number = 100): Promise<BatchOperationLog[]> {
    const [logsResult, eventsResult] = await Promise.all([
      supabase
        .from('batch_operation_logs')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(limit),
      supabase
        .from('batch_events')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(limit),
    ]);

    if (logsResult.error && eventsResult.error) {
      throw new BatchServiceError('Failed to query recent logs', 500, logsResult.error);
    }

    const logs = (logsResult.data || []) as BatchOperationLog[];
    const events = (eventsResult.data || []).map(eventToLog);

    const merged = [...logs, ...events];
    merged.sort((a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );

    return merged.slice(0, limit);
  },
};

export default operationLogService;
