import { useEffect, useState } from 'react'
import { Database, RefreshCw } from 'lucide-react'
import { getDbMode, switchDbMode } from '../api/nl2sql'

const MODES = [
  { value: 'mysql', label: 'MySQL 生产库' },
  { value: 'auto', label: '自动检测' },
]

export function DbModeBadge() {
  const [mode, setMode] = useState<string>('…')
  const [switching, setSwitching] = useState(false)

  const load = async () => {
    try {
      const res = await getDbMode()
      const db = res.data.database
      setMode(db.runtime_db_mode ?? db.mode)
    } catch {
      setMode('unknown')
    }
  }

  useEffect(() => { load() }, [])

  const toggle = async () => {
    setSwitching(true)
    try {
      const next = mode === 'mysql' ? 'auto' : 'mysql'
      await switchDbMode(next)
      await load()
    } finally {
      setSwitching(false)
    }
  }

  const isMysql = mode === 'mysql'

  return (
    <button
      onClick={toggle}
      disabled={switching}
      title="点击切换数据库模式"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '6px 14px',
        borderRadius: 20,
        border: 'none',
        cursor: 'pointer',
        fontSize: 13,
        fontWeight: 600,
        background: isMysql ? '#d1fae5' : '#e0e7ff',
        color: isMysql ? '#065f46' : '#3730a3',
        transition: 'all .2s',
      }}
    >
      {switching ? (
        <RefreshCw size={14} style={{ animation: 'spin 1s linear infinite' }} />
      ) : (
        <Database size={14} />
      )}
      {isMysql ? 'MySQL 生产库' : mode === 'auto' ? '自动 (Supabase)' : mode}
    </button>
  )
}
