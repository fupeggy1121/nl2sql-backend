import { useState, useEffect, useCallback } from 'react'
import {
  BotMessageSquare, RotateCcw, Book, Tag, Network, Sparkles, BarChart,
  Plus, MessageSquare
} from 'lucide-react'
import { processQuery, executeQuery } from './api/nl2sql'
import type { ProcessResponse, ExecuteResponse } from './types/api'
import { QueryInput } from './components/QueryInput'
import { SqlPreview } from './components/SqlPreview'
import { ResultTable } from './components/ResultTable'
import { PipelineTrace } from './components/PipelineTrace'
import { DbModeBadge } from './components/DbModeBadge'

// Ontology Management
import MappingManager from './components/MappingManager'
import OntologyViewer from './components/OntologyViewer'
import SynonymManager from './components/SynonymManager'

// AI Reports
import { MESPage } from './modules/mes'
import { ReportsModule } from './components/Reports/ReportsModule'
import { useData } from './hooks/useData'

// ── Types ─────────────────────────────────────────────────────────
type TopModule = 'ai-query' | 'ontology-management' | 'ai-reports'

interface ChatSession {
  id: string
  name: string
  created_at: string
}

// ── Sub-menus ─────────────────────────────────────────────────────
const ontologySubItems = [
  { id: 'semantic-mapping-management', label: '语义映射管理', icon: Tag },
  { id: 'ontology-viewer',             label: '本体可视化',   icon: Network },
  { id: 'synonym-management',          label: '同义词管理',   icon: Tag },
]

// ── AI Query Page (original functionality) ────────────────────────
function QueryPage() {
  const [loading, setLoading] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [plan, setPlan] = useState<ProcessResponse | null>(null)
  const [result, setResult] = useState<ExecuteResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [currentQuery, setCurrentQuery] = useState('')

  const handleQuery = async (query: string) => {
    setLoading(true); setError(null); setPlan(null); setResult(null); setCurrentQuery(query)
    try {
      const res = await processQuery(query)
      setPlan(res)
      if (!res.success) setError(res.error ?? '查询规划失败')
    } catch (e) { setError(String(e)) }
    finally { setLoading(false) }
  }
  const handleExecute = async (sql: string) => {
    if (!plan) return
    setExecuting(true); setError(null); setResult(null)
    try {
      const res = await executeQuery(sql, plan.session_id)
      setResult(res)
      if (!res.success) setError(res.error ?? '执行失败')
    } catch (e) { setError(String(e)) }
    finally { setExecuting(false) }
  }
  const reset = () => { setPlan(null); setResult(null); setError(null); setCurrentQuery('') }

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ background: '#fff', borderRadius: 12, padding: 24, border: '1px solid #e5e7eb', boxShadow: '0 1px 4px rgba(0,0,0,0.04)' }}>
        {currentQuery && (
          <div style={{ marginBottom: 12, fontSize: 13, color: '#6b7280', background: '#f5f3ff', borderRadius: 8, padding: '6px 12px', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: '#4f46e5' }}>查询：</span>{currentQuery}
          </div>
        )}
        <QueryInput onQuery={handleQuery} loading={loading} />
        {(plan || result) && (
          <button onClick={reset} style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff', color: '#6b7280', fontSize: 13, cursor: 'pointer' }}>
            <RotateCcw size={13} /> 新查询
          </button>
        )}
      </div>
      {error && <div style={{ padding: '14px 18px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 10, color: '#991b1b', fontSize: 14 }}>❌ {error}</div>}
      {loading && <div style={{ padding: 32, textAlign: 'center', color: '#6b7280', fontSize: 14, background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb' }}><div style={{ fontSize: 28, marginBottom: 8 }}>🤔</div>正在分析您的查询，生成 SQL…</div>}
      {plan?.query_plan && !loading && <SqlPreview plan={plan.query_plan} onExecute={handleExecute} executing={executing} />}
      {executing && <div style={{ padding: 24, textAlign: 'center', color: '#6b7280', fontSize: 14, background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb' }}><div style={{ fontSize: 28, marginBottom: 8 }}>⚡</div>正在执行查询…</div>}
      {result && !executing && <ResultTable result={result} />}
      {plan?.pipeline_trace && plan.pipeline_trace.length > 0 && !loading && <PipelineTrace steps={plan.pipeline_trace} />}
    </div>
  )
}

// ── Main App ──────────────────────────────────────────────────────
export default function App() {
  const { fetchChatSessions, createChatSession, fetchLatestChatSession } = useData()

  const [activeTopModule, setActiveTopModule] = useState<TopModule>('ai-query')
  const [activeSubModule, setActiveSubModule] = useState<string>('semantic-mapping-management')
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([])
  const [currentTime, setCurrentTime] = useState(new Date())

  useEffect(() => {
    const t = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    const init = async () => {
      const sessions = await fetchChatSessions()
      if (sessions.length === 0) {
        const id = crypto.randomUUID()
        const s = await createChatSession(id, '新对话 1')
        setChatSessions([s])
      } else {
        setChatSessions(sessions)
      }
    }
    init()
  }, [fetchChatSessions, createChatSession])

  const handleTopModuleChange = useCallback(async (mod: TopModule) => {
    setActiveTopModule(mod)
    if (mod === 'ontology-management') {
      setActiveSubModule('semantic-mapping-management')
    } else if (mod === 'ai-reports') {
      const sessions = await fetchChatSessions()
      const latest = await fetchLatestChatSession()
      if (latest.found && latest.session) {
        setActiveSubModule(latest.session.id)
      } else if (sessions.length > 0) {
        setActiveSubModule(sessions[0].id)
      }
    }
  }, [fetchChatSessions, fetchLatestChatSession])

  const startNewConversation = useCallback(async () => {
    const id = crypto.randomUUID()
    const name = `新对话 ${chatSessions.length + 1}`
    const s = await createChatSession(id, name)
    setChatSessions(prev => [s, ...prev])
    setActiveTopModule('ai-reports')
    setActiveSubModule(id)
  }, [chatSessions.length, createChatSession])

  const isChatSession = activeTopModule === 'ai-reports' && chatSessions.some(s => s.id === activeSubModule)

  const renderSidebar = () => {
    if (activeTopModule === 'ai-query') return null
    if (activeTopModule === 'ontology-management') {
      return (
        <nav style={{ width: 200, flexShrink: 0, background: '#fff', borderRight: '1px solid #e5e7eb', padding: '16px 0' }}>
          <div style={{ padding: '0 16px 8px', fontSize: 11, fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.5px' }}>本体管理</div>
          {ontologySubItems.map(item => {
            const Icon = item.icon
            const active = activeSubModule === item.id
            return (
              <button key={item.id} onClick={() => setActiveSubModule(item.id)}
                style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, padding: '9px 16px', background: active ? '#eff6ff' : 'transparent', color: active ? '#1d4ed8' : '#374151', border: 'none', cursor: 'pointer', fontSize: 13, textAlign: 'left', borderLeft: active ? '2px solid #2563eb' : '2px solid transparent' }}>
                <Icon size={14} />{item.label}
              </button>
            )
          })}
        </nav>
      )
    }
    if (activeTopModule === 'ai-reports') {
      return (
        <nav style={{ width: 220, flexShrink: 0, background: '#fff', borderRight: '1px solid #e5e7eb', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '12px 16px 4px', fontSize: 11, fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.5px' }}>模块</div>
          <button onClick={() => setActiveSubModule('saved-reports')}
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 16px', background: activeSubModule === 'saved-reports' ? '#eff6ff' : 'transparent', color: activeSubModule === 'saved-reports' ? '#1d4ed8' : '#374151', border: 'none', cursor: 'pointer', fontSize: 13, textAlign: 'left', borderLeft: activeSubModule === 'saved-reports' ? '2px solid #2563eb' : '2px solid transparent' }}>
            <BarChart size={14} />保存的报表
          </button>
          <div style={{ padding: '12px 16px 4px', fontSize: 11, fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.5px', marginTop: 4 }}>AI 对话</div>
          <button onClick={startNewConversation}
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 16px', background: 'transparent', color: '#4b5563', border: 'none', cursor: 'pointer', fontSize: 13, textAlign: 'left', borderLeft: '2px solid transparent' }}>
            <Plus size={14} />新对话
          </button>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {chatSessions.map(session => {
              const active = activeSubModule === session.id
              return (
                <button key={session.id} onClick={() => { setActiveTopModule('ai-reports'); setActiveSubModule(session.id) }}
                  style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, padding: '9px 16px', background: active ? '#eff6ff' : 'transparent', color: active ? '#1d4ed8' : '#374151', border: 'none', cursor: 'pointer', fontSize: 13, textAlign: 'left', borderLeft: active ? '2px solid #2563eb' : '2px solid transparent', overflow: 'hidden' }}>
                  <MessageSquare size={13} style={{ flexShrink: 0 }} />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{session.name}</span>
                </button>
              )
            })}
          </div>
        </nav>
      )
    }
    return null
  }

  const renderContent = () => {
    if (activeTopModule === 'ai-query') return <QueryPage />
    if (activeTopModule === 'ontology-management') {
      switch (activeSubModule) {
        case 'semantic-mapping-management': return <MappingManager />
        case 'ontology-viewer':             return <OntologyViewer />
        case 'synonym-management':          return <SynonymManager />
        default:                            return <MappingManager />
      }
    }
    if (activeTopModule === 'ai-reports') {
      if (activeSubModule === 'saved-reports') return <ReportsModule reportId={activeSubModule} />
      if (isChatSession) return <MESPage sessionId={activeSubModule} skipDataGeneration={true} />
      return <MESPage sessionId={chatSessions[0]?.id ?? 'default'} skipDataGeneration={true} />
    }
    return null
  }

  const topNavItems = [
    { id: 'ai-query' as TopModule,              label: 'AI 查询', icon: BotMessageSquare },
    { id: 'ontology-management' as TopModule,   label: '本体管理', icon: Book },
    { id: 'ai-reports' as TopModule,            label: 'AI 报表',  icon: Sparkles },
  ]

  return (
    <div style={{ minHeight: '100vh', background: '#f0f2f5', display: 'flex', flexDirection: 'column' }}>
      <header style={{ background: '#fff', borderBottom: '1px solid #e5e7eb', padding: '0 24px', height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'sticky', top: 0, zIndex: 100, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <BotMessageSquare size={20} color="#4f46e5" />
          <span style={{ fontSize: 16, fontWeight: 700, color: '#1a1a2e', marginRight: 24 }}>外延 MES · NL2SQL</span>
          <nav style={{ display: 'flex', gap: 2 }}>
            {topNavItems.map(item => {
              const Icon = item.icon
              const active = activeTopModule === item.id
              return (
                <button key={item.id} onClick={() => handleTopModuleChange(item.id)}
                  style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 6, border: 'none', background: active ? '#eff6ff' : 'transparent', color: active ? '#1d4ed8' : '#6b7280', fontSize: 13, fontWeight: active ? 600 : 400, cursor: 'pointer', transition: 'all .15s' }}>
                  <Icon size={14} />{item.label}
                </button>
              )
            })}
          </nav>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 12, color: '#9ca3af' }}>{currentTime.toLocaleTimeString('zh-CN')}</span>
          <DbModeBadge />
        </div>
      </header>

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {renderSidebar()}
        <main style={{ flex: 1, overflow: 'auto', padding: activeTopModule === 'ai-query' ? '32px 24px' : 0 }}>
          {renderContent()}
        </main>
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

