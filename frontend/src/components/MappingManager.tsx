/**
 * MappingManager.tsx — 映射字典管理 React 组件
 *
 * 4 个 Tab:
 *   1. 对象映射   (object_mappings)   — CRUD + 搜索
 *   2. 关系映射   (relation_mappings) — CRUD + 策略感知表单
 *   3. 值映射     (value_mappings)    — 域列表 + 展开编辑
 *   4. 变更记录   (changelog)         — 时间线只读
 *
 * 依赖: lucide-react (项目已有)
 *
 * 使用方式:
 *   import MappingManager from './MappingManager';
 *   <MappingManager />
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Plus, Search, RefreshCw, Trash2, Edit2, ChevronDown, ChevronRight,
  History, Database, GitBranch, Tag, FileText, AlertCircle, X, Check,
  Book
} from 'lucide-react';
import { mappingApi } from '../services/mappingApi';

// ══════════════════════════════════════════════════════════════════
// Types
// ══════════════════════════════════════════════════════════════════

interface ObjectMapping {
  logic_class: string;
  physical_table: string | null;
  primary_key: string | null;
  label_cn: string;
  display_column: string | null;
  filter_condition?: string | null;  // 同表多类区分条件，e.g. "parent_id != 0"
  key_columns: string[];
  properties: Record<string, string | null>;
  virtual?: boolean;
  note?: string;
}

interface RelationMapping {
  logic_relation: string;
  description: string;
  strategy: string;
  join_logic: Record<string, any>;
  confidence?: string;
}

interface ValueEntry {
  semantic_value: string;
  description?: string;
  physical_condition?: string;
  applies_to_table?: string;
  applies_to_column?: string;
  note?: string;
  [key: string]: any;
}

interface ValueDomain {
  domain: string;
  value_count: number;
}

interface BusinessRule {
  id: string;
  name: string;
  description: string;
  trigger_keywords: string[];
  physical_sql_template: string;
  involved_tables: string[];
  warning_tables: string[];
  semantic_pattern?: string;
}

interface ChangelogEntry {
  timestamp: string;
  user: string;
  action: 'create' | 'update' | 'delete';
  entry_type: string;
  key: string;
  before?: any;
  after?: any;
}

interface Summary {
  mapping_file: string;
  version: string;
  customer: string;
  object_mappings: number;
  relation_mappings: number;
  value_domains: number;
  business_rules: number;
}

type Tab = 'objects' | 'relations' | 'values' | 'rules' | 'changelog';

// ══════════════════════════════════════════════════════════════════
// Helper: Modal
// ══════════════════════════════════════════════════════════════════

interface ModalProps {
  title: string;
  onClose: () => void;
  onConfirm: () => void;
  confirmText?: string;
  children: React.ReactNode;
  wide?: boolean;
}

function Modal({ title, onClose, onConfirm, confirmText = '保存', children, wide }: ModalProps) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className={`bg-white rounded-xl shadow-2xl flex flex-col ${wide ? 'w-full max-w-3xl' : 'w-full max-w-lg'} max-h-[90vh]`}>
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b">
          <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <X size={20} />
          </button>
        </div>
        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {children}
        </div>
        {/* Footer */}
        <div className="flex justify-end gap-3 p-5 border-t bg-gray-50 rounded-b-xl">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors"
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// Helper: Form fields
// ══════════════════════════════════════════════════════════════════

function Field({
  label, children, required, hint
}: { label: string; children: React.ReactNode; required?: boolean; hint?: string }) {
  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-gray-700">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      {children}
      {hint && <p className="text-xs text-gray-400">{hint}</p>}
    </div>
  );
}

const inputCls = "w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50";
const textareaCls = `${inputCls} min-h-[80px] resize-y font-mono`;

// ══════════════════════════════════════════════════════════════════
// Helper: Badge
// ══════════════════════════════════════════════════════════════════

const STRATEGY_COLORS: Record<string, string> = {
  ForeignKey:   'bg-blue-100 text-blue-700',
  JoinTable:    'bg-purple-100 text-purple-700',
  Indirect:     'bg-orange-100 text-orange-700',
  Recursive:    'bg-green-100 text-green-700',
  Denormalized: 'bg-gray-100 text-gray-600',
};

const ACTION_COLORS: Record<string, string> = {
  create: 'bg-green-100 text-green-700',
  update: 'bg-yellow-100 text-yellow-700',
  delete: 'bg-red-100 text-red-700',
};

const CONFIDENCE_COLORS: Record<string, string> = {
  high:   'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  low:    'bg-red-100 text-red-600',
};

function Badge({ text, colorCls }: { text: string; colorCls: string }) {
  return (
    <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded-full ${colorCls}`}>
      {text}
    </span>
  );
}

// ══════════════════════════════════════════════════════════════════
// Tab 1: Object Mappings
// ══════════════════════════════════════════════════════════════════

function ObjectMappingsTab() {
  const [items, setItems] = useState<ObjectMapping[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  const [showModal, setShowModal] = useState(false);
  const [editItem, setEditItem] = useState<Partial<ObjectMapping> | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const PAGE_SIZE = 30;

  const load = useCallback(async (p = page, q = search) => {
    setLoading(true);
    try {
      const res = await mappingApi.getObjects({ q, page: p, page_size: PAGE_SIZE });
      setItems(res.data || []);
      setTotal(res.total || 0);
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, []);

  const handleSearch = (v: string) => {
    setSearch(v);
    setPage(1);
    load(1, v);
  };

  const openAdd = () => {
    setEditItem({
      logic_class: '', physical_table: '', primary_key: 'id',
      label_cn: '', display_column: '', filter_condition: '',
      key_columns: [], properties: {}, virtual: false, note: '',
    });
    setIsEditing(false);
    setShowModal(true);
  };

  const openEdit = (item: ObjectMapping) => {
    setEditItem({ ...item });
    setIsEditing(true);
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!editItem) return;
    setSaving(true);
    setError('');
    try {
      // Parse key_columns from string if needed
      const payload: any = { ...editItem };
      if (typeof payload.key_columns === 'string') {
        payload.key_columns = (payload.key_columns as string)
          .split(',').map((s: string) => s.trim()).filter(Boolean);
      }
      if (isEditing) {
        await mappingApi.updateObject(editItem.logic_class!, payload);
      } else {
        await mappingApi.createObject(payload);
      }
      setShowModal(false);
      load(page, search);
    } catch (e: any) {
      setError(e.message);
    }
    setSaving(false);
  };

  const handleDelete = async (logicClass: string) => {
    if (!confirm(`确认删除 ${logicClass}？此操作不可恢复。`)) return;
    try {
      await mappingApi.deleteObject(logicClass);
      load(page, search);
    } catch (e: any) {
      alert(e.message);
    }
  };

  // key_columns as editable comma list
  const keyColsStr = useMemo(
    () => Array.isArray(editItem?.key_columns) ? editItem!.key_columns.join(', ') : editItem?.key_columns || '',
    [editItem?.key_columns]
  );

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search}
            onChange={e => handleSearch(e.target.value)}
            placeholder="搜索 logic_class / 表名 / 中文标签..."
            className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50"
          />
        </div>
        <button
          onClick={() => load(page, search)}
          className="p-2 text-gray-500 border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
        <button
          onClick={openAdd}
          className="flex items-center gap-2 px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700"
        >
          <Plus size={16} />
          添加
        </button>
      </div>

      {/* Stats line */}
      <p className="text-xs text-gray-500">共 {total} 条{search ? `（已过滤）` : ''}</p>

      {/* Table */}
      <div className="border border-gray-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Logic Class</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Physical Table</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">中文标签</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Display Col</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Key Cols</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading && (
              <tr><td colSpan={6} className="py-8 text-center text-gray-400">加载中...</td></tr>
            )}
            {!loading && items.length === 0 && (
              <tr><td colSpan={6} className="py-8 text-center text-gray-400">暂无数据</td></tr>
            )}
            {items.map(item => (
              <tr key={item.logic_class} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 font-mono text-xs text-blue-700">{item.logic_class}</td>
                <td className="px-4 py-3 font-mono text-xs text-gray-600">
                  {item.physical_table || <span className="text-gray-300 italic">virtual</span>}
                  {item.filter_condition && (
                    <span className="ml-2 px-1.5 py-0.5 text-[10px] font-medium bg-amber-100 text-amber-700 rounded">
                      WHERE {item.filter_condition}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-800">{item.label_cn}</td>
                <td className="px-4 py-3 font-mono text-xs text-gray-500">{item.display_column || '—'}</td>
                <td className="px-4 py-3 text-xs text-gray-400">{(item.key_columns || []).length} 列</td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <button onClick={() => openEdit(item)} className="p-1 text-gray-400 hover:text-blue-600 transition-colors">
                      <Edit2 size={14} />
                    </button>
                    <button onClick={() => handleDelete(item.logic_class)} className="p-1 text-gray-400 hover:text-red-600 transition-colors">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-500">
          <span>第 {page} / {totalPages} 页</span>
          <div className="flex gap-2">
            <button
              disabled={page <= 1}
              onClick={() => { setPage(page - 1); load(page - 1, search); }}
              className="px-3 py-1 border rounded-lg disabled:opacity-40 hover:bg-gray-50"
            >
              上一页
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => { setPage(page + 1); load(page + 1, search); }}
              className="px-3 py-1 border rounded-lg disabled:opacity-40 hover:bg-gray-50"
            >
              下一页
            </button>
          </div>
        </div>
      )}

      {/* Add/Edit Modal */}
      {showModal && editItem && (
        <Modal
          title={isEditing ? `编辑：${editItem.logic_class}` : '新增对象映射'}
          onClose={() => setShowModal(false)}
          onConfirm={handleSave}
          confirmText={saving ? '保存中...' : '保存'}
          wide
        >
          {error && (
            <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 p-3 rounded-lg">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <Field label="Logic Class（本体 URI）" required hint="例：semi:Equipment">
            <input
              value={editItem.logic_class || ''}
              onChange={e => setEditItem({ ...editItem, logic_class: e.target.value })}
              disabled={isEditing}
              className={`${inputCls} ${isEditing ? 'bg-gray-50 text-gray-500' : ''}`}
              placeholder="semi:Equipment"
            />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="物理表名" hint="MySQL 表名">
              <input
                value={editItem.physical_table || ''}
                onChange={e => setEditItem({ ...editItem, physical_table: e.target.value })}
                className={inputCls}
                placeholder="equipment"
              />
            </Field>
            <Field label="主键列" hint="默认 id">
              <input
                value={editItem.primary_key || 'id'}
                onChange={e => setEditItem({ ...editItem, primary_key: e.target.value })}
                className={inputCls}
                placeholder="id"
              />
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Field label="中文标签（label_cn）" hint="用户输入此词时触发匹配" required>
              <input
                value={editItem.label_cn || ''}
                onChange={e => setEditItem({ ...editItem, label_cn: e.target.value })}
                className={inputCls}
                placeholder="设备"
              />
            </Field>
            <Field label="Display Column" hint="前端展示行用的标识列">
              <input
                value={editItem.display_column || ''}
                onChange={e => setEditItem({ ...editItem, display_column: e.target.value })}
                className={inputCls}
                placeholder="equipment_code"
              />
            </Field>
          </div>

          <Field
            label="Filter Condition（同表多类过滤）"
            hint="当多个本体类共用同一张物理表时，用于区分的 WHERE 条件。例：parent_id != 0（子批次）或 parent_id = 0（主批次）。留空表示无过滤。"
          >
            <input
              value={editItem.filter_condition || ''}
              onChange={e => setEditItem({ ...editItem, filter_condition: e.target.value || null })}
              className={inputCls}
              placeholder="parent_id != 0"
            />
          </Field>

          <Field label="Key Columns" hint="给 LLM 的 schema 提示列（逗号分隔）">
            <textarea
              value={keyColsStr}
              onChange={e => setEditItem({ ...editItem, key_columns: e.target.value as any })}
              className={textareaCls}
              placeholder="id, equipment_code, name, status, classify_id"
            />
          </Field>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="virtual-cb"
              checked={!!editItem.virtual}
              onChange={e => setEditItem({ ...editItem, virtual: e.target.checked })}
              className="w-4 h-4 rounded border-gray-300"
            />
            <label htmlFor="virtual-cb" className="text-sm text-gray-700">
              虚拟类（无对应物理表）
            </label>
          </div>

          <Field label="备注" hint="可选">
            <input
              value={editItem.note || ''}
              onChange={e => setEditItem({ ...editItem, note: e.target.value })}
              className={inputCls}
              placeholder="可选备注"
            />
          </Field>
        </Modal>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// Tab 2: Relation Mappings
// ══════════════════════════════════════════════════════════════════

const STRATEGIES = ['ForeignKey', 'JoinTable', 'Indirect', 'Recursive', 'Denormalized'];

function RelationMappingsTab() {
  const [items, setItems] = useState<RelationMapping[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [filterConf, setFilterConf] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editItem, setEditItem] = useState<Partial<RelationMapping> | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const load = useCallback(async (q = search, conf = filterConf) => {
    setLoading(true);
    try {
      const res = await mappingApi.getRelations({ q, confidence: conf || undefined });
      setItems(res.data || []);
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, []);

  const openAdd = () => {
    setEditItem({
      logic_relation: '', description: '', strategy: 'ForeignKey',
      join_logic: { source_table: '', source_key: '', target_table: '', target_key: 'id' }
    });
    setIsEditing(false);
    setShowModal(true);
  };

  const openEdit = (item: RelationMapping) => {
    setEditItem({ ...item, join_logic: { ...item.join_logic } });
    setIsEditing(true);
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!editItem) return;
    setSaving(true);
    setError('');
    try {
      if (isEditing) {
        await mappingApi.updateRelation(editItem.logic_relation!, editItem);
      } else {
        await mappingApi.createRelation(editItem);
      }
      setShowModal(false);
      load();
    } catch (e: any) {
      setError(e.message);
    }
    setSaving(false);
  };

  const handleDelete = async (logicRelation: string) => {
    if (!confirm(`确认删除关系 ${logicRelation}？`)) return;
    try {
      await mappingApi.deleteRelation(logicRelation);
      load();
    } catch (e: any) {
      alert(e.message);
    }
  };

  // join_logic form varies by strategy
  const renderJoinLogicForm = () => {
    if (!editItem) return null;
    const jl = editItem.join_logic || {};
    const setJl = (key: string, val: any) =>
      setEditItem({ ...editItem, join_logic: { ...jl, [key]: val } });

    switch (editItem.strategy) {
      case 'ForeignKey':
        return (
          <div className="grid grid-cols-2 gap-3">
            <Field label="source_table"><input value={jl.source_table || ''} onChange={e => setJl('source_table', e.target.value)} className={inputCls} placeholder="wafers" /></Field>
            <Field label="source_key"><input value={jl.source_key || ''} onChange={e => setJl('source_key', e.target.value)} className={inputCls} placeholder="batch_id" /></Field>
            <Field label="target_table"><input value={jl.target_table || ''} onChange={e => setJl('target_table', e.target.value)} className={inputCls} placeholder="local_production_batch" /></Field>
            <Field label="target_key"><input value={jl.target_key || ''} onChange={e => setJl('target_key', e.target.value)} className={inputCls} placeholder="id" /></Field>
          </div>
        );
      case 'JoinTable':
        return (
          <div className="grid grid-cols-2 gap-3">
            <Field label="source_table"><input value={jl.source_table || ''} onChange={e => setJl('source_table', e.target.value)} className={inputCls} /></Field>
            <Field label="source_pk"><input value={jl.source_pk || 'id'} onChange={e => setJl('source_pk', e.target.value)} className={inputCls} /></Field>
            <Field label="bridge_table"><input value={jl.bridge_table || ''} onChange={e => setJl('bridge_table', e.target.value)} className={inputCls} /></Field>
            <Field label="source_key（bridge.col）"><input value={jl.source_key || ''} onChange={e => setJl('source_key', e.target.value)} className={inputCls} /></Field>
            <Field label="target_key（bridge.col）"><input value={jl.target_key || ''} onChange={e => setJl('target_key', e.target.value)} className={inputCls} /></Field>
            <Field label="target_table"><input value={jl.target_table || ''} onChange={e => setJl('target_table', e.target.value)} className={inputCls} /></Field>
            <Field label="target_pk"><input value={jl.target_pk || 'id'} onChange={e => setJl('target_pk', e.target.value)} className={inputCls} /></Field>
            <Field label="order_by（可选）"><input value={jl.order_by || ''} onChange={e => setJl('order_by', e.target.value)} className={inputCls} placeholder="sequence" /></Field>
          </div>
        );
      case 'Recursive':
        return (
          <div className="grid grid-cols-2 gap-3">
            <Field label="table（自关联表）"><input value={jl.table || ''} onChange={e => setJl('table', e.target.value)} className={inputCls} placeholder="local_production_batch" /></Field>
            <Field label="self_key"><input value={jl.self_key || 'id'} onChange={e => setJl('self_key', e.target.value)} className={inputCls} placeholder="id" /></Field>
            <Field label="parent_key"><input value={jl.parent_key || ''} onChange={e => setJl('parent_key', e.target.value)} className={inputCls} placeholder="parent_batch_id" /></Field>
            <Field label="max_depth（默认 20）"><input type="number" value={jl.max_depth || 20} onChange={e => setJl('max_depth', parseInt(e.target.value))} className={inputCls} /></Field>
          </div>
        );
      default:
        return (
          <Field label="join_logic（JSON）" hint="手动填写 JSON">
            <textarea
              value={JSON.stringify(jl, null, 2)}
              onChange={e => {
                try { setEditItem({ ...editItem, join_logic: JSON.parse(e.target.value) }); } catch { }
              }}
              className={textareaCls}
              rows={6}
            />
          </Field>
        );
    }
  };

  const autoItems = items.filter(i => i.confidence);
  const reviewItems = items.filter(i => i.confidence === 'medium' || i.confidence === 'low');

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={e => { setSearch(e.target.value); load(e.target.value, filterConf); }}
            placeholder="搜索关系名 / 描述..." className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50" />
        </div>
        <select value={filterConf} onChange={e => { setFilterConf(e.target.value); load(search, e.target.value); }}
          className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none">
          <option value="">全部置信度</option>
          <option value="high">✅ 高</option>
          <option value="medium">⚠️ 中（待确认）</option>
        </select>
        <button onClick={() => load()} className="p-2 text-gray-500 border border-gray-300 rounded-lg hover:bg-gray-50">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
        <button onClick={openAdd} className="flex items-center gap-2 px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700">
          <Plus size={16} />添加
        </button>
      </div>

      {reviewItems.length > 0 && (
        <div className="flex items-center gap-2 text-sm text-yellow-700 bg-yellow-50 border border-yellow-200 rounded-lg p-3">
          <AlertCircle size={16} />
          <span>{reviewItems.length} 条自动生成的关系待人工确认（中/低置信度）</span>
        </div>
      )}

      <p className="text-xs text-gray-500">共 {items.length} 条关系映射</p>

      {/* Table */}
      <div className="border border-gray-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="w-8" />
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Logic Relation</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">策略</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">描述</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">置信度</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading && <tr><td colSpan={6} className="py-8 text-center text-gray-400">加载中...</td></tr>}
            {!loading && items.length === 0 && <tr><td colSpan={6} className="py-8 text-center text-gray-400">暂无数据 — 运行 generate_relation_mappings.py --merge 导入草稿</td></tr>}
            {items.map(item => (
              <React.Fragment key={item.logic_relation}>
                <tr className={`hover:bg-gray-50 transition-colors ${item.confidence === 'medium' ? 'bg-yellow-50/30' : ''}`}>
                  <td className="pl-3">
                    <button onClick={() => setExpandedRow(expandedRow === item.logic_relation ? null : item.logic_relation)}
                      className="text-gray-400 hover:text-gray-600">
                      {expandedRow === item.logic_relation ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-blue-700">{item.logic_relation}</td>
                  <td className="px-4 py-3">
                    <Badge text={item.strategy} colorCls={STRATEGY_COLORS[item.strategy] || 'bg-gray-100 text-gray-600'} />
                  </td>
                  <td className="px-4 py-3 text-gray-600 max-w-xs truncate" title={item.description}>{item.description || '—'}</td>
                  <td className="px-4 py-3">
                    {item.confidence && <Badge text={item.confidence} colorCls={CONFIDENCE_COLORS[item.confidence] || ''} />}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button onClick={() => openEdit(item)} className="p-1 text-gray-400 hover:text-blue-600"><Edit2 size={14} /></button>
                      <button onClick={() => handleDelete(item.logic_relation)} className="p-1 text-gray-400 hover:text-red-600"><Trash2 size={14} /></button>
                    </div>
                  </td>
                </tr>
                {expandedRow === item.logic_relation && (
                  <tr className="bg-gray-50">
                    <td colSpan={6} className="px-8 pb-4 pt-2">
                      <pre className="text-xs text-gray-600 bg-white border border-gray-200 rounded-lg p-3 overflow-x-auto">
                        {JSON.stringify(item.join_logic, null, 2)}
                      </pre>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal */}
      {showModal && editItem && (
        <Modal
          title={isEditing ? `编辑关系：${editItem.logic_relation}` : '新增关系映射'}
          onClose={() => setShowModal(false)}
          onConfirm={handleSave}
          confirmText={saving ? '保存中...' : '保存'}
          wide
        >
          {error && <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 p-3 rounded-lg"><AlertCircle size={16} />{error}</div>}

          <Field label="Logic Relation（本体关系 URI）" required hint="例：semi:belongsToLot">
            <input value={editItem.logic_relation || ''} onChange={e => setEditItem({ ...editItem, logic_relation: e.target.value })}
              disabled={isEditing} className={`${inputCls} ${isEditing ? 'bg-gray-50 text-gray-500' : ''}`} placeholder="semi:belongsToLot" />
          </Field>

          <Field label="描述">
            <input value={editItem.description || ''} onChange={e => setEditItem({ ...editItem, description: e.target.value })}
              className={inputCls} placeholder="XXX 表通过 xxx_id 关联 YYY 表" />
          </Field>

          <Field label="策略" required>
            <select value={editItem.strategy || 'ForeignKey'} onChange={e => setEditItem({ ...editItem, strategy: e.target.value, join_logic: {} })}
              className={inputCls}>
              {STRATEGIES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>

          <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 space-y-3">
            <p className="text-xs font-medium text-gray-500 uppercase">Join Logic（{editItem.strategy}）</p>
            {renderJoinLogicForm()}
          </div>
        </Modal>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// Tab 3: Value Mappings
// ══════════════════════════════════════════════════════════════════

function ValueMappingsTab() {
  const [domains, setDomains] = useState<ValueDomain[]>([]);
  const [expandedDomain, setExpandedDomain] = useState<string | null>(null);
  const [domainValues, setDomainValues] = useState<Record<string, ValueEntry[]>>({});
  const [loading, setLoading] = useState(false);
  const [editingEntry, setEditingEntry] = useState<{ domain: string; sv: string; data: Partial<ValueEntry> } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await mappingApi.getValueDomains();
      setDomains(res.data || []);
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  }, []);

  const loadDomain = useCallback(async (domain: string) => {
    if (domainValues[domain]) return;
    try {
      const res = await mappingApi.getValueDomain(domain);
      // API returns {data: {"SV": {...fields}}} — transform to array
      const raw = res.data || {};
      const entries: ValueEntry[] = Object.entries(raw).map(([sv, info]: [string, any]) => ({
        semantic_value: sv,
        ...info,
      }));
      setDomainValues(prev => ({ ...prev, [domain]: entries }));
    } catch (e: any) {
      setError(e.message);
    }
  }, [domainValues]);

  useEffect(() => { load(); }, []);

  const handleExpand = async (domain: string) => {
    if (expandedDomain === domain) {
      setExpandedDomain(null);
      return;
    }
    setExpandedDomain(domain);
    await loadDomain(domain);
  };

  const openEdit = (domain: string, entry: ValueEntry) => {
    setEditingEntry({ domain, sv: entry.semantic_value, data: { ...entry } });
  };

  const handleSaveValue = async () => {
    if (!editingEntry) return;
    setSaving(true);
    setError('');
    try {
      const { semantic_value, ...rest } = editingEntry.data as any;
      await mappingApi.upsertValue(editingEntry.domain, editingEntry.sv, rest);
      // refresh domain
      const res = await mappingApi.getValueDomain(editingEntry.domain);
      const raw = res.data || {};
      const entries: ValueEntry[] = Object.entries(raw).map(([sv, info]: [string, any]) => ({ semantic_value: sv, ...info }));
      setDomainValues(prev => ({ ...prev, [editingEntry.domain]: entries }));
      setEditingEntry(null);
    } catch (e: any) {
      setError(e.message);
    }
    setSaving(false);
  };

  const handleDeleteValue = async (domain: string, sv: string) => {
    if (!confirm(`删除 ${domain}/${sv}？`)) return;
    try {
      await mappingApi.deleteValue(domain, sv);
      const res = await mappingApi.getValueDomain(domain);
      const raw = res.data || {};
      const entries: ValueEntry[] = Object.entries(raw).map(([sv2, info]: [string, any]) => ({ semantic_value: sv2, ...info }));
      setDomainValues(prev => ({ ...prev, [domain]: entries }));
    } catch (e: any) {
      alert(e.message);
    }
  };

  const isTodo = (val: any): boolean =>
    typeof val === 'string' && val.includes('TODO');

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500">{domains.length} 个语义域</p>
        <button onClick={load} className="p-2 text-gray-500 border border-gray-300 rounded-lg hover:bg-gray-50">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg">{error}</div>}

      {loading && <div className="py-8 text-center text-gray-400">加载中...</div>}

      {domains.map(d => {
        const values = domainValues[d.domain] || [];
        const hasTodo = values.some(v => Object.values(v).some(isTodo));
        return (
          <div key={d.domain} className="border border-gray-200 rounded-xl overflow-hidden">
            {/* Domain header */}
            <button
              onClick={() => handleExpand(d.domain)}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center gap-3">
                {expandedDomain === d.domain ? <ChevronDown size={16} className="text-gray-400" /> : <ChevronRight size={16} className="text-gray-400" />}
                <span className="font-mono text-sm text-blue-700">{d.domain}</span>
                {hasTodo && <Badge text="包含 TODO" colorCls="bg-yellow-100 text-yellow-700" />}
              </div>
              <span className="text-xs text-gray-400">{d.value_count} 个值</span>
            </button>

            {/* Values */}
            {expandedDomain === d.domain && (
              <div className="border-t border-gray-100">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">语义值</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">描述</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">physical_condition</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">表 / 列</th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {values.map(entry => {
                      const todo = isTodo(entry.physical_condition);
                      return (
                        <tr key={entry.semantic_value} className={`hover:bg-gray-50 ${todo ? 'bg-yellow-50/40' : ''}`}>
                          <td className="px-4 py-2.5 font-mono text-xs font-medium text-purple-700">{entry.semantic_value}</td>
                          <td className="px-4 py-2.5 text-gray-600 text-xs">{entry.description || '—'}</td>
                          <td className="px-4 py-2.5 font-mono text-xs max-w-[200px] truncate" title={entry.physical_condition}>
                            {todo
                              ? <span className="text-yellow-600 flex items-center gap-1"><AlertCircle size={12} /> TODO</span>
                              : <span className="text-gray-600">{entry.physical_condition || '—'}</span>
                            }
                          </td>
                          <td className="px-4 py-2.5 text-xs text-gray-400">
                            {entry.applies_to_table ? `${entry.applies_to_table}.${entry.applies_to_column}` : '—'}
                          </td>
                          <td className="px-4 py-2.5 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <button onClick={() => openEdit(d.domain, entry)} className="p-1 text-gray-400 hover:text-blue-600"><Edit2 size={13} /></button>
                              <button onClick={() => handleDeleteValue(d.domain, entry.semantic_value)} className="p-1 text-gray-400 hover:text-red-600"><Trash2 size={13} /></button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}

      {/* Edit value modal */}
      {editingEntry && (
        <Modal
          title={`编辑值条目: ${editingEntry.domain} / ${editingEntry.sv}`}
          onClose={() => setEditingEntry(null)}
          onConfirm={handleSaveValue}
          confirmText={saving ? '保存中...' : '保存'}
        >
          {error && <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg">{error}</div>}
          <Field label="描述">
            <input value={editingEntry.data.description || ''} onChange={e => setEditingEntry({ ...editingEntry, data: { ...editingEntry.data, description: e.target.value } })} className={inputCls} />
          </Field>
          <Field label="physical_condition" hint="例：local_production_batch.status = 1">
            <input value={editingEntry.data.physical_condition || ''} onChange={e => setEditingEntry({ ...editingEntry, data: { ...editingEntry.data, physical_condition: e.target.value } })} className={`${inputCls} font-mono`} placeholder="table.column = value" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="applies_to_table">
              <input value={editingEntry.data.applies_to_table || ''} onChange={e => setEditingEntry({ ...editingEntry, data: { ...editingEntry.data, applies_to_table: e.target.value } })} className={inputCls} />
            </Field>
            <Field label="applies_to_column">
              <input value={editingEntry.data.applies_to_column || ''} onChange={e => setEditingEntry({ ...editingEntry, data: { ...editingEntry.data, applies_to_column: e.target.value } })} className={inputCls} />
            </Field>
          </div>
          <Field label="备注 / Note">
            <input value={editingEntry.data.note || ''} onChange={e => setEditingEntry({ ...editingEntry, data: { ...editingEntry.data, note: e.target.value } })} className={inputCls} />
          </Field>
        </Modal>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// Tab 4: Business Rules
// ══════════════════════════════════════════════════════════════════

function BusinessRulesTab() {
  const [items, setItems] = useState<BusinessRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editItem, setEditItem] = useState<Partial<BusinessRule> | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async (q = search) => {
    setLoading(true);
    try {
      const res = await mappingApi.getRules({ q });
      setItems(res.data || []);
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, []);

  const openAdd = () => {
    setEditItem({ id: '', name: '', description: '', trigger_keywords: [], physical_sql_template: '', involved_tables: [], warning_tables: [] });
    setIsEditing(false);
    setShowModal(true);
  };

  const openEdit = (item: BusinessRule) => {
    setEditItem({ ...item });
    setIsEditing(true);
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!editItem) return;
    setSaving(true);
    setError('');
    try {
      const payload = {
        ...editItem,
        trigger_keywords: typeof editItem.trigger_keywords === 'string'
          ? (editItem.trigger_keywords as any).split(',').map((s: string) => s.trim()).filter(Boolean)
          : editItem.trigger_keywords,
        involved_tables: typeof editItem.involved_tables === 'string'
          ? (editItem.involved_tables as any).split(',').map((s: string) => s.trim()).filter(Boolean)
          : editItem.involved_tables,
        warning_tables: typeof editItem.warning_tables === 'string'
          ? (editItem.warning_tables as any).split(',').map((s: string) => s.trim()).filter(Boolean)
          : editItem.warning_tables,
      };
      if (isEditing) {
        await mappingApi.updateRule(editItem.id!, payload);
      } else {
        await mappingApi.createRule(payload);
      }
      setShowModal(false);
      load();
    } catch (e: any) {
      setError(e.message);
    }
    setSaving(false);
  };

  const handleDelete = async (id: string) => {
    if (!confirm(`删除业务规则 ${id}？`)) return;
    try { await mappingApi.deleteRule(id); load(); } catch (e: any) { alert(e.message); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={e => { setSearch(e.target.value); load(e.target.value); }}
            placeholder="搜索规则 ID / 关键词..." className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50" />
        </div>
        <button onClick={() => load()} className="p-2 text-gray-500 border border-gray-300 rounded-lg hover:bg-gray-50">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
        <button onClick={openAdd} className="flex items-center gap-2 px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700">
          <Plus size={16} />添加
        </button>
      </div>

      {items.length === 0 && !loading && (
        <div className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center text-gray-400">
          <FileText size={32} className="mx-auto mb-3 opacity-40" />
          <p className="text-sm">暂无业务规则</p>
          <p className="text-xs mt-1">切换到生产库后，将已验证的 SQL 查询模板录入此处</p>
        </div>
      )}

      <div className="space-y-3">
        {items.map(item => (
          <div key={item.id} className="border border-gray-200 rounded-xl p-4 space-y-2">
            <div className="flex items-start justify-between">
              <div>
                <span className="font-mono text-sm font-medium text-blue-700">{item.id}</span>
                {item.name && <span className="ml-2 text-sm text-gray-700">{item.name}</span>}
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => openEdit(item)} className="p-1 text-gray-400 hover:text-blue-600"><Edit2 size={14} /></button>
                <button onClick={() => handleDelete(item.id)} className="p-1 text-gray-400 hover:text-red-600"><Trash2 size={14} /></button>
              </div>
            </div>
            {item.description && <p className="text-xs text-gray-600">{item.description}</p>}
            {item.trigger_keywords?.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {item.trigger_keywords.map(kw => (
                  <span key={kw} className="px-2 py-0.5 text-xs bg-blue-50 text-blue-600 rounded-full">{kw}</span>
                ))}
              </div>
            )}
            {item.physical_sql_template && (
              <pre className="text-xs text-gray-500 bg-gray-50 rounded-lg p-2 overflow-x-auto max-h-24">
                {item.physical_sql_template}
              </pre>
            )}
          </div>
        ))}
      </div>

      {showModal && editItem && (
        <Modal title={isEditing ? `编辑规则：${editItem.id}` : '新增业务规则'} onClose={() => setShowModal(false)} onConfirm={handleSave} confirmText={saving ? '保存中...' : '保存'} wide>
          {error && <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg">{error}</div>}
          <div className="grid grid-cols-2 gap-4">
            <Field label="规则 ID" required hint="唯一标识，如 wip_count_by_station">
              <input value={editItem.id || ''} onChange={e => setEditItem({ ...editItem, id: e.target.value })} disabled={isEditing} className={`${inputCls} ${isEditing ? 'bg-gray-50 text-gray-500' : ''}`} placeholder="wip_count_by_station" />
            </Field>
            <Field label="规则名称">
              <input value={editItem.name || ''} onChange={e => setEditItem({ ...editItem, name: e.target.value })} className={inputCls} placeholder="各工站在制品数量" />
            </Field>
          </div>
          <Field label="描述">
            <input value={editItem.description || ''} onChange={e => setEditItem({ ...editItem, description: e.target.value })} className={inputCls} />
          </Field>
          <Field label="触发关键词（逗号分隔）" hint="用户查询包含任意一个关键词时触发">
            <input value={Array.isArray(editItem.trigger_keywords) ? editItem.trigger_keywords.join(', ') : editItem.trigger_keywords || ''} onChange={e => setEditItem({ ...editItem, trigger_keywords: e.target.value as any })} className={inputCls} placeholder="在制品, WIP, 各工站" />
          </Field>
          <Field label="SQL 模板" hint="可用 {参数名} 作为占位符，注入 LLM Prompt 作为强提示">
            <textarea value={editItem.physical_sql_template || ''} onChange={e => setEditItem({ ...editItem, physical_sql_template: e.target.value })} className={`${textareaCls} min-h-[120px]`} placeholder="SELECT ... FROM ... WHERE ..." />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="涉及表（逗号分隔）">
              <input value={Array.isArray(editItem.involved_tables) ? editItem.involved_tables.join(', ') : editItem.involved_tables || ''} onChange={e => setEditItem({ ...editItem, involved_tables: e.target.value as any })} className={inputCls} />
            </Field>
            <Field label="警戒表（逗号分隔）" hint="LLM 容易误用的表">
              <input value={Array.isArray(editItem.warning_tables) ? editItem.warning_tables.join(', ') : editItem.warning_tables || ''} onChange={e => setEditItem({ ...editItem, warning_tables: e.target.value as any })} className={inputCls} />
            </Field>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// Tab 5: Changelog
// ══════════════════════════════════════════════════════════════════

function ChangelogTab() {
  const [records, setRecords] = useState<ChangelogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [filterType, setFilterType] = useState('');
  const [filterAction, setFilterAction] = useState('');
  const [expandedKey, setExpandedKey] = useState<string | null>(null);

  const PAGE_SIZE = 50;

  const load = useCallback(async (p = page) => {
    setLoading(true);
    try {
      const res = await mappingApi.getChangelog({ page: p, page_size: PAGE_SIZE, entry_type: filterType || undefined, action: filterAction || undefined });
      setRecords(res.data || []);
      setTotal(res.total || 0);
    } catch { }
    setLoading(false);
  }, [page, filterType, filterAction]);

  useEffect(() => { load(); }, [filterType, filterAction]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <select value={filterType} onChange={e => { setFilterType(e.target.value); setPage(1); }} className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none">
          <option value="">全部类型</option>
          <option value="object_mapping">对象映射</option>
          <option value="relation_mapping">关系映射</option>
          <option value="value_mapping">值映射</option>
          <option value="business_rule">业务规则</option>
        </select>
        <select value={filterAction} onChange={e => { setFilterAction(e.target.value); setPage(1); }} className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none">
          <option value="">全部操作</option>
          <option value="create">创建</option>
          <option value="update">更新</option>
          <option value="delete">删除</option>
        </select>
        <button onClick={() => load()} className="p-2 text-gray-500 border border-gray-300 rounded-lg hover:bg-gray-50">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
        <span className="text-xs text-gray-400">共 {total} 条</span>
      </div>

      {loading && <div className="py-8 text-center text-gray-400">加载中...</div>}
      {!loading && records.length === 0 && <div className="py-8 text-center text-gray-400">暂无变更记录</div>}

      <div className="space-y-2">
        {records.map((rec, i) => {
          const recKey = `${rec.timestamp}-${i}`;
          return (
            <div key={recKey} className="border border-gray-200 rounded-xl overflow-hidden">
              <button onClick={() => setExpandedKey(expandedKey === recKey ? null : recKey)} className="w-full flex items-center gap-3 p-3 hover:bg-gray-50 text-left">
                <Badge text={rec.action} colorCls={ACTION_COLORS[rec.action] || 'bg-gray-100 text-gray-600'} />
                <span className="text-xs text-gray-500 font-mono">{rec.entry_type}</span>
                <span className="text-sm text-gray-800 font-medium flex-1 truncate">{rec.key}</span>
                <span className="text-xs text-gray-400 whitespace-nowrap">{new Date(rec.timestamp).toLocaleString()}</span>
                {expandedKey === recKey ? <ChevronDown size={14} className="text-gray-400 flex-shrink-0" /> : <ChevronRight size={14} className="text-gray-400 flex-shrink-0" />}
              </button>
              {expandedKey === recKey && (
                <div className="border-t border-gray-100 p-4 grid grid-cols-2 gap-4">
                  {rec.before !== undefined && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-1">变更前 (before)</p>
                      <pre className="text-xs bg-red-50 text-red-700 rounded-lg p-3 overflow-x-auto max-h-60">
                        {JSON.stringify(rec.before, null, 2)}
                      </pre>
                    </div>
                  )}
                  {rec.after !== undefined && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-1">变更后 (after)</p>
                      <pre className="text-xs bg-green-50 text-green-700 rounded-lg p-3 overflow-x-auto max-h-60">
                        {JSON.stringify(rec.after, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-500">
          <span>第 {page} / {totalPages} 页</span>
          <div className="flex gap-2">
            <button disabled={page <= 1} onClick={() => { setPage(page - 1); load(page - 1); }} className="px-3 py-1 border rounded-lg disabled:opacity-40 hover:bg-gray-50">上一页</button>
            <button disabled={page >= totalPages} onClick={() => { setPage(page + 1); load(page + 1); }} className="px-3 py-1 border rounded-lg disabled:opacity-40 hover:bg-gray-50">下一页</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// Main Component
// ══════════════════════════════════════════════════════════════════

export default function MappingManager() {
  const [tab, setTab] = useState<Tab>('objects');
  const [summary, setSummary] = useState<Summary | null>(null);

  useEffect(() => {
    mappingApi.getSummary()
      .then(res => setSummary(res.data))
      .catch(() => { });
  }, []);

  const TABS: { key: Tab; label: string; icon: React.ReactNode; count?: number }[] = [
    { key: 'objects',   label: '对象映射',  icon: <Database size={15} />,    count: summary?.object_mappings },
    { key: 'relations', label: '关系映射',  icon: <GitBranch size={15} />,   count: summary?.relation_mappings },
    { key: 'values',    label: '值映射',    icon: <Tag size={15} />,          count: summary?.value_domains },
    { key: 'rules',     label: '业务规则',  icon: <Book size={15} />,         count: summary?.business_rules },
    { key: 'changelog', label: '变更记录',  icon: <History size={15} /> },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="w-full p-6 space-y-6">

        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">映射字典管理</h1>
            {summary && (
              <p className="text-sm text-gray-500 mt-1">
                {summary.customer} · v{summary.version} ·&nbsp;
                <span className="font-mono text-xs">{summary.mapping_file.split('/').pop()}</span>
              </p>
            )}
          </div>

        </div>



        {/* Tabs */}
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          {/* Tab nav */}
          <div className="flex border-b border-gray-200 overflow-x-auto">
            {TABS.map(t => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`flex items-center gap-2 px-5 py-3.5 text-sm font-medium whitespace-nowrap transition-colors ${
                  tab === t.key
                    ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50/30'
                    : 'text-gray-500 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                {t.icon}
                {t.label}
                {t.count !== undefined && (
                  <span className={`text-xs px-1.5 py-0.5 rounded-full ${tab === t.key ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'}`}>
                    {t.count}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="p-6">
            {tab === 'objects'   && <ObjectMappingsTab />}
            {tab === 'relations' && <RelationMappingsTab />}
            {tab === 'values'    && <ValueMappingsTab />}
            {tab === 'rules'     && <BusinessRulesTab />}
            {tab === 'changelog' && <ChangelogTab />}
          </div>
        </div>
      </div>
    </div>
  );
}