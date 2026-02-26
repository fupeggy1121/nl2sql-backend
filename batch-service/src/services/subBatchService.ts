// ============================================================
// 子批次服务 — 查询和操作
// ============================================================

import supabase from '../config/supabaseClient';
import { SubBatch } from '../types/batch.types';
import { BatchServiceError } from '../middleware/errorHandler';

/**
 * 批量填充子批次的关联信息：
 * - current_station_id → stations.code / stations.name
 * - current_carrier_id → carriers.carrier_code
 * - equipment_id (v2) → equipment 信息（如果有）
 * - 回退：batch_id → batches.equipment_code / equipment_name
 */
async function enrichSubBatches(subBatches: SubBatch[], batchId?: string): Promise<any[]> {
  if (!subBatches.length) return subBatches;

  // 收集去重的 station IDs 和 carrier IDs
  const stationIds = [...new Set(subBatches.map(sb => sb.current_station_id).filter(Boolean))];
  const carrierIds = [...new Set(subBatches.map(sb => sb.current_carrier_id).filter(Boolean))];

  // 并发查询关联表
  // 1. 查询站点（根据 ID）
  const stationQuery = stationIds.length > 0
    ? supabase.from('stations').select('id, code, name').in('id', stationIds)
    : { data: [] as any[], error: null };

  // 2. 查询载具
  const carrierQuery = carrierIds.length > 0
    ? supabase.from('carriers').select('id, carrier_code').in('id', carrierIds)
    : { data: [] as any[], error: null };

  // 3. 查询父批次设备信息（回退用，当 sub_batch 没有 equipment_id 时）
  const parentBatchId = batchId || subBatches[0]?.batch_id;
  const batchQuery = parentBatchId
    ? supabase.from('batches').select('id, equipment_code, equipment_name').eq('id', parentBatchId).single()
    : { data: null, error: null };

  // 4. 查询 v2 next_station 信息
  const nextStationIds = [...new Set(subBatches.map(sb => sb.next_station_id).filter(Boolean))] as string[];
  const nextStationQuery = nextStationIds.length > 0
    ? supabase.from('stations').select('id, code, name').in('id', nextStationIds)
    : { data: [] as any[], error: null };

  const [stationResult, carrierResult, batchResult, nextStationResult] = await Promise.all([
    stationQuery,
    carrierQuery,
    batchQuery,
    nextStationQuery,
  ]);

  // 构建映射
  const stationMap: Record<string, { code: string; name: string }> = {};
  if (stationResult.data) {
    for (const s of stationResult.data) {
      stationMap[s.id] = { code: s.code, name: s.name };
    }
  }

  const carrierMap: Record<string, string> = {};
  if (carrierResult.data) {
    for (const c of carrierResult.data) {
      carrierMap[c.id] = c.carrier_code;
    }
  }

  const nextStationMap: Record<string, { code: string; name: string }> = {};
  if (nextStationResult.data) {
    for (const s of nextStationResult.data) {
      nextStationMap[s.id] = { code: s.code, name: s.name };
    }
  }

  const parentBatch = batchResult.data;

  // 回填关联字段
  return subBatches.map(sb => ({
    ...sb,
    // 站点信息
    station_code: stationMap[sb.current_station_id]?.code || null,
    station_name: stationMap[sb.current_station_id]?.name || null,
    // 载具编码
    carrier_code: carrierMap[sb.current_carrier_id] || null,
    // 设备信息（回退到父批次）
    equipment_code: parentBatch?.equipment_code || null,
    equipment_name: parentBatch?.equipment_name || null,
    // v2: 下一站点
    next_station_code: sb.next_station_id ? (nextStationMap[sb.next_station_id]?.code || null) : null,
    next_station_name: sb.next_station_id ? (nextStationMap[sb.next_station_id]?.name || null) : null,
    // v2: lot_id
    lot_id: sb.lot_id || null,
  }));
}

export const subBatchService = {
  /**
   * 根据主批次 ID 查询所有子批次（含关联的站点名称、载具编码、设备信息）
   * 对应前端 getSubBatchesForMaster()
   */
  async getSubBatchesByBatchId(batchId: string): Promise<any[]> {
    const { data, error } = await supabase
      .from('sub_batches')
      .select('*')
      .eq('batch_id', batchId)
      .order('created_at');

    if (error) {
      throw new BatchServiceError('Failed to query sub-batches', 500, error);
    }

    return enrichSubBatches((data || []) as SubBatch[], batchId);
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
