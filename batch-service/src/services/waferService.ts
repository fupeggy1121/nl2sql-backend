// ============================================================
// 晶圆服务 — 晶圆查询和载具内容管理
// v2: 优先从 wafers 表读取（已反规范化），回退到 wafer_carrier_contents
// ============================================================

import supabase from '../config/supabaseClient';
import { Wafer, WaferCarrierContent } from '../types/batch.types';
import { BatchServiceError } from '../middleware/errorHandler';

export const waferService = {
  /**
   * 根据子批次 ID 列表查询晶圆（v2: 从 wafers 表读取）
   * 对应前端 fetchWafersForSubBatches()
   */
  async getWafersForSubBatches(subBatchIds: string[]): Promise<Wafer[]> {
    if (subBatchIds.length === 0) return [];

    const { data, error } = await supabase
      .from('wafers')
      .select('*')
      .in('sublot_id', subBatchIds)
      .order('slot_number');

    if (error) {
      throw new BatchServiceError('Failed to query wafers for sub-batches', 500, error);
    }

    return (data || []) as Wafer[];
  },

  /**
   * 根据批次 ID 查询晶圆
   */
  async getWafersByBatchId(batchId: string): Promise<Wafer[]> {
    const { data, error } = await supabase
      .from('wafers')
      .select('*')
      .eq('batch_id', batchId)
      .order('wafer_id_code');

    if (error) {
      throw new BatchServiceError('Failed to query wafers', 500, error);
    }

    return (data || []) as Wafer[];
  },

  /**
   * 查询指定批次在指定站点的检测结果
   */
  async getInspectionResults(batchId: string, stationCode?: string): Promise<any[]> {
    let query = supabase
      .from('wafer_inspection_results')
      .select('*')
      .eq('batch_id', batchId)
      .order('created_at', { ascending: false });

    if (stationCode) {
      query = query.eq('station_code', stationCode);
    }

    const { data, error } = await query;

    if (error) {
      throw new BatchServiceError('Failed to query inspection results', 500, error);
    }

    return data || [];
  },

  /**
   * 根据子批次 ID 查询晶圆，并关联检测数据
   * v2: 直接从 wafers 表获取完整信息（不再需要 wafer_carrier_contents JOIN）
   */
  async getWafersWithDetailsForSubBatches(
    subBatchIds: string[],
    stationCode: string,
    batchId: string
  ): Promise<any[]> {
    if (subBatchIds.length === 0) return [];

    // 1. 直接从 wafers 表获取（已包含 carrier_id, slot_number, wafer_type）
    const wafers = await waferService.getWafersForSubBatches(subBatchIds);

    if (wafers.length === 0) return [];

    // 2. 查询该批次在该站点的检测结果
    const inspectionResults = await waferService.getInspectionResults(batchId, stationCode);

    // 3. 构建检测结果映射
    const inspectionMap = new Map(
      inspectionResults.map(ir => [ir.wafer_id_code, ir])
    );

    // 4. 合并数据
    return wafers.map(w => {
      const inspection = inspectionMap.get(w.wafer_id_code);

      return {
        ...w,
        // 兼容旧的 wafer_carrier_contents 字段名
        wafer_id: w.id,
        sub_batch_id: w.sublot_id,
        wafer_type: w.wafer_type || 'GOOD',
        inspection_data: inspection?.inspection_data || null,
        // 前端兼容字段
        sublotId: w.sublot_id,
        type: inspection?.inspection_data?.waferType || w.wafer_type || 'GOOD',
      };
    });
  },
};

export default waferService;
