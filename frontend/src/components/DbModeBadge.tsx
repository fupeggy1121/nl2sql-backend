import { useEffect, useState } from 'react'
import { Database, RefreshCw } from 'lucide-react'
import { getDbMode, switchDbMode } from '../api/nl2sql'

export function DbModeBadge() {
  const [source, setSource] = useState<string>('…')
  const [hostHint, setHostHint] = useState<string>('')
  const [switching, setSwitching] = useState(false)

  const load = async () => {
    try {
      const res = await getDbMode()
      const db = res.data.database
      // mysql_source: "test" | "dev"
      setSource(db.mysql_source ?? (db.db_backend === 'mysql' ? 'test' : 'unknown'))
      setHostHint(db.mysql_host_hint ?? '')
    } catch {
      setSource('unknown')
    }
  }

  useEffect(() => { load() }, [])

  const toggle = async () => {
    setSwitching(true)
    try {
      const next = source === 'test' ? 'dev' : 'test'
      await switchDbMode(next)
      await load()
    } finally {
      setSwitching(false)
    }
  }

  const isTest = source === 'test'
  const label  = isTest ? 'MySQL 测试环境' : 'MySQL 开发环境'
  const title  = isTest
    ? `当前: 测试环境 (${hostHint})，点击切换到开发环境 (172.16.57.29:3306)`
    : `当前: 开发环境 (${hostHint})，点击切换到测试环境 (10.60.120.33:3336)`

  return (
    <button
      onClick={toggle}
      disabled={switching}
      title={title}
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
        background: isTest ? '#dbeafe' : '#d1fae5',
        color: isTest ? '#1e3a8a' : '#065f46',
        transition: 'all .2s',
      }}
    >
      {switching ? (
        <RefreshCw size={14} style={{ animation: 'spin 1s linear infinite' }} />
      ) : (
        <Database size={14} />
      )}
      {label}
    </button>
  )
}
