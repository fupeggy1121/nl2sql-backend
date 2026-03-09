// src/components/Dashboard/DashboardWidgetCard.tsx
import { useEffect, useState, useCallback, useRef } from 'react'
import { X, GripVertical, RefreshCw, Settings, AlertCircle } from 'lucide-react'
import { DashboardWidget, DashboardFilter, VisualizationType } from '../../types/dashboard'
import { EChartsVisualization } from '../../modules/mes/components/EChartsVisualization'
import { injectFilters, mergeFilters } from '../../utils/sqlFilterInjector'
import { executeApprovedQuery } from '../../services/nl2sqlApi'

interface Props {
  widget: DashboardWidget
  globalFilters: DashboardFilter[]
  isEditing: boolean
  savedReportName?: string
  savedReportSql?: string
  refreshTick: number
  onRemove: () => void
  onChartTypeChange: (type: VisualizationType) => void
}

const CHART_TYPES: { value: VisualizationType; label: string }[] = [
  { value: 'table', label: '表格' },
  { value: 'bar', label: '柱状图' },
  { value: 'line', label: '折线图' },
  { value: 'pie', label: '饼图' },
  { value: 'scatter', label: '散点图' },
  { value: 'card', label: '数字卡片' },
  { value: 'gauge', label: '仪表盘' },
  { value: 'heatmap', label: '热力图' },
]

type Status = 'idle' | 'loading' | 'ok' | 'error'

export function DashboardWidgetCard({
  widget, globalFilters, isEditing, savedReportName, savedReportSql, refreshTick, onRemove, onChartTypeChange
}: Props) {
  const [status, setStatus] = useState<Status>('idle')
  const [data, setData] = useState<any[]>([])
  const [chartType, setChartType] = useState<VisualizationType>(
    widget.chartTypeOverride || widget.defaultVisualizationType || 'table'
  )
  const [chartConfig, setChartConfig] = useState(widget.chartConfig ?? {})
  const [errorMsg, setErrorMsg] = useState('')
  const [showTypeMenu, setShowTypeMenu] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const getSql = useCallback((): string | null => {
    const src = widget.source
    if (src.type === 'nl-query') return src.sqlQuery
    if (src.type === 'saved-report') return savedReportSql ?? null
    return null
  }, [widget.source, savedReportSql])

  const loadData = useCallback(async () => {
    const sql = getSql()
    if (!sql) return

    // Cancel previous in-flight request
    if (abortRef.current) abortRef.current.abort()
    abortRef.current = new AbortController()

    setStatus('loading')
    setErrorMsg('')

    try {
      const merged = mergeFilters(globalFilters, widget.localFilters)
      const injectedSql = injectFilters(sql, merged)

      const response = await executeApprovedQuery(injectedSql)

      if (!response.success || !response.query_result?.success) {
        throw new Error(response.query_result?.error_message || response.error || '查询失败')
      }

      const result = response.query_result
      setData(result.data || [])

      // Use widget overrides first, then API response, then config snapshot
      if (!widget.chartTypeOverride) {
        const apiType = result.visualization_type as VisualizationType
        if (apiType) setChartType(apiType)
      }

      if (response.visualization) {
        setChartConfig(prev => ({
          ...widget.chartConfig,
          xAxisField: response.visualization!.xAxisField,
          yAxisField: response.visualization!.yAxisField,
          colorField: response.visualization!.colorField,
          ...prev,
        }))
      }

      setStatus('ok')
    } catch (err: any) {
      if (err?.name === 'AbortError') return
      setErrorMsg(err?.message || '请求失败')
      setStatus('error')
    }
  }, [getSql, globalFilters, widget.localFilters, widget.chartTypeOverride, widget.chartConfig])

  // Reload when globalFilters or refreshTick change
  useEffect(() => { loadData() }, [globalFilters, refreshTick]) // eslint-disable-line

  const displayTitle = widget.title || savedReportName ||
    (widget.source.type === 'nl-query' ? widget.source.query : '图表')

  const activeChartType = widget.chartTypeOverride || chartType

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#fff', borderRadius: 8, border: '1px solid #e5e7eb', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
      {/* Header */}
      <div className="drag-handle"
        style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 12px', background: '#f9fafb', borderBottom: '1px solid #e5e7eb', cursor: isEditing ? 'grab' : 'default', minHeight: 36 }}>
        {isEditing && <GripVertical size={13} color="#9ca3af" style={{ flexShrink: 0 }} />}
        <span style={{ flex: 1, fontSize: 12, fontWeight: 600, color: '#374151', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{displayTitle}</span>

        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
          {/* Refresh button */}
          <button onClick={e => { e.stopPropagation(); loadData() }}
            disabled={status === 'loading'}
            title="刷新"
            style={{ padding: 3, background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', display: 'flex' }}>
            <RefreshCw size={12} style={{ animation: status === 'loading' ? 'spin 1s linear infinite' : 'none' }} />
          </button>

          {/* Chart type switcher */}
          {isEditing && (
            <div style={{ position: 'relative' }}>
              <button onClick={e => { e.stopPropagation(); setShowTypeMenu(v => !v) }}
                title="切换图表类型"
                style={{ padding: 3, background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', display: 'flex' }}>
                <Settings size={12} />
              </button>
              {showTypeMenu && (
                <div style={{ position: 'absolute', right: 0, top: 20, background: '#fff', border: '1px solid #e5e7eb', borderRadius: 6, boxShadow: '0 4px 12px rgba(0,0,0,0.12)', zIndex: 50, minWidth: 110 }}>
                  {CHART_TYPES.map(ct => (
                    <button key={ct.value} onClick={() => { onChartTypeChange(ct.value); setChartType(ct.value); setShowTypeMenu(false) }}
                      style={{ display: 'block', width: '100%', textAlign: 'left', padding: '7px 12px', fontSize: 12, background: activeChartType === ct.value ? '#eff6ff' : 'none', color: activeChartType === ct.value ? '#1d4ed8' : '#374151', border: 'none', cursor: 'pointer' }}>
                      {ct.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Remove */}
          {isEditing && (
            <button onClick={e => { e.stopPropagation(); onRemove() }}
              title="移除"
              style={{ padding: 3, background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', display: 'flex' }}>
              <X size={12} />
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflow: 'auto', position: 'relative' }}>
        {status === 'idle' && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#9ca3af', fontSize: 12 }}>尚未加载</div>
        )}
        {status === 'loading' && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 6, color: '#6b7280', fontSize: 12 }}>
            <RefreshCw size={14} style={{ animation: 'spin 1s linear infinite' }} /> 加载中…
          </div>
        )}
        {status === 'error' && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 6, color: '#ef4444', fontSize: 12, padding: 16, textAlign: 'center' }}>
            <AlertCircle size={20} />
            <span>{errorMsg}</span>
            <button onClick={loadData} style={{ marginTop: 4, padding: '4px 12px', background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 4, fontSize: 11, color: '#ef4444', cursor: 'pointer' }}>重试</button>
          </div>
        )}
        {status === 'ok' && (
          <EChartsVisualization
            data={data}
            type={activeChartType}
            title={undefined}
            xAxisField={chartConfig.xAxisField}
            yAxisField={chartConfig.yAxisField}
            colorField={chartConfig.colorField}
            valueField={chartConfig.valueField}
            cardTheme={chartConfig.cardTheme}
            trend={chartConfig.trend}
            comparisonValue={chartConfig.comparisonValue}
            gaugeMin={chartConfig.gaugeMin}
            gaugeMax={chartConfig.gaugeMax}
            gaugeThresholds={chartConfig.gaugeThresholds}
          />
        )}
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
