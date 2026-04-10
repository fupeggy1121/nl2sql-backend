/**
 * SynonymManager.tsx — 同义词管理（重构版）
 *
 * 布局：左侧本体对象分组卡片 + 右侧同义词详情面板
 * 功能：场景分类导航、统一搜索（词/标签/URI）、chip 展示、inline 添加
 */
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Search, RefreshCw, Check, X, EyeOff } from 'lucide-react';
import { synonymApi } from '../services/synonymApi';

// ── 触发管道热重载 ────────────────────────────────────────────────
const triggerPipelineReload = async () => {
  try {
    const apiRoot = (import.meta as any)?.env?.VITE_API_BASE_URL
      ? (import.meta as any).env.VITE_API_BASE_URL.replace(/\/api\/query.*$/, '')
      : 'http://localhost:8000';
    await fetch(`${apiRoot}/api/v1/ontology/synonyms/reload`, { method: 'POST' });
  } catch { /* 静默 */ }
};

// ── Types ─────────────────────────────────────────────────────────
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

// ── 场景分类规则 ──────────────────────────────────────────────────
interface SceneTag { id: string; label: string; color: string; uriPatterns: string[] }

const SCENE_TAGS: SceneTag[] = [
  { id: 'all',       label: '全部',     color: '#6b7280', uriPatterns: [] },
  { id: 'equipment', label: '设备管理', color: '#2563eb', uriPatterns: ['equipment', 'maintenance', 'alarm', 'downtime', 'eqp'] },
  { id: 'process',   label: '工艺过程', color: '#7c3aed', uriPatterns: ['process', 'recipe', 'run', 'operation', 'step'] },
  { id: 'quality',   label: '质量检验', color: '#dc2626', uriPatterns: ['inspection', 'defect', 'quality', 'ng', 'fail'] },
  { id: 'material',  label: '物料追踪', color: '#d97706', uriPatterns: ['wafer', 'carrier', 'lot', 'material', 'product'] },
  { id: 'measure',   label: '量测参数', color: '#059669', uriPatterns: ['measurement', 'parameter', 'spec', 'measure', 'param'] },
];

function getSceneForUri(uri: string): string {
  const lower = uri.toLowerCase();
  for (const scene of SCENE_TAGS) {
    if (scene.id === 'all') continue;
    if (scene.uriPatterns.some(p => lower.includes(p))) return scene.id;
  }
  return 'all';
}

// ── 聚合结构 ──────────────────────────────────────────────────────
interface EntityGroup {
  uri: string;
  labelCn: string;
  type: string;
  scene: string;
  synonyms: Synonym[];
}

function buildGroups(synonyms: Synonym[]): EntityGroup[] {
  const map = new Map<string, EntityGroup>();
  for (const s of synonyms) {
    if (!map.has(s.target_uri)) {
      map.set(s.target_uri, {
        uri: s.target_uri,
        labelCn: s.target_label_cn || s.target_uri,
        type: s.target_type || 'class',
        scene: getSceneForUri(s.target_uri),
        synonyms: [],
      });
    }
    map.get(s.target_uri)!.synonyms.push(s);
  }
  return Array.from(map.values()).sort((a, b) => a.labelCn.localeCompare(b.labelCn, 'zh'));
}

// ── SceneBar ──────────────────────────────────────────────────────
function SceneBar({ active, counts, onChange }: {
  active: string;
  counts: Record<string, number>;
  onChange: (id: string) => void;
}) {
  return (
    <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' as const }}>
      {SCENE_TAGS.map(s => {
        const n = s.id === 'all' ? (counts['all'] ?? 0) : (counts[s.id] ?? 0);
        const isActive = active === s.id;
        return (
          <button key={s.id} onClick={() => onChange(s.id)} style={{
            padding: '3px 10px', borderRadius: 16,
            border: `1px solid ${isActive ? s.color : '#2d284e'}`,
            background: isActive ? s.color : '#12142a',
            color: isActive ? '#fff' : '#c4c9d6',
            fontSize: 11, fontWeight: isActive ? 600 : 400, cursor: 'pointer',
          }}>
            {s.label}{s.id !== 'all' && n > 0 ? ` (${n})` : s.id === 'all' ? ` (${n})` : ''}
          </button>
        );
      })}
    </div>
  );
}

// ── EntityCard ────────────────────────────────────────────────────
function EntityCard({ group, active, searchTerm, onClick }: {
  group: EntityGroup;
  active: boolean;
  searchTerm: string;
  onClick: () => void;
}) {
  const scene = SCENE_TAGS.find(s => s.id === group.scene) ?? SCENE_TAGS[0];
  const activeSynonyms = group.synonyms.filter(s => s.is_active);
  const previewWords = activeSynonyms.slice(0, 4).map(s => s.synonym);
  if (activeSynonyms.length > 4) previewWords.push(`+${activeSynonyms.length - 4}`);

  const hl = (text: string): React.ReactNode => {
    if (!searchTerm) return text;
    const idx = text.toLowerCase().indexOf(searchTerm.toLowerCase());
    if (idx < 0) return text;
    return <>{text.slice(0, idx)}<mark style={{ background: 'rgba(250,204,21,0.3)', color: '#fef08a', borderRadius: 2, padding: 0 }}>{text.slice(idx, idx + searchTerm.length)}</mark>{text.slice(idx + searchTerm.length)}</>;
  };

  return (
    <button onClick={onClick} style={{
      display: 'block', width: '100%', textAlign: 'left', padding: '11px 12px', borderRadius: 9,
      border: active ? `2px solid ${scene.color}` : '2px solid #2d284e',
      background: active ? `${scene.color}18` : '#12142a',
      cursor: 'pointer', marginBottom: 7, transition: 'all .12s',
      boxShadow: active ? `0 0 0 3px ${scene.color}20` : 'none',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
        <span style={{
          padding: '1px 7px', borderRadius: 10, fontSize: 10, fontWeight: 600,
          background: `${scene.color}18`, color: scene.color, border: `1px solid ${scene.color}30`,
          flexShrink: 0,
        }}>{scene.label}</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: '#f1f5f9', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
          {hl(group.labelCn)}
        </span>
        <span style={{ fontSize: 11, color: '#9ca3af', flexShrink: 0 }}>{activeSynonyms.length}</span>
      </div>
      <div style={{ fontSize: 10, color: '#9ca3af', marginBottom: 5, fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
        {group.uri}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 3 }}>
        {previewWords.map((w, i) => (
          <span key={i} style={{ padding: '1px 6px', borderRadius: 8, fontSize: 11, background: '#1a1c35', color: '#8892a4' }}>
            {searchTerm && !w.startsWith('+') ? hl(w) : w}
          </span>
        ))}
      </div>
    </button>
  );
}

// ── SynonymChip ───────────────────────────────────────────────────
function SynonymChip({ s, onToggle, onDelete }: {
  s: Synonym;
  onToggle: (id: number, active: boolean) => void;
  onDelete: (id: number) => void;
}) {
  const [hover, setHover] = useState(false);
  const isBuiltin = s.source === 'builtin';
  const canEdit = !!s.id && !isBuiltin;
  const tooltip = `来源：${s.source === 'builtin' ? '内置' : s.source === 'manual' ? '手动' : '自动'}${s.created_at ? ' | ' + new Date(s.created_at).toLocaleDateString('zh-CN') : ''}`;

  const borderColor = !s.is_active ? '#2d284e' : isBuiltin ? 'rgba(59,130,246,0.45)' : s.source === 'manual' ? 'rgba(139,92,246,0.45)' : 'rgba(16,185,129,0.4)';
  const bg = !s.is_active ? '#0d0e1a' : isBuiltin ? 'rgba(59,130,246,0.1)' : s.source === 'manual' ? 'rgba(139,92,246,0.1)' : 'rgba(16,185,129,0.1)';
  const color = !s.is_active ? '#4b5563' : isBuiltin ? '#93c5fd' : s.source === 'manual' ? '#c084fc' : '#34d399';

  return (
    <span title={tooltip} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)} style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      padding: '3px 9px', borderRadius: 14, fontSize: 12, fontWeight: 500,
      border: `1px solid ${borderColor}`, background: bg, color,
      textDecoration: !s.is_active ? 'line-through' : 'none',
      transition: 'all .1s', userSelect: 'none' as const,
    }}>
      {s.synonym}
      {hover && canEdit && (
        <span style={{ display: 'inline-flex', gap: 1, marginLeft: 2 }}>
          <button title={s.is_active ? '停用' : '启用'}
            onClick={e => { e.stopPropagation(); onToggle(s.id!, !s.is_active); }}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0 1px', lineHeight: 1, color: '#6b7280', fontSize: 11 }}>
            {s.is_active ? '⏸' : '▶'}
          </button>
          <button title="删除"
            onClick={e => { e.stopPropagation(); if (confirm(`删除"${s.synonym}"？`)) onDelete(s.id!); }}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0 1px', lineHeight: 1, color: '#dc2626', fontSize: 13, fontWeight: 700 }}>
            ×
          </button>
        </span>
      )}
    </span>
  );
}

// ── DetailPanel ───────────────────────────────────────────────────
function DetailPanel({ group, allUris, onRefresh }: {
  group: EntityGroup;
  allUris: { uri: string; label: string }[];
  onRefresh: () => void;
}) {
  const [newWord, setNewWord] = useState('');
  const [adding, setAdding] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const scene = SCENE_TAGS.find(s => s.id === group.scene) ?? SCENE_TAGS[0];

  const handleAdd = async () => {
    const words = newWord.split(/[,，\n]/).map(w => w.trim()).filter(Boolean);
    if (!words.length) return;
    setAdding(true);
    try {
      let res: any;
      if (words.length === 1) {
        res = await synonymApi.addSynonym(group.uri, words[0]);
      } else {
        res = await synonymApi.addSynonymsBatch(group.uri, words);
      }
      if (res && res.success === false) {
        alert(`添加失败：${res.error || '未知错误'}`);
        setAdding(false);
        return;
      }
    } catch (e: any) {
      alert(`添加失败：${e.message || String(e)}`);
      setAdding(false);
      return;
    }
    setNewWord('');
    await triggerPipelineReload();
    onRefresh();
    setAdding(false);
    inputRef.current?.focus();
  };

  const handleToggle = async (id: number, active: boolean) => {
    await synonymApi.updateSynonym(id, { is_active: active });
    await triggerPipelineReload();
    onRefresh();
  };

  const handleDelete = async (id: number) => {
    await synonymApi.deleteSynonym(id);
    await triggerPipelineReload();
    onRefresh();
  };

  const bySource: Record<string, Synonym[]> = { builtin: [], manual: [], auto: [] };
  for (const s of group.synonyms) bySource[s.source ?? 'manual'].push(s);

  const sourceLabel: Record<string, string> = { builtin: '内置词', manual: '手动维护', auto: '自动学习' };
  const sourceColor: Record<string, string> = { builtin: '#60a5fa', manual: '#c084fc', auto: '#34d399' };

  return (
    <div style={{ flex: 1, padding: '20px 24px', overflowY: 'auto' as const }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 20 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span style={{
              padding: '2px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600,
              background: `${scene.color}18`, color: scene.color, border: `1px solid ${scene.color}30`,
            }}>{scene.label}</span>
            <h2 style={{ fontSize: 17, fontWeight: 700, color: '#f1f5f9', margin: 0 }}>{group.labelCn}</h2>
          </div>
          <code style={{ fontSize: 11, color: '#6b7280', background: '#1a1c35', padding: '2px 8px', borderRadius: 4 }}>
            {group.uri}
          </code>
        </div>
        <div style={{ textAlign: 'right' as const, flexShrink: 0 }}>
          <div style={{ fontSize: 13, color: '#c4c9d6', marginBottom: 4 }}>
            共 <b>{group.synonyms.length}</b> 条 · 活跃 <b style={{ color: '#34d399' }}>{group.synonyms.filter(s => s.is_active).length}</b>
          </div>
          <div style={{ display: 'flex', gap: 10, fontSize: 11, color: '#9ca3af', justifyContent: 'flex-end' }}>
            <span style={{ color: '#60a5fa' }}>● 内置 {bySource.builtin.length}</span>
            <span style={{ color: '#c084fc' }}>● 手动 {bySource.manual.length}</span>
            <span style={{ color: '#34d399' }}>● 自动 {bySource.auto.length}</span>
          </div>
        </div>
      </div>

      {(['builtin', 'manual', 'auto'] as const).map(src => {
        const words = bySource[src];
        if (!words.length) return null;
        return (
          <div key={src} style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: sourceColor[src], marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: sourceColor[src], display: 'inline-block' }} />
              {sourceLabel[src]}
              <span style={{ color: '#9ca3af', fontWeight: 400 }}>({words.length})</span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 6 }}>
              {words.map((s, i) => (
                <SynonymChip key={s.id ?? i} s={s} onToggle={handleToggle} onDelete={handleDelete} />
              ))}
            </div>
          </div>
        );
      })}

      <div style={{
        marginTop: 8, padding: '13px 15px', borderRadius: 9,
        border: '1px dashed #3d3870', background: '#12142a',
      }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#c4c9d6', marginBottom: 7 }}>
          + 添加同义词
          <span style={{ fontSize: 11, color: '#9ca3af', fontWeight: 400, marginLeft: 6 }}>多个词用逗号或换行分隔，回车提交</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            ref={inputRef}
            value={newWord}
            onChange={e => setNewWord(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAdd(); } }}
            placeholder={`为"${group.labelCn}"添加别称…`}
            style={{
              flex: 1, padding: '7px 10px', border: '1px solid #2d284e', borderRadius: 6,
              fontSize: 13, outline: 'none', fontFamily: 'inherit',
            }}
          />
          <button
            onClick={handleAdd}
            disabled={!newWord.trim() || adding}
            style={{
              padding: '7px 16px', borderRadius: 6, border: 'none', fontSize: 13, fontWeight: 600,
              background: !newWord.trim() || adding ? '#2d284e' : '#4f46e5',
              color: !newWord.trim() || adding ? '#9ca3af' : '#fff',
              cursor: !newWord.trim() ? 'not-allowed' : 'pointer',
            }}
          >
            {adding ? '…' : '确认'}
          </button>
        </div>
      </div>

      <div style={{ marginTop: 14, fontSize: 11, color: '#9ca3af' }}>
        悬停词片可 ⏸ 停用 / × 删除 &nbsp;｜&nbsp;
        <span style={{ color: '#60a5fa' }}>蓝框 = 内置（不可删）</span> &nbsp;
        <span style={{ color: '#c084fc' }}>紫框 = 手动</span> &nbsp;
        <span style={{ color: '#34d399' }}>绿框 = 自动学习</span>
      </div>
    </div>
  );
}

// ── 主组件 ────────────────────────────────────────────────────────
export default function SynonymManager() {
  const [tab, setTab] = useState<Tab>('synonyms');
  const [stats, setStats] = useState<Stats | null>(null);
  const [synonyms, setSynonyms] = useState<Synonym[]>([]);
  const [unmatched, setUnmatched] = useState<UnmatchedTerm[]>([]);
  const [auditLog, setAuditLog] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const [searchTerm, setSearchTerm] = useState('');
  const [activeScene, setActiveScene] = useState('all');
  const [selectedUri, setSelectedUri] = useState<string | null>(null);

  // 审批 modal
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [approveItem, setApproveItem] = useState<UnmatchedTerm | null>(null);
  const [approveTable, setApproveTable] = useState('');

  // ── 派生数据 ──────────────────────────────────────────────────
  const allGroups = useMemo(() => buildGroups(synonyms), [synonyms]);

  const allUris = useMemo(() =>
    allGroups.map(g => ({ uri: g.uri, label: g.labelCn })),
    [allGroups]
  );

  const sceneCounts = useMemo(() => {
    const counts: Record<string, number> = { all: allGroups.length };
    for (const g of allGroups) {
      counts[g.scene] = (counts[g.scene] ?? 0) + 1;
    }
    return counts;
  }, [allGroups]);

  const filteredGroups = useMemo(() => {
    const q = searchTerm.toLowerCase();
    return allGroups.filter(g => {
      if (activeScene !== 'all' && g.scene !== activeScene) return false;
      if (!q) return true;
      return (
        g.labelCn.toLowerCase().includes(q) ||
        g.uri.toLowerCase().includes(q) ||
        g.synonyms.some(s => s.synonym.toLowerCase().includes(q))
      );
    });
  }, [allGroups, activeScene, searchTerm]);

  const selectedGroup = useMemo(
    () => filteredGroups.find(g => g.uri === selectedUri) ?? filteredGroups[0] ?? null,
    [filteredGroups, selectedUri]
  );

  // ── 数据加载 ──────────────────────────────────────────────────
  const loadStats = useCallback(async () => {
    const res = await synonymApi.getStats();
    if (res.success) setStats(res.data);
  }, []);

  const loadSynonyms = useCallback(async () => {
    setLoading(true);
    const res = await synonymApi.getSynonyms({});
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

  useEffect(() => {
    if (filteredGroups.length > 0 && (!selectedUri || !filteredGroups.find(g => g.uri === selectedUri))) {
      setSelectedUri(filteredGroups[0].uri);
    }
  }, [filteredGroups]);

  // ── 审批 ──────────────────────────────────────────────────────
  const handleApprove = async () => {
    if (!approveItem || !approveTable) return;
    await synonymApi.approveUnmatched(approveItem.id, approveTable);
    setShowApproveModal(false);
    loadUnmatched();
    loadSynonyms();
    loadStats();
    triggerPipelineReload();
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

  // ── 共用样式 ──────────────────────────────────────────────────
  const S = {
    container: { width: '100%', height: '100%', display: 'flex', flexDirection: 'column' as const, fontFamily: '-apple-system, sans-serif', background: '#0d0e1a' },
    topBar: { padding: '14px 20px 0', background: '#12142a', borderBottom: '1px solid #2d284e' },
    badge: { background: '#dc2626', color: '#fff', fontSize: 10, borderRadius: '50%', width: 16, height: 16, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginLeft: 5 },
    btn: (color: string): React.CSSProperties => ({
      display: 'inline-flex', alignItems: 'center', gap: 5, padding: '6px 14px', border: 'none',
      borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: 'pointer',
      color: '#fff', background: color,
    }),
  };

  return (
    <div style={S.container}>
      {/* Top bar */}
      <div style={S.topBar}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: '#f1f5f9' }}>同义词管理</span>
            {stats && (
              <div style={{ display: 'flex', gap: 10, fontSize: 12, color: '#6b7280' }}>
                <span>活跃 <b style={{ color: '#34d399' }}>{stats.synonyms.active}</b></span>
                <span>本体类 <b>{stats.synonyms.tables}</b></span>
                {stats.unmatched.pending > 0 && (
                  <span style={{ color: '#d97706' }}>待审批 <b>{stats.unmatched.pending}</b></span>
                )}
              </div>
            )}
          </div>
          <button style={S.btn('#6b7280')} onClick={() => { loadSynonyms(); loadStats(); }}>
            <RefreshCw size={12} /> 刷新
          </button>
        </div>
        <div style={{ display: 'flex', gap: 0 }}>
          {(['synonyms', 'unmatched', 'audit'] as Tab[]).map(t => (
            <div key={t}
              style={{
                padding: '10px 18px', cursor: 'pointer', fontSize: 13, fontWeight: tab === t ? 600 : 400,
                color: tab === t ? '#a5b4fc' : '#6b7280',
                borderBottom: `2px solid ${tab === t ? '#818cf8' : 'transparent'}`,
                marginBottom: -1,
              }}
              onClick={() => setTab(t)}>
              {t === 'synonyms' ? '同义词管理' : t === 'unmatched' ? '未匹配词审批' : '操作日志'}
              {t === 'unmatched' && stats && stats.unmatched.pending > 0 && (
                <span style={S.badge}>{stats.unmatched.pending}</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── 同义词管理 Tab ── */}
      {tab === 'synonyms' && (
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          {/* 左侧 */}
          <div style={{
            width: 300, minWidth: 260, flexShrink: 0, borderRight: '1px solid #2d284e',
            background: '#12142a', display: 'flex', flexDirection: 'column',
          }}>
            <div style={{ padding: '12px 12px 8px', borderBottom: '1px solid #1e1b4b' }}>
              <div style={{ position: 'relative' }}>
                <Search size={13} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: '#9ca3af' }} />
                <input
                  value={searchTerm}
                  onChange={e => setSearchTerm(e.target.value)}
                  placeholder="搜索对象名称或同义词…"
                  style={{
                    width: '100%', padding: '7px 28px 7px 28px', border: '1px solid #2d284e',
                    borderRadius: 8, fontSize: 13, outline: 'none', boxSizing: 'border-box',
                  }}
                />
                {searchTerm && (
                  <button onClick={() => setSearchTerm('')} style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', fontSize: 14, padding: 0 }}>×</button>
                )}
              </div>
            </div>
            <div style={{ padding: '8px 12px', borderBottom: '1px solid #1e1b4b' }}>
              <SceneBar active={activeScene} counts={sceneCounts} onChange={id => { setActiveScene(id); setSelectedUri(null); }} />
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '8px 8px' }}>
              {loading ? (
                <div style={{ padding: 24, textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>加载中…</div>
              ) : filteredGroups.length === 0 ? (
                <div style={{ padding: 24, textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>未找到匹配结果</div>
              ) : (
                filteredGroups.map(g => (
                  <EntityCard
                    key={g.uri}
                    group={g}
                    active={selectedGroup?.uri === g.uri}
                    searchTerm={searchTerm}
                    onClick={() => setSelectedUri(g.uri)}
                  />
                ))
              )}
            </div>
            <div style={{ padding: '7px 12px', borderTop: '1px solid #1e1b4b', fontSize: 11, color: '#9ca3af', display: 'flex', justifyContent: 'space-between' }}>
              <span>{filteredGroups.length} 个本体对象</span>
              <span>{filteredGroups.reduce((n, g) => n + g.synonyms.filter(s => s.is_active).length, 0)} 条活跃</span>
            </div>
          </div>

          {/* 右侧详情 */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {selectedGroup ? (
              <DetailPanel
                key={selectedGroup.uri}
                group={selectedGroup}
                allUris={allUris}
                onRefresh={() => { loadSynonyms(); loadStats(); }}
              />
            ) : (
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 14 }}>
                从左侧选择一个本体对象
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── 未匹配词 Tab ── */}
      {tab === 'unmatched' && (
        <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
          <div style={{ background: '#12142a', borderRadius: 10, border: '1px solid #2d284e', overflow: 'hidden' }}>
            <div style={{ padding: '12px 18px', borderBottom: '1px solid #1e1b4b', display: 'flex', justifyContent: 'space-between' }}>
              <b style={{ fontSize: 14 }}>未匹配查询词 ({unmatched.length})</b>
              <button style={S.btn('#6b7280')} onClick={loadUnmatched}><RefreshCw size={12} /> 刷新</button>
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#12142a' }}>
                  {['查询词', '频次', '原始查询', '推荐对象', '操作'].map(h => (
                    <th key={h} style={{ padding: '9px 14px', textAlign: 'left', fontWeight: 600, color: '#6b7280', borderBottom: '1px solid #2d284e' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {unmatched.map(t => (
                  <tr key={t.id} style={{ borderBottom: '1px solid #1e1b4b' }}>
                    <td style={{ padding: '9px 14px', fontWeight: 600 }}>{t.term}</td>
                    <td style={{ padding: '9px 14px', color: '#d97706' }}>{t.frequency}次</td>
                    <td style={{ padding: '9px 14px', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#6b7280' }}>{t.original_query || '—'}</td>
                    <td style={{ padding: '9px 14px' }}>{t.suggested_table ? <code style={{ fontSize: 11, background: '#1a1c35', padding: '1px 6px', borderRadius: 4 }}>{t.suggested_table}</code> : '—'}</td>
                    <td style={{ padding: '9px 14px' }}>
                      <div style={{ display: 'flex', gap: 5 }}>
                        <button style={S.btn('#059669')} onClick={() => { setApproveItem(t); setApproveTable(t.suggested_table || allUris[0]?.uri || ''); setShowApproveModal(true); }}>
                          <Check size={11} /> 映射
                        </button>
                        <button style={S.btn('#6b7280')} onClick={() => handleReject(t.id)}><X size={11} /></button>
                        <button style={S.btn('#9ca3af')} onClick={() => handleIgnore(t.id)}><EyeOff size={11} /></button>
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

      {/* ── 审计日志 Tab ── */}
      {tab === 'audit' && (
        <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
          <div style={{ background: '#12142a', borderRadius: 10, border: '1px solid #2d284e', overflow: 'hidden' }}>
            <div style={{ padding: '12px 18px', borderBottom: '1px solid #1e1b4b', display: 'flex', justifyContent: 'space-between' }}>
              <b style={{ fontSize: 14 }}>操作日志 ({auditLog.length})</b>
              <button style={S.btn('#6b7280')} onClick={loadAudit}><RefreshCw size={12} /> 刷新</button>
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#12142a' }}>
                  {['时间', '操作', '本体对象', '同义词', '操作人'].map(h => (
                    <th key={h} style={{ padding: '9px 14px', textAlign: 'left', fontWeight: 600, color: '#6b7280', borderBottom: '1px solid #2d284e' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {auditLog.map((l, i) => (
                  <tr key={l.id ?? i} style={{ borderBottom: '1px solid #1e1b4b' }}>
                    <td style={{ padding: '9px 14px', color: '#6b7280', whiteSpace: 'nowrap' }}>{l.created_at ? new Date(l.created_at).toLocaleString('zh-CN') : '—'}</td>
                    <td style={{ padding: '9px 14px' }}>
                      <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: 'rgba(59,130,246,0.15)', color: '#93c5fd' }}>{l.action}</span>
                    </td>
                    <td style={{ padding: '9px 14px' }}><code style={{ fontSize: 11, background: '#1a1c35', padding: '1px 6px', borderRadius: 4 }}>{l.target_uri || (l as any).table_name || '—'}</code></td>
                    <td style={{ padding: '9px 14px', fontWeight: 600 }}>{l.synonym}</td>
                    <td style={{ padding: '9px 14px', color: '#6b7280' }}>{l.performed_by}</td>
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

      {/* ── 审批 Modal ── */}
      {showApproveModal && approveItem && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200 }}
          onClick={() => setShowApproveModal(false)}>
          <div style={{ background: '#12142a', borderRadius: 12, width: 460, maxWidth: '90vw', boxShadow: '0 20px 60px rgba(0,0,0,.15)' }}
            onClick={e => e.stopPropagation()}>
            <div style={{ padding: '18px 22px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: 16, fontWeight: 600, margin: 0 }}>映射：<span style={{ color: '#4f46e5' }}>"{approveItem.term}"</span></h3>
              <button onClick={() => setShowApproveModal(false)} style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: '#9ca3af' }}>×</button>
            </div>
            <div style={{ padding: '14px 22px' }}>
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 13, fontWeight: 500, color: '#c4c9d6', display: 'block', marginBottom: 4 }}>映射到本体对象</label>
                <select
                  value={approveTable}
                  onChange={e => setApproveTable(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid #2d284e', borderRadius: 6, fontSize: 13 }}
                >
                  {allUris.map(u => <option key={u.uri} value={u.uri}>{u.label}（{u.uri}）</option>)}
                </select>
              </div>
              <div style={{ fontSize: 12, color: '#6b7280', display: 'flex', gap: 16 }}>
                <span>原始查询：{approveItem.original_query || '无'}</span>
                <span>出现 {approveItem.frequency} 次</span>
              </div>
            </div>
            <div style={{ padding: '12px 22px', borderTop: '1px solid #2d284e', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button style={S.btn('#6b7280')} onClick={() => setShowApproveModal(false)}>取消</button>
              <button style={S.btn('#059669')} onClick={handleApprove}>✓ 审批通过</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

