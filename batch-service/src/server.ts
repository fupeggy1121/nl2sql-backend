// ============================================================
// 批次作业后端服务 — Express 主入口
// ============================================================

import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import batchRoutes from './routes/batchRoutes';
import { errorHandler } from './middleware/errorHandler';

// 加载环境变量
dotenv.config();

const app = express();
const port = parseInt(process.env.PORT || '3001', 10);

// ─── CORS 配置 ───────────────────────────────────────────────
const allowedOrigins = (process.env.CORS_ORIGIN || 'http://localhost:5173')
  .split(',')
  .map(o => o.trim());

app.use(cors({
  origin: (origin, callback) => {
    // 允许无 origin 的请求（如 curl、Postman、服务间调用）
    if (!origin || allowedOrigins.includes(origin)) {
      callback(null, true);
    } else {
      callback(new Error(`CORS not allowed for origin: ${origin}`));
    }
  },
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true,
}));

// ─── Body 解析 ───────────────────────────────────────────────
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// ─── 请求日志 ───────────────────────────────────────────────
app.use((req, _res, next) => {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${req.method} ${req.path}`);
  next();
});

// ─── 路由挂载 ───────────────────────────────────────────────

// 健康检查
app.get('/health', (_req, res) => {
  res.json({
    status: 'ok',
    service: 'batch-service',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
  });
});

// 根路径
app.get('/', (_req, res) => {
  res.json({
    service: 'Batch Operations Backend Service',
    version: '1.0.0',
    endpoints: {
      health: 'GET /health',
      listBatches: 'GET /api/batch/list',
      batchDetail: 'GET /api/batch/:id',
      batchWafers: 'GET /api/batch/:id/wafers?stationCode=xxx',
      batchHistory: 'GET /api/batch/:id/history',
      confirmInstation: 'POST /api/batch/confirm-instation',
      confirmOutstation: 'POST /api/batch/confirm-outstation',
      confirmSplit: 'POST /api/batch/confirm-split',
      confirmMerge: 'POST /api/batch/confirm-merge',
    },
  });
});

// 批次作业 API
app.use('/api/batch', batchRoutes);

// ─── 全局错误处理 ────────────────────────────────────────────
app.use(errorHandler);

// ─── 启动服务 ───────────────────────────────────────────────
app.listen(port, () => {
  console.log(`\n========================================`);
  console.log(`  Batch Service running at http://localhost:${port}`);
  console.log(`  Health check: http://localhost:${port}/health`);
  console.log(`  API base:     http://localhost:${port}/api/batch`);
  console.log(`  CORS origins: ${allowedOrigins.join(', ')}`);
  console.log(`========================================\n`);
});

export default app;
