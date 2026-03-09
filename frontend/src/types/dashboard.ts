// src/types/dashboard.ts

export type FilterType = 'date-range' | 'select' | 'text'

export type VisualizationType =
  | 'bar' | 'line' | 'pie' | 'scatter' | 'card' | 'gauge'
  | 'table' | 'heatmap' | 'radar' | 'funnel' | 'treemap' | 'bar-line-combo'

export interface DashboardFilter {
  id: string
  label: string           // display label e.g. "时间范围"
  sqlColumn: string       // e.g. "gmt_create" or "DATE(gmt_create)"
  type: FilterType
  value?: string          // current runtime value
  defaultValue?: string   // saved default
  /** for type='select': options list (comma-separated or array) */
  options?: string[]
}

export interface WidgetLayout {
  x: number
  y: number
  w: number
  h: number
}

export type WidgetSource =
  | { type: 'saved-report'; savedReportId: string }
  | { type: 'nl-query'; query: string; sqlQuery: string }

export interface DashboardWidget {
  id: string
  title?: string                          // optional override for display title
  source: WidgetSource
  layout: WidgetLayout
  chartTypeOverride?: VisualizationType
  localFilters: DashboardFilter[]
  /** frozen chart config from the original query result */
  chartConfig?: {
    title?: string
    xAxisField?: string
    yAxisField?: string
    colorField?: string
    valueField?: string
    cardTheme?: 'success' | 'warning' | 'danger' | 'info'
    trend?: { direction: 'up' | 'down' | 'stable'; value: number }
    comparisonValue?: { label: string; value: number }
    gaugeMin?: number
    gaugeMax?: number
    gaugeThresholds?: number[]
  }
  defaultVisualizationType?: VisualizationType
}

export type RefreshInterval = 'manual' | '30s' | '1m' | '5m' | '10m'

export interface Dashboard {
  id: string
  name: string
  description?: string
  widgets: DashboardWidget[]
  globalFilters: DashboardFilter[]
  refreshInterval: RefreshInterval
  created_at: string
  updated_at: string
}
