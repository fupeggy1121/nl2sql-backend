// src/components/Dashboard/AddWidgetPanel.tsx
import { useState } from 'react'
import { X, Search, BarChart2, Plus, Loader2, CheckCircle2 } from 'lucide-react'
import { SavedReport } from '../../data/mockSavedReports'
import { DashboardWidget, VisualizationType } from '../../types/dashboard'
import { processNaturalLanguageQuery, executeApprovedQuery } from '../../services/nl2sqlApi'

interface Props {
  savedReports: SavedReport[]
  onAdd: (widget: DashboardWidget) => void
  onClose: () => void
}

type SourceTab = 'saved-report' | 'nl-query'

type NLStep = 'input' | 'processing' | 'confirm' | 'executing'

const getNextLayout = () => ({ x: 0, y: Infinity, w: 6, h: 4 })

export function AddWidgetPanel({ savedReports, onAdd, onClose }: Props) {
  const [tab, setTab] = useState<SourceTab>('saved-report')
  const [search, setSearch] = useState('')

  // NL-query state
  const [nlInput, setNlInput] = useState('')
  const [nlStep, setNlStep] = useState<NLStep>('input')
  const [nlSql, setNlSql] = useState('')
  const [nlError, setNlError] = useState('')
  const [nlVisType, setNlVisType] = useState<VisualizationType>('table')
  const [nlChartCfg, setNlChartCfg] = useState<any>({})

  // Widget config overlay (applies to both paths)
  const [configuring, setConfiguring] = useState<{ source: DashboardWidget['source']; defaultVis: VisualizationType; chartCfg: any } | null>(null)
  const [widgetTitle, setWidgetTitle] = useState('')
  const [chartTypeOverride, setChartTypeOverride] = useState<VisualizationType | ''>('')

  const filteredReports = savedReports.filter(r =>
    !search || r.name.toLowerCase().includes(search.toLowerCase())
  )

  const startConfiguring = (source: DashboardWidget['source'], defaultVis: VisualizationType, chartCfg: any) => {
    setConfiguring({ source, defaultVis, chartCfg })
    setWidgetTitle('')
    setChartTypeOverride('')
  }

  const handleAddFinal = () => {
    if (!configuring) return
    const widget: DashboardWidget = {
      id: crypto.randomUUID(),
      title: widgetTitle.trim() || undefined,
      source: configuring.source,
      layout: getNextLayout(),
      chartTypeOverride: chartTypeOverride || undefined,
      localFilters: [],
      chartConfig: configuring.chartCfg,
      defaultVisualizationType: configuring.defaultVis,
    }
    onAdd(widget)
    onClose()
  }

  // ── NL query flow ──
  const handleNlProcess = async () => {
    if (!nlInput.trim()) return
    setNlStep('processing')
    setNlError('')
    try {
      const res = await processNaturalLanguageQuery(nlInput.trim(), 'explain')
      const sql = res.query_plan?.generated_sql
      if (!sql) throw new Error('未生成 SQL，请换一种表达方式')
      setNlSql(sql)
      setNlStep('confirm')
    } catch (err: any) {
      setNlError(err?.message || '处理失败')
      setNlStep('input')
    }
  }

  const handleNlConfirm = async () => {
    setNlStep('executing')
    setNlError('')
    try {
      const res = await executeApprovedQuery(nlSql)
      if (!res.success || !res.query_result?.success) {
        throw new Error(res.query_result?.error_message || '执行失败')
      }
      const visType = (res.query_result.visualization_type || 'table') as VisualizationType
      const chartCfg = { xAxisField: res.visualization?.xAxisField, yAxisField: res.visualization?.yAxisField }
      setNlVisType(visType)
      setNlChartCfg(chartCfg)
      startConfiguring({ type: 'nl-query', query: nlInput.trim(), sqlQuery: nlSql }, visType, chartCfg)
    } catch (err: any) {
      setNlError(err?.message || '执行失败')
      setNlStep('confirm')
    }
  }

  // ── Config overlay ──
  if (configuring) {
    return (
      <div style={{ position: 'fixed', inset: 0, zIndex: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.3)' }}>
        <div style={{ background: '#fff', borderRadius: 10, boxShadow: '0 8px 32px rgba(0,0,0,0.18)', padding: 28, minWidth: 380, maxWidth: 480, width: '90vw' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
            <span style={{ fontSize: 15, fontWeight: 700, color: '#111827' }}>配置图表</span>
            <button onClick={() => setConfiguring(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af' }}><X size={16} /></button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <label style={{ fontSize: 12, color: '#6b7280' }}>
              标题（可选）
              <input value={widgetTitle} onChange={e => setWidgetTitle(e.target.value)}
                placeholder="留空使用报表名称"
                style={{ display: 'block', width: '100%', marginTop: 4, padding: '7px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }} />
            </label>

            <label style={{ fontSize: 12, color: '#6b7280' }}>
              图表类型
              <select value={chartTypeOverride || configuring.defaultVis}
                onChange={e => setChartTypeOverride(e.target.value as VisualizationType)}
                style={{ display: 'block', width: '100%', marginTop: 4, padding: '7px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13 }}>
                <option value="">自动（{configuring.defaultVis}）</option>
                <option value="table">表格</option>
                <option value="bar">柱状图</option>
                <option value="line">折线图</option>
                <option value="pie">饼图</option>
                <option value="scatter">散点图</option>
                <option value="card">数字卡片</option>
                <option value="gauge">仪表盘</option>
              </select>
            </label>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 24 }}>
            <button onClick={() => setConfiguring(null)}
              style={{ padding: '7px 16px', background: '#fff', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, cursor: 'pointer', color: '#374151' }}>
              取消
            </button>
            <button onClick={handleAddFinal}
              style={{ padding: '7px 20px', background: '#4f46e5', border: 'none', borderRadius: 6, fontSize: 13, color: '#fff', cursor: 'pointer', fontWeight: 600 }}>
              添加到看板
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'stretch', justifyContent: 'flex-end', background: 'rgba(0,0,0,0.25)' }}
      onClick={onClose}>
      <div style={{ width: 420, background: '#fff', display: 'flex', flexDirection: 'column', boxShadow: '-4px 0 20px rgba(0,0,0,0.12)', animation: 'slideInRight 0.18s ease' }}
        onClick={e => e.stopPropagation()}>
        {/* Panel header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', borderBottom: '1px solid #e5e7eb' }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#111827' }}>添加图表</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af' }}><X size={16} /></button>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid #e5e7eb' }}>
          {([['saved-report', '从保存的报表'], ['nl-query', '自然语言查询']] as [SourceTab, string][]).map(([id, label]) => (
            <button key={id} onClick={() => setTab(id)}
              style={{ flex: 1, padding: '10px 0', fontSize: 13, fontWeight: tab === id ? 600 : 400, color: tab === id ? '#4f46e5' : '#6b7280', background: 'none', border: 'none', borderBottom: tab === id ? '2px solid #4f46e5' : '2px solid transparent', cursor: 'pointer' }}>
              {label}
            </button>
          ))}
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
          {tab === 'saved-report' && (
            <>
              <div style={{ position: 'relative', marginBottom: 12 }}>
                <Search size={13} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: '#9ca3af' }} />
                <input value={search} onChange={e => setSearch(e.target.value)} placeholder="搜索报表…"
                  style={{ width: '100%', padding: '7px 10px 7px 28px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }} />
              </div>
              {filteredReports.length === 0 && (
                <div style={{ textAlign: 'center', padding: 32, color: '#9ca3af', fontSize: 13 }}>
                  {savedReports.length === 0 ? '暂无保存的报表。请先在 AI 对话中保存一个报表。' : '未找到匹配的报表'}
                </div>
              )}
              {filteredReports.map(r => (
                <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', border: '1px solid #e5e7eb', borderRadius: 7, marginBottom: 8, background: '#fafafa' }}>
                  <BarChart2 size={16} color="#6b7280" style={{ flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: '#111827', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.name}</div>
                    {r.description && <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>{r.description}</div>}
                    {r.visualizationType && <div style={{ fontSize: 11, color: '#6b7280', marginTop: 1 }}>{r.visualizationType}</div>}
                  </div>
                  {r.sqlQuery ? (
                    <button onClick={() => startConfiguring({ type: 'saved-report', savedReportId: r.id }, (r.visualizationType as VisualizationType) || 'table', r.chartConfig)}
                      style={{ padding: '5px 10px', background: '#4f46e5', border: 'none', borderRadius: 5, fontSize: 12, color: '#fff', cursor: 'pointer', flexShrink: 0, display: 'flex', alignItems: 'center', gap: 3 }}>
                      <Plus size={11} /> 添加
                    </button>
                  ) : (
                    <span style={{ fontSize: 11, color: '#9ca3af', flexShrink: 0 }}>缺少 SQL</span>
                  )}
                </div>
              ))}
            </>
          )}

          {tab === 'nl-query' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <textarea value={nlInput} onChange={e => setNlInput(e.target.value)}
                placeholder="输入自然语言查询，例如：统计各站点的在制品数量"
                rows={4}
                style={{ padding: '10px 12px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, resize: 'vertical', fontFamily: 'inherit' }} />

              {nlError && (
                <div style={{ fontSize: 12, color: '#ef4444', background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 5, padding: '8px 10px' }}>{nlError}</div>
              )}

              {nlStep === 'input' && (
                <button onClick={handleNlProcess} disabled={!nlInput.trim()}
                  style={{ padding: '8px 0', background: '#4f46e5', border: 'none', borderRadius: 6, fontSize: 13, color: '#fff', cursor: nlInput.trim() ? 'pointer' : 'not-allowed', opacity: nlInput.trim() ? 1 : 0.5, fontWeight: 600 }}>
                  生成 SQL
                </button>
              )}

              {nlStep === 'processing' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#6b7280', fontSize: 13 }}>
                  <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} /> 正在生成 SQL…
                </div>
              )}

              {(nlStep === 'confirm' || nlStep === 'executing') && (
                <>
                  <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 6, padding: 10 }}>
                    <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 4, fontWeight: 500 }}>生成的 SQL：</div>
                    <pre style={{ fontSize: 12, color: '#1e293b', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontFamily: 'monospace' }}>{nlSql}</pre>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={() => setNlStep('input')} style={{ flex: 1, padding: '8px 0', background: '#fff', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, cursor: 'pointer', color: '#374151' }}>
                      重新生成
                    </button>
                    <button onClick={handleNlConfirm} disabled={nlStep === 'executing'}
                      style={{ flex: 1, padding: '8px 0', background: '#4f46e5', border: 'none', borderRadius: 6, fontSize: 13, color: '#fff', cursor: nlStep === 'executing' ? 'not-allowed' : 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5 }}>
                      {nlStep === 'executing' ? <><Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} />执行中…</> : <><CheckCircle2 size={13} />确认并执行</>}
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
      <style>{`
        @keyframes slideInRight { from { transform: translateX(100%) } to { transform: translateX(0) } }
        @keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }
      `}</style>
    </div>
  )
}
