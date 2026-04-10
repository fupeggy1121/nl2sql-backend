// src/components/Dashboard/DashboardGrid.tsx
import { useCallback } from 'react'
import ReactGridLayout from 'react-grid-layout/legacy'
import type { LayoutItem, Layout as RGLLayout } from 'react-grid-layout'
import { PlusCircle } from 'lucide-react'
import { Dashboard, DashboardFilter, DashboardWidget, VisualizationType, WidgetLayout } from '../../types/dashboard'
import { DashboardWidgetCard } from './DashboardWidgetCard'
import { SavedReport } from '../../data/mockSavedReports'

interface Props {
  dashboard: Dashboard
  savedReports: SavedReport[]
  isEditing: boolean
  globalFilters: DashboardFilter[]
  refreshTick: number
  containerWidth: number
  onLayoutChange: (layouts: { id: string; layout: WidgetLayout }[]) => void
  onRemoveWidget: (widgetId: string) => void
  onChartTypeChange: (widgetId: string, type: VisualizationType) => void
  onAddClick: () => void
}

function toRGL(widget: DashboardWidget): LayoutItem {
  return {
    i: widget.id,
    x: widget.layout.x,
    y: widget.layout.y,
    w: widget.layout.w,
    h: widget.layout.h,
    minW: 2, minH: 2,
  }
}

function getSavedReportName(widget: DashboardWidget, savedReports: SavedReport[]): string | undefined {
  if (widget.source.type !== 'saved-report') return undefined
  const src = widget.source
  return savedReports.find(r => r.id === src.savedReportId)?.name
}

function getSavedReportSql(widget: DashboardWidget, savedReports: SavedReport[]): string | undefined {
  if (widget.source.type !== 'saved-report') return undefined
  const src = widget.source
  return savedReports.find(r => r.id === src.savedReportId)?.sqlQuery
}

export function DashboardGrid({
  dashboard, savedReports, isEditing, globalFilters, refreshTick,
  containerWidth, onLayoutChange, onRemoveWidget, onChartTypeChange, onAddClick,
}: Props) {
  const layouts: LayoutItem[] = dashboard.widgets.map(toRGL)

  const handleLayoutChange = useCallback((layout: RGLLayout) => {
    const mapped = Array.from(layout).map((l: LayoutItem) => ({
      id: l.i,
      layout: { x: l.x, y: l.y, w: l.w, h: l.h },
    }))
    onLayoutChange(mapped)
  }, [onLayoutChange])

  // Don't render below a minimum width to avoid RGL warnings
  const width = Math.max(containerWidth, 300)
  const rowH = 90

  if (dashboard.widgets.length === 0) {
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, color: '#9ca3af' }}>
        <PlusCircle size={40} strokeWidth={1} />
        <span style={{ fontSize: 14 }}>看板暂无图表</span>
        <button onClick={onAddClick}
          style={{ padding: '8px 20px', background: '#4f46e5', border: 'none', borderRadius: 6, fontSize: 13, color: '#fff', cursor: 'pointer', fontWeight: 600 }}>
          添加第一个图表
        </button>
      </div>
    )
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
      <ReactGridLayout
        layout={layouts}
        cols={12}
        rowHeight={rowH}
        width={width}
        isDraggable={isEditing}
        isResizable={isEditing}
        draggableHandle=".drag-handle"
        onLayoutChange={handleLayoutChange}
        margin={[10, 10] as [number, number]}
        containerPadding={[0, 0] as [number, number]}
        useCSSTransforms
      >
        {dashboard.widgets.map(widget => (
          <div key={widget.id}>
            <DashboardWidgetCard
              widget={widget}
              globalFilters={globalFilters}
              isEditing={isEditing}
              savedReportName={getSavedReportName(widget, savedReports)}
              savedReportSql={getSavedReportSql(widget, savedReports)}
              refreshTick={refreshTick}
              onRemove={() => onRemoveWidget(widget.id)}
              onChartTypeChange={type => onChartTypeChange(widget.id, type)}
            />
          </div>
        ))}
      </ReactGridLayout>

      {/* Add more chart button when editing */}
      {isEditing && (
        <div style={{ textAlign: 'center', paddingTop: 8 }}>
          <button onClick={onAddClick}
            style={{ padding: '7px 16px', background: '#12142a', border: '1px dashed #9ca3af', borderRadius: 6, fontSize: 12, color: '#6b7280', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <PlusCircle size={13} /> 添加图表
          </button>
        </div>
      )}
    </div>
  )
}
