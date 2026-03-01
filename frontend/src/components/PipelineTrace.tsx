import { useState } from 'react'
import { ChevronDown, ChevronRight, CheckCircle, XCircle, SkipForward } from 'lucide-react'
import type { PipelineStep } from '../types/api'

interface Props {
  steps: PipelineStep[]
}

const STEP_LABELS: Record<string, string> = {
  intent_router: '意图识别',
  semantic_resolver: '语义解析',
  query_planner: '查询规划',
  sql_generator: 'SQL 生成',
  sql_validator: 'SQL 校验',
  query_executor: '查询执行',
}

export function PipelineTrace({ steps }: Props) {
  const [open, setOpen] = useState(false)
  const [expandedStep, setExpandedStep] = useState<string | null>(null)

  const totalMs = steps.reduce((sum, s) => sum + (s.elapsed_ms ?? 0), 0)
  const hasError = steps.some(s => s.status === 'error')

  return (
    <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', overflow: 'hidden' }}>
      {/* Collapsed header */}
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '10px 16px', background: 'transparent', border: 'none',
          cursor: 'pointer', textAlign: 'left',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#6b7280' }}>
            Pipeline 追踪
          </span>
          <span style={{ fontSize: 12, color: '#9ca3af' }}>
            ({steps.length} 步 • {totalMs.toFixed(0)} ms)
          </span>
          {hasError && (
            <span style={{ fontSize: 12, color: '#ef4444', background: '#fef2f2', padding: '1px 6px', borderRadius: 8 }}>
              有错误
            </span>
          )}
        </div>
        {open ? <ChevronDown size={15} color="#9ca3af" /> : <ChevronRight size={15} color="#9ca3af" />}
      </button>

      {/* Expanded steps */}
      {open && (
        <div style={{ borderTop: '1px solid #e5e7eb', padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {steps.map(step => {
            const isExpanded = expandedStep === step.step
            const Icon = step.status === 'error' ? XCircle
              : step.status === 'skip' ? SkipForward
              : CheckCircle
            const iconColor = step.status === 'error' ? '#ef4444'
              : step.status === 'skip' ? '#9ca3af'
              : '#10b981'

            return (
              <div key={step.step} style={{
                borderRadius: 8, border: '1px solid #f3f4f6',
                overflow: 'hidden',
              }}>
                <button
                  onClick={() => setExpandedStep(isExpanded ? null : step.step)}
                  style={{
                    width: '100%', display: 'flex', alignItems: 'center',
                    gap: 10, padding: '8px 12px', background: '#f9fafb',
                    border: 'none', cursor: 'pointer', textAlign: 'left',
                  }}
                >
                  <Icon size={14} color={iconColor} />
                  <span style={{ fontSize: 13, fontWeight: 600, color: '#374151', flex: 1 }}>
                    {STEP_LABELS[step.step] ?? step.step}
                  </span>
                  <span style={{ fontSize: 12, color: '#9ca3af', whiteSpace: 'nowrap' }}>
                    {step.elapsed_ms?.toFixed(1)} ms
                  </span>
                  {isExpanded ? <ChevronDown size={13} color="#9ca3af" /> : <ChevronRight size={13} color="#9ca3af" />}
                </button>
                {isExpanded && (
                  <div style={{ padding: '8px 12px', borderTop: '1px solid #f3f4f6' }}>
                    <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>{step.summary}</div>
                    {step.detail && (
                      <pre style={{
                        fontSize: 11, background: '#1e1e3f', color: '#a5f3fc',
                        padding: '10px 14px', borderRadius: 6, overflowX: 'auto',
                        margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                        lineHeight: 1.6,
                      }}>
                        {JSON.stringify(step.detail, null, 2)}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
