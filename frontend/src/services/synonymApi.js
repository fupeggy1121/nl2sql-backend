/**
 * 同义词管理 API 客户端
 * 
 * 用法 (Bolt.new / React 前端):
 *   import { synonymApi } from './synonymApi';
 *   const all = await synonymApi.getSynonyms({ table_name: 'carriers' });
 */

// API 基础地址 — 与 nl2sqlApi_v2.js / FRONTEND_API_CONFIG.js 保持一致
const getBase = () => {
  // 1. Vite env (推荐)
  if (import.meta?.env?.VITE_API_BASE_URL) {
    // VITE_API_BASE_URL 可能包含 /api/query/unified 后缀，需要剥离
    return import.meta.env.VITE_API_BASE_URL.replace(/\/api\/query.*$/, '') + '/api/synonyms';
  }
  if (import.meta?.env?.VITE_API_URL) {
    return import.meta.env.VITE_API_URL.replace(/\/api\/query.*$/, '') + '/api/synonyms';
  }
  // 2. 本地开发默认
  return 'http://localhost:8000/api/synonyms';
};

const BASE = getBase();

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  return res.json();
}

export const synonymApi = {
  // ── 同义词 CRUD ──────────────────────────

  /** 获取同义词列表 */
  getSynonyms: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(qs ? `?${qs}` : '');
  },

  /** 获取表摘要 */
  getTablesSummary: () => request('/tables'),

  /** 添加同义词 (单条) */
  addSynonym: (table_name, synonym) =>
    request('', { method: 'POST', body: JSON.stringify({ table_name, synonym }) }),

  /** 批量添加同义词 */
  addSynonymsBatch: (table_name, synonyms) =>
    request('', { method: 'POST', body: JSON.stringify({ table_name, synonyms }) }),

  /** 更新同义词 */
  updateSynonym: (id, data) =>
    request(`/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

  /** 删除同义词 (软删除) */
  deleteSynonym: (id) => request(`/${id}`, { method: 'DELETE' }),

  /** 物理删除 */
  hardDeleteSynonym: (id) => request(`/${id}?hard=true`, { method: 'DELETE' }),

  /** 查询单个关键词映射 */
  lookup: (keyword) => request(`/lookup?keyword=${encodeURIComponent(keyword)}`),

  /** 获取完整映射表 */
  getMap: () => request('/map'),

  /** 获取统计 */
  getStats: () => request('/stats'),

  // ── 未匹配词 ──────────────────────────

  /** 获取未匹配词列表 */
  getUnmatched: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/unmatched?${qs}`);
  },

  /** 审批未匹配词 */
  approveUnmatched: (id, table_name) =>
    request(`/unmatched/${id}/approve`, { method: 'POST', body: JSON.stringify({ table_name }) }),

  /** 拒绝 */
  rejectUnmatched: (id) => request(`/unmatched/${id}/reject`, { method: 'POST' }),

  /** 忽略 */
  ignoreUnmatched: (id) => request(`/unmatched/${id}/ignore`, { method: 'POST' }),

  // ── 审计日志 ──────────────────────────
  getAuditLog: (limit = 50) => request(`/audit-log?limit=${limit}`),
};
