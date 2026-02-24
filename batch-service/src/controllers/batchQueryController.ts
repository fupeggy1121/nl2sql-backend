// ============================================================
// 数据查询控制器 — 批次、子批次、晶圆等 GET 端点
// 替代前端直接 supabase 查询
// ============================================================

import { Request, Response } from 'express';
import batchService from '../services/batchService';
import subBatchService from '../services/subBatchService';
import waferService from '../services/waferService';
import operationLogService from '../services/operationLogService';
import stationService from '../services/stationService';
import supabase from '../config/supabaseClient';
import { ApiResponse } from '../types/batch.types';
import { BatchServiceError } from '../middleware/errorHandler';

/**
 * GET /api/batch/:id
 * 查询批次详情（含子批次列表）
 */
export async function getBatchDetail(req: Request, res: Response): Promise<void> {
  const id = req.params.id as string;

  const detail = await batchService.getBatchWithSubBatches(id);

  const response: ApiResponse = {
    success: true,
    data: detail,
  };
  res.json(response);
}

/**
 * GET /api/batch/:id/wafers?stationCode=xxx
 * 查询批次在指定站点的晶圆数据（含检测结果）
 * 对应前端 fetchWafersForSubBatches()
 */
export async function getBatchWafers(req: Request, res: Response): Promise<void> {
  const id = req.params.id as string;
  const stationCode = req.query.stationCode as string;

  if (!stationCode) {
    throw new BatchServiceError('Missing required query parameter: stationCode', 400);
  }

  // 1. 获取子批次列表
  const subBatches = await subBatchService.getSubBatchesByBatchId(id);
  const subBatchIds = subBatches.map(sb => sb.id);

  // 2. 查询带详情的晶圆数据
  const wafers = await waferService.getWafersWithDetailsForSubBatches(
    subBatchIds,
    stationCode,
    id
  );

  const response: ApiResponse = {
    success: true,
    data: {
      subBatches,
      wafers,
    },
  };
  res.json(response);
}

/**
 * GET /api/batch/:id/history
 * 查询批次操作历史
 */
export async function getBatchHistory(req: Request, res: Response): Promise<void> {
  const id = req.params.id as string;
  const limit = parseInt(req.query.limit as string) || 50;

  const logs = await operationLogService.getOperationHistory(id, limit);

  const response: ApiResponse = {
    success: true,
    data: logs,
  };
  res.json(response);
}

/**
 * GET /api/batch/stations  或  GET /api/stations
 * 查询所有活跃站点（用于前端站点下拉框）
 */
export async function listStations(_req: Request, res: Response): Promise<void> {
  const stations = await stationService.listActiveStations();

  // 返回前端期望的格式: { code, name } 数组
  const mapped = stations.map(s => ({
    id: s.id,
    code: s.code,
    name: s.name,
    description: s.description,
    workshop: s.workshop,
    station_type: s.station_type,
    status: s.status,
  }));

  const response: ApiResponse = {
    success: true,
    data: mapped,
  };
  res.json(response);
}

/**
 * GET /api/batch/products  或  GET /api/products
 * 查询产品列表
 */
export async function listProducts(_req: Request, res: Response): Promise<void> {
  const { data, error } = await supabase
    .from('products')
    .select('supabase_id, id, product_code, product_name, product_category, product_type, customer_name, description, status, main_process_route_id')
    .order('product_code');

  if (error) {
    throw new BatchServiceError('Failed to list products', 500, error);
  }

  res.json({ success: true, data: data || [] } as ApiResponse);
}

/**
 * GET /api/batch/loss-wafers  或  GET /api/loss-wafers
 * 查询损耗晶圆记录（wafer_carrier_contents 中 defect 状态的晶圆）
 */
export async function listLossWafers(req: Request, res: Response): Promise<void> {
  const limit = parseInt(req.query.limit as string) || 200;

  // 查询非 GOOD 类型的晶圆（即损失片）
  const { data, error } = await supabase
    .from('wafer_carrier_contents')
    .select('*')
    .neq('wafer_type', 'GOOD')
    .order('updated_at', { ascending: false })
    .limit(limit);

  if (error) {
    throw new BatchServiceError('Failed to list loss wafers', 500, error);
  }

  res.json({ success: true, data: data || [] } as ApiResponse);
}

/**
 * GET /api/batch/list?status=xxx&station=xxx&limit=100
 * 查询批次列表
 */
export async function listBatches(req: Request, res: Response): Promise<void> {
  const status = req.query.status as string | undefined;
  const station = req.query.station as string | undefined;
  const limit = parseInt(req.query.limit as string) || 100;

  let batches;
  if (station) {
    batches = await batchService.getBatchesByStation(station);
  } else {
    batches = await batchService.listBatches(status, limit);
  }

  const response: ApiResponse = {
    success: true,
    data: batches,
  };
  res.json(response);
}
