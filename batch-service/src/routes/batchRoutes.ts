// ============================================================
// 批次作业路由定义
// ============================================================

import { Router } from 'express';
import { asyncHandler } from '../middleware/errorHandler';
import { authMiddleware, optionalAuth } from '../middleware/auth';

// 查询控制器
import {
  getBatchDetail,
  getBatchWafers,
  getBatchHistory,
  listBatches,
} from '../controllers/batchQueryController';

// 操作控制器
import { confirmOutstation } from '../controllers/outstationController';
import { confirmInstation } from '../controllers/instationController';
import { confirmSplit } from '../controllers/splitBatchController';
import { confirmMerge } from '../controllers/mergeBatchController';

const router = Router();

// ─── 是否启用 JWT 认证（通过环境变量控制） ──────────────────
// 设置 ENABLE_AUTH=true 启用认证，默认关闭（方便本地开发）
const authEnabled = process.env.ENABLE_AUTH === 'true';
const auth = authEnabled ? authMiddleware : (_req: any, _res: any, next: any) => next();
const optAuth = authEnabled ? optionalAuth : (_req: any, _res: any, next: any) => next();

if (!authEnabled) {
  console.log('[AUTH] JWT authentication is DISABLED. Set ENABLE_AUTH=true to enable.');
}

// ─── 查询端点（可选认证） ────────────────────────────────────

/** 批次列表 — GET /api/batch/list?status=&station=&limit= */
router.get('/list', optAuth, asyncHandler(listBatches));

/** 批次详情（含子批次） — GET /api/batch/:id */
router.get('/:id', optAuth, asyncHandler(getBatchDetail));

/** 批次晶圆数据 — GET /api/batch/:id/wafers?stationCode=xxx */
router.get('/:id/wafers', optAuth, asyncHandler(getBatchWafers));

/** 操作历史 — GET /api/batch/:id/history?limit=50 */
router.get('/:id/history', optAuth, asyncHandler(getBatchHistory));

// ─── 写操作端点（需要认证） ──────────────────────────────────

/** 进站确认 — POST /api/batch/confirm-instation */
router.post('/confirm-instation', auth, asyncHandler(confirmInstation));

/** 出站确认 — POST /api/batch/confirm-outstation */
router.post('/confirm-outstation', auth, asyncHandler(confirmOutstation));

/** 拆批确认 — POST /api/batch/confirm-split */
router.post('/confirm-split', auth, asyncHandler(confirmSplit));

/** 并批确认 — POST /api/batch/confirm-merge */
router.post('/confirm-merge', auth, asyncHandler(confirmMerge));

export default router;
