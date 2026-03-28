// ── Method metadata ────────────────────────────────────────────────
export interface ParamSchema {
  type: 'string' | 'number' | 'boolean' | 'select' | 'integer' | 'array'
  label?: string
  description?: string  // 后端实际返回的字段
  default?: unknown
  options?: { value: string; label: string }[]
  enum?: string[]       // 后端也可能用 enum 代替 options
  required?: boolean
  hidden?: boolean      // 隐藏在基础界面中
  tier?: 'business' | 'field' | 'advanced'  // 层次：业务参数/字段映射/高级
}

export interface MethodInfo {
  name: string
  label: string
  description: string
  params_schema: Record<string, ParamSchema>
}

// ── Data source config ─────────────────────────────────────────────
export type DataSourceType = 'sql' | 'table' | 'nlquery' | 'data'

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
  rows_count: number
  columns: string[]
  dtypes: Record<string, string>
  sample: Record<string, unknown>[]
  error?: string
}
