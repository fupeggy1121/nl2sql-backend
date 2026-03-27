import type {
  MethodInfo,
  AnalysisRequest,
  AnalysisResponse,
  DataSourceConfig,
  PreviewResponse,
} from '../types/analytics'

const BASE = import.meta.env.VITE_API_BASE ?? ''

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`POST ${path} → ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

export function listMethods(): Promise<MethodInfo[]> {
  return get<MethodInfo[]>('/api/v1/analytics/methods')
}

export function runAnalysis(req: AnalysisRequest): Promise<AnalysisResponse> {
  return post<AnalysisResponse>('/api/v1/analytics/run', req)
}

export function previewData(dataSource: DataSourceConfig, limit = 20): Promise<PreviewResponse> {
  return post<PreviewResponse>('/api/v1/analytics/preview', { data_source: dataSource, limit })
}
