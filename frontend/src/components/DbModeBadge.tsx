import { useEffect, useState } from 'react'
import { Database, RefreshCw } from 'lucide-react'
import { getDbMode, switchDbMode } from '../api/nl2sql'

export function DbModeBadge() {
  const [backend, setBackend] = useState<string>('…')
  const [switching, setSwitching] = useState(false)

  const load = async () => {
    try {
      const res = await getDbMode()
      const db = res.data.database
      // db_backend is the real query target: "mysql" | "supabase"
      setBackend(db.db_backend ?? (db.runtime_db_mode === 'mysql' ? 'mysql' : 'supabase'))
    } catch {
      setBackend('unknown')
    }
  }

  useEffect(() => { load() }, [])

  const toggle = async () => {
    setSwitching(true)
    try {
      const next = backend === 'mysql' ? 'supabase' : 'mysql'
      await switchDbMode(next)
      await load()
    } finally {
      setSwitching(false)
    }
  }

  const isMysql = backend === 'mysql'

  return (
    <button
      onClick={toggle}
      disabled={switching}
      title={isMysql ? '当前: MySQL 生产库，点击切换到 Supabase' : '当前: Supabase，点击切换到 MySQL 生产库'}
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
      {isMysql ? 'MySQL 生产库' : 'Supabase'}
    </button>
  )
}
