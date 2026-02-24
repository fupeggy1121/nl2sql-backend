// ============================================================
// 数据查询控制器 — 批次、子批次、晶圆等 GET 端点
// 替代前端直接 supabase 查询
// ============================================================

import { Request, Response } from 'express';
import batchService from '../services/batchService';
import subBatchService from '../services/subBatchService';
import waferService from '../services/waferService';
import operationLogService from '../services/operationLogService';
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
