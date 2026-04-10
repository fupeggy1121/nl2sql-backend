// src/components/Dashboard/DashboardModule.tsx
import { useState, useEffect, useRef, useCallback } from 'react'
import { Pencil, PlusCircle, RefreshCw } from 'lucide-react'
import { Dashboard, DashboardFilter, DashboardWidget, RefreshInterval, VisualizationType } from '../../types/dashboard'
import { useData } from '../../hooks/useData'
import { DashboardFilterBar } from './DashboardFilterBar'
import { DashboardGrid } from './DashboardGrid'
import { DashboardEditor } from './DashboardEditor'
import { AddWidgetPanel } from './AddWidgetPanel'

interface Props {
  dashboardId: string
}

const INTERVAL_MS: Record<RefreshInterval, number | null> = {
  manual: null, '30s': 30_000, '1m': 60_000, '5m': 300_000, '10m': 600_000,
}

export function DashboardModule({ dashboardId }: Props) {
  const { getDashboard, updateDashboard, addWidgetToDashboard, removeWidgetFromDashboard, updateWidgetLayouts, updateWidget, savedReports } = useData()

  const [dashboard, setDashboard] = useState<Dashboard | undefined>(() => getDashboard(dashboardId))
  const [isEditing, setIsEditing] = useState(false)
  const [showEditor, setShowEditor] = useState(false)
  const [showAddPanel, setShowAddPanel] = useState(false)
  const [activeFilters, setActiveFilters] = useState<DashboardFilter[]>([])
  const [refreshTick, setRefreshTick] = useState(0)
  const [containerWidth, setContainerWidth] = useState(900)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Sync dashboard from storage whenever dashboardId changes or external write happens
  const refreshDashboard = useCallback(() => {
    const d = getDashboard(dashboardId)
    setDashboard(d)
    if (d) setActiveFilters(d.globalFilters.map(f => ({ ...f, value: f.value ?? f.defaultValue ?? '' })))
  }, [dashboardId, getDashboard])

  useEffect(() => { refreshDashboard() }, [refreshDashboard])

  // Measure container width for react-grid-layout
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(entries => {
      const w = entries[0]?.contentRect.width
      if (w) setContainerWidth(w - 24) // account for padding
    })
    ro.observe(el)
    setContainerWidth(el.clientWidth - 24)
    return () => ro.disconnect()
  }, [])

  // Auto-refresh timer
  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current)
    const ms = INTERVAL_MS[dashboard?.refreshInterval ?? 'manual']
    if (ms) timerRef.current = setInterval(() => setRefreshTick(t => t + 1), ms)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [dashboard?.refreshInterval])

  if (!dashboard) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 14 }}>
        看板不存在或已被删除
      </div>
    )
  }

  const handleSaveEdit = async (data: { name: string; description?: string; globalFilters: DashboardFilter[] }) => {
    await updateDashboard(dashboard.id, data)
    setShowEditor(false)
    refreshDashboard()
  }

  const handleFiltersChange = (filters: DashboardFilter[]) => {
    setActiveFilters(filters)
    setRefreshTick(t => t + 1)
  }

  const handleSaveDefaults = async (filters: DashboardFilter[]) => {
    const updated = dashboard.globalFilters.map(f => {
      const live = filters.find(lf => lf.id === f.id)
      return live ? { ...f, defaultValue: live.value ?? f.defaultValue } : f
    })
    await updateDashboard(dashboard.id, { globalFilters: updated })
    refreshDashboard()
  }

  const handleIntervalChange = async (interval: RefreshInterval) => {
    await updateDashboard(dashboard.id, { refreshInterval: interval })
    refreshDashboard()
  }

  const handleAddWidget = async (widget: DashboardWidget) => {
    await addWidgetToDashboard(dashboard.id, widget)
    refreshDashboard()
    setRefreshTick(t => t + 1)
  }

  const handleRemoveWidget = async (widgetId: string) => {
    await removeWidgetFromDashboard(dashboard.id, widgetId)
    refreshDashboard()
  }

  const handleLayoutChange = async (layouts: { id: string; layout: { x: number; y: number; w: number; h: number } }[]) => {
    await updateWidgetLayouts(dashboard.id, layouts)
    // Don't refreshDashboard here to avoid flicker while dragging
    setDashboard(getDashboard(dashboardId))
  }

  const handleChartTypeChange = async (widgetId: string, type: VisualizationType) => {
    await updateWidget(dashboard.id, widgetId, { chartTypeOverride: type })
    refreshDashboard()
  }

  return (
    <div ref={containerRef} style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#0d0e1a', overflow: 'hidden' }}>
      {/* Dashboard header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 20px', background: '#12142a', borderBottom: '1px solid #2d284e', flexShrink: 0 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{dashboard.name}</div>
          {dashboard.description && <div style={{ fontSize: 12, color: '#6b7280', marginTop: 1 }}>{dashboard.description}</div>}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          {isEditing && (
            <button onClick={() => setShowAddPanel(true)}
              style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '6px 14px', background: 'rgba(59,130,246,0.12)', border: '1px solid #bfdbfe', borderRadius: 6, fontSize: 13, color: '#1d4ed8', cursor: 'pointer' }}>
              <PlusCircle size={13} /> 添加图表
            </button>
          )}
          <button onClick={() => { setIsEditing(v => !v) }}
            style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '6px 14px', background: isEditing ? '#4f46e5' : '#1e1b4b', border: isEditing ? 'none' : '1px solid #2d284e', borderRadius: 6, fontSize: 13, color: isEditing ? '#fff' : '#c4c9d6', cursor: 'pointer', fontWeight: isEditing ? 600 : 400 }}>
            <Pencil size={13} /> {isEditing ? '完成编辑' : '编辑看板'}
          </button>
          {isEditing && (
            <button onClick={() => setShowEditor(true)}
              style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '6px 14px', background: '#12142a', border: '1px solid #2d284e', borderRadius: 6, fontSize: 13, color: '#c4c9d6', cursor: 'pointer' }}>
              设置
            </button>
          )}
          <button onClick={() => setRefreshTick(t => t + 1)}
            style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '6px 12px', background: '#12142a', border: '1px solid #2d284e', borderRadius: 6, fontSize: 13, color: '#c4c9d6', cursor: 'pointer' }}>
            <RefreshCw size={13} />
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <DashboardFilterBar
        dashboard={dashboard}
        onFiltersChange={handleFiltersChange}
        onRefresh={() => setRefreshTick(t => t + 1)}
        onSaveDefaults={handleSaveDefaults}
        onIntervalChange={handleIntervalChange}
      />

      {/* Grid */}
      <DashboardGrid
        dashboard={dashboard}
        savedReports={savedReports}
        isEditing={isEditing}
        globalFilters={activeFilters}
        refreshTick={refreshTick}
        containerWidth={containerWidth}
        onLayoutChange={handleLayoutChange}
        onRemoveWidget={handleRemoveWidget}
        onChartTypeChange={handleChartTypeChange}
        onAddClick={() => setShowAddPanel(true)}
      />

      {/* Modals */}
      {showEditor && (
        <DashboardEditor existing={dashboard} onSave={handleSaveEdit} onClose={() => setShowEditor(false)} />
      )}
      {showAddPanel && (
        <AddWidgetPanel savedReports={savedReports} onAdd={handleAddWidget} onClose={() => setShowAddPanel(false)} />
      )}
    </div>
  )
}
