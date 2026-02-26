// ============================================================
// 主批次服务 — CRUD 和查询操作
// ============================================================

import supabase from '../config/supabaseClient';
import { Batch, SubBatch, BatchDetailResponse } from '../types/batch.types';
import { BatchServiceError } from '../middleware/errorHandler';

/**
 * 批量填充 current_station_name：通过 current_station_id JOIN stations
 */
async function enrichBatchesWithStationName(batches: Batch[]): Promise<Batch[]> {
  if (!batches.length) return batches;

  const stationIds = [...new Set(
    batches.map(b => b.current_station_id).filter(Boolean)
  )] as string[];

  const idToStation: Record<string, { code: string; name: string }> = {};
  if (stationIds.length > 0) {
    const { data } = await supabase
      .from('stations')
      .select('id, code, name')
      .in('id', stationIds);
    if (data) {
      for (const s of data) {
        idToStation[s.id] = { code: s.code, name: s.name };
      }
    }
  }

  return batches.map(b => ({
    ...b,
    current_station_name: b.current_station_id
      ? (idToStation[b.current_station_id]?.name || null)
      : null,
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
   * 按站点查询批次列表（先查 station ID，再用 current_station_id 过滤）
   */
  async getBatchesByStation(stationCode: string): Promise<Batch[]> {
    // 1. 查找站点 ID
    const { data: stationRows } = await supabase
      .from('stations')
      .select('id')
      .eq('code', stationCode)
      .limit(1);

    const stationId = stationRows?.[0]?.id;
    if (!stationId) {
      return []; // 无此站点编码，返回空
    }

    // 2. 用 current_station_id 过滤
    const { data, error } = await supabase
      .from('batches')
      .select('*')
      .eq('current_station_id', stationId)
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
