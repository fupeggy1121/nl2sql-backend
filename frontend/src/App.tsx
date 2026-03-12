import { useState, useEffect, useCallback } from 'react'
import {
  BotMessageSquare, Book, Tag, Network, Sparkles, BarChart,
  Plus, MessageSquare, FlaskConical, LayoutDashboard, Trash2, GitBranch
} from 'lucide-react'
import { DbModeBadge } from './components/DbModeBadge'
import MappingManager from './components/MappingManager'
import OntologyViewer from './components/OntologyViewer'
import SynonymManager from './components/SynonymManager'
import { MESPage } from './modules/mes'
import { ReportsModule } from './components/Reports/ReportsModule'
import NLTestManager from './components/NLTestManager'
import { DashboardModule } from './components/Dashboard/DashboardModule'
import { DashboardEditor } from './components/Dashboard/DashboardEditor'
import { TraceabilityView } from './components/Traceability/TraceabilityView'
import { useData } from './hooks/useData'

// ── Types ─────────────────────────────────────────────────────────
type TopModule = 'ai-chat' | 'ontology-management' | 'nl-testing'

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

// ── Main App ──────────────────────────────────────────────────────
export default function App() {
  const { fetchChatSessions, createChatSession, fetchLatestChatSession, dashboards, createDashboard, deleteDashboard, savedReports, deleteSavedReport } = useData()

  const [activeTopModule, setActiveTopModule] = useState<TopModule>('ai-chat')
  const [activeSubModule, setActiveSubModule] = useState<string>('')
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([])
  const [currentTime, setCurrentTime] = useState(new Date())
  const [showNewDashboard, setShowNewDashboard] = useState(false)
  const [traceabilityItems, setTraceabilityItems] = useState<{ id: string; label: string }[]>([])

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
        setActiveSubModule(id)
      } else {
        setChatSessions(sessions)
        setActiveSubModule(sessions[0].id)
      }
    }
    init()
  }, [fetchChatSessions, createChatSession])

  const handleTopModuleChange = useCallback(async (mod: TopModule) => {
    setActiveTopModule(mod)
    if (mod === 'ontology-management') {
      setActiveSubModule('semantic-mapping-management')
    } else if (mod === 'nl-testing') {
      setActiveSubModule('nl-testing')
    } else {
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
    setActiveTopModule('ai-chat')
    setActiveSubModule(id)
  }, [chatSessions.length, createChatSession])

  const handleNavigateToTraceability = useCallback(
    ({ lotCode, waferCode }: { lotCode?: string; waferCode?: string } = {}) => {
      const subKey = lotCode
        ? `traceability-lot:${lotCode}`
        : waferCode
        ? `traceability-wafer:${waferCode}`
        : 'traceability-lot:'
      const label = lotCode ? `批次 ${lotCode}` : waferCode ? `Wafer ${waferCode}` : '追溯查询'
      setTraceabilityItems(prev => {
        const exists = prev.some(i => i.id === subKey)
        return exists ? prev : [{ id: subKey, label }, ...prev]
      })
      setActiveTopModule('ai-chat')
      setActiveSubModule(subKey)
    },
    []
  )

  const renderSidebar = () => {
    if (activeTopModule === 'nl-testing') {
      return null
    }
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
    return (
      <nav style={{ width: 220, flexShrink: 0, background: '#fff', borderRight: '1px solid #e5e7eb', display: 'flex', flexDirection: 'column' }}>
          {/* ── 看板 section ───────────────────────────── */}
          <div style={{ padding: '12px 16px 4px', fontSize: 11, fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>看板</span>
            <button title="新建看板" onClick={() => setShowNewDashboard(true)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', padding: '0 2px', display: 'flex', alignItems: 'center' }}>
              <Plus size={13} />
            </button>
          </div>
          {dashboards.map(d => {
            const active = activeSubModule === `dashboard-${d.id}`
            return (
              <div key={d.id} style={{ position: 'relative', display: 'flex', alignItems: 'center' }}
                onMouseEnter={e => { const btn = (e.currentTarget as HTMLElement).querySelector<HTMLElement>('.del-btn'); if (btn) btn.style.opacity = '1' }}
                onMouseLeave={e => { const btn = (e.currentTarget as HTMLElement).querySelector<HTMLElement>('.del-btn'); if (btn) btn.style.opacity = '0' }}>
                <button onClick={() => { setActiveTopModule('ai-chat'); setActiveSubModule(`dashboard-${d.id}`) }}
                  style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8, padding: '9px 16px', background: active ? '#eff6ff' : 'transparent', color: active ? '#1d4ed8' : '#374151', border: 'none', cursor: 'pointer', fontSize: 13, textAlign: 'left', borderLeft: active ? '2px solid #2563eb' : '2px solid transparent', overflow: 'hidden' }}>
                  <LayoutDashboard size={13} style={{ flexShrink: 0 }} />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.name}</span>
                </button>
                <button className="del-btn" title="删除看板"
                  onClick={e => { e.stopPropagation(); if (confirm(`删除看板「${d.name}」？`)) { deleteDashboard(d.id); if (activeSubModule === `dashboard-${d.id}`) setActiveSubModule(chatSessions[0]?.id || '') } }}
                  style={{ opacity: 0, transition: 'opacity .15s', position: 'absolute', right: 8, background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', padding: '2px 4px', display: 'flex', alignItems: 'center' }}>
                  <Trash2 size={12} />
                </button>
              </div>
            )
          })}
          {dashboards.length === 0 && (
            <div style={{ padding: '6px 18px', fontSize: 12, color: '#d1d5db', fontStyle: 'italic' }}>暂无看板</div>
          )}
          {/* ── 保存的报表 ─────────────────────────────── */}
          <div style={{ padding: '12px 16px 4px', fontSize: 11, fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.5px', marginTop: 4 }}>报表</div>
          {savedReports.map(r => {
            const active = activeSubModule === `report-${r.id}`
            return (
              <div key={r.id} style={{ position: 'relative', display: 'flex', alignItems: 'center' }}
                onMouseEnter={e => { const btn = (e.currentTarget as HTMLElement).querySelector<HTMLElement>('.del-rpt'); if (btn) btn.style.opacity = '1' }}
                onMouseLeave={e => { const btn = (e.currentTarget as HTMLElement).querySelector<HTMLElement>('.del-rpt'); if (btn) btn.style.opacity = '0' }}>
                <button onClick={() => { setActiveTopModule('ai-chat'); setActiveSubModule(`report-${r.id}`) }}
                  style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8, padding: '9px 16px', background: active ? '#eff6ff' : 'transparent', color: active ? '#1d4ed8' : '#374151', border: 'none', cursor: 'pointer', fontSize: 13, textAlign: 'left', borderLeft: active ? '2px solid #2563eb' : '2px solid transparent', overflow: 'hidden' }}>
                  <BarChart size={13} style={{ flexShrink: 0 }} />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.name}</span>
                </button>
                <button className="del-rpt" title="删除报表"
                  onClick={e => { e.stopPropagation(); if (confirm(`删除报表「${r.name}」？`)) { deleteSavedReport(r.id); if (activeSubModule === `report-${r.id}`) setActiveSubModule(chatSessions[0]?.id || '') } }}
                  style={{ opacity: 0, transition: 'opacity .15s', position: 'absolute', right: 8, background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', padding: '2px 4px', display: 'flex', alignItems: 'center' }}>
                  <Trash2 size={12} />
                </button>
              </div>
            )
          })}
          {savedReports.length === 0 && (
            <div style={{ padding: '6px 18px', fontSize: 12, color: '#d1d5db', fontStyle: 'italic' }}>暂无保存的报表</div>
          )}
          {/* ── 追溯记录 ─────────────────────────────── */}
          <div style={{ padding: '12px 16px 4px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.5px' }}>追溯查询</span>
            <button
              onClick={() => handleNavigateToTraceability({})}
              title="新建追溯查询"
              style={{ display: 'flex', alignItems: 'center', gap: 3, padding: '2px 7px', borderRadius: 5, border: '1px solid #e5e7eb', background: '#f9fafb', color: '#374151', fontSize: 11, cursor: 'pointer' }}>
              <Plus size={11} />新建
            </button>
          </div>
          {traceabilityItems.length > 0 && (
            <>
              {traceabilityItems.map(item => {
                const active = activeSubModule === item.id
                return (
                  <div key={item.id} style={{ position: 'relative', display: 'flex', alignItems: 'center' }}
                    onMouseEnter={e => { const btn = (e.currentTarget as HTMLElement).querySelector<HTMLElement>('.del-trc'); if (btn) btn.style.opacity = '1' }}
                    onMouseLeave={e => { const btn = (e.currentTarget as HTMLElement).querySelector<HTMLElement>('.del-trc'); if (btn) btn.style.opacity = '0' }}>
                    <button onClick={() => { setActiveTopModule('ai-chat'); setActiveSubModule(item.id) }}
                      style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8, padding: '9px 16px', background: active ? '#eff6ff' : 'transparent', color: active ? '#1d4ed8' : '#374151', border: 'none', cursor: 'pointer', fontSize: 13, textAlign: 'left', borderLeft: active ? '2px solid #2563eb' : '2px solid transparent', overflow: 'hidden' }}>
                      <GitBranch size={13} style={{ flexShrink: 0 }} />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.label}</span>
                    </button>
                    <button className="del-trc" title="关闭追溯"
                      onClick={e => { e.stopPropagation(); setTraceabilityItems(prev => prev.filter(i => i.id !== item.id)); if (activeSubModule === item.id) setActiveSubModule(chatSessions[0]?.id || '') }}
                      style={{ opacity: 0, transition: 'opacity .15s', position: 'absolute', right: 8, background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280', padding: '2px 4px', display: 'flex', alignItems: 'center' }}>
                      <Trash2 size={12} />
                    </button>
                  </div>
                )
              })}
            </>
          )}
          <div style={{ padding: '12px 16px 4px', fontSize: 11, fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.5px', marginTop: 4 }}>AI 对话</div>
          <button onClick={startNewConversation}
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 16px', background: 'transparent', color: '#4b5563', border: 'none', cursor: 'pointer', fontSize: 13, textAlign: 'left', borderLeft: '2px solid transparent' }}>
            <Plus size={14} />新对话
          </button>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {chatSessions.map(session => {
              const active = activeSubModule === session.id
              return (
                <button key={session.id} onClick={() => { setActiveTopModule('ai-chat'); setActiveSubModule(session.id) }}
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

  const renderContent = () => {
    if (activeTopModule === 'nl-testing') {
      return <NLTestManager />
    }
    if (activeTopModule === 'ontology-management') {
      switch (activeSubModule) {
        case 'semantic-mapping-management': return <MappingManager />
        case 'ontology-viewer':             return <OntologyViewer />
        case 'synonym-management':          return <SynonymManager />
        default:                            return <MappingManager />
      }
    }
    if (activeSubModule === 'saved-reports') return <ReportsModule reportId={undefined} />
    if (activeSubModule.startsWith('report-')) {
      const id = activeSubModule.replace('report-', '')
      return <ReportsModule reportId={id} />
    }
    if (activeSubModule.startsWith('dashboard-')) {
      const id = activeSubModule.replace('dashboard-', '')
      return <DashboardModule dashboardId={id} />
    }
    if (activeSubModule.startsWith('traceability-')) {
      const params = activeSubModule.replace('traceability-', '')
      return <TraceabilityView params={params} />
    }
    const sessionId = activeSubModule || chatSessions[0]?.id || 'default'
    return <MESPage sessionId={sessionId} skipDataGeneration={true} onNavigateToTraceability={handleNavigateToTraceability} />
  }

  const topNavItems = [
    { id: 'ai-chat' as TopModule,             label: '智能报表', icon: Sparkles },
    { id: 'ontology-management' as TopModule, label: '本体管理', icon: Book },
    { id: 'nl-testing' as TopModule,          label: '语义测试', icon: FlaskConical },
  ]

  return (
    <div style={{ height: '100vh', background: '#f0f2f5', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <header style={{ background: '#fff', borderBottom: '1px solid #e5e7eb', padding: '0 24px', height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'sticky', top: 0, zIndex: 100, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <BotMessageSquare size={20} color="#4f46e5" />
          <span style={{ fontSize: 16, fontWeight: 700, color: '#1a1a2e', marginRight: 24 }}>ChatBI</span>
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

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>
        {renderSidebar()}
        <main style={{ flex: 1, minHeight: 0, overflow: (activeTopModule === 'ontology-management' || activeTopModule === 'nl-testing') ? 'auto' : 'hidden', display: 'flex', flexDirection: 'column' }}>
          {renderContent()}
        </main>
      </div>

      {showNewDashboard && (
        <DashboardEditor
          onSave={async (data) => {
            const d = await createDashboard(data)
            setActiveTopModule('ai-chat')
            setActiveSubModule(`dashboard-${d.id}`)
            setShowNewDashboard(false)
          }}
          onClose={() => setShowNewDashboard(false)}
        />
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

