import type { MethodInfo, ParamSchema } from '../../types/analytics'

interface Props {
  method: MethodInfo | undefined
  params: Record<string, unknown>
  onChange: (params: Record<string, unknown>) => void
}

function ParamField({
  name, schema, value, onChange,
}: {
  name: string
  schema: ParamSchema
  value: unknown
  onChange: (v: unknown) => void
}) {
  const inputStyle: React.CSSProperties = {
    padding: '6px 10px', borderRadius: 6, border: '1px solid #d1d5db',
    fontSize: 13, width: '100%', boxSizing: 'border-box', background: '#fff',
  }

  if (schema.type === 'boolean') {
    return (
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={Boolean(value ?? schema.default)}
          onChange={e => onChange(e.target.checked)}
          style={{ width: 14, height: 14 }}
        />
        {schema.label}
      </label>
    )
  }

  if (schema.type === 'select' && schema.options) {
    return (
      <div>
        <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 4 }}>
          {schema.label}
        </label>
        <select
          value={String(value ?? schema.default ?? '')}
          onChange={e => onChange(e.target.value)}
          style={inputStyle}
        >
          {schema.options.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>
    )
  }

  if (schema.type === 'number') {
    return (
      <div>
        <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 4 }}>
          {schema.label}
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

  // string / default
  return (
    <div>
      <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 4 }}>
        {schema.label}
      </label>
      <input
        type="text"
        value={String(value ?? schema.default ?? '')}
        onChange={e => onChange(e.target.value)}
        style={inputStyle}
      />
    </div>
  )
}

export function ParamsForm({ method, params, onChange }: Props) {
  if (!method) {
    return <div style={{ color: '#9ca3af', fontSize: 13 }}>请先选择分析方法</div>
  }

  const schema = method.params_schema ?? {}
  const keys = Object.keys(schema)

  if (keys.length === 0) {
    return <div style={{ color: '#9ca3af', fontSize: 13 }}>此方法无需额外参数</div>
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
      {keys.map(key => (
        <ParamField
          key={key}
          name={key}
          schema={schema[key]}
          value={params[key]}
          onChange={v => onChange({ ...params, [key]: v })}
        />
      ))}
    </div>
  )
}
