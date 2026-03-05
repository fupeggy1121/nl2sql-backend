import { useState, useEffect, useCallback } from 'react'
import {
  BotMessageSquare, Book, Tag, Network, Sparkles, BarChart,
  Plus, MessageSquare
} from 'lucide-react'
import { DbModeBadge } from './components/DbModeBadge'
import MappingManager from './components/MappingManager'
import OntologyViewer from './components/OntologyViewer'
import SynonymManager from './components/SynonymManager'
import { MESPage } from './modules/mes'
import { ReportsModule } from './components/Reports/ReportsModule'
import { useData } from './hooks/useData'

// ── Types ─────────────────────────────────────────────────────────
type TopModule = 'ai-chat' | 'ontology-management'

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
  const { fetchChatSessions, createChatSession, fetchLatestChatSession } = useData()

  const [activeTopModule, setActiveTopModule] = useState<TopModule>('ai-chat')
  const [activeSubModule, setActiveSubModule] = useState<string>('')
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

  const renderSidebar = () => {
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
    if (activeTopModule === 'ontology-management') {
      switch (activeSubModule) {
        case 'semantic-mapping-management': return <MappingManager />
        case 'ontology-viewer':             return <OntologyViewer />
        case 'synonym-management':          return <SynonymManager />
        default:                            return <MappingManager />
      }
    }
    if (activeSubModule === 'saved-reports') return <ReportsModule reportId={activeSubModule} />
    const sessionId = activeSubModule || chatSessions[0]?.id || 'default'
    return <MESPage sessionId={sessionId} skipDataGeneration={true} />
  }

  const topNavItems = [
    { id: 'ai-chat' as TopModule,             label: '智能报表', icon: Sparkles },
    { id: 'ontology-management' as TopModule, label: '本体管理', icon: Book },
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
        <main style={{ flex: 1, minHeight: 0, overflow: activeTopModule === 'ontology-management' ? 'auto' : 'hidden', display: 'flex', flexDirection: 'column' }}>
          {renderContent()}
        </main>
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

