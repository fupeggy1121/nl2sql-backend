/**
 * BaselinesManager.tsx — 预警基线管理（独立页面）
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Search, RefreshCw, Trash2, Edit2, AlertCircle, X } from 'lucide-react';
import { baselineApi, Baseline, ThresholdItem } from '../services/baselineApi';

const LEVEL_META: Record<string, { label: string; color: string; bg: string }> = {
  target:   { label: '目标值',  color: '#10b981', bg: 'bg-emerald-50' },
  warning:  { label: '预警值',  color: '#f59e0b', bg: 'bg-amber-50'   },
  critical: { label: '临界值',  color: '#ef4444', bg: 'bg-red-50'     },
};

const EMPTY_THRESHOLD: ThresholdItem = { value: 0, level: 'warning', label: '预警值', color: '#f59e0b' };

const EMPTY_BASELINE: Omit<Baseline, 'id' | 'created_at' | 'updated_at'> = {
  label: '',
  field: '',
  keywords: [],
  scope: {},
  thresholds: [{ ...EMPTY_THRESHOLD }],
  direction: 'below',
  enabled: true,
  created_by: 'user',
};

export default function BaselinesManager() {
  const [items, setItems] = useState<Baseline[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<Partial<Baseline> | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await baselineApi.list({ q: search });
      setItems(res.items);
    } catch (e: any) {
      setError(e.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => { load(); }, [load]);

  const handleEdit = (bl: Baseline) => {
    setEditing({ ...bl, thresholds: bl.thresholds?.length ? bl.thresholds : [{ ...EMPTY_THRESHOLD }] });
    setIsNew(false);
  };
  const handleNew = () => {
    setEditing({ ...EMPTY_BASELINE, thresholds: [{ ...EMPTY_THRESHOLD }] });
    setIsNew(true);
  };
  const handleCancel = () => { setEditing(null); setIsNew(false); };

  const handleSave = async () => {
    if (!editing) return;
    setSaving(true);
    setError('');
    try {
      if (isNew) {
        await baselineApi.create(editing as any);
      } else {
        await baselineApi.update(editing.id!, editing);
      }
      setEditing(null);
      setIsNew(false);
      await load();
    } catch (e: any) {
      setError(e.message || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('确认删除此基线？')) return;
    try {
      await baselineApi.delete(id);
      await load();
    } catch (e: any) {
      setError(e.message || '删除失败');
    }
  };

  const handleToggle = async (id: string) => {
    try {
      await baselineApi.toggle(id);
      await load();
    } catch (e: any) {
      setError(e.message || '切换失败');
    }
  };

  const setField = (key: keyof Baseline, val: any) =>
    setEditing(prev => prev ? { ...prev, [key]: val } : prev);

  const setThreshold = (idx: number, key: keyof ThresholdItem, val: any) =>
    setEditing(prev => {
      if (!prev) return prev;
      const ts = [...(prev.thresholds || [])];
      ts[idx] = { ...ts[idx], [key]: val };
      if (key === 'level') {
        ts[idx].label = LEVEL_META[val]?.label || val;
        ts[idx].color = LEVEL_META[val]?.color || ts[idx].color;
      }
      return { ...prev, thresholds: ts };
    });

  const addThreshold = () =>
    setEditing(prev => prev ? { ...prev, thresholds: [...(prev.thresholds || []), { ...EMPTY_THRESHOLD }] } : prev);

  const removeThreshold = (idx: number) =>
    setEditing(prev => {
      if (!prev) return prev;
      const ts = (prev.thresholds || []).filter((_, i) => i !== idx);
      return { ...prev, thresholds: ts };
    });

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="w-full p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">数据源管理</h1>
          <p className="text-sm text-gray-500 mt-1">预警基线配置与管理</p>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="flex items-center gap-2 px-6 py-4 border-b border-gray-200">
            <AlertCircle size={16} className="text-orange-500" />
            <span className="font-semibold text-gray-900 text-sm">预警基线</span>
          </div>
          <div className="p-6 space-y-4">
            {/* Toolbar */}
            <div className="flex items-center gap-3">
              <div className="relative flex-1 max-w-xs">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="搜索基线…"
                  className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full"
                />
              </div>
              <button onClick={load} className="flex items-center gap-1.5 px-3 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">
                <RefreshCw size={14} /> 刷新
              </button>
              <button onClick={handleNew} className="flex items-center gap-1.5 px-3 py-2 text-sm bg-orange-600 text-white rounded-lg hover:bg-orange-700">
                <Plus size={14} /> 新建基线
              </button>
            </div>

            {error && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</div>}

            {/* List */}
            {loading ? (
              <div className="text-sm text-gray-400 py-8 text-center">加载中…</div>
            ) : items.length === 0 ? (
              <div className="text-sm text-gray-400 py-8 text-center">暂无预警基线，点击「新建基线」创建第一条</div>
            ) : (
              <div className="space-y-2">
                {items.map(bl => (
                  <div key={bl.id} className={`border rounded-lg p-4 ${bl.enabled ? 'border-gray-200 bg-white' : 'border-gray-100 bg-gray-50 opacity-60'}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-medium text-gray-900 text-sm">{bl.label}</span>
                          <span className="font-mono text-xs text-gray-400 border border-gray-200 rounded px-1">{bl.field}</span>
                          <span className={`text-xs px-1.5 py-0.5 rounded-full ${bl.direction === 'above' ? 'bg-blue-50 text-blue-700' : 'bg-purple-50 text-purple-700'}`}>
                            {bl.direction === 'above' ? '超过预警' : '低于预警'}
                          </span>
                          {!bl.enabled && <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full">已禁用</span>}
                        </div>
                        <div className="flex flex-wrap gap-1.5 mt-2">
                          {(bl.thresholds || []).map((t, i) => (
                            <span key={i} className="text-xs rounded-full px-2 py-0.5 font-medium"
                              style={{ backgroundColor: `${t.color || '#6b7280'}20`, color: t.color || '#6b7280', border: `1px solid ${t.color || '#6b7280'}40` }}>
                              {t.label}: {t.value}
                            </span>
                          ))}
                        </div>
                        {bl.keywords?.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1.5">
                            {bl.keywords.map((kw, i) => (
                              <span key={i} className="text-xs bg-gray-100 text-gray-600 rounded px-1.5 py-0.5">{kw}</span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        <button onClick={() => handleToggle(bl.id)} title={bl.enabled ? '禁用' : '启用'}
                          className="text-xs px-2 py-1 border rounded hover:bg-gray-50">
                          {bl.enabled ? '禁用' : '启用'}
                        </button>
                        <button onClick={() => handleEdit(bl)} className="p-1.5 rounded hover:bg-blue-50 text-blue-600">
                          <Edit2 size={13} />
                        </button>
                        <button onClick={() => handleDelete(bl.id)} className="p-1.5 rounded hover:bg-red-50 text-red-500">
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Editor Modal */}
            {editing && (
              <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
                <div className="bg-white rounded-xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
                  <div className="flex items-center justify-between px-6 py-4 border-b">
                    <h3 className="font-semibold text-gray-900">{isNew ? '新建预警基线' : '编辑预警基线'}</h3>
                    <button onClick={handleCancel} className="p-1.5 rounded hover:bg-gray-100"><X size={16} /></button>
                  </div>
                  <div className="px-6 py-4 space-y-4">
                    <div>
                      <label className="text-xs font-medium text-gray-600 mb-1 block">基线名称 *</label>
                      <input value={editing.label || ''} onChange={e => setField('label', e.target.value)}
                        placeholder="如：库存预警、良率下限" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-gray-600 mb-1 block">Y轴字段名 *</label>
                      <input value={editing.field || ''} onChange={e => setField('field', e.target.value)}
                        placeholder="如：yield_rate, output_qty, inventory_qty" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono" />
                      <p className="text-xs text-gray-400 mt-0.5">图表 yAxisField 精确匹配时自动应用基线</p>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-gray-600 mb-1 block">触发关键词（逗号分隔）</label>
                      <input
                        value={(editing.keywords || []).join(', ')}
                        onChange={e => setField('keywords', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                        placeholder="如：库存, 存货, WIP" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-gray-600 mb-1 block">预警方向</label>
                      <div className="flex gap-3">
                        {(['below', 'above'] as const).map(d => (
                          <label key={d} className="flex items-center gap-1.5 text-sm cursor-pointer">
                            <input type="radio" checked={editing.direction === d} onChange={() => setField('direction', d)} />
                            {d === 'below' ? '低于阈值时预警（如库存不足）' : '高于阈值时预警（如温度超限）'}
                          </label>
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-medium text-gray-600">阈值配置</label>
                        <button onClick={addThreshold} className="text-xs text-blue-600 hover:underline flex items-center gap-0.5">
                          <Plus size={12} /> 添加阈值
                        </button>
                      </div>
                      <div className="space-y-2">
                        {(editing.thresholds || []).map((t, i) => (
                          <div key={i} className="flex items-center gap-2 border border-gray-100 rounded-lg p-2 bg-gray-50">
                            <select value={t.level}
                              onChange={e => setThreshold(i, 'level', e.target.value)}
                              className="text-xs border border-gray-200 rounded px-2 py-1 bg-white">
                              {Object.entries(LEVEL_META).map(([k, v]) => (
                                <option key={k} value={k}>{v.label}</option>
                              ))}
                            </select>
                            <input type="number" value={t.value}
                              onChange={e => setThreshold(i, 'value', parseFloat(e.target.value) || 0)}
                              className="w-24 text-xs border border-gray-200 rounded px-2 py-1 bg-white font-mono"
                              placeholder="数值" />
                            <input type="color" value={t.color || LEVEL_META[t.level]?.color || '#6b7280'}
                              onChange={e => setThreshold(i, 'color', e.target.value)}
                              className="w-8 h-7 border border-gray-200 rounded cursor-pointer" />
                            <button onClick={() => removeThreshold(i)} className="ml-auto p-1 rounded hover:bg-red-50 text-red-400">
                              <X size={12} />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                    <label className="flex items-center gap-2 text-sm cursor-pointer">
                      <input type="checkbox" checked={editing.enabled ?? true} onChange={e => setField('enabled', e.target.checked)} />
                      启用此基线
                    </label>
                  </div>
                  {error && <div className="mx-6 mb-3 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>}
                  <div className="flex justify-end gap-2 px-6 py-4 border-t">
                    <button onClick={handleCancel} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">取消</button>
                    <button onClick={handleSave} disabled={saving} className="px-4 py-2 text-sm bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:opacity-50">
                      {saving ? '保存中…' : '保存'}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
