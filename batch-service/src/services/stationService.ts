// ============================================================
// 站点服务 — 站点查询和工艺路线导航
// ============================================================

import supabase from '../config/supabaseClient';
import { Station, ProcessRouteStation } from '../types/batch.types';
import { BatchServiceError } from '../middleware/errorHandler';

export const stationService = {
  /**
   * 根据站点代码查询站点
   */
  async getStationByCode(code: string): Promise<Station | null> {
    const { data, error } = await supabase
      .from('stations')
      .select('*')
      .eq('code', code)
      .single();

    if (error) {
      // .single() 在没有匹配行时也会返回 error
      if (error.code === 'PGRST116') return null;
      throw new BatchServiceError('Failed to query station', 500, error);
    }

    return data as Station;
  },

  /**
   * 根据站点 ID 查询站点
   */
  async getStationById(id: string): Promise<Station | null> {
    const { data, error } = await supabase
      .from('stations')
      .select('*')
      .eq('id', id)
      .single();

    if (error) {
      if (error.code === 'PGRST116') return null;
      throw new BatchServiceError('Failed to query station by ID', 500, error);
    }

    return data as Station;
  },

  /**
   * 查询当前站点在工艺路线中的下一个站点
   */
  async getNextStation(
    currentStationCode: string
  ): Promise<{ code: string; name: string } | null> {
    // 1. 找到当前站点的 ID
    const currentStation = await stationService.getStationByCode(currentStationCode);
    if (!currentStation) return null;

    // 2. 在工艺路线中找到当前站点
    const { data: routeStations, error: rsError } = await supabase
      .from('process_route_stations')
      .select('*')
      .eq('station_id', currentStation.id)
      .order('sequence')
      .limit(1);

    if (rsError || !routeStations || routeStations.length === 0) {
      return null;
    }

    const currentRS = routeStations[0] as ProcessRouteStation;

    // 3. 查找 sequence 之后的第一个站点
    const { data: nextStations, error: nextError } = await supabase
      .from('process_route_stations')
      .select('*, station:station_id(code, name)')
      .eq('route_id', currentRS.route_id)
      .gt('sequence', currentRS.sequence)
      .order('sequence')
      .limit(1);

    if (nextError || !nextStations || nextStations.length === 0) {
      return null; // 已是最后一站
    }

    const next = nextStations[0] as any;
    return {
      code: next.station?.code || '',
      name: next.station?.name || '',
    };
  },

  /**
   * 查询所有活跃站点
   */
  async listActiveStations(): Promise<Station[]> {
    const { data, error } = await supabase
      .from('stations')
      .select('*')
      .eq('status', 'active')
      .order('code');

    if (error) {
      throw new BatchServiceError('Failed to list stations', 500, error);
    }

    return (data || []) as Station[];
  },
};

export default stationService;
