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
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import mermaid from 'mermaid';
import {
  Plus, Search, RefreshCw, Trash2, Edit2, ChevronDown, ChevronRight,
  History, Database, GitBranch, Tag, FileText, AlertCircle, X, Check,
  Book, BarChart2, Link2, Eye
} from 'lucide-react';
import { mappingApi } from '../services/mappingApi';
import { ontologyApi } from '../services/ontologyApi';

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
  /** 虚拟类子类型: action_event | EmbeddedJSON */
  virtual_kind?: string | null;
  /** EmbeddedJSON: 宿主物理表，如 product_model */
  embedded_in?: string | null;
  /** EmbeddedJSON: JSON 列名，如 main_route */
  source_json_column?: string | null;
  /** EmbeddedJSON: JSONPath 表达式，如 $.processes[*].measurementParamList[*] */
  source_json_path?: string | null;
  note?: string;
}

interface RelationMapping {
  logic_relation: string;
  description: string;
  strategy: string;
  join_logic: Record<string, any>;
  per_record_type_join?: Record<string, { strategy: string; description?: string; join_logic: Record<string, any> }>;
  applicable_record_types?: string[];
  domain_class?: string;
  range_class?: string;
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

interface MetricDefinition {
  metric_id: string;
  zh_names: string[];
  anchor_table: string;
  formula: string;
  granularity: string[];
  description: string;
  join_path?: string | null;
  auto_filter?: string | null;
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
  metric_definitions: number;
}

type Tab = 'objects' | 'relations' | 'values' | 'rules' | 'metrics' | 'changelog';

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
  ForeignKey:    'bg-blue-100 text-blue-700',
  JoinVia:       'bg-cyan-100 text-cyan-700',
  JoinTable:     'bg-purple-100 text-purple-700',
  CompositeKey:  'bg-indigo-100 text-indigo-700',
  Indirect:      'bg-orange-100 text-orange-700',
  Recursive:     'bg-green-100 text-green-700',
  Denormalized:  'bg-gray-100 text-gray-600',
  EmbeddedJSON:  'bg-teal-100 text-teal-700',
  EmbeddedJSON_FK: 'bg-teal-100 text-teal-600',
  EventLog:      'bg-yellow-100 text-yellow-700',
  ValueLookup:   'bg-pink-100 text-pink-700',
  Virtual:       'bg-gray-100 text-gray-400',
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
// Helper: PropertiesAndColumnsEditor
// 替代原先的 Key Columns 纯文本框，分为:
//   上半部分 — 语义属性绑定 (properties: sem:hasX → physical_col)
//   下半部分 — 完整列清单   (key_columns, 逗号分隔)
// ══════════════════════════════════════════════════════════════════

interface DataProperty {
  uri: string;
  label: string;
  comment: string;
  range_type: string;
  domain_uris: string[];
}

interface PropRow {
  id: number;
  semProp: string;
  physCol: string;
}

function PropertiesAndColumnsEditor({
  properties,
  onPropertiesChange,
  keyColsStr,
  onKeyColsChange,
  logicClass,
}: {
  properties: Record<string, string | null>;
  onPropertiesChange: (p: Record<string, string | null>) => void;
  keyColsStr: string;
  onKeyColsChange: (s: string) => void;
  logicClass?: string;
}) {
  const [dataProps, setDataProps] = useState<DataProperty[]>([]);
  const [loadingDp, setLoadingDp] = useState(false);
  const [rows, setRows] = useState<PropRow[]>([]);
  const nextId = React.useRef(0);

  // 从 properties dict 初始化行
  useEffect(() => {
    const initial: PropRow[] = Object.entries(properties || {}).map(([k, v]) => ({
      id: nextId.current++,
      semProp: k,
      physCol: v ?? '',
    }));
    setRows(initial);
  }, []); // 仅初始化一次

  // 拉取本体数据属性列表
  useEffect(() => {
    setLoadingDp(true);
    ontologyApi.getDataProperties()
      .then((data: DataProperty[]) => setDataProps(data))
      .catch(() => setDataProps([]))
      .finally(() => setLoadingDp(false));
  }, []);

  // 把 rows 同步回 properties dict
  const syncUp = (newRows: PropRow[]) => {
    const dict: Record<string, string | null> = {};
    newRows.forEach(r => {
      if (r.semProp.trim()) {
        dict[r.semProp.trim()] = r.physCol.trim() || null;
      }
    });
    onPropertiesChange(dict);
  };

  const updateRow = (id: number, field: 'semProp' | 'physCol', value: string) => {
    const updated = rows.map(r => r.id === id ? { ...r, [field]: value } : r);
    setRows(updated);
    syncUp(updated);
  };

  const addRow = () => {
    const newRow: PropRow = { id: nextId.current++, semProp: '', physCol: '' };
    const updated = [...rows, newRow];
    setRows(updated);
    syncUp(updated);
  };

  const removeRow = (id: number) => {
    const updated = rows.filter(r => r.id !== id);
    setRows(updated);
    syncUp(updated);
  };

  // 快速推断：根据 logicClass 过滤出域包含该类的属性（优先显示）
  const relevantProps = useMemo(() => {
    if (!logicClass || dataProps.length === 0) return dataProps;
    const cls = logicClass.startsWith('semi:') ? logicClass : `semi:${logicClass}`;
    const relevant = dataProps.filter(p =>
      p.domain_uris.length === 0 || p.domain_uris.includes(cls)
    );
    const others = dataProps.filter(p =>
      p.domain_uris.length > 0 && !p.domain_uris.includes(cls)
    );
    return [...relevant, ...others];
  }, [dataProps, logicClass]);

  const alreadyBound = new Set(rows.map(r => r.semProp).filter(Boolean));

  return (
    <div className="space-y-4">
      {/* ─── Section 1: 语义属性绑定 ─── */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Link2 size={14} className="text-blue-500" />
            <span className="text-sm font-medium text-gray-700">语义属性绑定</span>
            <span className="text-xs text-gray-400 ml-1">
              (DatatypeProperty → 物理列，LLM 读取此映射理解字段业务含义)
            </span>
          </div>
          <button
            type="button"
            onClick={addRow}
            className="flex items-center gap-1 px-2 py-1 text-xs text-blue-600 border border-blue-300 rounded-md hover:bg-blue-50 transition-colors"
          >
            <Plus size={12} /> 添加绑定
          </button>
        </div>

        {rows.length === 0 ? (
          <div className="flex items-center justify-center h-16 border border-dashed border-gray-200 rounded-lg text-xs text-gray-400">
            暂无语义绑定 — 点击「添加绑定」开始
          </div>
        ) : (
          <div className="border border-gray-200 rounded-lg overflow-hidden">
            {/* Header */}
            <div className="grid grid-cols-[1fr_auto_1fr_auto] bg-gray-50 border-b border-gray-200 px-3 py-2 text-xs font-medium text-gray-500 uppercase gap-2">
              <span>本体属性 (DatatypeProperty)</span>
              <span className="w-5 text-center text-gray-300">→</span>
              <span>物理列</span>
              <span className="w-6" />
            </div>
            {/* Rows */}
            <div className="divide-y divide-gray-100">
              {rows.map(row => {
                const matched = dataProps.find(p => p.uri === row.semProp);
                return (
                  <div
                    key={row.id}
                    className="grid grid-cols-[1fr_auto_1fr_auto] items-center gap-2 px-3 py-2 hover:bg-gray-50"
                  >
                    {/* Semantic property */}
                    <div className="relative">
                      <input
                        list={`dp-list-${row.id}`}
                        value={row.semProp}
                        onChange={e => updateRow(row.id, 'semProp', e.target.value)}
                        placeholder="semi:hasState"
                        className="w-full px-2 py-1.5 text-xs font-mono border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500/40"
                      />
                      <datalist id={`dp-list-${row.id}`}>
                        {relevantProps
                          .filter(p => !alreadyBound.has(p.uri) || p.uri === row.semProp)
                          .map(p => (
                            <option key={p.uri} value={p.uri}>{p.label} ({p.range_type})</option>
                          ))}
                      </datalist>

                    </div>
                    {/* Arrow */}
                    <span className="text-gray-300 text-sm self-start mt-2">→</span>
                    {/* Physical column */}
                    <input
                      value={row.physCol}
                      onChange={e => updateRow(row.id, 'physCol', e.target.value)}
                      placeholder="status"
                      className="w-full px-2 py-1.5 text-xs font-mono border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500/40 self-start"
                    />
                    {/* Delete */}
                    <button
                      type="button"
                      onClick={() => removeRow(row.id)}
                      className="self-start mt-1.5 p-1 text-gray-300 hover:text-red-500 transition-colors"
                      title="删除此绑定"
                    >
                      <X size={14} />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}
        {loadingDp && (
          <p className="text-[10px] text-gray-400 flex items-center gap-1">
            <RefreshCw size={10} className="animate-spin" /> 加载本体属性列表…
          </p>
        )}
      </div>

      {/* ─── Section 2: 完整列清单 ─── */}
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Database size={14} className="text-gray-400" />
          <span className="text-sm font-medium text-gray-700">完整列清单 (key_columns)</span>
        </div>
        <textarea
          value={keyColsStr}
          onChange={e => onKeyColsChange(e.target.value)}
          className={textareaCls}
          rows={3}
          placeholder="id, status, current_lot_code, gmt_create, ..."
        />
        <p className="text-xs text-gray-400">
          所有列名（逗号分隔）。包含已绑定语义属性的列和其余原始列，完整提供给 LLM schema 上下文使用。
        </p>
      </div>
    </div>
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
      key_columns: [], properties: {},
      virtual: false, virtual_kind: '', embedded_in: '', source_json_column: '', source_json_path: '',
      note: '',
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
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">语义属性 / 列</th>
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
                  {item.physical_table ? (
                    <>
                      {item.physical_table}
                      {item.filter_condition && (
                        <span className="ml-2 px-1.5 py-0.5 text-[10px] font-medium bg-amber-100 text-amber-700 rounded">
                          WHERE {item.filter_condition}
                        </span>
                      )}
                    </>
                  ) : item.virtual_kind === 'EmbeddedJSON' ? (
                    <div className="space-y-0.5">
                      <span className="inline-block px-1.5 py-0.5 text-[10px] font-medium bg-teal-100 text-teal-700 rounded">
                        EmbeddedJSON
                      </span>
                      {item.embedded_in && (
                        <div className="text-gray-500 leading-tight">
                          <span className="text-gray-700">{item.embedded_in}</span>
                          {item.source_json_column && (
                            <span className="text-gray-400">.{item.source_json_column}</span>
                          )}
                        </div>
                      )}
                      {item.source_json_path && (
                        <div className="text-[10px] text-teal-600 font-mono break-all leading-tight max-w-[220px]">
                          {item.source_json_path}
                        </div>
                      )}
                    </div>
                  ) : (
                    <span className="text-gray-300 italic">virtual</span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-800">{item.label_cn}</td>
                <td className="px-4 py-3 font-mono text-xs text-gray-500">{item.display_column || '—'}</td>
                <td className="px-4 py-3 text-xs">
                  <div className="flex items-center gap-2">
                    {Object.keys(item.properties || {}).length > 0 && (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded text-[10px] font-medium">
                        <Link2 size={10} />
                        {Object.keys(item.properties).length} 语义属性
                      </span>
                    )}
                    <span className="text-gray-400">{(item.key_columns || []).length} 列</span>
                  </div>
                </td>
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

          <PropertiesAndColumnsEditor
            properties={editItem.properties || {}}
            onPropertiesChange={props => setEditItem({ ...editItem, properties: props })}
            keyColsStr={keyColsStr}
            onKeyColsChange={v => setEditItem({ ...editItem, key_columns: v as any })}
            logicClass={editItem.logic_class}
          />

          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="virtual-cb"
                checked={!!editItem.virtual}
                onChange={e => setEditItem({
                  ...editItem,
                  virtual: e.target.checked,
                  // 取消虚拟时清除虚拟类专属字段
                  ...(e.target.checked ? {} : {
                    virtual_kind: '', embedded_in: '', source_json_column: '', source_json_path: ''
                  })
                })}
                className="w-4 h-4 rounded border-gray-300"
              />
              <label htmlFor="virtual-cb" className="text-sm text-gray-700">
                虚拟类（无对应物理表）
              </label>
            </div>

            {editItem.virtual && (
              <div className="pl-6 space-y-3 border-l-2 border-gray-200">
                <Field label="虚拟类型（virtual_kind）" hint="EmbeddedJSON = 嵌入 JSON 列；action_event = 抽象事件类">
                  <select
                    value={editItem.virtual_kind || ''}
                    onChange={e => setEditItem({ ...editItem, virtual_kind: e.target.value || null })}
                    className={inputCls}
                  >
                    <option value="">— 请选择 —</option>
                    <option value="EmbeddedJSON">EmbeddedJSON（嵌入 JSON 字段）</option>
                    <option value="action_event">action_event（抽象事件/抽象父类）</option>
                  </select>
                </Field>

                {editItem.virtual_kind === 'EmbeddedJSON' && (
                  <div className="space-y-3 p-3 bg-teal-50 rounded-lg border border-teal-200">
                    <p className="text-xs font-medium text-teal-700">EmbeddedJSON 数据源配置</p>
                    <Field label="宿主表（embedded_in）" hint="承载 JSON 列的物理表，如 product_model">
                      <input
                        value={editItem.embedded_in || ''}
                        onChange={e => setEditItem({ ...editItem, embedded_in: e.target.value })}
                        className={inputCls}
                        placeholder="product_model"
                      />
                    </Field>
                    <Field label="JSON 列名（source_json_column）" hint="存储 JSON 的列名，如 main_route">
                      <input
                        value={editItem.source_json_column || ''}
                        onChange={e => setEditItem({ ...editItem, source_json_column: e.target.value })}
                        className={inputCls}
                        placeholder="main_route"
                      />
                    </Field>
                    <Field
                      label="JSONPath（source_json_path）"
                      hint="定位嵌入数组元素的路径，如 $.processes[*].measurementParamList[*]"
                    >
                      <input
                        value={editItem.source_json_path || ''}
                        onChange={e => setEditItem({ ...editItem, source_json_path: e.target.value })}
                        className={`${inputCls} font-mono`}
                        placeholder="$.processes[*].measurementParamList[*]"
                      />
                    </Field>
                    <div className="text-xs text-teal-600 bg-teal-100 rounded p-2 leading-relaxed">
                      <strong>数据来源预览：</strong>
                      {editItem.embedded_in && editItem.source_json_column ? (
                        <span className="font-mono ml-1">
                          {editItem.embedded_in}.{editItem.source_json_column}
                          {editItem.source_json_path ? ` → ${editItem.source_json_path}` : ''}
                        </span>
                      ) : (
                        <span className="text-teal-400 ml-1">填写宿主表和列名后显示</span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
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

const STRATEGIES = [
  'ForeignKey',
  'JoinVia',
  'JoinTable',
  'CompositeKey',
  'Indirect',
  'Recursive',
  'Denormalized',
  'EmbeddedJSON',
  'EmbeddedJSON_FK',
  'EventLog',
  'ValueLookup',
  'Virtual',
  'per_record_type',
];

type RelationViewMode = 'list' | 'path';
type RelationLayer = 'event' | 'snapshot' | 'entity';

interface ScenarioPreset {
  id: string;
  label: string;
  description: string;
  chains: string[][];
}

const SCENARIO_PRESETS: ScenarioPreset[] = [
  {
    id: 'split',
    label: '拆批链路',
    description: '拆批事件的事件层→快照层→实体层主路径',
    chains: [
      ['semi:hasTransitionDetail', 'semi:snapshotOfSublot'],
      ['semi:hasWaferTransitionSnapshot', 'semi:transitionSnapshotOfWafer'],
      ['semi:producesLot', 'semi:producesSublot'],
      ['semi:splitsFromSublot', 'semi:chooseSourceWafer', 'semi:assignsWaferToSublot']
    ]
  },
  {
    id: 'genealogy',
    label: '谱系通用链路',
    description: '适用于拆批/并批/攒批等谱系操作的通用快照路径',
    chains: [
      ['semi:hasTransitionDetail', 'semi:snapshotOfSublot', 'semi:transitionSnapshotAtStation'],
      ['semi:hasWaferTransitionSnapshot', 'semi:transitionSnapshotOfWafer', 'semi:transitionSnapshotInSublot']
    ]
  },
  {
    id: 'measurement',
    label: '量测链路',
    description: '量测事件与量测快照语义路径',
    chains: [
      ['semi:hasSnapshot', 'semi:snapshotOfWafer'],
      ['semi:hasSnapshot', 'semi:snapshotAtStation'],
      ['semi:hasSnapshot', 'semi:snapshotInLot', 'semi:snapshotInSublot']
    ]
  }
];

function classifyRelationLayer(item: RelationMapping): RelationLayer {
  const d = item.domain_class || '';
  const r = item.range_class || '';
  const rel = item.logic_relation || '';

  if (d.includes('EventRecord') || rel.startsWith('semi:hasTransition') || rel === 'semi:hasSnapshot' || rel === 'semi:hasWaferTransitionSnapshot') {
    return 'event';
  }
  if (d.includes('Snapshot') || r.includes('Snapshot') || rel.includes('Snapshot') || rel.startsWith('semi:snapshot')) {
    return 'snapshot';
  }
  return 'entity';
}

function summarizeJoinLogic(joinLogic: Record<string, any> | undefined): string {
  if (!joinLogic) return '—';
  const parts: string[] = [];
  if (joinLogic.source_table) parts.push(`src:${joinLogic.source_table}`);
  if (joinLogic.source_key) parts.push(`srcKey:${joinLogic.source_key}`);
  if (joinLogic.via_table) parts.push(`via:${joinLogic.via_table}`);
  if (joinLogic.via_source_key) parts.push(`viaSrc:${joinLogic.via_source_key}`);
  if (joinLogic.via_target_key) parts.push(`viaTgt:${joinLogic.via_target_key}`);
  if (joinLogic.filter_condition || joinLogic.via_filter) parts.push(`filter:${joinLogic.filter_condition || joinLogic.via_filter}`);
  if (joinLogic.via2_table) parts.push(`via2:${joinLogic.via2_table}`);
  if (joinLogic.target_table) parts.push(`tgt:${joinLogic.target_table}`);
  if (joinLogic.target_key) parts.push(`tgtKey:${joinLogic.target_key}`);
  if (joinLogic.target_via_expr) parts.push(`expr:${joinLogic.target_via_expr}`);
  return parts.length ? parts.join(' | ') : '—';
}

function summarizePerRecordTypeJoin(
  perJoin: Record<string, { strategy: string; join_logic: Record<string, any> }> | undefined
): string {
  if (!perJoin) return '—';
  return Object.entries(perJoin)
    .map(([type, cfg]) => `${type.replace('semi:', '')}(${cfg.strategy}): ${summarizeJoinLogic(cfg.join_logic)}`)
    .join(' \n');
}

function formatClassName(cls?: unknown): string {
  if (cls === null || cls === undefined) return '—';

  const normalize = (value: unknown) => {
    if (value === null || value === undefined) return '—';
    const text = String(value);
    return text.replace(/^semi:/, '');
  };

  if (Array.isArray(cls)) {
    if (cls.length === 0) return '—';
    return cls.map(normalize).join(' | ');
  }

  return normalize(cls);
}

function getRiskAnalysis(rel: RelationMapping | undefined): { level: 'low' | 'medium' | 'high'; reasons: string[] } {
  if (!rel) return { level: 'high', reasons: ['关系定义缺失'] };

  const reasons: string[] = [];
  const jl = rel.join_logic || {};
  const sourceKey = String(jl.source_key || '');
  const targetKey = String(jl.target_key || '');
  const expr = String(jl.target_via_expr || '');
  const filter = String(jl.via_filter || jl.filter_condition || '');
  const strategy = rel.strategy || '';

  if (strategy === 'Virtual' || strategy === 'EventLog' || strategy === 'Indirect') reasons.push(`策略 ${strategy} 不是稳定的直接 FK 关系`);
  if (strategy === 'JoinVia' || strategy === 'JoinTable' || jl.via2_table) reasons.push('存在中间表/多跳路径，语义依赖路径完整性');
  if (expr || /JSON_EXTRACT|\$\./i.test(expr)) reasons.push('目标值来自 JSON/表达式推导，不是显式外键');
  if (/JSON_EXTRACT|isSource|source|target/i.test(filter)) reasons.push('依赖过滤条件区分源侧/目标侧，语义容易误用');
  if ((sourceKey && !/(^id$|_id$|wafer_id$|batch_resume_log_id$|batch_resume_detail_log_id$)/i.test(sourceKey)) || (targetKey && !/(^id$|_id$|wafer_id$|batch_resume_log_id$|batch_resume_detail_log_id$)/i.test(targetKey))) reasons.push('依赖编码/名称列匹配而非标准 ID 外键');
  if (!rel.domain_class || !rel.range_class) reasons.push('Domain/Range 信息不完整，层级语义需要人工确认');

  if (reasons.length >= 3) return { level: 'high', reasons };
  if (reasons.length >= 1) return { level: 'medium', reasons };
  return { level: 'low', reasons: ['标准直接关系，语义脆弱性较低'] };
}

function getRiskBadgeColor(level: 'low' | 'medium' | 'high'): string {
  if (level === 'high') return 'bg-red-100 text-red-700';
  if (level === 'medium') return 'bg-yellow-100 text-yellow-700';
  return 'bg-green-100 text-green-700';
}

function getRiskLabel(level: 'low' | 'medium' | 'high'): string {
  if (level === 'high') return '高风险边';
  if (level === 'medium') return '中风险边';
  return '低风险边';
}

function buildChainText(preset: ScenarioPreset, relationMap: Map<string, RelationMapping>, review = false, chain?: string[], chainIndex?: number): string {
  const chains = chain ? [chain] : preset.chains;
  const title = chain ? `链路：${(chainIndex || 0) + 1}` : `说明：${preset.description}`;
  const lines: string[] = [`场景：${preset.label}`, title, ''];

  chains.forEach((current, idx) => {
    if (!chain) lines.push(`链路 ${idx + 1}：`);
    current.forEach((relName, stepIndex) => {
      const rel = relationMap.get(relName);
      if (!rel) {
        lines.push(`${stepIndex + 1}. ${relName}（未找到定义）`);
        return;
      }
      const risk = getRiskAnalysis(rel);
      if (!review) {
        lines.push(`${stepIndex + 1}. ${rel.logic_relation} | ${formatClassName(rel.domain_class)} -> ${formatClassName(rel.range_class)} | ${rel.strategy}`);
        lines.push(`   风险：${getRiskLabel(risk.level)} | ${risk.reasons.join('；')}`);
        lines.push(`   JOIN摘要：${rel.strategy === 'per_record_type' ? summarizePerRecordTypeJoin(rel.per_record_type_join) : summarizeJoinLogic(rel.join_logic)}`);
      } else {
        lines.push(`[${stepIndex + 1}] ${rel.logic_relation}`);
        lines.push(`- 层级：${classifyRelationLayer(rel) === 'event' ? '事件层' : classifyRelationLayer(rel) === 'snapshot' ? '快照层' : '实体层'}`);
        lines.push(`- Domain：${rel.domain_class || '—'}`);
        lines.push(`- Range：${rel.range_class || '—'}`);
        lines.push(`- Strategy：${rel.strategy || '—'}`);
        lines.push(`- 风险：${getRiskLabel(risk.level)}`);
        lines.push(`- 风险原因：${risk.reasons.join('；')}`);
        lines.push(`- JOIN摘要：${rel.strategy === 'per_record_type' ? summarizePerRecordTypeJoin(rel.per_record_type_join) : summarizeJoinLogic(rel.join_logic)}`);
        lines.push(`- 描述：${rel.description || '—'}`);
        lines.push('- 审查问题：');
        lines.push('  [ ] 语义是否准确？');
        lines.push('  [ ] 是否跳层？');
        lines.push('  [ ] 物理路径/过滤条件是否可靠？');
        lines.push('  [ ] 是否混淆快照状态与当前状态？');
      }
    });
    lines.push('');
  });
  return lines.join('\n').trim();
}

function buildChainMermaid(preset: ScenarioPreset, relationMap: Map<string, RelationMapping>, chains?: string[][]): string {
  const lines: string[] = ['flowchart LR'];
  const targetChains = chains || preset.chains;
  const sanitize = (value: string) => value.replace(/[^a-zA-Z0-9_]/g, '_');
  targetChains.forEach((chain, chainIndex) => {
    chain.forEach((relName, stepIndex) => {
      const rel = relationMap.get(relName);
      if (!rel) return;
      const domain = formatClassName(rel.domain_class);
      const range = formatClassName(rel.range_class);
      const a = `${sanitize(domain)}_${chainIndex}_${stepIndex}_d`;
      const b = `${sanitize(range)}_${chainIndex}_${stepIndex}_r`;
      lines.push(`  ${a}["${domain}"]`);
      lines.push(`  ${b}["${range}"]`);
      lines.push(`  ${a} -->|${rel.logic_relation}\\n${rel.strategy}| ${b}`);
    });
  });
  lines.push(`  %% ${preset.label}`);
  return lines.join('\n');
}

// ══════════════════════════════════════════════════════════════════
// Mermaid Preview Modal
// ══════════════════════════════════════════════════════════════════

mermaid.initialize({ startOnLoad: false, theme: 'default', flowchart: { curve: 'basis' } });

function MermaidPreviewModal({ code, onClose }: { code: string; onClose: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !code) return;
    const id = `mermaid-preview-${Date.now()}`;
    el.innerHTML = '';
    mermaid.render(id, code)
      .then(({ svg }) => { el.innerHTML = svg; })
      .catch(e => setError(String(e)));
  }, [code]);

  const handleCopy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden m-4"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200">
          <span className="text-sm font-semibold text-gray-800">Mermaid 图预览</span>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="px-3 py-1.5 text-xs border border-emerald-300 rounded-md bg-emerald-600 text-white hover:bg-emerald-700"
            >
              {copied ? '已复制 ✓' : '复制代码'}
            </button>
            <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-gray-700 rounded-md hover:bg-gray-100">
              <X size={18} />
            </button>
          </div>
        </div>
        {/* Diagram */}
        <div className="overflow-auto flex-1 p-6 flex items-start justify-center bg-gray-50">
          {error
            ? <pre className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-4 whitespace-pre-wrap">{error}</pre>
            : <div ref={containerRef} className="[&_svg]:max-w-full [&_svg]:h-auto" />
          }
        </div>
        {/* Raw code */}
        <details className="border-t border-gray-200">
          <summary className="px-5 py-2 text-xs text-gray-500 cursor-pointer select-none hover:bg-gray-50">查看 Mermaid 代码</summary>
          <pre className="px-5 py-3 text-xs text-gray-700 bg-gray-50 overflow-auto max-h-48 whitespace-pre-wrap font-mono">{code}</pre>
        </details>
      </div>
    </div>
  );
}

function matchScenario(item: RelationMapping, scenario: string): boolean {
  if (!scenario) return true;
  const corpus = `${item.logic_relation || ''} ${item.description || ''} ${item.domain_class || ''} ${item.range_class || ''}`.toLowerCase();
  if (scenario === 'split') return /split|拆批|produces|assigns|transition/.test(corpus);
  if (scenario === 'genealogy') return /split|merge|accumulate|谱系|transition|source|target/.test(corpus);
  if (scenario === 'measurement') return /measurement|snapshot|量测|param|process_measure_data/.test(corpus);
  return true;
}

function RelationMappingsTab() {
  const [items, setItems] = useState<RelationMapping[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [filterConf, setFilterConf] = useState('');
  const [viewMode, setViewMode] = useState<RelationViewMode>('list');
  const [layerFilter, setLayerFilter] = useState('');
  const [scenarioFilter, setScenarioFilter] = useState('');
  const [activePreset, setActivePreset] = useState<string>(SCENARIO_PRESETS[0].id);
  const [copyMessage, setCopyMessage] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editItem, setEditItem] = useState<Partial<RelationMapping> | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [mermaidCode, setMermaidCode] = useState<string | null>(null);

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
    const cloned: Partial<RelationMapping> = { ...item, join_logic: { ...(item.join_logic || {}) } };
    if (item.per_record_type_join) {
      cloned.per_record_type_join = Object.fromEntries(
        Object.entries(item.per_record_type_join).map(([k, v]) => [k, { ...v, join_logic: { ...v.join_logic } }])
      );
    }
    setEditItem(cloned);
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

  const filteredItems = useMemo(() => items.filter(item => {
    if (layerFilter && classifyRelationLayer(item) !== layerFilter) return false;
    if (scenarioFilter && !matchScenario(item, scenarioFilter)) return false;
    return true;
  }), [items, layerFilter, scenarioFilter]);

  const groupedItems = useMemo(() => {
    const groups: Record<RelationLayer, RelationMapping[]> = { event: [], snapshot: [], entity: [] };
    filteredItems.forEach(item => groups[classifyRelationLayer(item)].push(item));
    return groups;
  }, [filteredItems]);

  const relationMap = useMemo(() => new Map(items.map(item => [item.logic_relation, item])), [items]);
  const currentPreset = useMemo(() => SCENARIO_PRESETS.find(p => p.id === activePreset) || SCENARIO_PRESETS[0], [activePreset]);

  const copyText = async (text: string, successMsg: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopyMessage(successMsg);
      window.setTimeout(() => setCopyMessage(''), 2500);
    } catch {
      setCopyMessage('复制失败，请检查浏览器剪贴板权限');
      window.setTimeout(() => setCopyMessage(''), 3000);
    }
  };

  // join_logic form varies by strategy
  const renderJoinLogicForm = () => {
    if (!editItem) return null;
    const jl = editItem.join_logic || {};
    const setJl = (key: string, val: any) =>
      setEditItem({ ...editItem, join_logic: { ...jl, [key]: val } });

    if (editItem.strategy === 'per_record_type') {
      const perJoin = editItem.per_record_type_join || {};
      const setPerJoinField = (type: string, key: string, val: any) => {
        const existing = perJoin[type] || { strategy: 'ForeignKey', join_logic: {} };
        setEditItem({
          ...editItem,
          per_record_type_join: {
            ...perJoin,
            [type]: { ...existing, join_logic: { ...existing.join_logic, [key]: val } },
          },
        });
      };
      return (
        <div className="space-y-4">
          <p className="text-xs text-gray-400">每个事件类型独立配置 join_logic（只读展示，如需修改请直接编辑 JSON）</p>
          {Object.entries(perJoin).map(([type, cfg]) => (
            <div key={type} className="border border-blue-100 rounded-lg p-3 bg-blue-50/40">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-semibold text-blue-700 bg-blue-100 rounded px-2 py-0.5">{type.replace('semi:', '')}</span>
                <span className="text-xs text-gray-500">{cfg.strategy}</span>
                {cfg.description && <span className="text-xs text-gray-400 truncate max-w-xs" title={cfg.description}>{cfg.description}</span>}
              </div>
              <pre className="text-xs text-gray-600 bg-white border border-blue-100 rounded p-2 overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(cfg.join_logic, null, 2)}
              </pre>
              <div className="mt-2">
                <Field label={`${type.replace('semi:', '')} join_logic（JSON 编辑）`} hint="修改后回车生效">
                  <textarea
                    defaultValue={JSON.stringify(cfg.join_logic, null, 2)}
                    onChange={e => {
                      try {
                        const parsed = JSON.parse(e.target.value);
                        const existing = perJoin[type] || { strategy: 'ForeignKey', join_logic: {} };
                        setEditItem({
                          ...editItem,
                          per_record_type_join: {
                            ...perJoin,
                            [type]: { ...existing, join_logic: parsed },
                          },
                        });
                      } catch { }
                    }}
                    className={textareaCls}
                    rows={5}
                  />
                </Field>
              </div>
            </div>
          ))}
          <Field label="per_record_type_join（完整 JSON）" hint="直接编辑整个结构">
            <textarea
              defaultValue={JSON.stringify(perJoin, null, 2)}
              onChange={e => {
                try { setEditItem({ ...editItem, per_record_type_join: JSON.parse(e.target.value) }); } catch { }
              }}
              className={textareaCls}
              rows={10}
            />
          </Field>
        </div>
      );
    }

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
      case 'JoinVia':
        return (
          <div className="grid grid-cols-2 gap-3">
            <Field label="source_table"><input value={jl.source_table || ''} onChange={e => setJl('source_table', e.target.value)} className={inputCls} /></Field>
            <Field label="source_key"><input value={jl.source_key || 'id'} onChange={e => setJl('source_key', e.target.value)} className={inputCls} /></Field>
            <Field label="via_table（中间表）"><input value={jl.via_table || ''} onChange={e => setJl('via_table', e.target.value)} className={inputCls} /></Field>
            <Field label="via_source_key"><input value={jl.via_source_key || ''} onChange={e => setJl('via_source_key', e.target.value)} className={inputCls} /></Field>
            <Field label="via_target_key"><input value={jl.via_target_key || ''} onChange={e => setJl('via_target_key', e.target.value)} className={inputCls} /></Field>
            <Field label="filter_condition（可选）" hint="中间表行级过滤，e.g. JSON_EXTRACT(t.extra,'$.isSource')=true"><input value={jl.filter_condition || ''} onChange={e => setJl('filter_condition', e.target.value)} className={inputCls} /></Field>
            <Field label="target_table"><input value={jl.target_table || ''} onChange={e => setJl('target_table', e.target.value)} className={inputCls} /></Field>
            <Field label="target_key"><input value={jl.target_key || ''} onChange={e => setJl('target_key', e.target.value)} className={inputCls} /></Field>
            <Field label="via2_table（第二跳，可选）"><input value={jl.via2_table || ''} onChange={e => setJl('via2_table', e.target.value)} className={inputCls} /></Field>
            <Field label="via2_source_key"><input value={jl.via2_source_key || ''} onChange={e => setJl('via2_source_key', e.target.value)} className={inputCls} /></Field>
            <Field label="via2_target_key"><input value={jl.via2_target_key || ''} onChange={e => setJl('via2_target_key', e.target.value)} className={inputCls} /></Field>
            <Field label="备注" hint="可选"><input value={jl.note || ''} onChange={e => setJl('note', e.target.value)} className={inputCls} /></Field>
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
      case 'EmbeddedJSON':
        return (
          <div className="grid grid-cols-2 gap-3">
            <Field label="source_table"><input value={jl.source_table || ''} onChange={e => setJl('source_table', e.target.value)} className={inputCls} placeholder="matrix_routerx_config_route" /></Field>
            <Field label="jsonb_column（JSON 列名）"><input value={jl.jsonb_column || ''} onChange={e => setJl('jsonb_column', e.target.value)} className={inputCls} placeholder="processes" /></Field>
            <Field label="inner_key（数组元素关联键）"><input value={jl.inner_key || ''} onChange={e => setJl('inner_key', e.target.value)} className={inputCls} placeholder="id" /></Field>
            <Field label="target_table"><input value={jl.target_table || ''} onChange={e => setJl('target_table', e.target.value)} className={inputCls} placeholder="matrix_routerx_config_process" /></Field>
            <Field label="target_key"><input value={jl.target_key || 'id'} onChange={e => setJl('target_key', e.target.value)} className={inputCls} placeholder="id" /></Field>
            <Field label="note（SQL 提示，可选）" hint="给 LLM 的 JSON_TABLE 用法说明">
              <textarea value={jl.note || ''} onChange={e => setJl('note', e.target.value)} className={textareaCls} rows={3} />
            </Field>
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

  const reviewItems = filteredItems.filter(i => i.confidence === 'medium' || i.confidence === 'low');

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="inline-flex rounded-lg border border-gray-300 overflow-hidden">
          <button onClick={() => setViewMode('list')} className={`px-3 py-2 text-sm ${viewMode === 'list' ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}>分层列表</button>
          <button onClick={() => setViewMode('path')} className={`px-3 py-2 text-sm ${viewMode === 'path' ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}>场景链路</button>
        </div>

        <div className="relative flex-1 min-w-[200px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={e => { setSearch(e.target.value); load(e.target.value, filterConf); }}
            placeholder="搜索关系名 / 描述..." className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50" />
        </div>
        <select value={scenarioFilter} onChange={e => setScenarioFilter(e.target.value)} className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none">
          <option value="">全部场景</option>
          <option value="split">拆批</option>
          <option value="genealogy">谱系</option>
          <option value="measurement">量测</option>
        </select>
        <select value={layerFilter} onChange={e => setLayerFilter(e.target.value)} className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none">
          <option value="">全部层级</option>
          <option value="event">事件层</option>
          <option value="snapshot">快照层</option>
          <option value="entity">实体层</option>
        </select>
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

      <p className="text-xs text-gray-500">共 {filteredItems.length} 条关系映射（原始 {items.length} 条）</p>

      {viewMode === 'path' && (
        <div className="border border-blue-200 bg-blue-50/50 rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm font-medium text-gray-700">场景预设</span>
            <select value={activePreset} onChange={e => setActivePreset(e.target.value)} className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none bg-white">
              {SCENARIO_PRESETS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
            <button onClick={() => copyText(buildChainText(currentPreset, relationMap, false), '已复制简版链路')} className="px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white text-gray-700 hover:bg-gray-50">复制简版链路</button>
            <button onClick={() => copyText(buildChainText(currentPreset, relationMap, true), '已复制审查版链路')} className="px-3 py-2 text-sm border border-blue-300 rounded-lg bg-blue-600 text-white hover:bg-blue-700">复制审查版链路</button>
            <button onClick={() => setMermaidCode(buildChainMermaid(currentPreset, relationMap))} className="flex items-center gap-1.5 px-3 py-2 text-sm border border-emerald-300 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700"><Eye size={14} />预览 Mermaid</button>
            <span className="text-xs text-gray-500">{currentPreset.description}</span>
            {copyMessage && <span className="text-xs text-green-600">{copyMessage}</span>}
          </div>

          <div className="space-y-3">
            {currentPreset.chains.map((chain, index) => (
              <div key={`${currentPreset.id}-${index}`} className="border border-gray-200 bg-white rounded-lg p-3">
                <div className="flex items-center justify-between gap-3 flex-wrap mb-2">
                  <p className="text-xs font-medium text-gray-500">链路 {index + 1}</p>
                  <div className="flex items-center gap-2 flex-wrap">
                    <button onClick={() => copyText(buildChainText(currentPreset, relationMap, false, chain, index), `已复制链路 ${index + 1} 简版`)} className="px-2.5 py-1 text-xs border border-gray-300 rounded-md bg-white text-gray-700 hover:bg-gray-50">复制本链路</button>
                    <button onClick={() => copyText(buildChainText(currentPreset, relationMap, true, chain, index), `已复制链路 ${index + 1} 审查版`)} className="px-2.5 py-1 text-xs border border-blue-300 rounded-md bg-blue-600 text-white hover:bg-blue-700">复制本链路审查版</button>
                    <button onClick={() => setMermaidCode(buildChainMermaid(currentPreset, relationMap, [chain]))} className="flex items-center gap-1 px-2.5 py-1 text-xs border border-emerald-300 rounded-md bg-emerald-600 text-white hover:bg-emerald-700"><Eye size={12} />Mermaid</button>
                  </div>
                </div>

                <div className="space-y-2">
                  {chain.map((relName, stepIndex) => {
                    const rel = relationMap.get(relName);
                    if (!rel) {
                      return <div key={relName} className="text-xs text-red-500 bg-red-50 border border-red-100 rounded px-2 py-1">{stepIndex + 1}. {relName}（当前映射集中未找到）</div>;
                    }
                    const risk = getRiskAnalysis(rel);
                    return (
                      <div key={relName} className="border border-gray-200 rounded-md p-2 bg-gray-50">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs text-gray-500">{stepIndex + 1}</span>
                          <span className="font-mono text-xs text-blue-700">{rel.logic_relation}</span>
                          <Badge text={rel.strategy} colorCls={STRATEGY_COLORS[rel.strategy] || 'bg-gray-100 text-gray-600'} />
                          <Badge text={classifyRelationLayer(rel) === 'event' ? '事件层' : classifyRelationLayer(rel) === 'snapshot' ? '快照层' : '实体层'} colorCls={classifyRelationLayer(rel) === 'event' ? 'bg-indigo-100 text-indigo-700' : classifyRelationLayer(rel) === 'snapshot' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-700'} />
                          <Badge text={getRiskLabel(risk.level)} colorCls={getRiskBadgeColor(risk.level)} />
                        </div>
                        <div className="mt-1 text-xs text-gray-600">{formatClassName(rel.domain_class)} → {formatClassName(rel.range_class)}</div>
                        <div className="mt-1 text-xs text-amber-700">风险原因：{risk.reasons.join('；')}</div>
                        <div className="mt-1 text-xs text-gray-500 break-all">JOIN摘要：{rel.strategy === 'per_record_type' ? summarizePerRecordTypeJoin(rel.per_record_type_join) : summarizeJoinLogic(rel.join_logic)}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Table */}
      {viewMode === 'list' && <div className="space-y-4">
      {(['event', 'snapshot', 'entity'] as RelationLayer[]).map(layer => {
        const layerItems = groupedItems[layer];
        const layerTitle = layer === 'event' ? '事件层关系' : layer === 'snapshot' ? '快照层关系' : '实体层关系';
        return (
      <div key={layer} className="border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">{layerTitle}</span>
          <span className="text-xs text-gray-500">{layerItems.length} 条</span>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="w-8" />
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Logic Relation</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">策略</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Domain → Range</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">描述</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">置信度</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading && layer === 'event' && <tr><td colSpan={7} className="py-8 text-center text-gray-400">加载中...</td></tr>}
            {!loading && filteredItems.length === 0 && layer === 'event' && <tr><td colSpan={7} className="py-8 text-center text-gray-400">暂无数据 — 运行 generate_relation_mappings.py --merge 导入草稿</td></tr>}
            {!loading && layerItems.length === 0 && filteredItems.length > 0 && <tr><td colSpan={7} className="py-5 text-center text-gray-300 text-xs">该层级无匹配关系</td></tr>}
            {layerItems.map((item, idx) => {
              const rowKey = `${item.logic_relation}::${item.domain_class || idx}`;
              const risk = getRiskAnalysis(item);
              return (
              <React.Fragment key={rowKey}>
                <tr className={`hover:bg-gray-50 transition-colors ${item.confidence === 'medium' ? 'bg-yellow-50/30' : ''}`}>
                  <td className="pl-3">
                    <button onClick={() => setExpandedRow(expandedRow === rowKey ? null : rowKey)}
                      className="text-gray-400 hover:text-gray-600">
                      {expandedRow === rowKey ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-blue-700">{item.logic_relation}</td>
                  <td className="px-4 py-3">
                    <Badge text={item.strategy} colorCls={STRATEGY_COLORS[item.strategy] || 'bg-gray-100 text-gray-600'} />
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-600">{formatClassName(item.domain_class)} → {formatClassName(item.range_class)}</td>
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
                {expandedRow === rowKey && (
                  <tr className="bg-gray-50">
                    <td colSpan={7} className="px-8 pb-4 pt-2 space-y-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge text={getRiskLabel(risk.level)} colorCls={getRiskBadgeColor(risk.level)} />
                        <span className="text-xs text-amber-700">风险原因：{risk.reasons.join('；')}</span>
                      </div>
                      <div className="text-xs text-gray-500 break-all">
                        JOIN摘要：{item.strategy === 'per_record_type'
                          ? summarizePerRecordTypeJoin(item.per_record_type_join)
                          : summarizeJoinLogic(item.join_logic)}
                      </div>
                      {item.strategy === 'per_record_type' && item.per_record_type_join ? (
                        <div className="space-y-2">
                          {Object.entries(item.per_record_type_join).map(([type, cfg]) => (
                            <div key={type} className="bg-white border border-gray-200 rounded-lg p-3">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs font-semibold text-blue-700 bg-blue-50 rounded px-2 py-0.5">{type.replace('semi:', '')}</span>
                                <span className="text-xs text-gray-500">{cfg.strategy}</span>
                              </div>
                              <pre className="text-xs text-gray-600 overflow-x-auto">{JSON.stringify(cfg.join_logic, null, 2)}</pre>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <pre className="text-xs text-gray-600 bg-white border border-gray-200 rounded-lg p-3 overflow-x-auto">
                          {JSON.stringify(item.join_logic, null, 2)}
                        </pre>
                      )}
                      {item.domain_class && <div className="text-xs text-gray-400">domain: {item.domain_class} → range: {item.range_class}</div>}
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );})}
          </tbody>
        </table>
      </div>
        )})}
      </div>}

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
            <select value={editItem.strategy || 'ForeignKey'} onChange={e => {
              const strat = e.target.value;
              setEditItem({
                ...editItem,
                strategy: strat,
                join_logic: {},
                per_record_type_join: strat === 'per_record_type' ? editItem.per_record_type_join || {} : undefined,
              });
            }} className={inputCls}>
              {STRATEGIES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>

          <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 space-y-3">
            <p className="text-xs font-medium text-gray-500 uppercase">Join Logic（{editItem.strategy}）</p>
            {renderJoinLogicForm()}
          </div>
        </Modal>
      )}

      {/* Mermaid Preview Modal */}
      {mermaidCode !== null && (
        <MermaidPreviewModal code={mermaidCode} onClose={() => setMermaidCode(null)} />
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
// Tab 5: Metrics
// ══════════════════════════════════════════════════════════════════

function MetricsTab() {
  const [items, setItems] = useState<MetricDefinition[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editItem, setEditItem] = useState<Partial<MetricDefinition> | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async (q = search) => {
    setLoading(true);
    setError('');
    try {
      const res = await mappingApi.getMetrics({ q });
      setItems(res.data || []);
    } catch (e: any) {
      setError(e.message || '加载指标定义失败');
      setItems([]);
    }
    setLoading(false);
  }, [search]);

  useEffect(() => { load(); }, []);

  const openAdd = () => {
    setEditItem({
      metric_id: '',
      zh_names: [],
      anchor_table: '',
      formula: '',
      granularity: [],
      description: '',
      join_path: '',
      auto_filter: '',
    });
    setIsEditing(false);
    setShowModal(true);
  };

  const openEdit = (item: MetricDefinition) => {
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
        zh_names: typeof editItem.zh_names === 'string'
          ? (editItem.zh_names as any).split(',').map((s: string) => s.trim()).filter(Boolean)
          : (editItem.zh_names || []),
        granularity: typeof editItem.granularity === 'string'
          ? (editItem.granularity as any).split(',').map((s: string) => s.trim()).filter(Boolean)
          : (editItem.granularity || []),
      };

      if (isEditing) {
        await mappingApi.updateMetric(editItem.metric_id!, payload);
      } else {
        await mappingApi.createMetric(payload);
      }

      setShowModal(false);
      load();
    } catch (e: any) {
      setError(e.message || '保存指标定义失败');
    }
    setSaving(false);
  };

  const handleDelete = async (metricId: string) => {
    if (!confirm(`删除指标定义 ${metricId}？`)) return;
    try {
      await mappingApi.deleteMetric(metricId);
      load();
    } catch (e: any) {
      alert(e.message || '删除失败');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); load(e.target.value); }}
            placeholder="搜索 metric_id / 中文别名 / anchor_table..."
            className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50"
          />
        </div>
        <button onClick={() => load()} className="p-2 text-gray-500 border border-gray-300 rounded-lg hover:bg-gray-50">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
        <button onClick={openAdd} className="flex items-center gap-2 px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700">
          <Plus size={16} />添加
        </button>
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg">{error}</div>}

      {!loading && items.length === 0 && !error && (
        <div className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center text-gray-400">
          <BarChart2 size={32} className="mx-auto mb-3 opacity-40" />
          <p className="text-sm">暂无指标定义</p>
          <p className="text-xs mt-1">请先在 mapping_prod.json 的 metric_definitions 中配置后再编辑</p>
        </div>
      )}

      <div className="space-y-3">
        {items.map(item => (
          <div key={item.metric_id} className="border border-gray-200 rounded-xl p-4 space-y-2">
            <div className="flex items-start justify-between">
              <div>
                <span className="font-mono text-sm font-medium text-blue-700">{item.metric_id}</span>
                {item.zh_names?.length > 0 && (
                  <span className="ml-2 text-sm text-gray-700">{item.zh_names.join(' / ')}</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => openEdit(item)} className="p-1 text-gray-400 hover:text-blue-600"><Edit2 size={14} /></button>
                <button onClick={() => handleDelete(item.metric_id)} className="p-1 text-gray-400 hover:text-red-600"><Trash2 size={14} /></button>
              </div>
            </div>

            <div className="text-xs text-gray-600">anchor_table: <span className="font-mono">{item.anchor_table || '—'}</span></div>
            <div className="text-xs text-gray-600">formula: <span className="font-mono">{item.formula || '—'}</span></div>
            <div className="text-xs text-gray-600">granularity: {(item.granularity || []).join(', ') || '—'}</div>
            {item.description && <p className="text-xs text-gray-600">{item.description}</p>}
          </div>
        ))}
      </div>

      {showModal && editItem && (
        <Modal title={isEditing ? `编辑指标：${editItem.metric_id}` : '新增指标定义'} onClose={() => setShowModal(false)} onConfirm={handleSave} confirmText={saving ? '保存中...' : '保存'} wide>
          {error && <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg">{error}</div>}

          <div className="grid grid-cols-2 gap-4">
            <Field label="metric_id" required>
              <input value={editItem.metric_id || ''} onChange={e => setEditItem({ ...editItem, metric_id: e.target.value })} disabled={isEditing} className={`${inputCls} ${isEditing ? 'bg-gray-50 text-gray-500' : ''}`} placeholder="wip_count_by_station" />
            </Field>
            <Field label="anchor_table" required>
              <input value={editItem.anchor_table || ''} onChange={e => setEditItem({ ...editItem, anchor_table: e.target.value })} className={inputCls} placeholder="matrix_routerx_operation_lot" />
            </Field>
          </div>

          <Field label="中文别名（zh_names，逗号分隔）">
            <input value={Array.isArray(editItem.zh_names) ? editItem.zh_names.join(', ') : (editItem.zh_names as any) || ''} onChange={e => setEditItem({ ...editItem, zh_names: e.target.value as any })} className={inputCls} placeholder="在制品数量, 工站WIP" />
          </Field>

          <Field label="formula" required>
            <textarea value={editItem.formula || ''} onChange={e => setEditItem({ ...editItem, formula: e.target.value })} className={`${textareaCls} min-h-[90px]`} placeholder="COUNT(DISTINCT lot_id)" />
          </Field>

          <Field label="granularity（逗号分隔）">
            <input value={Array.isArray(editItem.granularity) ? editItem.granularity.join(', ') : (editItem.granularity as any) || ''} onChange={e => setEditItem({ ...editItem, granularity: e.target.value as any })} className={inputCls} placeholder="process, product, day" />
          </Field>

          <Field label="description">
            <input value={editItem.description || ''} onChange={e => setEditItem({ ...editItem, description: e.target.value })} className={inputCls} />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="join_path（可选）">
              <input value={editItem.join_path || ''} onChange={e => setEditItem({ ...editItem, join_path: e.target.value })} className={inputCls} />
            </Field>
            <Field label="auto_filter（可选）">
              <input value={editItem.auto_filter || ''} onChange={e => setEditItem({ ...editItem, auto_filter: e.target.value })} className={inputCls} />
            </Field>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// Tab 6: Changelog
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
          <option value="value_mapping">状态映射</option>
          <option value="business_rule">业务规则</option>
          <option value="metric_definition">指标定义</option>
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
    { key: 'values',    label: '状态映射',    icon: <Tag size={15} />,          count: summary?.value_domains },
    { key: 'rules',     label: '业务规则',  icon: <Book size={15} />,         count: summary?.business_rules },
    { key: 'metrics',   label: '指标定义',  icon: <BarChart2 size={15} />,    count: summary?.metric_definitions },
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
            {tab === 'metrics'   && <MetricsTab />}
            {tab === 'changelog' && <ChangelogTab />}
          </div>
        </div>
      </div>
    </div>
  );
}