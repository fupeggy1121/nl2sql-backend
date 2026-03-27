import type { MethodInfo } from '../../types/analytics'

const METHOD_ICONS: Record<string, string> = {
  descriptive: '📊',
  spc:         '📈',
  hypothesis:  '🔬',
  correlation: '🔗',
  pareto:      '🎯',
  regression:  '📉',
  prediction:  '🤖',
  anomaly:     '⚠️',
}

const METHOD_COLORS: Record<string, string> = {
  descriptive: '#3b82f6',
  spc:         '#10b981',
  hypothesis:  '#8b5cf6',
  correlation: '#f59e0b',
  pareto:      '#ef4444',
  regression:  '#6366f1',
  prediction:  '#ec4899',
  anomaly:     '#f97316',
}

interface Props {
  methods: MethodInfo[]
  selected: string
  onSelect: (name: string) => void
}

export function MethodSelector({ methods, selected, onSelect }: Props) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 10 }}>
      {methods.map(m => {
        const isActive = selected === m.name
        const color = METHOD_COLORS[m.name] ?? '#6b7280'
        return (
          <button
            key={m.name}
            onClick={() => onSelect(m.name)}
            style={{
              display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 6,
              padding: '12px 14px', borderRadius: 10, cursor: 'pointer', textAlign: 'left',
              border: isActive ? `2px solid ${color}` : '2px solid #e5e7eb',
              background: isActive ? `${color}12` : '#fff',
              transition: 'all .15s',
              boxShadow: isActive ? `0 0 0 3px ${color}20` : 'none',
            }}
          >
            <span style={{ fontSize: 22 }}>{METHOD_ICONS[m.name] ?? '📋'}</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: isActive ? color : '#111827' }}>
              {m.label}
            </span>
            <span style={{ fontSize: 11, color: '#6b7280', lineHeight: '1.4' }}>
              {m.description}
            </span>
          </button>
        )
      })}
    </div>
  )
}
