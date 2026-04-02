/**
 * baselineApi — 预警基线 CRUD 前端服务
 *
 * 封装 /api/v1/baselines 的所有 HTTP 请求，
 * 供 MappingManager BaselinesTab 使用
 */

export interface ThresholdItem {
  value: number;
  level: "target" | "warning" | "critical";
  label: string;
  color?: string;
}

export interface Baseline {
  id: string;
  metric_id?: string;
  label: string;
  field: string;
  keywords: string[];
  scope?: Record<string, unknown>;
  thresholds: ThresholdItem[];
  direction?: "above" | "below";
  enabled?: boolean;
  created_by?: string;
  created_at?: string;
  updated_at?: string;
}

export type BaselineCreate = Omit<Baseline, "id" | "created_at" | "updated_at"> & {
  id?: string;
};

export type BaselineUpdate = Partial<BaselineCreate>;

const BASE = "/api/v1/baselines";

async function request<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`HTTP ${res.status}: ${body}`);
  }
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

export const baselineApi = {
  /** 列出基线，可按关键词搜索 */
  list: (params?: { q?: string; enabled_only?: boolean }) => {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.enabled_only) qs.set("enabled_only", "true");
    const url = qs.toString() ? `${BASE}?${qs}` : BASE;
    return request<{ items: Baseline[]; total: number }>(url);
  },

  /** 获取单条基线 */
  get: (id: string) =>
    request<{ item: Baseline }>(`${BASE}/${encodeURIComponent(id)}`),

  /** 创建新基线 */
  create: (payload: BaselineCreate) =>
    request<{ item: Baseline }>(BASE, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  /** 更新基线 */
  update: (id: string, payload: BaselineUpdate) =>
    request<{ item: Baseline }>(`${BASE}/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  /** 删除基线 */
  delete: (id: string) =>
    request<void>(`${BASE}/${encodeURIComponent(id)}`, { method: "DELETE" }),

  /** 切换启用/禁用 */
  toggle: (id: string) =>
    request<{ item: Baseline }>(
      `${BASE}/${encodeURIComponent(id)}/toggle`,
      { method: "PATCH" }
    ),
};
