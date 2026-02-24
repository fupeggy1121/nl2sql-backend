// ============================================================
// 全局错误处理中间件
// ============================================================

import { Request, Response, NextFunction } from 'express';
import { ApiResponse } from '../types/batch.types';

/** 自定义业务错误 */
export class BatchServiceError extends Error {
  public statusCode: number;
  public details?: any;

  constructor(message: string, statusCode: number = 400, details?: any) {
    super(message);
    this.name = 'BatchServiceError';
    this.statusCode = statusCode;
    this.details = details;
  }
}

/** 统一错误处理中间件 */
export function errorHandler(
  err: Error,
  _req: Request,
  res: Response,
  _next: NextFunction
): void {
  console.error(`[ERROR] ${err.name}: ${err.message}`);

  if (err instanceof BatchServiceError) {
    const response: ApiResponse = {
      success: false,
      error: err.message,
      ...(err.details && { data: err.details }),
    };
    res.status(err.statusCode).json(response);
    return;
  }

  // Supabase / PostgreSQL 错误
  if ('code' in err && typeof (err as any).code === 'string') {
    const pgErr = err as any;
    const response: ApiResponse = {
      success: false,
      error: pgErr.message || 'Database error',
      message: pgErr.details || pgErr.hint || undefined,
    };
    res.status(500).json(response);
    return;
  }

  // 未知错误
  const response: ApiResponse = {
    success: false,
    error: process.env.NODE_ENV === 'production'
      ? 'Internal server error'
      : err.message,
  };
  res.status(500).json(response);
}

/** 异步路由包装器 — 自动 catch 异常并转发到 errorHandler */
export function asyncHandler(
  fn: (req: Request, res: Response, next: NextFunction) => Promise<any>
) {
  return (req: Request, res: Response, next: NextFunction) => {
    Promise.resolve(fn(req, res, next)).catch(next);
  };
}
