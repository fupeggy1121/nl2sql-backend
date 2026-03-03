import { useState } from 'react'
import { ChevronDown, ChevronRight, CheckCircle, XCircle, SkipForward } from 'lucide-react'
import type { PipelineStep } from '../types/api'

interface Props {
  steps: PipelineStep[]
}

const STEP_LABELS: Record<string, string> = {
  intent_router:     '🧭 意图识别',
  semantic_resolver: '🔗 语义解析',
  query_planner:     '📋 查询规划',
  sql_generator:     '🤖 分析意图·生成SQL',
  sql_validator:     '✅ SQL 校验',
  query_executor:    '🗄️ 查询执行',
  data_executor:     '🗄️ 数据执行',
  result_analyzer:   '📊 结果分析',
  chart_generator:   '📈 图表生成',
  response_builder:  '📦 响应构建',
  rag_chat:          '💬 智能问答',
}

/** sql_generator 步骤的专属展开面板：SQL代码块 + 置信度 + Token用量 */
function SqlGeneratorDetail({ step }: { step: PipelineStep }) {
  const d = step.detail as Record<string, unknown> | undefined
  const tokens = step.llm_tokens
  const sql: string = (d?.sql as string) ?? ''
  const confidence: number = (d?.confidence as number) ?? 0
  const retryCount: number = (d?.retry_count as number) ?? 0

  const confColor = confidence >= 0.8 ? '#10b981' : confidence >= 0.6 ? '#f59e0b' : '#ef4444'

  return (
    <div style={{ padding: '10px 12px', borderTop: '1px solid #f3f4f6', display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* 摘要 */}
      <div style={{ fontSize: 13, color: '#6b7280' }}>{step.summary}</div>

      {/* SQL 代码块 */}
      {sql && (
        <div>
          <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 4, fontWeight: 600, letterSpacing: 0.5 }}>
            生成的 SQL 语句
          </div>
          <pre style={{
            fontSize: 12, background: '#0f172a', color: '#7dd3fc',
            padding: '12px 14px', borderRadius: 8, overflowX: 'auto',
            margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
            lineHeight: 1.7, fontFamily: '"JetBrains Mono", "Fira Code", "Menlo", monospace',
            border: '1px solid #1e3a5f',
          }}>
            {sql}
          </pre>
        </div>
      )}

      {/* 置信度 + 重试次数 + Token 用量 */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {confidence > 0 && (
          <span style={{
            fontSize: 12, padding: '3px 10px', borderRadius: 20,
            background: `${confColor}18`, color: confColor, fontWeight: 600,
          }}>
            置信度 {(confidence * 100).toFixed(0)}%
          </span>
        )}
        {retryCount > 0 && (
          <span style={{
            fontSize: 12, padding: '3px 10px', borderRadius: 20,
            background: '#fef9c3', color: '#a16207', fontWeight: 500,
          }}>
            重试 #{retryCount}
          </span>
        )}
        {tokens && tokens.total > 0 && (
          <span style={{
            fontSize: 12, padding: '3px 10px', borderRadius: 20,
            background: '#f0f4ff', color: '#4f6ef5', fontWeight: 500,
          }}>
            Tokens: {tokens.input}↑ {tokens.output}↓ {tokens.total} total
          </span>
        )}
        {d?.has_semantic_context && (
          <span style={{
            fontSize: 12, padding: '3px 10px', borderRadius: 20,
            background: '#f0fdf4', color: '#15803d',
          }}>
            + 语义上下文
          </span>
        )}
        {d?.has_few_shot && (
          <span style={{
            fontSize: 12, padding: '3px 10px', borderRadius: 20,
            background: '#faf5ff', color: '#7c3aed',
          }}>
            + Few-shot 示例
          </span>
        )}
      </div>
    </div>
  )
}

export function PipelineTrace({ steps }: Props) {
  const [open, setOpen] = useState(false)
  const [expandedStep, setExpandedStep] = useState<string | null>(null)

  const totalMs = steps.reduce((sum, s) => sum + (s.elapsed_ms ?? 0), 0)
  const hasError = steps.some(s => s.status === 'error')
  const sqlStep = steps.find(s => s.step === 'sql_generator' && s.status !== 'error')

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
          {/* 收起时预览生成的 SQL 片段 */}
          {!open && sqlStep && (sqlStep.detail?.sql as string | undefined) && (
            <span style={{
              fontSize: 11, color: '#4f6ef5', background: '#f0f4ff',
              padding: '1px 8px', borderRadius: 8, maxWidth: 240,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              SQL: {(sqlStep.detail.sql as string).slice(0, 60).replace(/\s+/g, ' ')}…
            </span>
          )}
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
            const isSqlGen = step.step === 'sql_generator'
            const Icon = step.status === 'error' ? XCircle
              : step.status === 'skip' ? SkipForward
              : CheckCircle
            const iconColor = step.status === 'error' ? '#ef4444'
              : step.status === 'skip' ? '#9ca3af'
              : isSqlGen ? '#4f6ef5'
              : '#10b981'

            return (
              <div key={step.step} style={{
                borderRadius: 8,
                border: isSqlGen ? '1px solid #c7d2fe' : '1px solid #f3f4f6',
                overflow: 'hidden',
                boxShadow: isSqlGen ? '0 0 0 2px #eef2ff' : 'none',
              }}>
                <button
                  onClick={() => setExpandedStep(isExpanded ? null : step.step)}
                  style={{
                    width: '100%', display: 'flex', alignItems: 'center',
                    gap: 10, padding: '8px 12px',
                    background: isSqlGen ? '#f5f7ff' : '#f9fafb',
                    border: 'none', cursor: 'pointer', textAlign: 'left',
                  }}
                >
                  <Icon size={14} color={iconColor} />
                  <span style={{ fontSize: 13, fontWeight: 600, color: isSqlGen ? '#3730a3' : '#374151', flex: 1 }}>
                    {STEP_LABELS[step.step] ?? step.step}
                  </span>
                  <span style={{ fontSize: 12, color: '#9ca3af', whiteSpace: 'nowrap' }}>
                    {step.elapsed_ms?.toFixed(1)} ms
                  </span>
                  {isExpanded ? <ChevronDown size={13} color="#9ca3af" /> : <ChevronRight size={13} color="#9ca3af" />}
                </button>

                {isExpanded && (
                  isSqlGen
                    ? <SqlGeneratorDetail step={step} />
                    : (
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
                    )
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
