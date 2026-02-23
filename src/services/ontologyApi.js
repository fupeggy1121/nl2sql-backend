/**
 * 本体管理 API 客户端
 *
 * 用法 (Bolt.new / React 前端):
 *   import { ontologyApi } from './ontologyApi';
 *   const ttl = await ontologyApi.getTTL();
 *   const versions = await ontologyApi.listVersions();
 */

// API 基础地址 — 与 nl2sqlApi_v2.js / synonymApi.js 保持一致
const getBase = () => {
  // 1. Vite env (推荐)
  if (typeof import !== 'undefined' && import.meta?.env?.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL.replace(/\/api\/query.*$/, '') + '/api/v1/ontology';
  }
  if (typeof import !== 'undefined' && import.meta?.env?.VITE_API_URL) {
    return import.meta.env.VITE_API_URL.replace(/\/api\/query.*$/, '') + '/api/v1/ontology';
  }
  // 2. React CRA env
  if (typeof process !== 'undefined' && process.env?.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL.replace(/\/api\/query.*$/, '') + '/api/v1/ontology';
  }
  // 3. 本地开发默认
  return 'http://localhost:8000/api/v1/ontology';
};

const BASE = getBase();

// ─── 通用请求工具 ─────────────────────────────
async function request(path, options = {}) {
  const url = BASE + path;
  let res;
  try {
    res = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
  } catch (err) {
    throw new Error(
      `无法连接后端 ${url}。请检查：\n` +
      `1. 后端服务是否启动 (uvicorn app.main:app --port 8000)\n` +
      `2. Bolt.new 无法访问 localhost，需设置 VITE_API_BASE_URL 为公网地址\n` +
      `   例: VITE_API_BASE_URL=https://xxx.trycloudflare.com/api/query/unified\n` +
      `原始错误: ${err.message}`
    );
  }
  // 检测非 JSON 响应（常见于请求打到了前端 dev server 而非后端）
  const ct = res.headers.get('content-type') || '';
  if (!ct.includes('application/json')) {
    const preview = (await res.text()).slice(0, 120);
    throw new Error(
      `后端返回了非 JSON 响应 (Content-Type: ${ct})。\n` +
      `请求地址: ${url}\n` +
      `这通常是因为 VITE_API_BASE_URL 未配置或指向了错误的地址。\n` +
      `Bolt.new 中的 localhost 指向 WebContainer 自身，不是你的本机！\n` +
      `解决: 在 Bolt.new 的 .env 中设置 VITE_API_BASE_URL 为后端公网地址。\n` +
      `响应预览: ${preview}`
    );
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function requestText(path) {
  const url = BASE + path;
  let res;
  try {
    res = await fetch(url);
  } catch (err) {
    throw new Error(`无法连接后端 ${url}: ${err.message}`);
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.text();
}

// ─── API 方法 ─────────────────────────────────
export const ontologyApi = {
  /** 获取本体 & 映射统计 */
  getSummary: () => request('/summary'),

  /** 获取当前 TTL 文件内容 (text/turtle) */
  getTTL: () => requestText('/ttl'),

  /** 上传新 TTL 文件 */
  uploadTTL: async (file, message = '', author = 'web-ui') => {
    const form = new FormData();
    form.append('file', file);
    form.append('message', message);
    form.append('author', author);
    const res = await fetch(BASE + '/ttl/upload', { method: 'POST', body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  /** 获取版本历史列表 */
  listVersions: () => request('/ttl/versions'),

  /** 获取指定版本详情 + 内容 */
  getVersion: (version) => request(`/ttl/versions/${version}`),

  /** 回滚到指定版本 */
  rollback: (version) => request(`/ttl/rollback/${version}`, { method: 'POST' }),

  /** 两个版本的差异统计 */
  diffVersions: (v1, v2) => request(`/ttl/diff?v1=${v1}&v2=${v2}`),

  /** 热重载 TTL + mapping */
  reload: () => request('/reload', { method: 'POST' }),

  /** 获取 D3 力导向图数据 (nodes + links JSON) */
  getGraph: () => request('/graph'),

  /** 语义解析 */
  resolve: (query) => request('/resolve', {
    method: 'POST',
    body: JSON.stringify({ query }),
  }),

  /** 血缘路径查询 */
  getLineage: (source, target) =>
    request(`/lineage?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}`),
};

export default ontologyApi;
