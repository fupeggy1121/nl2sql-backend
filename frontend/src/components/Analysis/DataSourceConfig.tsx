import { useState } from 'react'
import type { DataSourceConfig, DataSourceType } from '../../types/analytics'

interface Props {
  value: DataSourceConfig
  onChange: (cfg: DataSourceConfig) => void
}

const TABS: { id: DataSourceType; label: string }[] = [
  { id: 'sql',     label: 'SQL 查询' },
  { id: 'table',   label: '数据表' },
  { id: 'nlquery', label: '自然语言' },
]

export function DataSourceConfig({ value, onChange }: Props) {
  const [limitStr, setLimitStr] = useState(String(value.limit ?? 500))

  const setType = (type: DataSourceType) => onChange({ type, limit: value.limit })

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #2d284e',
    fontSize: 13, fontFamily: 'monospace', boxSizing: 'border-box', background: '#12142a',
    outline: 'none', resize: 'vertical',
  }

  const labelStyle: React.CSSProperties = {
    display: 'block', fontSize: 12, fontWeight: 600, color: '#c4c9d6', marginBottom: 4,
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Tab row */}
      <div style={{ display: 'flex', gap: 6 }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setType(t.id)}
            style={{
              padding: '5px 14px', borderRadius: 6, border: '1px solid',
              borderColor: value.type === t.id ? '#2563eb' : '#d1d5db',
              background: value.type === t.id ? 'rgba(59,130,246,0.12)' : '#12142a',
              color: value.type === t.id ? '#1d4ed8' : '#374151',
              fontSize: 12, fontWeight: value.type === t.id ? 600 : 400, cursor: 'pointer',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {value.type === 'sql' && (
        <div>
          <label style={labelStyle}>SQL 语句</label>
          <textarea
            rows={4}
            placeholder="SELECT * FROM your_table WHERE ..."
            value={value.sql ?? ''}
            onChange={e => onChange({ ...value, sql: e.target.value })}
            style={inputStyle}
          />
        </div>
      )}

      {value.type === 'table' && (
        <div>
          <label style={labelStyle}>表名</label>
          <input
            type="text"
            placeholder="例：production_log"
            value={value.table ?? ''}
            onChange={e => onChange({ ...value, table: e.target.value })}
            style={{ ...inputStyle, resize: undefined }}
          />
        </div>
      )}

      {value.type === 'nlquery' && (
        <div>
          <label style={labelStyle}>自然语言描述</label>
          <textarea
            rows={2}
            placeholder="例：查询上周所有产线的良率数据"
            value={value.nlquery ?? ''}
            onChange={e => onChange({ ...value, nlquery: e.target.value })}
            style={inputStyle}
          />
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <label style={{ ...labelStyle, marginBottom: 0, whiteSpace: 'nowrap' }}>数据行数上限</label>
        <input
          type="number"
          min={10}
          max={10000}
          value={limitStr}
          onChange={e => {
            setLimitStr(e.target.value)
            const n = parseInt(e.target.value, 10)
            if (!isNaN(n) && n > 0) onChange({ ...value, limit: n })
          }}
          style={{ width: 90, padding: '5px 8px', borderRadius: 6, border: '1px solid #2d284e', fontSize: 13 }}
        />
      </div>
    </div>
  )
}
