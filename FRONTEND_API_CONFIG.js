/**
 * API 配置文件
 * 支持多个环境的后端 URL
 */

// 获取当前环境
const getEnvironment = () => {
  const isDevelopment = import.meta.env.MODE === 'development';
  const isProduction = import.meta.env.MODE === 'production';
  
  // 检查是否在 WebContainer 中
  const isWebContainer = typeof window !== 'undefined' && window.location.hostname.includes('webcontainer');
  
  return { isDevelopment, isProduction, isWebContainer };
};

// API 地址配置
const API_CONFIG = {
  // 本地开发（直接访问）
  local: 'http://localhost:8000/api/query',
  
  // 内网 IP（仅限本地网络）
  internal: 'http://192.168.2.13:8000/api/query',
  
  // Cloudflare Tunnel（公网可访问 - 临时 URL）
  cloudflare_temp: 'https://colored-hypothesis-animated-toddler.trycloudflare.com/api/query',
  
  // Cloudflare Tunnel（固定 URL - 需要配置）
  cloudflare_fixed: process.env.REACT_APP_API_URL || process.env.VITE_API_URL || '',
  
  // 备用地址
  production: process.env.REACT_APP_API_PRODUCTION_URL || '',
};

/**
 * 获取当前环境的 API 基础 URL
 */
export const getApiBaseUrl = () => {
  const { isDevelopment, isWebContainer } = getEnvironment();
  
  // 从环境变量获取（优先级最高）
  if (process.env.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL;
  }
  if (process.env.VITE_API_URL) {
    return process.env.VITE_API_URL;
  }
  
  // WebContainer 环境 - 使用 Cloudflare Tunnel
  if (isWebContainer) {
    // 使用临时 URL（每次重启会变化）
    // 或使用固定 URL（需在下方配置）
    return API_CONFIG.cloudflare_temp;
  }
  
  // 本地开发环境
  if (isDevelopment) {
    return API_CONFIG.local;
  }
  
  // 生产环境
  return API_CONFIG.production || API_CONFIG.cloudflare_fixed;
};

/**
 * 获取完整的 API 端点 URL
 */
export const getApiUrl = (endpoint) => {
  const baseUrl = getApiBaseUrl();
  return `${baseUrl}${endpoint.startsWith('/') ? endpoint : '/' + endpoint}`;
};

/**
 * API 端点常量
 */
export const API_ENDPOINTS = {
  // 健康检查
  HEALTH: '/health',
  
  // Supabase NL2SQL
  NL_EXECUTE_SUPABASE: '/nl-execute-supabase',
  SUPABASE_SCHEMA: '/supabase/schema',
  SUPABASE_CONNECTION: '/supabase/connection',
  
  // 通用 NL2SQL
  NL_TO_SQL: '/nl-to-sql',
  NL_EXECUTE: '/nl-execute',
};

/**
 * 打印当前 API 配置（用于调试）
 */
export const logApiConfig = () => {
  const { isDevelopment, isWebContainer } = getEnvironment();
  console.log('📡 API Configuration:');
  console.log('  Environment:', { isDevelopment, isWebContainer });
  console.log('  API Base URL:', getApiBaseUrl());
  console.log('  Full endpoints:', {
    health: getApiUrl(API_ENDPOINTS.HEALTH),
    nl2sql: getApiUrl(API_ENDPOINTS.NL_EXECUTE_SUPABASE),
  });
};

export default {
  getApiBaseUrl,
  getApiUrl,
  API_ENDPOINTS,
  logApiConfig,
};
