// ============================================================
// 子批次服务 — 查询和操作
// ============================================================

import supabase from '../config/supabaseClient';
import { SubBatch } from '../types/batch.types';
import { BatchServiceError } from '../middleware/errorHandler';

export const subBatchService = {
  /**
   * 根据主批次 ID 查询所有子批次
   * 对应前端 getSubBatchesForMaster()
   */
  async getSubBatchesByBatchId(batchId: string): Promise<SubBatch[]> {
    const { data, error } = await supabase
      .from('sub_batches')
      .select('*')
      .eq('batch_id', batchId)
      .order('created_at');

    if (error) {
      throw new BatchServiceError('Failed to query sub-batches', 500, error);
    }

    return (data || []) as SubBatch[];
  },

  /**
   * 根据 ID 查询单个子批次
   */
  async getSubBatchById(subBatchId: string): Promise<SubBatch> {
    const { data, error } = await supabase
      .from('sub_batches')
      .select('*')
      .eq('id', subBatchId)
      .single();

    if (error || !data) {
      throw new BatchServiceError(`Sub-batch not found: ${subBatchId}`, 404);
    }

    return data as SubBatch;
  },

  /**
   * 根据多个 ID 批量查询子批次
   */
  async getSubBatchesByIds(ids: string[]): Promise<SubBatch[]> {
    if (ids.length === 0) return [];

    const { data, error } = await supabase
      .from('sub_batches')
      .select('*')
      .in('id', ids);

    if (error) {
      throw new BatchServiceError('Failed to query sub-batches by IDs', 500, error);
    }

    return (data || []) as SubBatch[];
  },
};

export default subBatchService;
