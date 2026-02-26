/**
 * 批次作业 API 客户端
 *
 * 用法 (React 前端):
 *   import { batchApiService } from './batchApiService';
 *
 *   // 设置认证 Token（登录后调用一次）
 *   batchApiService.setAuthToken(supabaseSession.access_token);
 *
 *   // 调用 API
 *   const detail = await batchApiService.getBatchDetail('batch-id');
 *   await batchApiService.confirmOutstation({ batchId, waferResults, subBatches });
 */

// 统一 API 基础地址 — 与 batchApiService.ts 保持一致
// 确保 VITE_API_BASE_URL 在 .env 文件中设置为 https://batch-service-mmtw.onrender.com/api
const getBase = () => {
  // 1. Vite env (推荐)
  if (import.meta?.env?.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  if (import.meta?.env?.VITE_BATCH_API_URL) {
    return import.meta.env.VITE_BATCH_API_URL;
  }
  if (import.meta?.env?.VITE_API_URL) {
    return import.meta.env.VITE_API_URL.replace(/\/api\/query.*$/, '') + '/api';
  }
  // 2. React CRA env
  if (typeof process !== 'undefined' && process.env?.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL.replace(/\/api\/query.*$/, '') + '/api';
  }
  // 3. 线上默认（Render 部署地址）
  return 'https://batch-service-mmtw.onrender.com/api';
};

const BASE = getBase();

// ─── 认证 Token 管理 ──────────────────────────
let _authToken = null;

// ─── 通用请求工具 ─────────────────────────────
async function request(path, options = {}) {
  const url = BASE + path;

  // 构建请求头，自动注入 Authorization
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  if (_authToken) {
    headers['Authorization'] = `Bearer ${_authToken}`;
  }

  let res;
  try {
    res = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err) {
    throw new Error(
      `无法连接批次作业后端 ${url}。请检查：\n` +
      `1. 后端服务是否启动 (cd batch-service && npm run dev)\n` +
      `2. 端口是否正确 (默认 3001)\n` +
      `原始错误: ${err.message}`
    );
  }

  // 401 特殊处理 — Token 过期或无效
  if (res.status === 401) {
    const body = await res.json().catch(() => ({}));
    const error = new Error(body.error || '认证失败，请重新登录');
    error.code = 'AUTH_REQUIRED';
    throw error;
  }

  // 403 权限不足
  if (res.status === 403) {
    const body = await res.json().catch(() => ({}));
    const error = new Error(body.error || '权限不足');
    error.code = 'FORBIDDEN';
    throw error;
  }

  // 检测非 JSON 响应
  const ct = res.headers.get('content-type') || '';
  if (!ct.includes('application/json')) {
    const preview = (await res.text()).slice(0, 200);
    throw new Error(
      `批次作业后端返回了非 JSON 响应 (Content-Type: ${ct})。\n` +
      `请求地址: ${url}\n` +
      `请确认 VITE_BATCH_API_URL 配置正确。\n` +
      `响应预览: ${preview}`
    );
  }

  const body = await res.json();

  if (!res.ok || body.success === false) {
    throw new Error(body.error || body.message || `HTTP ${res.status}`);
  }

  // 返回 data 字段（数组/对象），而非整个 { success, data } 包装
  // 这样前端可以直接: const batches = await listBatches() → batches 即数组
  return body.data !== undefined ? body.data : body;
}

// ─── API 方法 ─────────────────────────────────
export const batchApiService = {

  // ── 查询 ──────────────────────────────────

  /** 查询批次列表 — 返回 BatchData[] */
  listBatches: async (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    const data = await request(`/batch/list${qs ? '?' + qs : ''}`);
    // snake_case → camelCase 转换（含 current_station_name → stationName）
    if (Array.isArray(data)) {
      return data.map(b => ({
        id: b.id,
        batchCode: b.batch_code ?? b.batchCode,
        productCode: b.product_code ?? b.productCode,
        productName: b.product_name ?? b.productName,
        totalQty: b.total_qty ?? b.totalQty,
        goodQty: b.good_qty ?? b.goodQty,
        defectQty: b.defect_qty ?? b.defectQty,
        status: b.status,
        station: b.current_station_code ?? b.station,
        stationName: b.current_station_name ?? b.stationName ?? '未知站点',
        equipmentCode: b.equipment_code ?? b.equipmentCode,
        equipmentName: b.equipment_name ?? b.equipmentName,
        equipmentChamber: b.equipment_chamber ?? b.equipmentChamber,
        nextStationCode: b.next_station_code ?? b.nextStationCode,
        nextStationName: b.next_station_name ?? b.nextStationName,
        productVersion: b.product_version ?? b.productVersion,
        recipeCode: b.recipe_code ?? b.recipeCode,
        ingotId: b.ingot_id ?? b.ingotId,
        isSmallBatch: b.is_small_batch ?? b.isSmallBatch,
        isHold: b.is_hold ?? b.isHold,
      }));
    }
    return data;
  },

  /** 查询所有站点 — 返回 StationData[] */
  listStations: () => request('/stations'),

  /** 查询所有站点（别名，兼容 context 中的 fetchStations / getStations） */
  getStations: () => request('/stations'),

  /** 查询产品列表 — 返回 ProductData[] */
  getProducts: () => request('/products'),

  /** 查询损耗晶圆记录 — 返回 WaferLossRecord[] */
  getLossWafers: (limit = 200) => request(`/loss-wafers?limit=${limit}`),

  /** 查询批次详情（含子批次） */
  getBatchDetail: (batchId) =>
    request(`/batch/${batchId}`),

  /** 查询批次晶圆数据（含检测结果） */
  getBatchWafers: (batchId, stationCode) =>
    request(`/batch/${batchId}/wafers?stationCode=${encodeURIComponent(stationCode)}`),

  /** 查询操作历史 */
  getBatchHistory: (batchId, limit = 50) =>
    request(`/batch/${batchId}/history?limit=${limit}`),

  // ── 写操作 ────────────────────────────────

  /**
   * 出站确认
   * 对应原 handleConfirmOutstation
   */
  confirmOutstation: (batchId, payload) =>
    request('/batch/confirm-outstation', {
      method: 'POST',
      body: JSON.stringify({ batchId, ...payload }),
    }),

  /**
   * 进站确认
   */
  confirmInstation: (payload) =>
    request('/confirm-instation', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /**
   * 拆批确认
   */
  confirmSplit: (payload) =>
    request('/confirm-split', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /**
   * 并批确认
   */
  confirmMerge: (payload) =>
    request('/confirm-merge', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // ── 认证 Token 管理 ──────────────────────

  /**
   * 设置 Bearer Token（登录成功后调用）
   * @param {string} token - Supabase session.access_token
   */
  setAuthToken: (token) => {
    _authToken = token;
  },

  /** 清除 Token（登出时调用） */
  clearAuthToken: () => {
    _authToken = null;
  },

  /** 获取当前 Token（调试用） */
  getAuthToken: () => _authToken,
};

export default batchApiService;
