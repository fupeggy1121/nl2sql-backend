import { useState } from 'react'
import { Database, Target } from 'lucide-react'
import DataSourceManager from './DataSourceManager'
import BaselinesManager from './BaselinesManager'

type Tab = 'connections' | 'baselines'

const tabs: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'connections', label: '数据源连接配置', icon: Database },
  { id: 'baselines',  label: '指标项 Target 配置', icon: Target },
]

export default function DataSourcePage() {
  const [activeTab, setActiveTab] = useState<Tab>('connections')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#0d0e1a' }}>
      {/* Tab bar */}
      <div style={{
        flexShrink: 0,
        background: '#12142a',
        borderBottom: '1px solid #1e1b4b',
        padding: '0 24px',
        display: 'flex',
        gap: 2,
      }}>
        {tabs.map(tab => {
          const Icon = tab.icon
          const active = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 7,
                padding: '13px 18px',
                background: 'transparent',
                border: 'none',
                borderBottom: active ? '2px solid #6366f1' : '2px solid transparent',
                color: active ? '#a5b4fc' : '#6b7280',
                fontSize: 13,
                fontWeight: active ? 600 : 400,
                cursor: 'pointer',
                transition: 'all .15s',
                marginBottom: -1,
              }}
            >
              <Icon size={14} />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', background: '#0d0e1a' }}>
        {activeTab === 'connections' && <DataSourceManager />}
        {activeTab === 'baselines'   && <BaselinesManager />}
      </div>
    </div>
  )
}
