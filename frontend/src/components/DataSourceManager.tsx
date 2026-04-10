import { useEffect, useState, useCallback } from 'react'
import {
  Database, Plus, Pencil, Trash2, CheckCircle, XCircle,
  Loader2, Star, StarOff, Wifi, WifiOff, ChevronRight,
} from 'lucide-react'
import {
  listDataSources,
  createDataSource,
  updateDataSource,
  deleteDataSource,
  setDefaultDataSource,
  testDataSourceConnection,
  type DataSource,
  type DataSourcePayload,
} from '../api/dataSourcesApi'

// ── 样式常量 ──────────────────────────────────────────────────────
const card: React.CSSProperties = {
  background: '#12142a',
  border: '1px solid #1e1b4b',
  borderRadius: 10,
  padding: '20px 24px',
  marginBottom: 12,
  display: 'flex',
  alignItems: 'center',
  gap: 16,
}
const btn = (bg: string, color: string): React.CSSProperties => ({
  display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '6px 14px', borderRadius: 7, border: 'none',
  background: bg, color, fontSize: 13, fontWeight: 500,
  cursor: 'pointer', transition: 'opacity .15s',
})
const input: React.CSSProperties = {
  width: '100%', background: '#0d0e1a', border: '1px solid #2d284e',
  borderRadius: 7, padding: '8px 12px', color: '#e2e8f0', fontSize: 13,
  outline: 'none', boxSizing: 'border-box',
}
const label: React.CSSProperties = {
  display: 'block', fontSize: 12, fontWeight: 600,
  color: '#8892a4', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5,
}
const row: React.CSSProperties = { display: 'flex', gap: 12 }
const field = (flex = 1): React.CSSProperties => ({ flex, minWidth: 0 })

type TestStatus = 'idle' | 'testing' | 'ok' | 'error'

type FormData = {
  source_id: string
  display_name: string
  host: string
  port: string
  db: string
  user: string
  password: string
  description: string
}

const EMPTY_FORM: FormData = {
  source_id: '', display_name: '', host: '', port: '3306',
  db: '', user: '', password: '', description: '',
}

// ── 编辑抽屉 ─────────────────────────────────────────────────────
function DrawerForm({
  initial,
  isNew,
  onSave,
  onCancel,
}: {
  initial: FormData
  isNew: boolean
  onSave: (data: FormData) => Promise<void>
  onCancel: () => void
}) {
  const [form, setForm] = useState<FormData>(initial)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [testStatus, setTestStatus] = useState<TestStatus>('idle')
  const [testMsg, setTestMsg] = useState('')

  const set = (key: keyof FormData, value: string) =>
    setForm(f => ({ ...f, [key]: value }))

  const handleSave = async () => {
    if (!form.host || !form.db || !form.user) {
      setError('Host、数据库名、用户名为必填项')
      return
    }
    if (isNew && !form.source_id) {
      setError('数据源 ID 为必填项')
      return
    }
    setSaving(true)
    setError('')
    try {
      await onSave(form)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    if (!form.host || !form.db || !form.user) {
      setTestMsg('请先填写 Host、数据库名和用户名')
      setTestStatus('error')
      return
    }
    // 若是新数据源，先临时保存再测试
    if (isNew) {
      setTestMsg('请先保存后再测试连接')
      setTestStatus('error')
      return
    }
    setTestStatus('testing')
    setTestMsg('')
    try {
      const res = await testDataSourceConnection(form.source_id)
      setTestStatus(res.success ? 'ok' : 'error')
      setTestMsg(res.message)
    } catch (e: any) {
      setTestStatus('error')
      setTestMsg(e.message)
    }
  }

  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, bottom: 0, width: 480,
      background: '#0d0e1a', borderLeft: '1px solid #1e1b4b',
      boxShadow: '-8px 0 32px rgba(0,0,0,.6)',
      zIndex: 1000, display: 'flex', flexDirection: 'column',
    }}>
      {/* Header */}
      <div style={{ padding: '20px 24px', borderBottom: '1px solid #1e1b4b', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Database size={18} color="#6366f1" />
        <span style={{ fontSize: 16, fontWeight: 700, color: '#f1f5f9' }}>
          {isNew ? '新增数据源' : `编辑: ${form.display_name || form.source_id}`}
        </span>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {isNew && (
          <div>
            <span style={label}>数据源 ID <span style={{ color: '#f87171' }}>*</span></span>
            <input style={input} placeholder="唯一标识，如 equip_mgmt" value={form.source_id}
              onChange={e => set('source_id', e.target.value.replace(/\s/g, '_').toLowerCase())} />
            <div style={{ fontSize: 11, color: '#6b7280', marginTop: 4 }}>仅限小写字母、数字和下划线</div>
          </div>
        )}
        <div>
          <span style={label}>显示名称</span>
          <input style={input} placeholder="如 MES 生产数据库" value={form.display_name}
            onChange={e => set('display_name', e.target.value)} />
        </div>
        <div style={row}>
          <div style={field(3)}>
            <span style={label}>Host <span style={{ color: '#f87171' }}>*</span></span>
            <input style={input} placeholder="10.60.120.33" value={form.host}
              onChange={e => set('host', e.target.value)} />
          </div>
          <div style={field(1)}>
            <span style={label}>Port</span>
            <input style={input} placeholder="3306" type="number" value={form.port}
              onChange={e => set('port', e.target.value)} />
          </div>
        </div>
        <div>
          <span style={label}>数据库名 <span style={{ color: '#f87171' }}>*</span></span>
          <input style={input} placeholder="cc_semi_mvp" value={form.db}
            onChange={e => set('db', e.target.value)} />
        </div>
        <div style={row}>
          <div style={field()}>
            <span style={label}>用户名 <span style={{ color: '#f87171' }}>*</span></span>
            <input style={input} placeholder="root" value={form.user}
              onChange={e => set('user', e.target.value)} />
          </div>
          <div style={field()}>
            <span style={label}>密码 {!isNew && <span style={{ fontWeight: 400, textTransform: 'none', color: '#6b7280' }}>(留空保留原密码)</span>}</span>
            <input style={input} type="password" placeholder={isNew ? '••••••' : '留空不修改'} value={form.password}
              onChange={e => set('password', e.target.value)} />
          </div>
        </div>
        <div>
          <span style={label}>备注说明</span>
          <input style={input} placeholder="可选" value={form.description}
            onChange={e => set('description', e.target.value)} />
        </div>

        {/* Test button */}
        {!isNew && (
          <div>
            <button style={btn(
              testStatus === 'ok' ? 'rgba(16,185,129,.15)' :
              testStatus === 'error' ? 'rgba(239,68,68,.15)' : '#1e1b4b',
              testStatus === 'ok' ? '#34d399' :
              testStatus === 'error' ? '#f87171' : '#a5b4fc',
            )} onClick={handleTest} disabled={testStatus === 'testing'}>
              {testStatus === 'testing' ? <Loader2 size={14} className="spin" /> :
               testStatus === 'ok' ? <CheckCircle size={14} /> :
               testStatus === 'error' ? <XCircle size={14} /> :
               <Wifi size={14} />}
              测试连接
            </button>
            {testMsg && (
              <div style={{ marginTop: 6, fontSize: 12, color: testStatus === 'ok' ? '#34d399' : '#f87171' }}>
                {testMsg}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div style={{ padding: '16px 24px', borderTop: '1px solid #1e1b4b', display: 'flex', gap: 10, alignItems: 'center' }}>
        {error && <span style={{ flex: 1, fontSize: 12, color: '#f87171' }}>{error}</span>}
        {!error && <div style={{ flex: 1 }} />}
        <button style={btn('#1e1b4b', '#9da5b8')} onClick={onCancel}>取消</button>
        <button style={btn('#4f46e5', '#fff')} onClick={handleSave} disabled={saving}>
          {saving ? <Loader2 size={14} /> : null}
          保存
        </button>
      </div>
    </div>
  )
}

// ── 主组件 ───────────────────────────────────────────────────────
export default function DataSourceManager() {
  const [sources, setSources] = useState<DataSource[]>([])
  const [defaultId, setDefaultId] = useState('')
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<DataSource | null>(null) // null = new
  const [testStatuses, setTestStatuses] = useState<Record<string, TestStatus>>({})
  const [testMsgs, setTestMsgs] = useState<Record<string, string>>({})
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({})

  const load = useCallback(async () => {
    setLoading(true)
    setErr('')
    try {
      const res = await listDataSources()
      setSources(res.sources)
      setDefaultId(res.default_source_id)
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const openNew = () => { setEditTarget(null); setDrawerOpen(true) }
  const openEdit = (s: DataSource) => { setEditTarget(s); setDrawerOpen(true) }
  const closeDrawer = () => setDrawerOpen(false)

  const handleSave = async (form: FormData) => {
    if (editTarget) {
      await updateDataSource(editTarget.source_id, {
        display_name: form.display_name,
        host: form.host,
        port: Number(form.port),
        db: form.db,
        user: form.user,
        password: form.password,
        description: form.description,
      })
    } else {
      const payload: DataSourcePayload = {
        display_name: form.display_name,
        host: form.host,
        port: Number(form.port),
        db: form.db,
        user: form.user,
        password: form.password,
        description: form.description,
        read_timeout: 45,
      }
      await createDataSource(form.source_id, payload)
    }
    setDrawerOpen(false)
    load()
  }

  const handleDelete = async (s: DataSource) => {
    if (s.is_default) return
    if (!confirm(`确认删除数据源「${s.display_name || s.source_id}」？`)) return
    setActionLoading(prev => ({ ...prev, [s.source_id]: true }))
    try {
      await deleteDataSource(s.source_id)
      load()
    } catch (e: any) {
      alert(e.message)
    } finally {
      setActionLoading(prev => ({ ...prev, [s.source_id]: false }))
    }
  }

  const handleSetDefault = async (s: DataSource) => {
    if (s.is_default) return
    setActionLoading(prev => ({ ...prev, [s.source_id]: true }))
    try {
      await setDefaultDataSource(s.source_id)
      load()
    } catch (e: any) {
      alert(e.message)
    } finally {
      setActionLoading(prev => ({ ...prev, [s.source_id]: false }))
    }
  }

  const handleTest = async (s: DataSource) => {
    setTestStatuses(prev => ({ ...prev, [s.source_id]: 'testing' }))
    setTestMsgs(prev => ({ ...prev, [s.source_id]: '' }))
    try {
      const res = await testDataSourceConnection(s.source_id)
      setTestStatuses(prev => ({ ...prev, [s.source_id]: res.success ? 'ok' : 'error' }))
      setTestMsgs(prev => ({ ...prev, [s.source_id]: res.message }))
    } catch (e: any) {
      setTestStatuses(prev => ({ ...prev, [s.source_id]: 'error' }))
      setTestMsgs(prev => ({ ...prev, [s.source_id]: e.message }))
    }
  }

  const formInitial = editTarget
    ? {
        source_id: editTarget.source_id,
        display_name: editTarget.display_name,
        host: editTarget.host,
        port: String(editTarget.port),
        db: editTarget.db,
        user: editTarget.user,
        password: '',
        description: editTarget.description,
      }
    : EMPTY_FORM

  return (
    <div style={{ padding: '28px 32px', maxWidth: 820 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div style={{ fontSize: 13, color: '#6b7280' }}>
          配置和管理多个 MySQL 数据库连接，系统将在查询时自动路由到对应数据源
        </div>
        <button style={btn('#4f46e5', '#fff')} onClick={openNew}>
          <Plus size={14} /> 新增数据源
        </button>
      </div>

      {/* Error */}
      {err && (
        <div style={{ background: 'rgba(239,68,68,.1)', border: '1px solid rgba(239,68,68,.3)', borderRadius: 8, padding: '10px 16px', color: '#f87171', fontSize: 13, marginBottom: 16 }}>
          {err}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#6b7280', padding: 32 }}>
          <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
          加载中...
        </div>
      )}

      {/* Source list */}
      {!loading && sources.map((s) => {
        const ts = testStatuses[s.source_id] ?? 'idle'
        const tm = testMsgs[s.source_id] ?? ''
        const busy = actionLoading[s.source_id] ?? false
        return (
          <div key={s.source_id} style={{
            ...card,
            borderColor: s.is_default ? 'rgba(99,102,241,.4)' : '#1e1b4b',
            boxShadow: s.is_default ? '0 0 0 1px rgba(99,102,241,.2)' : 'none',
          }}>
            {/* Left icon */}
            <div style={{
              width: 42, height: 42, borderRadius: 10, flexShrink: 0,
              background: s.is_default ? 'rgba(99,102,241,.15)' : 'rgba(255,255,255,.05)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Database size={18} color={s.is_default ? '#818cf8' : '#6b7280'} />
            </div>

            {/* Info */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 15, fontWeight: 600, color: '#f1f5f9' }}>
                  {s.display_name || s.source_id}
                </span>
                {s.is_default && (
                  <span style={{ fontSize: 11, padding: '2px 7px', borderRadius: 4, background: 'rgba(99,102,241,.2)', color: '#a5b4fc', fontWeight: 600 }}>
                    默认
                  </span>
                )}
                <span style={{ fontSize: 11, color: '#8892a4', fontFamily: 'monospace' }}>
                  {s.source_id}
                </span>
              </div>
              <div style={{ fontSize: 12, color: '#6b7280', display: 'flex', alignItems: 'center', gap: 4 }}>
                <ChevronRight size={11} />
                {s.host}:{s.port} / {s.db} &nbsp;·&nbsp; {s.user}
                {s.description && <span style={{ marginLeft: 8 }}>— {s.description}</span>}
              </div>
              {/* Test result */}
              {ts !== 'idle' && (
                <div style={{
                  marginTop: 4, fontSize: 12,
                  color: ts === 'ok' ? '#34d399' : ts === 'error' ? '#f87171' : '#6b7280',
                  display: 'flex', alignItems: 'center', gap: 4,
                }}>
                  {ts === 'testing' ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> :
                   ts === 'ok' ? <CheckCircle size={12} /> : <XCircle size={12} />}
                  {ts === 'testing' ? '连接测试中...' : tm}
                </div>
              )}
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
              <button
                onClick={() => handleTest(s)}
                disabled={ts === 'testing'}
                title="测试连接"
                style={{ ...btn('transparent', '#6b7280'), padding: '6px' }}
              >
                {ts === 'testing' ? <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} /> :
                 ts === 'ok' ? <Wifi size={15} color="#34d399" /> :
                 ts === 'error' ? <WifiOff size={15} color="#f87171" /> :
                 <Wifi size={15} />}
              </button>
              {!s.is_default && (
                <button
                  onClick={() => handleSetDefault(s)}
                  disabled={busy}
                  title="设为默认"
                  style={{ ...btn('transparent', '#6b7280'), padding: '6px' }}
                >
                  <StarOff size={15} />
                </button>
              )}
              {s.is_default && (
                <button disabled title="当前默认" style={{ ...btn('transparent', '#818cf8'), padding: '6px', cursor: 'default' }}>
                  <Star size={15} />
                </button>
              )}
              <button
                onClick={() => openEdit(s)}
                title="编辑"
                style={{ ...btn('transparent', '#6b7280'), padding: '6px' }}
              >
                <Pencil size={15} />
              </button>
              {!s.is_default && (
                <button
                  onClick={() => handleDelete(s)}
                  disabled={busy}
                  title="删除"
                  style={{ ...btn('transparent', '#6b7280'), padding: '6px' }}
                >
                  <Trash2 size={15} />
                </button>
              )}
            </div>
          </div>
        )
      })}

      {!loading && sources.length === 0 && !err && (
        <div style={{ textAlign: 'center', padding: '48px 0', color: '#8892a4', fontSize: 14 }}>
          暂无数据源，点击「新增数据源」开始添加
        </div>
      )}

      {/* Drawer */}
      {drawerOpen && (
        <>
          <div
            onClick={closeDrawer}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 999 }}
          />
          <DrawerForm
            key={editTarget?.source_id ?? '__new__'}
            initial={formInitial}
            isNew={!editTarget}
            onSave={handleSave}
            onCancel={closeDrawer}
          />
        </>
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
