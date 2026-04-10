// src/components/Dashboard/DashboardEditor.tsx
import { useState } from 'react'
import { X, Plus, Trash2 } from 'lucide-react'
import { Dashboard, DashboardFilter, FilterType } from '../../types/dashboard'

interface Props {
  existing?: Dashboard   // undefined = create mode
  onSave: (data: { name: string; description?: string; globalFilters: DashboardFilter[] }) => void
  onClose: () => void
}

const FILTER_TYPES: { value: FilterType; label: string }[] = [
  { value: 'date-range', label: '时间范围' },
  { value: 'select',     label: '下拉选择' },
  { value: 'text',       label: '文本搜索' },
]

function newFilter(): DashboardFilter {
  return { id: crypto.randomUUID(), label: '', sqlColumn: '', type: 'text', options: [] }
}

export function DashboardEditor({ existing, onSave, onClose }: Props) {
  const [name, setName] = useState(existing?.name ?? '')
  const [description, setDescription] = useState(existing?.description ?? '')
  const [filters, setFilters] = useState<DashboardFilter[]>(
    existing?.globalFilters ?? []
  )
  const [error, setError] = useState('')

  const handleSave = () => {
    if (!name.trim()) { setError('看板名称不能为空'); return }
    // validate filters have label + sqlColumn
    for (const f of filters) {
      if (!f.label.trim() || !f.sqlColumn.trim()) {
        setError('所有过滤器都必须填写"标签"和"字段列名"'); return
      }
    }
    onSave({ name: name.trim(), description: description.trim() || undefined, globalFilters: filters })
  }

  const addFilter = () => setFilters(prev => [...prev, newFilter()])
  const removeFilter = (id: string) => setFilters(prev => prev.filter(f => f.id !== id))
  const updateFilter = (id: string, patch: Partial<DashboardFilter>) =>
    setFilters(prev => prev.map(f => f.id === id ? { ...f, ...patch } : f))

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 400, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.3)' }}>
      <div style={{ background: '#12142a', borderRadius: 10, boxShadow: '0 8px 32px rgba(0,0,0,0.18)', padding: '28px 28px 24px', width: '90vw', maxWidth: 520, maxHeight: '90vh', overflowY: 'auto' }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 22 }}>
          <span style={{ fontSize: 16, fontWeight: 700, color: '#f1f5f9' }}>{existing ? '编辑看板' : '新建看板'}</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af' }}><X size={16} /></button>
        </div>

        {/* Basic fields */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginBottom: 22 }}>
          <label style={{ fontSize: 12, color: '#6b7280' }}>
            看板名称 <span style={{ color: '#ef4444' }}>*</span>
            <input value={name} onChange={e => { setName(e.target.value); setError('') }}
              placeholder="e.g. 产线生产看板"
              style={{ display: 'block', width: '100%', marginTop: 5, padding: '8px 10px', border: '1px solid #2d284e', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }} />
          </label>
          <label style={{ fontSize: 12, color: '#6b7280' }}>
            描述（可选）
            <textarea value={description} onChange={e => setDescription(e.target.value)}
              rows={2}
              placeholder="简短说明看板用途"
              style={{ display: 'block', width: '100%', marginTop: 5, padding: '8px 10px', border: '1px solid #2d284e', borderRadius: 6, fontSize: 13, resize: 'vertical', fontFamily: 'inherit', boxSizing: 'border-box' }} />
          </label>
        </div>

        {/* Global filters */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#c4c9d6' }}>全局过滤条件</span>
            <button onClick={addFilter}
              style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '4px 10px', background: 'rgba(59,130,246,0.12)', border: '1px solid #bfdbfe', borderRadius: 5, fontSize: 12, color: '#1d4ed8', cursor: 'pointer' }}>
              <Plus size={11} /> 新增过滤器
            </button>
          </div>

          {filters.length === 0 && (
            <p style={{ fontSize: 12, color: '#9ca3af', padding: '8px 0' }}>暂无全局过滤条件（可选）</p>
          )}

          {filters.map((f, idx) => (
            <div key={f.id} style={{ border: '1px solid #2d284e', borderRadius: 7, padding: 12, marginBottom: 10, background: '#12142a' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 500, color: '#6b7280' }}>过滤器 {idx + 1}</span>
                <button onClick={() => removeFilter(f.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444' }}><Trash2 size={13} /></button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <label style={{ fontSize: 12, color: '#6b7280' }}>
                  显示标签
                  <input value={f.label} onChange={e => updateFilter(f.id, { label: e.target.value })}
                    placeholder="e.g. 时间范围"
                    style={{ display: 'block', width: '100%', marginTop: 3, padding: '5px 8px', border: '1px solid #2d284e', borderRadius: 5, fontSize: 12, boxSizing: 'border-box' }} />
                </label>
                <label style={{ fontSize: 12, color: '#6b7280' }}>
                  字段列名
                  <input value={f.sqlColumn} onChange={e => updateFilter(f.id, { sqlColumn: e.target.value })}
                    placeholder="e.g. gmt_create"
                    style={{ display: 'block', width: '100%', marginTop: 3, padding: '5px 8px', border: '1px solid #2d284e', borderRadius: 5, fontSize: 12, boxSizing: 'border-box' }} />
                </label>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 8 }}>
                <label style={{ fontSize: 12, color: '#6b7280' }}>
                  类型
                  <select value={f.type} onChange={e => updateFilter(f.id, { type: e.target.value as FilterType })}
                    style={{ display: 'block', width: '100%', marginTop: 3, padding: '5px 8px', border: '1px solid #2d284e', borderRadius: 5, fontSize: 12 }}>
                    {FILTER_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </select>
                </label>
                <label style={{ fontSize: 12, color: '#6b7280' }}>
                  默认值
                  <input value={f.defaultValue ?? ''} onChange={e => updateFilter(f.id, { defaultValue: e.target.value })}
                    placeholder={f.type === 'date-range' ? 'YYYY-MM-DD,YYYY-MM-DD' : ''}
                    style={{ display: 'block', width: '100%', marginTop: 3, padding: '5px 8px', border: '1px solid #2d284e', borderRadius: 5, fontSize: 12, boxSizing: 'border-box' }} />
                </label>
              </div>
              {f.type === 'select' && (
                <label style={{ display: 'block', marginTop: 8, fontSize: 12, color: '#6b7280' }}>
                  选项值（英文逗号分隔）
                  <input value={(f.options ?? []).join(',')} onChange={e => updateFilter(f.id, { options: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                    placeholder="选项1,选项2,选项3"
                    style={{ display: 'block', width: '100%', marginTop: 3, padding: '5px 8px', border: '1px solid #2d284e', borderRadius: 5, fontSize: 12, boxSizing: 'border-box' }} />
                </label>
              )}
            </div>
          ))}
        </div>

        {error && <p style={{ fontSize: 12, color: '#ef4444', marginBottom: 12 }}>{error}</p>}

        {/* Footer */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button onClick={onClose}
            style={{ padding: '8px 18px', background: '#12142a', border: '1px solid #2d284e', borderRadius: 6, fontSize: 13, cursor: 'pointer', color: '#c4c9d6' }}>
            取消
          </button>
          <button onClick={handleSave}
            style={{ padding: '8px 22px', background: '#4f46e5', border: 'none', borderRadius: 6, fontSize: 13, color: '#fff', cursor: 'pointer', fontWeight: 600 }}>
            {existing ? '保存修改' : '创建看板'}
          </button>
        </div>
      </div>
    </div>
  )
}
