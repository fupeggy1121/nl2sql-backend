/**
 * 映射字典管理 API 客户端
 *
 * 用法:
 *   import { mappingApi } from './mappingApi';
 *   const res = await mappingApi.getObjectsSummary();
 */

// API 基础地址 — 与 synonymApi.js 保持相同的解析逻辑
const getBase = () => {
  if (typeof import.meta !== 'undefined' && import.meta?.env?.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL.replace(/\/api\/query.*$/, '') + '/api/mapping';
  }
  if (typeof import.meta !== 'undefined' && import.meta?.env?.VITE_API_URL) {
    return import.meta.env.VITE_API_URL.replace(/\/api\/query.*$/, '') + '/api/mapping';
  }
  if (typeof process !== 'undefined' && process.env?.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL.replace(/\/api\/query.*$/, '') + '/api/mapping';
  }
  return 'http://localhost:8000/api/mapping';
};

const BASE = getBase();

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

/** URL-encode a logic_class / logic_relation key for path params */
const enc = (key) => encodeURIComponent(key);

export const mappingApi = {

  // ── 摘要 & 缓存 ──────────────────────────────────────────────

  /** 获取 mapping 文件摘要 */
  getSummary: () => request('/summary'),

  /** 强制重载后端映射缓存 */
  reloadCache: () => request('/reload', { method: 'POST' }),

  // ── object_mappings CRUD ──────────────────────────────────────

  /**
   * 获取 object_mappings 列表
   * @param {Object} params - { q, page, page_size }
   */
  getObjects: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== ''))
    ).toString();
    return request('/objects' + (qs ? `?${qs}` : ''));
  },

  /** 获取单条 object_mapping */
  getObject: (logicClass) => request(`/objects/${enc(logicClass)}`),

  /** 新增 object_mapping */
  createObject: (data) =>
    request('/objects', { method: 'POST', body: JSON.stringify(data) }),

  /** 更新 object_mapping（部分更新） */
  updateObject: (logicClass, data) =>
    request(`/objects/${enc(logicClass)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  /** 删除 object_mapping */
  deleteObject: (logicClass) =>
    request(`/objects/${enc(logicClass)}`, { method: 'DELETE' }),

  // ── relation_mappings CRUD ────────────────────────────────────

  /**
   * 获取 relation_mappings 列表
   * @param {Object} params - { q, confidence }
   */
  getRelations: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== ''))
    ).toString();
    return request('/relations' + (qs ? `?${qs}` : ''));
  },

  /** 新增 relation_mapping */
  createRelation: (data) =>
    request('/relations', { method: 'POST', body: JSON.stringify(data) }),

  /** 更新 relation_mapping */
  updateRelation: (logicRelation, data) =>
    request(`/relations/${enc(logicRelation)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  /** 删除 relation_mapping */
  deleteRelation: (logicRelation) =>
    request(`/relations/${enc(logicRelation)}`, { method: 'DELETE' }),

  // ── value_mappings ────────────────────────────────────────────

  /** 获取所有语义域列表 */
  getValueDomains: () => request('/values'),

  /** 获取某个语义域下的所有值 */
  getValueDomain: (domain) => request(`/values/${enc(domain)}`),

  /** 新增或更新某个值条目 */
  upsertValue: (domain, semanticValue, data) =>
    request(`/values/${enc(domain)}/${enc(semanticValue)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  /** 删除某个值条目 */
  deleteValue: (domain, semanticValue) =>
    request(`/values/${enc(domain)}/${enc(semanticValue)}`, { method: 'DELETE' }),

  // ── business_rules CRUD ───────────────────────────────────────

  /**
   * 获取业务规则列表
   * @param {Object} params - { q }
   */
  getRules: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== ''))
    ).toString();
    return request('/rules' + (qs ? `?${qs}` : ''));
  },

  /** 新增业务规则 */
  createRule: (data) =>
    request('/rules', { method: 'POST', body: JSON.stringify(data) }),

  /** 更新业务规则 */
  updateRule: (id, data) =>
    request(`/rules/${enc(id)}`, { method: 'PUT', body: JSON.stringify(data) }),

  /** 删除业务规则 */
  deleteRule: (id) =>
    request(`/rules/${enc(id)}`, { method: 'DELETE' }),

  // ── metric_definitions CRUD ───────────────────────────────────

  /**
   * 获取指标定义列表
   * @param {Object} params - { q }
   */
  getMetrics: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== ''))
    ).toString();
    return request('/metrics' + (qs ? `?${qs}` : ''));
  },

  /** 新增指标定义 */
  createMetric: (data) =>
    request('/metrics', { method: 'POST', body: JSON.stringify(data) }),

  /** 更新指标定义（部分更新） */
  updateMetric: (metricId, data) =>
    request(`/metrics/${enc(metricId)}`, { method: 'PUT', body: JSON.stringify(data) }),

  /** 删除指标定义 */
  deleteMetric: (metricId) =>
    request(`/metrics/${enc(metricId)}`, { method: 'DELETE' }),

  // ── 变更日志 ──────────────────────────────────────────────────

  /**
   * 获取变更日志
   * @param {Object} params - { page, page_size, entry_type, action }
   */
  getChangelog: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== ''))
    ).toString();
    return request('/changelog' + (qs ? `?${qs}` : ''));
  },

  // ── 映射模式切换 ──────────────────────────────────────────────

  /**
   * 获取当前映射模式（prod / demo / custom）
   * 返回: { mode, source, file, runtime_override, env_mapping_file }
   */
  getMode: () => request('/mode'),

  /**
   * 切换运行时映射模式
   * @param {"prod"|"demo"|"auto"} mode
   */
  switchMode: (mode) =>
    request('/switch', { method: 'POST', body: JSON.stringify({ mode }) }),
};
