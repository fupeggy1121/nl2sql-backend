// ============================================================
// 主批次服务 — CRUD 和查询操作
// ============================================================

import supabase from '../config/supabaseClient';
import { Batch, SubBatch, BatchDetailResponse } from '../types/batch.types';
import { BatchServiceError } from '../middleware/errorHandler';

export const batchService = {
  /**
   * 根据 ID 查询批次
   */
  async getBatchById(batchId: string): Promise<Batch> {
    const { data, error } = await supabase
      .from('batches')
      .select('*')
      .eq('id', batchId)
      .single();

    if (error || !data) {
      throw new BatchServiceError(
        `Batch not found: ${batchId}`,
        404,
        error
      );
    }

    return data as Batch;
  },

  /**
   * 查询批次详情（含子批次）
   */
  async getBatchWithSubBatches(batchId: string): Promise<BatchDetailResponse> {
    // 并发查询批次和子批次
    const [batchResult, subBatchResult] = await Promise.all([
      supabase.from('batches').select('*').eq('id', batchId).single(),
      supabase.from('sub_batches').select('*').eq('batch_id', batchId).order('created_at'),
    ]);

    if (batchResult.error || !batchResult.data) {
      throw new BatchServiceError(`Batch not found: ${batchId}`, 404);
    }

    return {
      batch: batchResult.data as Batch,
      subBatches: (subBatchResult.data || []) as SubBatch[],
    };
  },

  /**
   * 按站点查询批次列表
   */
  async getBatchesByStation(stationCode: string): Promise<Batch[]> {
    const { data, error } = await supabase
      .from('batches')
      .select('*')
      .eq('current_station_code', stationCode)
      .order('updated_at', { ascending: false });

    if (error) {
      throw new BatchServiceError('Failed to query batches by station', 500, error);
    }

    return (data || []) as Batch[];
  },

  /**
   * 查询所有批次（可选状态过滤）
   */
  async listBatches(status?: string, limit: number = 100): Promise<Batch[]> {
    let query = supabase
      .from('batches')
      .select('*')
      .order('updated_at', { ascending: false })
      .limit(limit);

    if (status) {
      query = query.eq('status', status);
    }

    const { data, error } = await query;

    if (error) {
      throw new BatchServiceError('Failed to list batches', 500, error);
    }

    return (data || []) as Batch[];
  },
};

export default batchService;
