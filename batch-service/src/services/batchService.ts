// ============================================================
// 主批次服务 — CRUD 和查询操作
// ============================================================

import supabase from '../config/supabaseClient';
import { Batch, SubBatch, BatchDetailResponse } from '../types/batch.types';
import { BatchServiceError } from '../middleware/errorHandler';

/**
 * 批量填充 current_station_name：
 * 通过 current_station_code 关联 stations 表获取 name
 */
async function enrichBatchesWithStationName(batches: Batch[]): Promise<Batch[]> {
  if (!batches.length) return batches;

  // 收集所有不重复的 station codes
  const codes = [...new Set(
    batches
      .map(b => b.current_station_code)
      .filter(Boolean)
  )];

  if (!codes.length) return batches;

  // 一次性查询所有相关站点
  const { data: stations } = await supabase
    .from('stations')
    .select('code, name')
    .in('code', codes);

  // 构建 code → name 映射
  const codeToName: Record<string, string> = {};
  if (stations) {
    for (const s of stations) {
      codeToName[s.code] = s.name;
    }
  }

  // 回填 current_station_name
  return batches.map(b => ({
    ...b,
    current_station_name: b.current_station_name
      || codeToName[b.current_station_code]
      || null,
  }));
}

export const batchService = {
  /**
   * 根据 ID 查询批次（自动填充站点名称）
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

    const [enriched] = await enrichBatchesWithStationName([data as Batch]);
    return enriched;
  },

  /**
   * 查询批次详情（含子批次，自动填充站点名称）
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

    const [enrichedBatch] = await enrichBatchesWithStationName([batchResult.data as Batch]);

    return {
      batch: enrichedBatch,
      subBatches: (subBatchResult.data || []) as SubBatch[],
    };
  },

  /**
   * 按站点查询批次列表（自动填充站点名称）
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

    return enrichBatchesWithStationName((data || []) as Batch[]);
  },

  /**
   * 查询所有批次（可选状态过滤，自动填充站点名称）
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

    return enrichBatchesWithStationName((data || []) as Batch[]);
  },
};

export default batchService;
