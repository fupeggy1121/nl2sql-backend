// ============================================================
// 晶圆服务 — 晶圆查询和载具内容管理
// ============================================================

import supabase from '../config/supabaseClient';
import { WaferCarrierContent } from '../types/batch.types';
import { BatchServiceError } from '../middleware/errorHandler';

export const waferService = {
  /**
   * 根据子批次 ID 列表查询晶圆载具内容
   * 对应前端 fetchWafersForSubBatches()
   */
  async getWafersForSubBatches(subBatchIds: string[]): Promise<WaferCarrierContent[]> {
    if (subBatchIds.length === 0) return [];

    const { data, error } = await supabase
      .from('wafer_carrier_contents')
      .select('*')
      .in('sub_batch_id', subBatchIds)
      .order('slot_number');

    if (error) {
      throw new BatchServiceError('Failed to query wafer carrier contents', 500, error);
    }

    return (data || []) as WaferCarrierContent[];
  },

  /**
   * 根据批次 ID 查询晶圆
   */
  async getWafersByBatchId(batchId: string): Promise<any[]> {
    const { data, error } = await supabase
      .from('wafers')
      .select('*')
      .eq('batch_id', batchId)
      .order('wafer_id_code');

    if (error) {
      throw new BatchServiceError('Failed to query wafers', 500, error);
    }

    return data || [];
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
   * 根据子批次 ID 查询晶圆载具内容，并关联晶圆和检测数据
   * 提供前端表单所需的完整晶圆信息
   */
  async getWafersWithDetailsForSubBatches(
    subBatchIds: string[],
    stationCode: string,
    batchId: string
  ): Promise<any[]> {
    if (subBatchIds.length === 0) return [];

    // 1. 查询载具内容
    const carrierContents = await waferService.getWafersForSubBatches(subBatchIds);

    if (carrierContents.length === 0) return [];

    // 2. 查询关联的晶圆信息
    const waferIds = carrierContents.map(wc => wc.wafer_id);
    const { data: wafers } = await supabase
      .from('wafers')
      .select('*')
      .in('id', waferIds);

    // 3. 查询该批次在该站点的检测结果
    const inspectionResults = await waferService.getInspectionResults(batchId, stationCode);

    // 4. 合并数据
    const waferMap = new Map((wafers || []).map(w => [w.id, w]));
    const inspectionMap = new Map(
      inspectionResults.map(ir => [ir.wafer_id_code, ir])
    );

    return carrierContents.map(wc => {
      const wafer = waferMap.get(wc.wafer_id);
      const inspection = wafer ? inspectionMap.get(wafer.wafer_id_code) : null;

      return {
        ...wc,
        wafer_id_code: wafer?.wafer_id_code || '',
        wafer_type: wc.wafer_type || 'GOOD',
        inspection_data: inspection?.inspection_data || null,
        // 前端兼容字段
        sublotId: wc.sub_batch_id,
        type: inspection?.inspection_data?.waferType || wc.wafer_type || 'GOOD',
      };
    });
  },
};

export default waferService;
