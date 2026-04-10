import { useState } from 'react'
import { Code2, Play, Pencil, CheckCircle, AlertCircle } from 'lucide-react'
import type { QueryPlan } from '../types/api'

interface Props {
  plan: QueryPlan
  onExecute: (sql: string) => void
  executing: boolean
}

export function SqlPreview({ plan, onExecute, executing }: Props) {
  const [editing, setEditing] = useState(false)
  const [sql, setSql] = useState(plan.generated_sql)

  const confidence = Math.round(plan.sql_confidence * 100)
  const confColor = confidence >= 80 ? '#10b981' : confidence >= 50 ? '#f59e0b' : '#ef4444'

  return (
    <div style={{
      background: '#12142a',
      borderRadius: 12,
      border: '1px solid #2d284e',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 16px',
        background: '#0d0e1a',
        borderBottom: '1px solid #2d284e',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Code2 size={16} color="#4f46e5" />
          <span style={{ fontWeight: 600, fontSize: 14, color: '#c4c9d6' }}>
            生成的 SQL
          </span>
          <span style={{
            padding: '2px 8px',
            borderRadius: 10,
            background: `${confColor}22`,
            color: confColor,
            fontSize: 12,
            fontWeight: 600,
          }}>
            置信度 {confidence}%
          </span>
        </div>
        <button
          onClick={() => setEditing(e => !e)}
          style={{
            display: 'flex', alignItems: 'center', gap: 4,
            padding: '4px 10px', borderRadius: 6, border: '1px solid #2d284e',
            background: editing ? 'rgba(99,102,241,0.15)' : '#12142a', color: editing ? '#4f46e5' : '#6b7280',
            fontSize: 13, cursor: 'pointer', fontWeight: 500,
          }}
        >
          <Pencil size={13} />
          {editing ? '完成编辑' : '编辑 SQL'}
        </button>
      </div>

      {/* SQL code block */}
      <div style={{ position: 'relative' }}>
        {editing ? (
          <textarea
            value={sql}
            onChange={e => setSql(e.target.value)}
            style={{
              width: '100%',
              padding: '16px 20px',
              background: '#1e1e3f',
              color: '#a5f3fc',
              fontFamily: 'Monaco, Consolas, monospace',
              fontSize: 14,
              lineHeight: 1.7,
              border: 'none',
              outline: 'none',
              resize: 'vertical',
              minHeight: 120,
            }}
            spellCheck={false}
          />
        ) : (
          <pre style={{
            padding: '16px 20px',
            background: '#1e1e3f',
            color: '#a5f3fc',
            fontFamily: 'Monaco, Consolas, monospace',
            fontSize: 14,
            lineHeight: 1.7,
            overflowX: 'auto',
            margin: 0,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
          }}>
            {sql}
          </pre>
        )}
      </div>

      {/* Note + correction info */}
      {plan.self_correction && plan.self_correction.retries > 0 && (
        <div style={{
          padding: '8px 16px',
          background: 'rgba(245,158,11,0.1)',
          borderTop: '1px solid #fde68a',
          display: 'flex', alignItems: 'center', gap: 6,
          fontSize: 13, color: '#92400e',
        }}>
          <AlertCircle size={14} />
          SQL 自动修正 {plan.self_correction.retries} 次
        </div>
      )}

      {/* Explanation */}
      {plan.explanation && (
        <div style={{
          padding: '10px 16px',
          borderTop: '1px solid #2d284e',
          fontSize: 13, color: '#6b7280',
          display: 'flex', alignItems: 'flex-start', gap: 6,
        }}>
          <CheckCircle size={14} style={{ marginTop: 1, flexShrink: 0, color: '#10b981' }} />
          {plan.explanation}
        </div>
      )}

      {/* Execute button */}
      <div style={{ padding: '12px 16px', borderTop: '1px solid #2d284e', textAlign: 'right' }}>
        <button
          onClick={() => onExecute(sql)}
          disabled={executing}
          style={{
            padding: '10px 22px',
            borderRadius: 8,
            border: 'none',
            background: executing ? '#c7d2fe' : '#4f46e5',
            color: '#fff',
            fontSize: 14,
            fontWeight: 600,
            cursor: executing ? 'not-allowed' : 'pointer',
            display: 'inline-flex', alignItems: 'center', gap: 8,
            transition: 'background .2s',
          }}
        >
          <Play size={16} />
          {executing ? '执行中…' : '执行查询'}
        </button>
      </div>
    </div>
  )
}
