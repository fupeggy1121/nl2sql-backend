import { useState } from 'react'
import type { MethodInfo, ParamSchema } from '../../types/analytics'

interface Props {
  method: MethodInfo | undefined
  params: Record<string, unknown>
  onChange: (params: Record<string, unknown>) => void
  /** 已从数据预览中检测到的列名，用于下拉提示 */
  detectedColumns?: string[]
}

/** 从 schema 中取可读标签（优先 label，降级 description，再降级 key） */
function getLabel(key: string, schema: ParamSchema): string {
  return schema.label || schema.description?.replace(/（.*?）/g, '').replace(/\(.*?\)/g, '').trim() || key
}

/** 从 schema 中取提示文字 */
function getHint(schema: ParamSchema): string {
  return schema.description || ''
}

function ParamField({
  name, schema, value, onChange, detectedColumns,
}: {
  name: string
  schema: ParamSchema
  value: unknown
  onChange: (v: unknown) => void
  detectedColumns?: string[]
}) {
  const inputStyle: React.CSSProperties = {
    padding: '6px 10px', borderRadius: 6, border: '1px solid #d1d5db',
    fontSize: 13, width: '100%', boxSizing: 'border-box', background: '#fff',
  }
  const label = getLabel(name, schema)
  const hint = getHint(schema)

  // 枚举选项：支持 options 数组 或 enum 字符串数组
  const enumOptions: { value: string; label: string }[] =
    schema.options ??
    (schema.enum ? schema.enum.map(v => ({ value: v, label: v })) : [])

  if (schema.type === 'boolean') {
    return (
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }} title={hint}>
        <input
          type="checkbox"
          checked={Boolean(value ?? schema.default)}
          onChange={e => onChange(e.target.checked)}
          style={{ width: 14, height: 14 }}
        />
        <span>{label}</span>
        {hint && <span style={{ color: '#9ca3af', fontSize: 11 }}>ⓘ</span>}
      </label>
    )
  }

  if (enumOptions.length > 0) {
    return (
      <div title={hint}>
        <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 4 }}>
          {label}{hint && <span style={{ color: '#9ca3af', fontWeight: 400, marginLeft: 4, fontSize: 11 }}>ⓘ {hint}</span>}
        </label>
        <select
          value={String(value ?? schema.default ?? '')}
          onChange={e => onChange(e.target.value)}
          style={inputStyle}
        >
          {enumOptions.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>
    )
  }

  if (schema.type === 'number' || schema.type === 'integer') {
    return (
      <div>
        <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 4 }}>
          {label}{hint && <span style={{ color: '#9ca3af', fontWeight: 400, marginLeft: 4, fontSize: 11 }}>ⓘ {hint}</span>}
        </label>
        <input
          type="number"
          value={String(value ?? schema.default ?? '')}
          onChange={e => {
            const n = parseFloat(e.target.value)
            onChange(isNaN(n) ? e.target.value : n)
          }}
          style={inputStyle}
        />
      </div>
    )
  }

  // string：如果有检测到的列名，且字段名含 column/col，显示下拉辅助
  const isColumnField = detectedColumns && detectedColumns.length > 0 &&
    (name.includes('column') || name.includes('col') || name.includes('_field'))

  return (
    <div>
      <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 4 }}>
        {label}{hint && <span style={{ color: '#9ca3af', fontWeight: 400, marginLeft: 4, fontSize: 11 }}>ⓘ {hint}</span>}
      </label>
      {isColumnField ? (
        <select
          value={String(value ?? schema.default ?? '')}
          onChange={e => onChange(e.target.value)}
          style={inputStyle}
        >
          <option value="">（自动检测）</option>
          {detectedColumns!.map(col => (
            <option key={col} value={col}>{col}</option>
          ))}
        </select>
      ) : (
        <input
          type="text"
          value={String(value ?? schema.default ?? '')}
          placeholder={String(schema.default ?? '')}
          onChange={e => onChange(e.target.value)}
          style={inputStyle}
        />
      )}
    </div>
  )
}

export function ParamsForm({ method, params, onChange, detectedColumns }: Props) {
  const [showAdvanced, setShowAdvanced] = useState(false)

  if (!method) {
    return <div style={{ color: '#9ca3af', fontSize: 13 }}>请先选择分析场景</div>
  }

  const schema = method.params_schema ?? {}
  const keys = Object.keys(schema)

  if (keys.length === 0) {
    return (
      <div style={{ color: '#6b7280', fontSize: 13, padding: '8px 0' }}>
        ✅ 此分析无需额外参数，直接点击「运行分析」即可。
      </div>
    )
  }

  // 分层：字段列名参数 vs 业务参数 vs 高级参数
  const fieldKeys = keys.filter(k =>
    k.includes('column') || k.includes('col') || k.includes('_field') || schema[k].tier === 'field'
  )
  const advancedKeys = keys.filter(k =>
    schema[k].tier === 'advanced' ||
    k.includes('subgroup') || k.includes('contamination') ||
    k.includes('threshold') || k.includes('percentile') || k.includes('fit_intercept')
  )
  const businessKeys = keys.filter(k =>
    !fieldKeys.includes(k) && !advancedKeys.includes(k)
  )

  const renderGroup = (groupKeys: string[]) => (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
      {groupKeys.map(key => (
        <ParamField
          key={key}
          name={key}
          schema={schema[key]}
          value={params[key]}
          detectedColumns={detectedColumns}
          onChange={v => onChange({ ...params, [key]: v })}
        />
      ))}
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 业务参数（最重要，始终展开）*/}
      {businessKeys.length > 0 && (
        <div>
          {businessKeys.length + fieldKeys.length > 2 && (
            <div style={{ fontSize: 11, fontWeight: 600, color: '#6b7280', marginBottom: 8, textTransform: 'uppercase' }}>
              分析参数
            </div>
          )}
          {renderGroup(businessKeys)}
        </div>
      )}

      {/* 字段映射（有列名检测时折叠，否则展开）*/}
      {fieldKeys.length > 0 && (
        <details open={!detectedColumns || detectedColumns.length === 0} style={{ border: '1px solid #e5e7eb', borderRadius: 8 }}>
          <summary style={{ padding: '8px 14px', fontSize: 12, fontWeight: 600, color: '#374151', cursor: 'pointer', userSelect: 'none' }}>
            字段映射（列名设置）{detectedColumns && detectedColumns.length > 0 ? ' — 已自动检测，可展开确认' : ''}
          </summary>
          <div style={{ padding: '12px 14px' }}>
            {renderGroup(fieldKeys)}
          </div>
        </details>
      )}

      {/* 高级参数折叠 */}
      {advancedKeys.length > 0 && (
        <div>
          <button
            onClick={() => setShowAdvanced(v => !v)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280', fontSize: 12, padding: 0, display: 'flex', alignItems: 'center', gap: 4 }}
          >
            {showAdvanced ? '▾' : '▸'} 高级参数
          </button>
          {showAdvanced && (
            <div style={{ marginTop: 10 }}>
              {renderGroup(advancedKeys)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
