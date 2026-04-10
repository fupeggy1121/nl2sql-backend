import type { AnalysisResult } from '../../types/analytics'
import { EChartsRenderer } from './EChartsRenderer'

interface Props {
  result: AnalysisResult
  answer?: string
}

function StatsTable({ stats }: { stats: Record<string, unknown> }) {
  const entries = Object.entries(stats)
  if (entries.length === 0) return null
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ background: '#12142a' }}>
            <th style={{ padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid #2d284e', fontWeight: 600, color: '#c4c9d6' }}>指标</th>
            <th style={{ padding: '8px 12px', textAlign: 'right', borderBottom: '1px solid #2d284e', fontWeight: 600, color: '#c4c9d6' }}>值</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([k, v]) => (
            <tr key={k} style={{ borderBottom: '1px solid #1e1b4b' }}>
              <td style={{ padding: '7px 12px', color: '#6b7280' }}>{k}</td>
              <td style={{ padding: '7px 12px', textAlign: 'right', fontFamily: 'monospace', color: '#f1f5f9' }}>
                {typeof v === 'object' ? JSON.stringify(v) : String(v ?? '—')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ResultView({ result, answer }: Props) {
  const { stats, charts, summary } = result

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* AI answer summary */}
      {answer && (
        <div style={{
          padding: '14px 16px', background: 'rgba(16,185,129,0.1)', borderRadius: 10,
          border: '1px solid #bbf7d0', fontSize: 14, color: '#166534', lineHeight: '1.7',
        }}>
          {answer}
        </div>
      )}

      {/* Stats summary banner */}
      {summary && (
        <div style={{
          padding: '12px 16px', background: 'rgba(59,130,246,0.12)', borderRadius: 10,
          border: '1px solid #bfdbfe', fontSize: 13, color: '#1e40af',
        }}>
          {summary}
        </div>
      )}

      {/* Stats table */}
      {stats && Object.keys(stats).length > 0 && (
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#c4c9d6', marginBottom: 8 }}>统计结果</div>
          <div style={{ border: '1px solid #2d284e', borderRadius: 8, overflow: 'hidden' }}>
            <StatsTable stats={stats as Record<string, unknown>} />
          </div>
        </div>
      )}

      {/* Charts */}
      {charts.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {charts.map((chart, i) => (
            <div key={i} style={{ background: '#12142a', border: '1px solid #2d284e', borderRadius: 10, padding: '12px 16px' }}>
              <EChartsRenderer chart={chart} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
