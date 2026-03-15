/**
 * SynonymManager.tsx — 同义词管理 React 组件
 * 
 * 用于 Bolt.new 前端集成。
 * 
 * 依赖: lucide-react (已在项目中使用)
 * 
 * 使用方式:
 *   import SynonymManager from './SynonymManager';
 *   <SynonymManager />
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Plus, Search, RefreshCw, Check, X, EyeOff,
  ChevronDown, History, AlertCircle, Database, Tag
} from 'lucide-react';
import { synonymApi } from '../services/synonymApi';

// 保存/删除同义词后，通知后端刷新管道内存字典（无需重启服务）
const triggerPipelineReload = async () => {
  try {
    const apiRoot = (import.meta as any)?.env?.VITE_API_BASE_URL
      ? (import.meta as any).env.VITE_API_BASE_URL.replace(/\/api\/query.*$/, '')
      : 'http://localhost:8000';
    await fetch(`${apiRoot}/api/v1/ontology/synonyms/reload`, { method: 'POST' });
  } catch {
    // 静默失败，不影响 UI 操作
  }
};

// ─── Types ────────────────────────────────────

interface Synonym {
  id: number | null;
  target_uri: string;
  target_label_cn: string;
  target_type?: string;
  synonym: string;
  source: string;
  is_active: boolean;
  created_at: string | null;
  created_by: string;
}

interface UnmatchedTerm {
  id: number;
  term: string;
  original_query: string;
  frequency: number;
  suggested_table: string | null;
  status: string;
  created_at: string | null;
}

interface Stats {
  synonyms: { total: number; active: number; tables: number; manual: number; auto: number; builtin: number };
  unmatched: { total: number; pending: number; approved: number; rejected: number };
}

type Tab = 'synonyms' | 'unmatched' | 'audit';

// ─── Component ────────────────────────────────

export default function SynonymManager() {
  const [tab, setTab] = useState<Tab>('synonyms');
  const [stats, setStats] = useState<Stats | null>(null);
  const [synonyms, setSynonyms] = useState<Synonym[]>([]);
  const [unmatched, setUnmatched] = useState<UnmatchedTerm[]>([]);
  const [auditLog, setAuditLog] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterTable, setFilterTable] = useState('');
  const [filterType, setFilterType] = useState('');

  // Add modal state
  const [showAddModal, setShowAddModal] = useState(false);
  const [addTable, setAddTable] = useState('');
  const [addSynonyms, setAddSynonyms] = useState('');

  // Approve modal state
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [approveItem, setApproveItem] = useState<UnmatchedTerm | null>(null);
  const [approveTable, setApproveTable] = useState('');

  // ─── Derived ──────────────────────────────
  const tableNames = useMemo(() => {
    const set = new Set(synonyms.map(s => s.target_uri));
    return Array.from(set).sort();
  }, [synonyms]);

  const classLabel = (uri: string) => {
    const found = synonyms.find(s => s.target_uri === uri);
    return found?.target_label_cn ? `${found.target_label_cn} (${uri})` : uri;
  };

  const filteredSynonyms = useMemo(() => {
    return synonyms.filter(s => {
      if (filterTable && s.target_uri !== filterTable) return false;
      if (filterType && (s.target_type || 'class') !== filterType) return false;
      if (searchTerm && !s.synonym.toLowerCase().includes(searchTerm.toLowerCase())
        && !s.target_uri.toLowerCase().includes(searchTerm.toLowerCase())
        && !(s.target_label_cn || '').toLowerCase().includes(searchTerm.toLowerCase())) return false;
      return true;
    });
  }, [synonyms, filterTable, filterType, searchTerm]);

  // ─── Data loading ─────────────────────────
  const loadStats = useCallback(async () => {
    const res = await synonymApi.getStats();
    if (res.success) setStats(res.data);
  }, []);

  const loadSynonyms = useCallback(async () => {
    setLoading(true);
    const res = await synonymApi.getSynonyms({ is_active: 'true' });
    setSynonyms(res.data || []);
    setLoading(false);
  }, []);

  const loadUnmatched = useCallback(async () => {
    setLoading(true);
    const res = await synonymApi.getUnmatched({ status: 'pending', limit: '100' });
    setUnmatched(res.data || []);
    setLoading(false);
  }, []);

  const loadAudit = useCallback(async () => {
    setLoading(true);
    const res = await synonymApi.getAuditLog(100);
    setAuditLog(res.data || []);
    setLoading(false);
  }, []);

  useEffect(() => { loadStats(); loadSynonyms(); }, []);
  useEffect(() => {
    if (tab === 'unmatched') loadUnmatched();
    if (tab === 'audit') loadAudit();
  }, [tab]);

  // ─── Actions ──────────────────────────────
  const handleAdd = async () => {
    if (!addTable || !addSynonyms.trim()) return;
    const lines = addSynonyms.split('\n').map(l => l.trim()).filter(Boolean);
    if (lines.length === 1) {
      await synonymApi.addSynonym(addTable, lines[0]);
    } else {
      await synonymApi.addSynonymsBatch(addTable, lines);
    }
    setShowAddModal(false);
    setAddSynonyms('');
    loadSynonyms();
    loadStats();
    triggerPipelineReload(); // 刷新管道内存字典
  };

  const handleToggle = async (id: number, active: boolean) => {
    await synonymApi.updateSynonym(id, { is_active: active });
    loadSynonyms();
    loadStats();
    triggerPipelineReload(); // 刷新管道内存字典
  };

  const handleDelete = async (id: number) => {
    if (!confirm('确定删除?')) return;
    await synonymApi.deleteSynonym(id);
    loadSynonyms();
    loadStats();
    triggerPipelineReload(); // 刷新管道内存字典
  };

  const handleApprove = async () => {
    if (!approveItem || !approveTable) return;
    await synonymApi.approveUnmatched(approveItem.id, approveTable);
    setShowApproveModal(false);
    loadUnmatched();
    loadSynonyms();
    loadStats();
    triggerPipelineReload(); // 刷新管道内存字典
  };

  const handleReject = async (id: number) => {
    await synonymApi.rejectUnmatched(id);
    loadUnmatched();
    loadStats();
  };

  const handleIgnore = async (id: number) => {
    await synonymApi.ignoreUnmatched(id);
    loadUnmatched();
    loadStats();
  };

  // ─── Styles ───────────────────────────────
  const styles = {
    container: { maxWidth: '100%', width: '100%', margin: '0 auto', padding: 24, fontFamily: '-apple-system, sans-serif', boxSizing: 'border-box' as const },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 },
    title: { fontSize: 22, fontWeight: 700 as const, color: '#111' },
    statBar: { display: 'flex', gap: 16, fontSize: 13, color: '#6b7280' },
    tabs: { display: 'flex', gap: 0, borderBottom: '2px solid #e5e7eb', marginBottom: 24 },
    tab: (active: boolean) => ({
      padding: '10px 18px', cursor: 'pointer', fontWeight: 500 as const, fontSize: 14,
      color: active ? '#4f46e5' : '#6b7280', borderBottom: `2px solid ${active ? '#4f46e5' : 'transparent'}`,
      marginBottom: -2, position: 'relative' as const,
    }),
    badge: { background: '#dc2626', color: 'white', fontSize: 11, borderRadius: '50%', width: 18, height: 18, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginLeft: 6 },
    card: { background: 'white', borderRadius: 8, border: '1px solid #e5e7eb', boxShadow: '0 1px 3px rgba(0,0,0,.1)', marginBottom: 16 },
    cardHeader: { padding: '14px 20px', borderBottom: '1px solid #f3f4f6', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
    btn: (color: string) => ({
      display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', border: 'none', borderRadius: 6,
      fontSize: 13, fontWeight: 500 as const, cursor: 'pointer', color: 'white', background: color,
    }),
    btnSm: (color: string) => ({
      padding: '3px 8px', border: 'none', borderRadius: 4, fontSize: 12, cursor: 'pointer',
      color: 'white', background: color,
    }),
    tag: (bg: string, color: string) => ({
      display: 'inline-block', padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 500 as const,
      background: bg, color,
    }),
    table: { width: '100%', borderCollapse: 'collapse' as const, fontSize: 13 },
    th: { background: '#f9fafb', padding: '10px 14px', textAlign: 'left' as const, fontWeight: 600 as const, color: '#6b7280', borderBottom: '1px solid #e5e7eb' },
    td: { padding: '10px 14px', borderBottom: '1px solid #f3f4f6' },
    overlay: { position: 'fixed' as const, inset: 0, background: 'rgba(0,0,0,.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200 },
    modal: { background: 'white', borderRadius: 12, width: 460, maxWidth: '90vw', boxShadow: '0 20px 60px rgba(0,0,0,.15)' },
    input: { width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 14, outline: 'none' },
  };

  const typeTag = (type?: string) => {
    const map: Record<string, [string, string, string]> = {
      class:         ['#dbeafe', '#1d4ed8', '实体类'],
      relation:      ['#f3e8ff', '#7c3aed', '关系'],
      data_property: ['#ccfbf1', '#0f766e', '数据属性'],
    };
    const [bg, c, label] = map[type || 'class'] || ['#f3f4f6', '#6b7280', type || '?'];
    return <span style={styles.tag(bg, c)}>{label}</span>;
  };

  const sourceTag = (source: string) => {
    const map: Record<string, [string, string]> = { builtin: ['#dbeafe', '#1d4ed8'], manual: ['#fae8ff', '#a21caf'], auto: ['#d1fae5', '#065f46'] };
    const [bg, c] = map[source] || ['#f3f4f6', '#6b7280'];
    return <span style={styles.tag(bg, c)}>{source === 'builtin' ? '内置' : source === 'manual' ? '手动' : '自动'}</span>;
  };

  // ─── Render ───────────────────────────────
  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h1 style={styles.title}>📋 <span style={{ color: '#4f46e5' }}>NL2SQL</span> 同义词管理</h1>
        <div style={styles.statBar}>
          {stats && <>
            <span>同义词 <b>{stats.synonyms.active}</b></span>
            <span>本体类 <b>{stats.synonyms.tables}</b></span>
            <span style={{ color: '#d97706' }}>待审批 <b>{stats.unmatched.pending}</b></span>
          </>}
        </div>
      </div>

      {/* Tabs */}
      <div style={styles.tabs}>
        {(['synonyms', 'unmatched', 'audit'] as Tab[]).map(t => (
          <div key={t} style={styles.tab(tab === t)} onClick={() => setTab(t)}>
            {t === 'synonyms' ? '同义词管理' : t === 'unmatched' ? '未匹配词审批' : '操作日志'}
            {t === 'unmatched' && stats && stats.unmatched.pending > 0 && (
              <span style={styles.badge}>{stats.unmatched.pending}</span>
            )}
          </div>
        ))}
      </div>

      {/* Panel: Synonyms */}
      {tab === 'synonyms' && (
        <>
          <div style={styles.card}>
            <div style={styles.cardHeader}>
              <b>同义词列表 ({filteredSynonyms.length})</b>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <select value={filterType} onChange={e => setFilterType(e.target.value)} style={{ ...styles.input, width: 120 } as any}>
                  <option value="">全部类型</option>
                  <option value="class">实体类</option>
                  <option value="relation">关系</option>
                  <option value="data_property">数据属性</option>
                </select>
                <select value={filterTable} onChange={e => setFilterTable(e.target.value)} style={styles.input as any}>
                  <option value="">全部 URI</option>
                  {tableNames.map(t => <option key={t} value={t}>{classLabel(t)}</option>)}
                </select>
                <input placeholder="搜索..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
                  style={{ ...styles.input, width: 160 }} />
                <button style={styles.btn('#4f46e5')} onClick={() => { setAddTable(tableNames[0] || ''); setShowAddModal(true); }}>
                  <Plus size={14} /> 添加
                </button>
              </div>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={styles.table}>
                <thead>
                  <tr>{['类型', '本体 URI', '同义词', '来源', '状态', '操作'].map(h => <th key={h} style={styles.th}>{h}</th>)}</tr>
                </thead>
                <tbody>
                  {filteredSynonyms.map((s, i) => (
                    <tr key={`${s.target_uri}-${s.synonym}-${i}`}>
                      <td style={styles.td}>{typeTag(s.target_type)}</td>
                      <td style={styles.td}>
                        <span style={{ fontWeight: 600, color: '#374151', fontSize: 13 }}>{s.target_label_cn || s.target_uri}</span>
                        <br/>
                        <code style={{ fontSize: 11, background: '#f3f4f6', padding: '1px 5px', borderRadius: 4, color: '#6b7280' }}>{s.target_uri}</code>
                      </td>
                      <td style={{ ...styles.td, fontWeight: 600 }}>{s.synonym}</td>
                      <td style={styles.td}>{sourceTag(s.source)}</td>
                      <td style={styles.td}>
                        <span style={styles.tag(s.is_active ? '#ecfdf5' : '#f3f4f6', s.is_active ? '#059669' : '#9ca3af')}>
                          {s.is_active ? '活跃' : '停用'}
                        </span>
                      </td>
                      <td style={styles.td}>
                        {s.id ? (
                          <div style={{ display: 'flex', gap: 4 }}>
                            <button style={styles.btnSm(s.is_active ? '#6b7280' : '#059669')} onClick={() => handleToggle(s.id!, !s.is_active)}>
                              {s.is_active ? '停用' : '启用'}
                            </button>
                            <button style={styles.btnSm('#dc2626')} onClick={() => handleDelete(s.id!)}>删除</button>
                          </div>
                        ) : <span style={{ fontSize: 12, color: '#9ca3af' }}>只读</span>}
                      </td>
                    </tr>
                  ))}
                  {filteredSynonyms.length === 0 && (
                    <tr><td colSpan={6} style={{ padding: 32, textAlign: 'center', color: '#9ca3af' }}>暂无数据</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Panel: Unmatched */}
      {tab === 'unmatched' && (
        <div style={styles.card}>
          <div style={styles.cardHeader}>
            <b>未匹配查询词 ({unmatched.length})</b>
            <button style={styles.btn('#6b7280')} onClick={loadUnmatched}><RefreshCw size={14} /> 刷新</button>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={styles.table}>
              <thead>
                <tr>{['查询词', '频次', '原始查询', '推荐表', '操作'].map(h => <th key={h} style={styles.th}>{h}</th>)}</tr>
              </thead>
              <tbody>
                {unmatched.map(t => (
                  <tr key={t.id}>
                    <td style={{ ...styles.td, fontWeight: 600 }}>{t.term}</td>
                    <td style={styles.td}>{t.frequency}次</td>
                    <td style={{ ...styles.td, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.original_query || '-'}</td>
                    <td style={styles.td}>{t.suggested_table || '-'}</td>
                    <td style={styles.td}>
                      <div style={{ display: 'flex', gap: 4 }}>
                        <button style={styles.btnSm('#059669')} onClick={() => { setApproveItem(t); setApproveTable(t.suggested_table || tableNames[0] || ''); setShowApproveModal(true); }}>
                          <Check size={12} /> 审批
                        </button>
                        <button style={styles.btnSm('#6b7280')} onClick={() => handleReject(t.id)}><X size={12} /></button>
                        <button style={styles.btnSm('#9ca3af')} onClick={() => handleIgnore(t.id)}><EyeOff size={12} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
                {unmatched.length === 0 && (
                  <tr><td colSpan={5} style={{ padding: 32, textAlign: 'center', color: '#9ca3af' }}>🎉 暂无待处理的未匹配词</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Panel: Audit */}
      {tab === 'audit' && (
        <div style={styles.card}>
          <div style={styles.cardHeader}>
            <b>操作日志 ({auditLog.length})</b>
            <button style={styles.btn('#6b7280')} onClick={loadAudit}><RefreshCw size={14} /> 刷新</button>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={styles.table}>
              <thead>
                <tr>{['时间', '操作', '表名', '同义词', '操作人'].map(h => <th key={h} style={styles.th}>{h}</th>)}</tr>
              </thead>
              <tbody>
                {auditLog.map(l => (
                  <tr key={l.id}>
                    <td style={styles.td}>{l.created_at ? new Date(l.created_at).toLocaleString('zh-CN') : '-'}</td>
                    <td style={styles.td}><span style={styles.tag('#dbeafe', '#1d4ed8')}>{l.action}</span></td>
                    <td style={styles.td}><code>{l.target_uri || (l as any).table_name}</code></td>
                    <td style={{ ...styles.td, fontWeight: 600 }}>{l.synonym}</td>
                    <td style={styles.td}>{l.performed_by}</td>
                  </tr>
                ))}
                {auditLog.length === 0 && (
                  <tr><td colSpan={5} style={{ padding: 32, textAlign: 'center', color: '#9ca3af' }}>暂无操作日志</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Add Modal */}
      {showAddModal && (
        <div style={styles.overlay} onClick={() => setShowAddModal(false)}>
          <div style={styles.modal} onClick={e => e.stopPropagation()}>
            <div style={{ padding: '20px 24px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: 17, fontWeight: 600 }}>添加同义词</h3>
              <button onClick={() => setShowAddModal(false)} style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: '#9ca3af' }}>&times;</button>
            </div>
            <div style={{ padding: '16px 24px' }}>
              <div style={{ marginBottom: 14 }}>
                <label style={{ fontSize: 13, fontWeight: 500, color: '#374151', display: 'block', marginBottom: 4 }}>本体类 (URI)</label>
                <select value={addTable} onChange={e => setAddTable(e.target.value)} style={styles.input as any}>
                  {tableNames.map(t => <option key={t} value={t}>{classLabel(t)}</option>)}
                </select>
              </div>
              <div style={{ marginBottom: 14 }}>
                <label style={{ fontSize: 13, fontWeight: 500, color: '#374151', display: 'block', marginBottom: 4 }}>同义词（每行一个）</label>
                <textarea value={addSynonyms} onChange={e => setAddSynonyms(e.target.value)} rows={4}
                  placeholder="输入同义词，每行一条" style={{ ...styles.input, resize: 'vertical' } as any} />
              </div>
            </div>
            <div style={{ padding: '14px 24px', borderTop: '1px solid #f3f4f6', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button style={styles.btn('#6b7280')} onClick={() => setShowAddModal(false)}>取消</button>
              <button style={styles.btn('#4f46e5')} onClick={handleAdd}>确认添加</button>
            </div>
          </div>
        </div>
      )}

      {/* Approve Modal */}
      {showApproveModal && approveItem && (
        <div style={styles.overlay} onClick={() => setShowApproveModal(false)}>
          <div style={styles.modal} onClick={e => e.stopPropagation()}>
            <div style={{ padding: '20px 24px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: 17, fontWeight: 600 }}>审批: "{approveItem.term}"</h3>
              <button onClick={() => setShowApproveModal(false)} style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: '#9ca3af' }}>&times;</button>
            </div>
            <div style={{ padding: '16px 24px' }}>
              <div style={{ marginBottom: 14 }}>
                <label style={{ fontSize: 13, fontWeight: 500, color: '#374151', display: 'block', marginBottom: 4 }}>映射到本体类</label>
                <select value={approveTable} onChange={e => setApproveTable(e.target.value)} style={styles.input as any}>
                  {tableNames.map(t => <option key={t} value={t}>{classLabel(t)}</option>)}
                </select>
              </div>
              <p style={{ fontSize: 13, color: '#6b7280' }}>原始查询: {approveItem.original_query || '无'}</p>
              <p style={{ fontSize: 13, color: '#6b7280' }}>出现频次: {approveItem.frequency}次</p>
            </div>
            <div style={{ padding: '14px 24px', borderTop: '1px solid #f3f4f6', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button style={styles.btn('#6b7280')} onClick={() => setShowApproveModal(false)}>取消</button>
              <button style={styles.btn('#059669')} onClick={handleApprove}>✓ 审批通过</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
