import { useEffect, useState, useCallback } from 'react'
import {
  Settings, Plus, Trash2, Loader2, Save, ArrowRight, Info,
} from 'lucide-react'
import { listDataSources, updateRoleAliases } from '../api/dataSourcesApi'

// ── 样式 ─────────────────────────────────────────────────────────
const btn = (bg: string, color: string): React.CSSProperties => ({
  display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '6px 14px', borderRadius: 7, border: 'none',
  background: bg, color, fontSize: 13, fontWeight: 500,
  cursor: 'pointer', transition: 'opacity .15s',
})
const input: React.CSSProperties = {
  background: '#0d0e1a', border: '1px solid #2d284e',
  borderRadius: 7, padding: '7px 11px', color: '#e2e8f0', fontSize: 13,
  outline: 'none', boxSizing: 'border-box' as const,
}
const select: React.CSSProperties = {
  ...input,
  appearance: 'none' as const,
  paddingRight: 28,
  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E")`,
  backgroundRepeat: 'no-repeat',
  backgroundPosition: 'right 8px center',
}

// ── 主组件 ───────────────────────────────────────────────────────
export default function RoleAliasManager() {
  const [sourceIds, setSourceIds] = useState<string[]>([])
  const [aliases, setAliases] = useState<Record<string, string>>({})
  const [pending, setPending] = useState<Record<string, string>>({})
  const [newRole, setNewRole] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')
  const [saved, setSaved] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setErr('')
    try {
      const res = await listDataSources()
      setSourceIds(res.sources.map(s => s.source_id))
      const ra = res.role_aliases ?? {}
      setAliases(ra)
      setPending(ra)
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const dirty = JSON.stringify(pending) !== JSON.stringify(aliases)

  const handleSave = async () => {
    setSaving(true)
    setErr('')
    try {
      const res = await updateRoleAliases(pending)
      setAliases(res.role_aliases)
      setPending(res.role_aliases)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleAddRole = () => {
    const role = newRole.trim().toLowerCase().replace(/\s/g, '_')
    if (!role || role in pending) return
    setPending(p => ({ ...p, [role]: sourceIds[0] ?? '' }))
    setNewRole('')
  }

  const handleRemoveRole = (role: string) => {
    setPending(p => {
      const next = { ...p }
      delete next[role]
      return next
    })
  }

  const handleSetTarget = (role: string, target: string) => {
    setPending(p => ({ ...p, [role]: target }))
  }

  return (
    <div style={{ padding: '28px 32px', maxWidth: 760 }}>
      {/* Concept explanation */}
      <div style={{
        background: 'rgba(99,102,241,.08)', border: '1px solid rgba(99,102,241,.2)',
        borderRadius: 10, padding: '14px 18px', marginBottom: 28,
        display: 'flex', gap: 12, alignItems: 'flex-start',
      }}>
        <Info size={16} color="#818cf8" style={{ flexShrink: 0, marginTop: 1 }} />
        <div style={{ fontSize: 13, color: '#a5b4fc', lineHeight: 1.7 }}>
          <strong style={{ color: '#c7d2fe' }}>角色映射</strong>
          {' '}让 Ontology Mapping 中的 <code style={{ background: 'rgba(99,102,241,.2)', padding: '1px 5px', borderRadius: 4 }}>source_id</code> 成为"逻辑角色名"，而非绑死某个数据库实例。
          <br />
          例如，将角色 <code style={{ background: 'rgba(99,102,241,.2)', padding: '1px 5px', borderRadius: 4 }}>pms</code> 指向 <strong>pms_prod</strong>（生产）或 <strong>pms_test</strong>（测试），
          切换环境时只需改映射关系，Mapping 文件不需要任何修改。
        </div>
      </div>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Settings size={16} color="#6366f1" />
          <span style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9' }}>当前角色映射</span>
          {dirty && (
            <span style={{ fontSize: 11, padding: '2px 7px', borderRadius: 4, background: 'rgba(251,191,36,.15)', color: '#fbbf24' }}>
              未保存
            </span>
          )}
        </div>
        <button
          style={{
            ...btn(dirty ? '#4f46e5' : '#1e1b4b', dirty ? '#fff' : '#6b7280'),
            opacity: saving ? 0.7 : 1,
          }}
          onClick={handleSave}
          disabled={!dirty || saving}
        >
          {saving ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> :
           saved ? '✓ 已保存' : <><Save size={14} /> 保存</>}
        </button>
      </div>

      {/* Error */}
      {err && (
        <div style={{ background: 'rgba(239,68,68,.1)', border: '1px solid rgba(239,68,68,.3)', borderRadius: 8, padding: '10px 16px', color: '#f87171', fontSize: 13, marginBottom: 16 }}>
          {err}
        </div>
      )}

      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#6b7280', padding: 32 }}>
          <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> 加载中...
        </div>
      ) : (
        <>
          {/* Alias rows */}
          {Object.keys(pending).length === 0 ? (
            <div style={{ textAlign: 'center', padding: '32px 0', color: '#4b5563', fontSize: 13 }}>
              暂无角色映射。Mapping 中有明确 source_id 的本体对象将直接使用同名数据源。
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 20 }}>
              {/* Column headers */}
              <div style={{ display: 'grid', gridTemplateColumns: '200px 32px 1fr 36px', gap: 8, padding: '0 4px', marginBottom: 2 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: '#8892a4', textTransform: 'uppercase', letterSpacing: 0.5 }}>逻辑角色名（Mapping 中使用）</span>
                <span />
                <span style={{ fontSize: 11, fontWeight: 600, color: '#8892a4', textTransform: 'uppercase', letterSpacing: 0.5 }}>指向的实际数据源</span>
                <span />
              </div>

              {Object.entries(pending).map(([role, target]) => (
                <div key={role} style={{
                  display: 'grid', gridTemplateColumns: '200px 32px 1fr 36px',
                  gap: 8, alignItems: 'center',
                  background: '#12142a', border: '1px solid #1e1b4b',
                  borderRadius: 8, padding: '10px 12px',
                }}>
                  {/* Role name */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <code style={{
                      fontSize: 13, fontWeight: 600, color: '#a5b4fc',
                      background: 'rgba(99,102,241,.12)', padding: '3px 8px', borderRadius: 5,
                    }}>
                      {role}
                    </code>
                  </div>

                  {/* Arrow */}
                  <ArrowRight size={14} color="#4b5563" style={{ justifySelf: 'center' }} />

                  {/* Target selector */}
                  <div style={{ position: 'relative' }}>
                    <select
                      style={{ ...select, width: '100%' }}
                      value={target}
                      onChange={e => handleSetTarget(role, e.target.value)}
                    >
                      <option value="">— 未分配 —</option>
                      {sourceIds.map(sid => (
                        <option key={sid} value={sid}>{sid}</option>
                      ))}
                    </select>
                  </div>

                  {/* Delete */}
                  <button
                    onClick={() => handleRemoveRole(role)}
                    style={{ ...btn('transparent', '#6b7280'), padding: '4px', justifySelf: 'center' }}
                    title="删除此角色"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Add new role */}
          <div style={{
            display: 'flex', gap: 8, alignItems: 'center',
            background: '#12142a', border: '1px dashed #2d284e',
            borderRadius: 8, padding: '12px 14px',
          }}>
            <Plus size={14} color="#6366f1" />
            <input
              style={{ ...input, flex: 1, maxWidth: 220 }}
              placeholder="新角色名，如 pms / mes / eap"
              value={newRole}
              onChange={e => setNewRole(e.target.value.replace(/\s/g, '_').toLowerCase())}
              onKeyDown={e => e.key === 'Enter' && handleAddRole()}
            />
            <button
              style={btn('#1e1b4b', '#a5b4fc')}
              onClick={handleAddRole}
              disabled={!newRole.trim()}
            >
              添加角色
            </button>
          </div>

          {/* Quick reference */}
          {sourceIds.length > 0 && (
            <div style={{ marginTop: 28 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 10 }}>
                已配置的数据源（可供角色指向）
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {sourceIds.map(sid => (
                  <span key={sid} style={{
                    fontSize: 12, padding: '4px 10px', borderRadius: 6,
                    background: '#12142a', border: '1px solid #1e1b4b',
                    color: '#8892a4', fontFamily: 'monospace',
                  }}>
                    {sid}
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
