import { useState, useEffect, useCallback } from 'react'
import { listMethods, runAnalysis } from '../../api/analytics'
import type { MethodInfo, DataSourceConfig, AnalysisResponse } from '../../types/analytics'
import { MethodSelector } from './MethodSelector'
import { DataSourceConfig as DataSourceConfigPanel } from './DataSourceConfig'
import { ParamsForm } from './ParamsForm'
import { ResultView } from './ResultView'

type Step = 'method' | 'source' | 'params' | 'result'

const STEPS: { id: Step; label: string }[] = [
  { id: 'method', label: '① 选择分析方法' },
  { id: 'source', label: '② 配置数据来源' },
  { id: 'params', label: '③ 设置参数' },
  { id: 'result', label: '④ 分析结果' },
]

function StepBar({ current, completed }: { current: Step; completed: Set<Step> }) {
  const currentIdx = STEPS.findIndex(s => s.id === current)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginBottom: 24 }}>
      {STEPS.map((s, i) => {
        const done = completed.has(s.id)
        const active = s.id === current
        const reachable = done || active || (i > 0 && completed.has(STEPS[i - 1].id))
        return (
          <div key={s.id} style={{ display: 'flex', alignItems: 'center', flex: i < STEPS.length - 1 ? 1 : undefined }}>
            <div style={{
              padding: '5px 14px', borderRadius: 20, fontSize: 12, fontWeight: active ? 600 : 400,
              background: active ? '#2563eb' : done ? '#d1fae5' : '#f3f4f6',
              color: active ? '#fff' : done ? '#065f46' : reachable ? '#374151' : '#9ca3af',
              whiteSpace: 'nowrap',
              cursor: reachable ? 'default' : 'default',
            }}>
              {s.label}
            </div>
            {i < STEPS.length - 1 && (
              <div style={{ flex: 1, height: 2, background: done ? '#a7f3d0' : '#e5e7eb', minWidth: 16 }} />
            )}
          </div>
        )
      })}
    </div>
  )
}

function SectionCard({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, overflow: 'hidden', marginBottom: 16 }}>
      <div style={{ padding: '12px 18px', borderBottom: '1px solid #f3f4f6', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#111827' }}>{title}</div>
        {action}
      </div>
      <div style={{ padding: '16px 18px' }}>{children}</div>
    </div>
  )
}

export function AnalysisPage() {
  const [methods, setMethods] = useState<MethodInfo[]>([])
  const [loadingMethods, setLoadingMethods] = useState(true)
  const [methodsError, setMethodsError] = useState('')

  const [selectedMethod, setSelectedMethod] = useState('')
  const [dataSource, setDataSource] = useState<DataSourceConfig>({ type: 'sql', sql: '', limit: 500 })
  const [params, setParams] = useState<Record<string, unknown>>({})

  const [step, setStep] = useState<Step>('method')
  const [completed, setCompleted] = useState<Set<Step>>(new Set())

  const [running, setRunning] = useState(false)
  const [response, setResponse] = useState<AnalysisResponse | null>(null)
  const [runError, setRunError] = useState('')

  // Load method list
  useEffect(() => {
    listMethods()
      .then(list => setMethods(list))
      .catch(e => setMethodsError(String(e)))
      .finally(() => setLoadingMethods(false))
  }, [])

  // Reset params when method changes
  useEffect(() => {
    const m = methods.find(m => m.name === selectedMethod)
    if (m) {
      const defaults: Record<string, unknown> = {}
      for (const [k, schema] of Object.entries(m.params_schema ?? {})) {
        if (schema.default !== undefined) defaults[k] = schema.default
      }
      setParams(defaults)
    }
  }, [selectedMethod, methods])

  const markComplete = (s: Step) => setCompleted(prev => new Set([...prev, s]))

  const handleMethodSelect = (name: string) => {
    setSelectedMethod(name)
    markComplete('method')
    setStep('source')
    setResponse(null)
    setRunError('')
  }

  const handleSourceNext = () => {
    markComplete('source')
    setStep('params')
  }

  const handleRun = useCallback(async () => {
    if (!selectedMethod) return
    setRunning(true)
    setRunError('')
    setResponse(null)
    try {
      const res = await runAnalysis({ method: selectedMethod, data_source: dataSource, params })
      setResponse(res)
      markComplete('params')
      setStep('result')
    } catch (e) {
      setRunError(String(e))
    } finally {
      setRunning(false)
    }
  }, [selectedMethod, dataSource, params])

  const currentMethod = methods.find(m => m.name === selectedMethod)
  const canRunFromParams = !!selectedMethod && (dataSource.sql || dataSource.table || dataSource.nlquery)

  const btnStyle = (disabled: boolean): React.CSSProperties => ({
    padding: '8px 20px', borderRadius: 8, border: 'none', cursor: disabled ? 'not-allowed' : 'pointer',
    fontSize: 13, fontWeight: 600,
    background: disabled ? '#e5e7eb' : '#2563eb',
    color: disabled ? '#9ca3af' : '#fff',
  })

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: 24, background: '#f8fafc' }}>
      <div style={{ maxWidth: 960, margin: '0 auto' }}>
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#111827' }}>自助数据分析</div>
          <div style={{ fontSize: 13, color: '#6b7280', marginTop: 4 }}>选择分析方法 → 配置数据来源 → 设置参数 → 查看结果</div>
        </div>

        <StepBar current={step} completed={completed} />

        {/* Step 1: Method selection */}
        <SectionCard
          title="选择分析方法"
          action={selectedMethod ? (
            <span style={{ fontSize: 12, color: '#059669', fontWeight: 600, background: '#d1fae5', padding: '3px 10px', borderRadius: 12 }}>
              已选：{currentMethod?.label ?? selectedMethod}
            </span>
          ) : undefined}
        >
          {loadingMethods ? (
            <div style={{ color: '#6b7280', fontSize: 13 }}>加载分析方法...</div>
          ) : methodsError ? (
            <div style={{ color: '#dc2626', fontSize: 13 }}>加载失败: {methodsError}</div>
          ) : (
            <MethodSelector methods={methods} selected={selectedMethod} onSelect={handleMethodSelect} />
          )}
        </SectionCard>

        {/* Step 2: Data source */}
        {(step === 'source' || completed.has('source') || step === 'params' || step === 'result') && (
          <SectionCard title="配置数据来源">
            <DataSourceConfigPanel value={dataSource} onChange={setDataSource} />
            {step === 'source' && (
              <div style={{ marginTop: 14, display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  onClick={handleSourceNext}
                  disabled={!dataSource.sql && !dataSource.table && !dataSource.nlquery}
                  style={btnStyle(!dataSource.sql && !dataSource.table && !dataSource.nlquery)}
                >
                  下一步 →
                </button>
              </div>
            )}
          </SectionCard>
        )}

        {/* Step 3: Params + Run */}
        {(step === 'params' || step === 'result') && (
          <SectionCard title="设置参数">
            <ParamsForm method={currentMethod} params={params} onChange={setParams} />
            <div style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
              <button
                onClick={handleRun}
                disabled={running || !canRunFromParams}
                style={btnStyle(running || !canRunFromParams)}
              >
                {running ? '分析中...' : '▶ 运行分析'}
              </button>
              {running && (
                <span style={{ fontSize: 12, color: '#6b7280' }}>正在执行分析，请稍候...</span>
              )}
              {runError && (
                <span style={{ fontSize: 12, color: '#dc2626' }}>错误: {runError}</span>
              )}
            </div>
          </SectionCard>
        )}

        {/* Step 4: Result */}
        {response && (
          <SectionCard
            title="分析结果"
            action={
              <button
                onClick={() => {
                  setStep('params')
                  setResponse(null)
                  setRunError('')
                }}
                style={{ padding: '4px 12px', borderRadius: 6, border: '1px solid #d1d5db', background: '#fff', fontSize: 12, cursor: 'pointer', color: '#374151' }}
              >
                重新分析
              </button>
            }
          >
            {response.success && response.result ? (
              <ResultView result={response.result} answer={response.answer} />
            ) : (
              <div style={{ padding: '16px', background: '#fef2f2', borderRadius: 8, color: '#dc2626', fontSize: 13 }}>
                分析失败：{response.error ?? '未知错误'}
              </div>
            )}
          </SectionCard>
        )}
      </div>
    </div>
  )
}
