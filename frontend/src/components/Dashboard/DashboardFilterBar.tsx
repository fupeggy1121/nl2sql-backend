// src/components/Dashboard/DashboardFilterBar.tsx
import { useState } from 'react'
import { Filter, RotateCcw, Save, RefreshCw, Clock } from 'lucide-react'
import { Dashboard, DashboardFilter, RefreshInterval } from '../../types/dashboard'

interface Props {
  dashboard: Dashboard
  onFiltersChange: (filters: DashboardFilter[]) => void
  onRefresh: () => void
  onSaveDefaults: (filters: DashboardFilter[]) => void
  onIntervalChange: (interval: RefreshInterval) => void
}

const INTERVAL_OPTIONS: { value: RefreshInterval; label: string }[] = [
  { value: 'manual', label: '手动刷新' },
  { value: '30s',   label: '30 秒' },
  { value: '1m',    label: '1 分钟' },
  { value: '5m',    label: '5 分钟' },
  { value: '10m',   label: '10 分钟' },
]

function FilterInput({ filter, onChange }: { filter: DashboardFilter; onChange: (val: string) => void }) {
  const val = filter.value ?? filter.defaultValue ?? ''

  if (filter.type === 'date-range') {
    const [start, end] = val.split(',')
    const setRange = (s: string, e: string) => onChange(`${s},${e}`)
    return (
      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <input type="date" value={start ?? ''} onChange={ev => setRange(ev.target.value, end ?? '')}
          style={{ fontSize: 12, padding: '3px 6px', border: '1px solid #d1d5db', borderRadius: 4, color: '#374151' }} />
        <span style={{ color: '#9ca3af', fontSize: 12 }}>至</span>
        <input type="date" value={end ?? ''} onChange={ev => setRange(start ?? '', ev.target.value)}
          style={{ fontSize: 12, padding: '3px 6px', border: '1px solid #d1d5db', borderRadius: 4, color: '#374151' }} />
      </span>
    )
  }

  if (filter.type === 'select' && filter.options && filter.options.length > 0) {
    return (
      <select value={val} onChange={ev => onChange(ev.target.value)}
        style={{ fontSize: 12, padding: '3px 8px', border: '1px solid #d1d5db', borderRadius: 4, color: '#374151' }}>
        <option value="">全部</option>
        {filter.options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
      </select>
    )
  }

  return (
    <input type="text" value={val} onChange={ev => onChange(ev.target.value)}
      placeholder={filter.label}
      style={{ fontSize: 12, padding: '3px 8px', border: '1px solid #d1d5db', borderRadius: 4, color: '#374151', width: 140 }} />
  )
}

export function DashboardFilterBar({ dashboard, onFiltersChange, onRefresh, onSaveDefaults, onIntervalChange }: Props) {
  const [filters, setFilters] = useState<DashboardFilter[]>(
    dashboard.globalFilters.map(f => ({ ...f, value: f.value ?? f.defaultValue ?? '' }))
  )
  const [dirty, setDirty] = useState(false)

  if (dashboard.globalFilters.length === 0 && dashboard.refreshInterval === 'manual') {
    // simplified bar: just a refresh button
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', padding: '8px 16px', background: '#f9fafb', borderBottom: '1px solid #e5e7eb', gap: 8 }}>
        <button onClick={onRefresh}
          style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '5px 12px', background: '#fff', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 12, color: '#374151', cursor: 'pointer' }}>
          <RefreshCw size={12} /> 刷新
        </button>
        <select value={dashboard.refreshInterval} onChange={ev => onIntervalChange(ev.target.value as RefreshInterval)}
          style={{ fontSize: 12, padding: '4px 8px', border: '1px solid #d1d5db', borderRadius: 6, color: '#374151' }}>
          {INTERVAL_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>
    )
  }

  const handleChange = (filterId: string, val: string) => {
    setFilters(prev => prev.map(f => f.id === filterId ? { ...f, value: val } : f))
    setDirty(true)
  }

  const handleApply = () => {
    onFiltersChange(filters)
    setDirty(false)
  }

  const handleReset = () => {
    const reset = dashboard.globalFilters.map(f => ({ ...f, value: f.defaultValue ?? '' }))
    setFilters(reset)
    onFiltersChange(reset)
    setDirty(false)
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 10, padding: '10px 16px', background: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
      <Filter size={13} color="#6b7280" />
      {filters.map(filter => (
        <span key={filter.id} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 12, color: '#6b7280', fontWeight: 500 }}>{filter.label}：</span>
          <FilterInput filter={filter} onChange={val => handleChange(filter.id, val)} />
        </span>
      ))}

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
        {dirty && (
          <button onClick={handleReset} title="重置"
            style={{ display: 'flex', alignItems: 'center', gap: 3, padding: '4px 10px', background: '#fff', border: '1px solid #d1d5db', borderRadius: 5, fontSize: 12, color: '#6b7280', cursor: 'pointer' }}>
            <RotateCcw size={11} /> 重置
          </button>
        )}
        <button onClick={() => onSaveDefaults(filters)} title="保存为默认值"
          style={{ display: 'flex', alignItems: 'center', gap: 3, padding: '4px 10px', background: '#fff', border: '1px solid #d1d5db', borderRadius: 5, fontSize: 12, color: '#6b7280', cursor: 'pointer' }}>
          <Save size={11} /> 保存默认
        </button>
        <button onClick={handleApply}
          style={{ display: 'flex', alignItems: 'center', gap: 3, padding: '4px 12px', background: '#4f46e5', border: 'none', borderRadius: 5, fontSize: 12, color: '#fff', cursor: 'pointer' }}>
          应用过滤
        </button>
        <button onClick={onRefresh}
          style={{ display: 'flex', alignItems: 'center', gap: 3, padding: '4px 10px', background: '#fff', border: '1px solid #d1d5db', borderRadius: 5, fontSize: 12, color: '#374151', cursor: 'pointer' }}>
          <RefreshCw size={11} />
        </button>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#9ca3af' }}>
          <Clock size={11} />
          <select value={dashboard.refreshInterval} onChange={ev => onIntervalChange(ev.target.value as RefreshInterval)}
            style={{ fontSize: 12, padding: '3px 6px', border: '1px solid #d1d5db', borderRadius: 5, color: '#374151' }}>
            {INTERVAL_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </span>
      </div>
    </div>
  )
}
