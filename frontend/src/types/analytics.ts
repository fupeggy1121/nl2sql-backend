// ── Method metadata ────────────────────────────────────────────────
export interface ParamSchema {
  type: 'string' | 'number' | 'boolean' | 'select'
  label: string
  default?: unknown
  options?: { value: string; label: string }[]
  required?: boolean
}

export interface MethodInfo {
  name: string
  label: string
  description: string
  params_schema: Record<string, ParamSchema>
}

// ── Data source config ─────────────────────────────────────────────
export type DataSourceType = 'sql' | 'table' | 'nlquery'

export interface DataSourceConfig {
  type: DataSourceType
  sql?: string
  table?: string
  nlquery?: string
  limit?: number
}

// ── Request / response ─────────────────────────────────────────────
export interface AnalysisRequest {
  method: string
  data_source: DataSourceConfig
  params: Record<string, unknown>
}

export interface ChartData {
  _renderer?: 'echarts' | 'plotly'
  // echarts option fields
  title?: { text?: string }
  xAxis?: unknown
  yAxis?: unknown
  series?: unknown[]
  // raw plotly (fallback)
  data?: unknown[]
  layout?: unknown
  [key: string]: unknown
}

export interface AnalysisResult {
  method: string
  summary: string
  stats?: Record<string, unknown>
  charts: ChartData[]
  raw?: Record<string, unknown>
}

export interface AnalysisResponse {
  success: boolean
  answer?: string
  result?: AnalysisResult
  error?: string
}

// ── Preview ────────────────────────────────────────────────────────
export interface PreviewResponse {
  success: boolean
  columns: string[]
  rows: unknown[][]
  total_rows: number
  error?: string
}
