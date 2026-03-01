import { useState } from 'react'
import { BotMessageSquare, RotateCcw } from 'lucide-react'
import { processQuery, executeQuery } from './api/nl2sql'
import type { ProcessResponse, ExecuteResponse } from './types/api'
import { QueryInput } from './components/QueryInput'
import { SqlPreview } from './components/SqlPreview'
import { ResultTable } from './components/ResultTable'
import { PipelineTrace } from './components/PipelineTrace'
import { DbModeBadge } from './components/DbModeBadge'

export default function App() {
  const [loading, setLoading] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [plan, setPlan] = useState<ProcessResponse | null>(null)
  const [result, setResult] = useState<ExecuteResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [currentQuery, setCurrentQuery] = useState('')

  const handleQuery = async (query: string) => {
    setLoading(true)
    setError(null)
    setPlan(null)
    setResult(null)
    setCurrentQuery(query)
    try {
      const res = await processQuery(query)
      setPlan(res)
      if (!res.success) {
        setError(res.error ?? '查询规划失败')
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  const handleExecute = async (sql: string) => {
    if (!plan) return
    setExecuting(true)
    setError(null)
    setResult(null)
    try {
      const res = await executeQuery(sql, plan.session_id)
      setResult(res)
      if (!res.success) {
        setError(res.error ?? '执行失败')
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setExecuting(false)
    }
  }

  const reset = () => {
    setPlan(null); setResult(null); setError(null); setCurrentQuery('')
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f0f2f5' }}>
      {/* Top bar */}
      <header style={{
        background: '#fff',
        borderBottom: '1px solid #e5e7eb',
        padding: '0 32px',
        height: 56,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 100,
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <BotMessageSquare size={22} color="#4f46e5" />
          <span style={{ fontSize: 17, fontWeight: 700, color: '#1a1a2e' }}>
            AI 报表查询
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <DbModeBadge />
          {(plan || result) && (
            <button
              onClick={reset}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '6px 12px', borderRadius: 8,
                border: '1px solid #e5e7eb', background: '#fff',
                color: '#6b7280', fontSize: 13, cursor: 'pointer',
              }}
            >
              <RotateCcw size={13} />
              新查询
            </button>
          )}
        </div>
      </header>

      {/* Main */}
      <main style={{
        maxWidth: 960,
        margin: '0 auto',
        padding: '32px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: 20,
      }}>
        {/* Query card */}
        <div style={{
          background: '#fff',
          borderRadius: 12,
          padding: 24,
          border: '1px solid #e5e7eb',
          boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
        }}>
          {currentQuery && (
            <div style={{
              marginBottom: 12,
              fontSize: 13, color: '#6b7280',
              background: '#f5f3ff', borderRadius: 8, padding: '6px 12px',
              display: 'inline-flex', alignItems: 'center', gap: 6,
            }}>
              <span style={{ color: '#4f46e5' }}>查询：</span>
              {currentQuery}
            </div>
          )}
          <QueryInput onQuery={handleQuery} loading={loading} />
        </div>

        {/* Error */}
        {error && (
          <div style={{
            padding: '14px 18px',
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: 10,
            color: '#991b1b',
            fontSize: 14,
          }}>
            ❌ {error}
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div style={{
            padding: 32, textAlign: 'center', color: '#6b7280', fontSize: 14,
            background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb',
          }}>
            <div style={{ fontSize: 28, marginBottom: 8 }}>🤔</div>
            正在分析您的查询，生成 SQL…
          </div>
        )}

        {/* SQL Preview */}
        {plan?.query_plan && !loading && (
          <SqlPreview
            plan={plan.query_plan}
            onExecute={handleExecute}
            executing={executing}
          />
        )}

        {/* Executing state */}
        {executing && (
          <div style={{
            padding: 24, textAlign: 'center', color: '#6b7280', fontSize: 14,
            background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb',
          }}>
            <div style={{ fontSize: 28, marginBottom: 8 }}>⚡</div>
            正在执行查询…
          </div>
        )}

        {/* Result table */}
        {result && !executing && (
          <ResultTable result={result} />
        )}

        {/* Pipeline trace */}
        {plan?.pipeline_trace && plan.pipeline_trace.length > 0 && !loading && (
          <PipelineTrace steps={plan.pipeline_trace} />
        )}
      </main>

      {/* Spin animation */}
      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}
