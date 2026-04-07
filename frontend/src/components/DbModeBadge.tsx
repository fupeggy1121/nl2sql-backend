import { useEffect, useRef, useState } from 'react'
import { Database, RefreshCw, Check } from 'lucide-react'
import { getDbMode, switchDbMode } from '../api/nl2sql'

interface EnvOption {
  key: string
  label: string
  host: string
  color: string
  bg: string
}

const ENV_OPTIONS: EnvOption[] = [
  { key: 'test', label: 'MySQL 测试环境',   host: '10.60.120.33:3336',  color: '#1e3a8a', bg: '#dbeafe' },
  { key: 'dev',  label: 'MySQL 开发环境',   host: '172.16.57.29:3306',  color: '#065f46', bg: '#d1fae5' },
  { key: 'epi',  label: '外延测试环境',      host: '10.60.120.33:40306', color: '#92400e', bg: '#fef3c7' },
]

export function DbModeBadge() {
  const [source, setSource] = useState<string>('…')
  const [open, setOpen]     = useState(false)
  const [switching, setSwitching] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const load = async () => {
    try {
      const res = await getDbMode()
      const db = res.data.database
      setSource(db.mysql_source ?? (db.db_backend === 'mysql' ? 'test' : 'unknown'))
    } catch {
      setSource('unknown')
    }
  }

  useEffect(() => { load() }, [])

  // Close modal when clicking outside
  useEffect(() => {
    if (!open) return
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  const select = async (key: string) => {
    if (key === source || switching) return
    setSwitching(true)
    setOpen(false)
    try {
      await switchDbMode(key)
      await load()
    } finally {
      setSwitching(false)
    }
  }

  const current = ENV_OPTIONS.find(e => e.key === source)

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      {/* Icon button */}
      <button
        onClick={() => setOpen(v => !v)}
        disabled={switching}
        title={current ? `当前: ${current.label} (${current.host})` : '数据库环境'}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 34,
          height: 34,
          borderRadius: 8,
          border: '1px solid',
          borderColor: current?.color ?? '#6b7280',
          background: current?.bg ?? '#f3f4f6',
          color: current?.color ?? '#374151',
          cursor: switching ? 'not-allowed' : 'pointer',
          transition: 'all .15s',
        }}
      >
        {switching
          ? <RefreshCw size={15} style={{ animation: 'spin 1s linear infinite' }} />
          : <Database size={15} />
        }
      </button>

      {/* Dropdown modal */}
      {open && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 8px)',
          right: 0,
          width: 240,
          background: '#fff',
          border: '1px solid #e5e7eb',
          borderRadius: 10,
          boxShadow: '0 4px 20px rgba(0,0,0,.1)',
          zIndex: 9999,
          overflow: 'hidden',
        }}>
          <div style={{ padding: '10px 14px 6px', fontSize: 11, fontWeight: 600, color: '#6b7280', letterSpacing: '.04em', textTransform: 'uppercase' }}>
            选择数据库环境
          </div>
          {ENV_OPTIONS.map(env => {
            const isActive = env.key === source
            return (
              <button
                key={env.key}
                onClick={() => select(env.key)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  width: '100%',
                  padding: '9px 14px',
                  gap: 10,
                  background: isActive ? env.bg : 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'background .1s',
                }}
                onMouseEnter={e => { if (!isActive) (e.currentTarget as HTMLButtonElement).style.background = '#f9fafb' }}
                onMouseLeave={e => { if (!isActive) (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
              >
                <div style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: env.color, flexShrink: 0,
                }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: isActive ? 600 : 400, color: isActive ? env.color : '#111827' }}>
                    {env.label}
                  </div>
                  <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 1 }}>{env.host}</div>
                </div>
                {isActive && <Check size={13} style={{ color: env.color, flexShrink: 0 }} />}
              </button>
            )
          })}
          <div style={{ height: 6 }} />
        </div>
      )}
    </div>
  )
}
