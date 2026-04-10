// 数据源管理 API

const BASE = import.meta.env.VITE_API_BASE ?? ''

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  return res.json()
}

export interface DataSource {
  source_id: string
  display_name: string
  host: string
  port: number
  db: string
  user: string
  password: string
  description: string
  is_default: boolean
}

export interface DataSourcesResponse {
  success: boolean
  default_source_id: string
  sources: DataSource[]
}

export interface DataSourcePayload {
  display_name: string
  host: string
  port: number
  db: string
  user: string
  password: string
  description: string
  read_timeout: number
}

export function listDataSources(): Promise<DataSourcesResponse> {
  return apiFetch('/api/v1/data-sources')
}

export function createDataSource(source_id: string, body: DataSourcePayload): Promise<{ success: boolean; source: DataSource }> {
  const params = new URLSearchParams({ source_id })
  return apiFetch(`/api/v1/data-sources?${params}`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function updateDataSource(source_id: string, body: Partial<DataSourcePayload>): Promise<{ success: boolean; source: DataSource }> {
  return apiFetch(`/api/v1/data-sources/${encodeURIComponent(source_id)}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

export function deleteDataSource(source_id: string): Promise<{ success: boolean }> {
  return apiFetch(`/api/v1/data-sources/${encodeURIComponent(source_id)}`, { method: 'DELETE' })
}

export function setDefaultDataSource(source_id: string): Promise<{ success: boolean }> {
  return apiFetch(`/api/v1/data-sources/${encodeURIComponent(source_id)}/default`, { method: 'PUT' })
}

export function testDataSourceConnection(source_id: string): Promise<{ success: boolean; message: string }> {
  return apiFetch(`/api/v1/data-sources/${encodeURIComponent(source_id)}/test`, { method: 'POST' })
}
