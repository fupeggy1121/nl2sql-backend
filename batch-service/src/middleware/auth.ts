// ============================================================
// JWT 认证中间件
//
// 作用：
// 1. 验证前端请求是否携带有效的 JWT Token
// 2. 防止未授权的客户端直接调用后端 API（如恶意脚本、爬虫）
// 3. 从 Token 中提取用户信息（userId, role），注入 req.user
// 4. 支持按角色控制操作权限（如只有 operator 能出站）
//
// 支持两种认证模式：
// - Supabase Auth JWT：前端通过 supabase.auth.signIn() 获取的 access_token
// - 自定义 API Key：用于服务间调用（如其他后端服务调用批次 API）
//
// 使用方式：
//   // 保护所有写操作端点
//   router.post('/confirm-outstation', authMiddleware, asyncHandler(confirmOutstation));
//
//   // 或保护整个路由组
//   router.use(authMiddleware);
// ============================================================

import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';

// ─── 类型定义 ─────────────────────────────────────────────

/** JWT Payload 中的用户信息 */
export interface AuthUser {
  userId: string;
  email?: string;
  role?: string;        // admin | operator | viewer
  aud?: string;         // audience (supabase: 'authenticated')
  iss?: string;         // issuer
}

/** 扩展 Express Request，注入认证用户信息 */
declare global {
  namespace Express {
    interface Request {
      user?: AuthUser;
    }
  }
}

// ─── 配置 ─────────────────────────────────────────────────

/**
 * JWT 验证密钥
 *
 * Supabase 的 JWT Secret 可在 Dashboard > Settings > API > JWT Secret 中找到。
 * 它用于验证 supabase.auth 签发的 access_token。
 *
 * 如果使用自定义 JWT，请设置 JWT_SECRET 环境变量。
 */
function getJwtSecret(): string {
  // 优先使用自定义 JWT_SECRET
  if (process.env.JWT_SECRET) {
    return process.env.JWT_SECRET;
  }

  // 从 Supabase Service Role Key 中提取 JWT Secret
  // Supabase JWT 使用 HS256，secret 就是项目的 JWT secret
  // 在 Supabase Dashboard > Settings > API > JWT Secret 中获取
  if (process.env.SUPABASE_JWT_SECRET) {
    return process.env.SUPABASE_JWT_SECRET;
  }

  throw new Error(
    'Missing JWT configuration. Set JWT_SECRET or SUPABASE_JWT_SECRET in .env\n' +
    'Supabase JWT Secret 可在 Dashboard > Settings > API > JWT Secret 中找到'
  );
}

// ─── 中间件实现 ───────────────────────────────────────────

/**
 * JWT 认证中间件
 *
 * 从请求头提取 Token 并验证：
 *   Authorization: Bearer <jwt-token>
 *   或
 *   x-api-key: <api-key>
 */
export function authMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  // 1. 检查 API Key（服务间调用）
  const apiKey = req.headers['x-api-key'] as string;
  if (apiKey && process.env.API_KEY && apiKey === process.env.API_KEY) {
    req.user = {
      userId: 'service-account',
      role: 'admin',
    };
    return next();
  }

  // 2. 提取 Bearer Token
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    res.status(401).json({
      success: false,
      error: '未提供认证凭证',
      message: '请在请求头中包含 Authorization: Bearer <token>',
    });
    return;
  }

  const token = authHeader.substring(7); // 去掉 "Bearer "

  // 3. 验证 JWT
  try {
    const secret = getJwtSecret();
    const decoded = jwt.verify(token, secret, {
      algorithms: ['HS256'],
    }) as jwt.JwtPayload;

    // 4. 提取用户信息并注入 req.user
    req.user = {
      userId: decoded.sub || decoded.user_id || decoded.id || 'unknown',
      email: decoded.email,
      role: decoded.role || decoded.user_role || 'operator',
      aud: decoded.aud as string,
      iss: decoded.iss,
    };

    next();
  } catch (err: any) {
    if (err.name === 'TokenExpiredError') {
      res.status(401).json({
        success: false,
        error: 'Token 已过期',
        message: '请重新登录获取新的 Token',
      });
      return;
    }

    if (err.name === 'JsonWebTokenError') {
      res.status(401).json({
        success: false,
        error: 'Token 无效',
        message: err.message,
      });
      return;
    }

    // JWT_SECRET 未配置
    if (err.message?.includes('Missing JWT configuration')) {
      console.error('[AUTH]', err.message);
      res.status(500).json({
        success: false,
        error: 'JWT 认证未配置',
        message: '后端服务需要配置 JWT_SECRET 或 SUPABASE_JWT_SECRET',
      });
      return;
    }

    res.status(401).json({
      success: false,
      error: '认证失败',
      message: err.message,
    });
  }
}

/**
 * 可选认证中间件 — 如果有 Token 就验证，没有也放行
 * 适用于查询端点：登录用户可看到更多数据，匿名用户看基础数据
 */
export function optionalAuth(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    // 没有 Token，匿名放行
    return next();
  }

  // 有 Token 就验证
  authMiddleware(req, res, next);
}

/**
 * 角色检查中间件工厂
 * 用法: router.post('/admin-only', authMiddleware, requireRole('admin'), handler)
 */
export function requireRole(...allowedRoles: string[]) {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (!req.user) {
      res.status(401).json({
        success: false,
        error: '未认证',
      });
      return;
    }

    const userRole = req.user.role || 'viewer';
    if (!allowedRoles.includes(userRole)) {
      res.status(403).json({
        success: false,
        error: '权限不足',
        message: `需要角色: ${allowedRoles.join(' 或 ')}，当前角色: ${userRole}`,
      });
      return;
    }

    next();
  };
}
