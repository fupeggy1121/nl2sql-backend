// components/Traceability/TraceabilityView.tsx
// 批次 / Wafer 追溯面板：谱系 DAG + 过站时间轴 + 元数据面板
// 支持头部下拉筛选批次 / Wafer
import React, { useEffect, useRef, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import {
  GitBranch, Clock, Cpu, ChevronRight, AlertCircle,
  Loader2, RefreshCw, Search, ChevronDown,
} from 'lucide-react';

// ── 类型定义 ──────────────────────────────────────────────────────
interface StateTransition {
  id: string;
  from_node: string;
  to_node: string;
  event: string;       // 事件标签（中文操作名）
  event_type: string;  // CHECKIN|CHECKOUT|SPLIT|MERGE|REWORK|NG|HOLD|RELEASE|DONE|OTHER
  lot_code: string;
  process_code?: string;
  process_name?: string;
  operator?: string;
  operator_id?: string;
  time?: string;
  has_measurements?: boolean;
  measurements?: Array<{ name: string; value: string; unit: string }>;
  station?: string;
  station_id?: string;
  equipment?: string;
  wafer_count?: number;
  child_lot?: string;
  note?: string;
}

interface LotTraceabilityData {
  success: boolean;
  lot_code: string;
  lot_info: Record<string, any>;
  wafer_ids: string[];
  genealogy_events: Array<Record<string, any>>;
  state_transitions: StateTransition[];  // 状态机 DAG 边列表
  pass_records: Array<Record<string, any>>;
  measurement_records: Array<Record<string, any>>;
  error?: string;
}

interface WaferTraceabilityData {
  success: boolean;
  wafer_code: string;
  timeline: Array<Record<string, any>>;
  error?: string;
}

interface TraceabilityViewProps {
  params: string; // "lot:L001" | "wafer:W001" | plain lot code
}

const API_BASE = 'http://localhost:8000/api/v1/traceability';

// ── 工具函数 ──────────────────────────────────────────────────────
function parseParams(raw: string): { lotCode?: string; waferCode?: string } {
  if (raw.startsWith('lot:')) return { lotCode: raw.slice(4) };
  if (raw.startsWith('wafer:')) return { waferCode: raw.slice(6) };
  return { lotCode: raw };
}

// 颜色映射
const EVENT_COLOR: Record<string, string> = {
  CHECKIN:  '#3b82f6',  // 蓝   — 进站
  CHECKOUT: '#10b981',  // 绿   — 出站
  SPLIT:    '#f59e0b',  // 橙   — 拆批/拆父批
  MERGE:    '#8b5cf6',  // 紫   — 并批/攒批
  REWORK:   '#ef4444',  // 红   — 返工
  NG:       '#dc2626',  // 深红 — 不良录入
  HOLD:     '#d97706',  // 琥珀 — 暂停
  RELEASE:  '#059669',  // 青绿 — 释放
  DONE:     '#047857',  // 深绿 — 完成批次
  OTHER:    '#94a3b8',  // 灰   — 其他
};

// 节点样式 — 解析 {lot_code}@{state_label} 格式
function nodeStyle(nodeId: string, _rootLot: string) {
  const atIdx = nodeId.indexOf('@');
  const label = atIdx >= 0 ? nodeId.substring(atIdx + 1) : nodeId;
  if (label === '投料' || label === '创建')           return { color: '#6b7280', size: 28, symbol: 'roundRect' };
  if (label === '完成' || label === '完成批次')        return { color: '#047857', size: 28, symbol: 'roundRect' };
  if (label.endsWith('-进站') || label === '进站')     return { color: '#3b82f6', size: 22, symbol: 'circle' };
  if (label.endsWith('-出站') || label === '出站')     return { color: '#10b981', size: 22, symbol: 'circle' };
  if (label.includes('拆'))                           return { color: '#f59e0b', size: 24, symbol: 'diamond' };
  if (label.includes('并') || label.includes('攒'))   return { color: '#8b5cf6', size: 24, symbol: 'diamond' };
  if (label === '返工')                               return { color: '#ef4444', size: 24, symbol: 'triangle' };
  if (label === '不良录入')                           return { color: '#dc2626', size: 22, symbol: 'circle' };
  if (label === '暂停')                               return { color: '#d97706', size: 20, symbol: 'circle' };
  return { color: '#94a3b8', size: 20, symbol: 'circle' };
}

// 拓扑排序 + 分层布局，返回每个节点的固定 (x, y) 坐标
function computeDAGLayout(
  transitions: StateTransition[],
): Map<string, { x: number; y: number }> {
  const outEdges = new Map<string, Set<string>>();
  const inDegree  = new Map<string, number>();
  const allNodes  = new Set<string>();

  for (const t of transitions) {
    allNodes.add(t.from_node);
    allNodes.add(t.to_node);
    if (!outEdges.has(t.from_node)) outEdges.set(t.from_node, new Set());
    outEdges.get(t.from_node)!.add(t.to_node);
    inDegree.set(t.to_node, (inDegree.get(t.to_node) ?? 0) + 1);
  }
  for (const n of allNodes) if (!inDegree.has(n)) inDegree.set(n, 0);

  // Kahn's BFS：计算每个节点的最晚层次（最长路径）
  const level = new Map<string, number>();
  const tempIn = new Map(inDegree);
  const queue: string[] = [];
  for (const [n, d] of inDegree) if (d === 0) { queue.push(n); level.set(n, 0); }

  while (queue.length) {
    const node = queue.shift()!;
    const lv = level.get(node) ?? 0;
    for (const nb of outEdges.get(node) ?? []) {
      level.set(nb, Math.max(level.get(nb) ?? 0, lv + 1));
      const deg = (tempIn.get(nb) ?? 1) - 1;
      tempIn.set(nb, deg);
      if (deg === 0) queue.push(nb);
    }
  }
  for (const n of allNodes) if (!level.has(n)) level.set(n, 0);

  // 按层分组，同层按批次+状态名稳定排序，避免同层交叉
  const byLevel = new Map<number, string[]>();
  for (const [n, lv] of level) {
    if (!byLevel.has(lv)) byLevel.set(lv, []);
    byLevel.get(lv)!.push(n);
  }
  for (const nodes of byLevel.values()) nodes.sort();

  const LEVEL_GAP = 200;   // 层间距（Y方向）—— 增大防止节点/标签垂直重叠
  const NODE_GAP  = 280;   // 同层节点间距（X方向）—— 增大防止节点水平重叠
  const positions = new Map<string, { x: number; y: number }>();

  for (const [lv, nodesAtLevel] of byLevel) {
    const totalW = (nodesAtLevel.length - 1) * NODE_GAP;
    nodesAtLevel.forEach((n, i) => {
      positions.set(n, {
        x: i * NODE_GAP - totalW / 2,
        y: lv * LEVEL_GAP,
      });
    });
  }
  return positions;
}

// 构建节点 hover tooltip HTML
function buildNodeTooltip(id: string, incomingTrans: StateTransition[]): string {
  const atIdx     = id.indexOf('@');
  const stateLabel = atIdx >= 0 ? id.substring(atIdx + 1) : id;
  const lotCode   = atIdx >= 0 ? id.substring(0, atIdx) : id;
  const lotShort  = lotCode.split('-').slice(-2).join('-');
  const dashIdx   = stateLabel.lastIndexOf('-');
  const eventKind = dashIdx >= 0 ? stateLabel.substring(dashIdx + 1) : stateLabel;
  const stationStr = dashIdx >= 0 ? stateLabel.substring(0, dashIdx) : '';

  const t = incomingTrans[0];
  const row = (label: string, val: string | number | undefined, icon = '') =>
    val != null && val !== '' && val !== 0
      ? `<tr><td style="color:#9ca3af;padding:2px 10px 2px 0;white-space:nowrap">${icon}${label}</td><td style="color:#1f2937">${val}</td></tr>`
      : '';

  let html = `<div style="max-width:300px;font-size:12px;line-height:1.6;font-family:sans-serif">`;
  html += `<div style="font-weight:700;font-size:13px;color:#111827;margin-bottom:6px;border-bottom:1px solid #e5e7eb;padding-bottom:4px">`;
  html += stationStr ? `${stationStr} · ${eventKind}` : stateLabel;
  html += `</div>`;

  if (t) {
    const operator = t.operator_id || t.operator || '';
    const station  = t.station || stationStr || '';
    const stId     = t.station_id ? ` (${t.station_id})` : '';
    html += `<table style="border-collapse:collapse">`;
    html += row('批次号',   lotCode);
    html += row('事件',     t.event);
    html += row('时间',     t.time, '⏱ ');
    html += row('操作人',   operator, '👤 ');
    html += row('工序站点', station + stId, '🏭 ');
    html += row('设备',     t.equipment, '⚙️ ');
    html += row('批次规模', t.wafer_count ? `${t.wafer_count} 片 Wafer` : '', '📦 ');
    html += row('子批次',   t.child_lot, '🔀 ');
    html += row('备注',     t.note, '📝 ');
    html += `</table>`;

    if (t.event_type === 'CHECKIN' && t.wafer_count) {
      html += `<div style="margin-top:8px;border-top:1px solid #e5e7eb;padding-top:6px">`;
      html += `<div style="font-size:11px;font-weight:600;color:#6b7280;margin-bottom:3px">📸 进站快照</div>`;
      html += `<div style="font-size:11px;color:#374151">批次: <b>${lotShort}</b> · ${t.wafer_count} 片 Wafer</div>`;
      html += `</div>`;
    } else if (t.event_type === 'SPLIT' && t.child_lot) {
      html += `<div style="margin-top:8px;border-top:1px solid #e5e7eb;padding-top:6px">`;
      html += `<div style="font-size:11px;font-weight:600;color:#6b7280;margin-bottom:3px">🔀 拆批快照</div>`;
      html += `<div style="font-size:11px;color:#374151">母批: <b>${lotShort}</b> → 子批: <b>${t.child_lot.split('-').slice(-2).join('-')}</b></div>`;
      if (t.wafer_count) html += `<div style="font-size:11px;color:#374151">Wafer: ${t.wafer_count} 片</div>`;
      html += `</div>`;
    }
    if (t.measurements && t.measurements.length > 0) {
      html += `<div style="margin-top:8px;border-top:1px solid #e5e7eb;padding-top:6px">`;
      html += `<div style="font-size:11px;font-weight:600;color:#6b7280;margin-bottom:3px">🔬 量测数据</div>`;
      t.measurements.forEach((m) => {
        html += `<div style="font-size:11px;color:#374151">${m.name}: <b>${m.value}${m.unit ? ' ' + m.unit : ''}</b></div>`;
      });
      html += `</div>`;
    }
  } else {
    html += `<div style="color:#6b7280;font-size:11px">批次: ${lotCode}</div>`;
  }
  html += `</div>`;
  return html;
}

function buildGenealogyOption(
  transitions: StateTransition[],
  rootLot: string,
) {
  if (!transitions || transitions.length === 0) return null;

  const positions = computeDAGLayout(transitions);

  // 各节点的入边映射，用于 hover 时展示事件属性
  const nodeToIncoming = new Map<string, StateTransition[]>();
  for (const t of transitions) {
    if (!nodeToIncoming.has(t.to_node)) nodeToIncoming.set(t.to_node, []);
    nodeToIncoming.get(t.to_node)!.push(t);
  }

  // 将坐标偏移至全正区域
  const posValues = Array.from(positions.values());
  const minX = posValues.length ? Math.min(...posValues.map((p) => p.x)) : 0;
  const OX = -minX + 80;
  const OY = 60;

  const nodeIds = new Set<string>();
  transitions.forEach((t) => { nodeIds.add(t.from_node); nodeIds.add(t.to_node); });

  const nodes = Array.from(nodeIds).map((id) => {
    const s = nodeStyle(id, rootLot);
    const atIdx     = id.indexOf('@');
    const stateLabel = atIdx >= 0 ? id.substring(atIdx + 1) : id;
    const lotCode   = atIdx >= 0 ? id.substring(0, atIdx) : '';
    const lotShort  = lotCode.split('-').pop() ?? lotCode;
    const dashIdx   = stateLabel.lastIndexOf('-');
    const eventKind = dashIdx >= 0 ? stateLabel.substring(dashIdx + 1) : stateLabel;
    const stationStr = dashIdx >= 0 ? stateLabel.substring(0, dashIdx) : '';
    const isStartEnd = stateLabel === '投料' || stateLabel === '创建' || stateLabel === '完成' || stateLabel === '完成批次';
    const pos = positions.get(id) ?? { x: 0, y: 0 };
    const incoming = nodeToIncoming.get(id) ?? [];

    return {
      id, name: id,
      x: pos.x + OX,
      y: pos.y + OY,
      symbolSize: s.size,
      symbol: s.symbol,
      itemStyle: { color: s.color },
      label: {
        show: true,
        formatter: isStartEnd
          ? `{bold|${lotShort}}`
          : stationStr
            ? `{state|${eventKind}}\n{proc|${stationStr}}`
            : `{state|${stateLabel}}\n{proc|${lotShort}}`,
        rich: {
          bold:  { fontSize: 11, color: '#1f2937', fontWeight: 'bold', lineHeight: 16 },
          state: { fontSize: 11, color: '#1f2937', fontWeight: 'bold', lineHeight: 16 },
          proc:  { fontSize: 9,  color: '#6b7280', lineHeight: 14 },
        },
        position: 'bottom',
      },
      _incoming: incoming,
    };
  });

  const links = transitions.map((t) => ({
    source: t.from_node,
    target: t.to_node,
    // 箭头线上不再显示事件名（已在节点上展示）
    label: { show: false },
    lineStyle: {
      color: EVENT_COLOR[t.event_type] ?? '#94a3b8',
      width: t.event_type === 'CHECKIN' || t.event_type === 'CHECKOUT' ? 1.5 : 2.5,
      curveness: t.event_type === 'SPLIT' || t.event_type === 'REWORK' ? 0.25 : 0,
      type: t.event_type === 'CHECKIN' ? 'dashed' : 'solid',
    },
  }));

  return {
    animation: false,
    backgroundColor: '#f8fafc',
    tooltip: {
      trigger: 'item',
      enterable: false,
      formatter: (p: any) => {
        if (p.dataType === 'node') {
          return buildNodeTooltip(p.data.id as string, (p.data._incoming ?? []) as StateTransition[]);
        }
        return '';
      },
    },
    series: [{
      type: 'graph',
      layout: 'none',          // 使用固定坐标，消除 force 随机重叠
      data: nodes,
      links,
      roam: true,
      draggable: true,
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: [0, 10],
      emphasis: { focus: 'adjacency', scale: 1.2 },
    }],
  };
}

// ── 通用 select 样式 ──────────────────────────────────────────────
const selectStyle: React.CSSProperties = {
  padding: '5px 28px 5px 10px',
  borderRadius: 6,
  border: '1px solid #d1d5db',
  background: '#fff',
  fontSize: 13,
  color: '#374151',
  cursor: 'pointer',
  appearance: 'none' as any,
  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`,
  backgroundRepeat: 'no-repeat',
  backgroundPosition: 'right 8px center',
  minWidth: 120,
};

// ── 子组件：搜索输入框（支持回车提交）────────────────────────────
const SearchInput: React.FC<{
  value: string;
  placeholder: string;
  onSubmit: (v: string) => void;
}> = ({ value, placeholder, onSubmit }) => {
  const [draft, setDraft] = useState(value);
  // 当外部 value 改变时同步 draft
  useEffect(() => setDraft(value), [value]);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <div style={{ position: 'relative' }}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && draft.trim() && onSubmit(draft.trim())}
          placeholder={placeholder}
          style={{
            padding: '5px 32px 5px 10px', borderRadius: 6,
            border: '1px solid #d1d5db', fontSize: 13, color: '#374151',
            outline: 'none', width: 150,
          }}
        />
        <button
          onClick={() => draft.trim() && onSubmit(draft.trim())}
          style={{
            position: 'absolute', right: 4, top: '50%', transform: 'translateY(-50%)',
            background: 'none', border: 'none', cursor: 'pointer', padding: 2,
            color: '#9ca3af', display: 'flex', alignItems: 'center',
          }}
        >
          <Search size={13} />
        </button>
      </div>
    </div>
  );
};

// ── 子组件：元数据面板 ─────────────────────────────────────────────
const MetaPanel: React.FC<{ title: string; data: Record<string, any> }> = ({ title, data }) => {
  const entries = Object.entries(data).filter(([, v]) => v !== null && v !== undefined && v !== '');
  return (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginBottom: 16 }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 10, borderBottom: '1px solid #f3f4f6', paddingBottom: 8 }}>{title}</div>
      {entries.length === 0 ? (
        <div style={{ fontSize: 12, color: '#9ca3af', fontStyle: 'italic' }}>暂无数据</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 12px' }}>
          {entries.map(([k, v]) => (
            <div key={k} style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: 10, color: '#9ca3af', marginBottom: 1 }}>{k}</span>
              <span style={{ fontSize: 12, color: '#1f2937', wordBreak: 'break-all' }}>{String(v)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ── 子组件：过站时间轴 ─────────────────────────────────────────────
const PassTimeline: React.FC<{ records: Array<Record<string, any>> }> = ({ records }) => {
  if (records.length === 0)
    return <div style={{ textAlign: 'center', padding: '32px 0', color: '#9ca3af', fontSize: 13 }}>暂无过站记录</div>;
  return (
    <div style={{ position: 'relative', paddingLeft: 24 }}>
      <div style={{ position: 'absolute', left: 9, top: 8, bottom: 8, width: 2, background: '#e5e7eb', borderRadius: 1 }} />
      {records.map((rec, idx) => (
        <div key={rec.id || idx} style={{ position: 'relative', marginBottom: 16 }}>
          <div style={{ position: 'absolute', left: -24, top: 4, width: 10, height: 10, borderRadius: '50%', background: '#3b82f6', border: '2px solid #fff', boxShadow: '0 0 0 1px #93c5fd', zIndex: 1 }} />
          <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 6, padding: '8px 12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <Cpu size={12} color="#6b7280" />
              <span style={{ fontWeight: 600, fontSize: 12, color: '#1f2937' }}>
                {rec.station_id || rec.station_name || `记录 #${idx + 1}`}
              </span>
              {rec.equipment_id && (
                <><ChevronRight size={11} color="#9ca3af" /><span style={{ fontSize: 11, color: '#6b7280' }}>{rec.equipment_id}</span></>
              )}
              {rec.wafer_id && (
                <span style={{ marginLeft: 'auto', fontSize: 10, color: '#6b7280', background: '#f3f4f6', padding: '1px 6px', borderRadius: 10 }}>
                  {rec.wafer_id}
                </span>
              )}
            </div>
            <div style={{ display: 'flex', gap: 16, fontSize: 11, color: '#9ca3af' }}>
              {rec.in_time && <span><Clock size={10} style={{ verticalAlign: 'middle', marginRight: 3 }} />IN: {rec.in_time}</span>}
              {rec.out_time && <span>OUT: {rec.out_time}</span>}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

// ── 子组件：简单数据表格 ───────────────────────────────────────────
const SimpleTable: React.FC<{ rows: Array<Record<string, any>> }> = ({ rows }) => {
  if (rows.length === 0)
    return <div style={{ textAlign: 'center', padding: '24px 0', color: '#9ca3af', fontSize: 13 }}>暂无记录</div>;
  const cols = Object.keys(rows[0]);
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, color: '#374151' }}>
        <thead>
          <tr style={{ background: '#f9fafb' }}>
            {cols.map((c) => <th key={c} style={{ padding: '6px 10px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontWeight: 600, whiteSpace: 'nowrap', color: '#6b7280' }}>{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{ background: i % 2 === 0 ? '#fff' : '#f9fafb', borderBottom: '1px solid #f3f4f6' }}>
              {cols.map((c) => <td key={c} style={{ padding: '6px 10px', whiteSpace: 'nowrap', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>{row[c] == null ? '—' : String(row[c])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// ── 主组件 ────────────────────────────────────────────────────────
type ActiveTab = 'timeline' | 'genealogy' | 'measurement';
type ViewMode = 'lot' | 'wafer';

export const TraceabilityView: React.FC<TraceabilityViewProps> = ({ params }) => {
  const initial = parseParams(params);

  // ── 当前查询目标（内部可变，不依赖 props）──
  const [viewMode, setViewMode] = useState<ViewMode>(initial.waferCode ? 'wafer' : 'lot');
  const [activeLot, setActiveLot] = useState<string>(initial.lotCode || '');
  const [activeWafer, setActiveWafer] = useState<string>(initial.waferCode || '');

  // ── 数据 ──
  const [loading, setLoading] = useState(true);
  const [lotData, setLotData] = useState<LotTraceabilityData | null>(null);
  const [waferData, setWaferData] = useState<WaferTraceabilityData | null>(null);

  // ── UI 筛选 ──
  const [selectedWafer, setSelectedWafer] = useState<string>('all'); // wafer 下拉筛选（批次模式下）
  const [activeTab, setActiveTab] = useState<ActiveTab>('genealogy');

  // ── 当 props.params 从外部变更时（sidebar 切换）同步 ──
  useEffect(() => {
    const p = parseParams(params);
    if (p.waferCode) {
      setViewMode('wafer');
      setActiveWafer(p.waferCode);
      setActiveLot('');
    } else {
      setViewMode('lot');
      setActiveLot(p.lotCode || '');
      setActiveWafer('');
    }
    setSelectedWafer('all');
  }, [params]);

  const fetchData = async () => {
    setLoading(true);
    setLotData(null);
    setWaferData(null);
    try {
      if (viewMode === 'lot' && activeLot) {
        const res = await fetch(`${API_BASE}/lot/${encodeURIComponent(activeLot)}`);
        if (res.ok) setLotData(await res.json());
      } else if (viewMode === 'wafer' && activeWafer) {
        const res = await fetch(`${API_BASE}/wafer/${encodeURIComponent(activeWafer)}`);
        if (res.ok) setWaferData(await res.json());
      }
    } catch (e) {
      console.error('[TraceabilityView] fetch error:', e);
    } finally {
      setLoading(false);
    }
  };

  // 切换模式或目标时重新加载
  useEffect(() => {
    // wafer 模式下很系谱 DAG 不存在，默认切换到 timeline
    if (viewMode === 'wafer') setActiveTab('timeline');
    else setActiveTab('genealogy');
    if ((viewMode === 'lot' && activeLot) || (viewMode === 'wafer' && activeWafer)) {
      setSelectedWafer('all');
      fetchData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode, activeLot, activeWafer]);

  // ── 当前展示的批次内 wafer 列表 ──
  const waferIdOptions: string[] = lotData?.wafer_ids || [];

  // ── 筛选后的过站记录 ──
  const filteredPassRecords = lotData
    ? (selectedWafer === 'all'
        ? lotData.pass_records
        : lotData.pass_records.filter((r) => String(r.wafer_id) === selectedWafer))
    : [];
  const filteredMeasurements = lotData
    ? (selectedWafer === 'all'
        ? lotData.measurement_records
        : lotData.measurement_records.filter((r) => String(r.wafer_id) === selectedWafer))
    : [];

  const tabs: { id: ActiveTab; label: string; icon: React.ReactNode }[] = [
    ...(viewMode === 'lot'
      ? [
          { id: 'genealogy' as ActiveTab, label: '谱系 DAG', icon: <GitBranch size={13} /> },
          { id: 'measurement' as ActiveTab, label: '量测记录', icon: <Cpu size={13} /> },
        ]
      : []),
    { id: 'timeline', label: '过站时间轴', icon: <Clock size={13} /> },
  ];

  const renderTabContent = () => {
    if (viewMode === 'lot' && lotData) {
      if (activeTab === 'timeline') return <PassTimeline records={filteredPassRecords} />;
      if (activeTab === 'measurement') return <SimpleTable rows={filteredMeasurements} />;
      if (activeTab === 'genealogy') {
        const transitions = lotData.state_transitions ?? [];
        if (transitions.length === 0)
          return <div style={{ textAlign: 'center', padding: '32px 0', color: '#9ca3af', fontSize: 13 }}>该批次暂无状态转移数据</div>;
        const option = buildGenealogyOption(transitions, lotData.lot_code);
        if (!option) return null;
        return (
          <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <div style={{ fontSize: 11, color: '#9ca3af', padding: '6px 16px', borderBottom: '1px solid #f3f4f6', flexShrink: 0 }}>
              节点 = 批次状态快照 &nbsp;·&nbsp; 连线 = 驱动状态切换的操作事件 &nbsp;·&nbsp; 可拖拽节点 / 滚轮缩放
            </div>
            <ReactECharts option={option} style={{ flex: 1, minHeight: 0 }} />
          </div>
        );
      }
    }
    if (viewMode === 'wafer' && waferData) {
      return <PassTimeline records={waferData.timeline} />;
    }
    return null;
  };

  const currentTarget = viewMode === 'lot' ? activeLot : activeWafer;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#f0f2f5', overflow: 'hidden' }}>

      {/* ── 头部 ── */}
      <header style={{ background: '#fff', borderBottom: '1px solid #e5e7eb', padding: '10px 20px', display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0, flexWrap: 'wrap' }}>
        <GitBranch size={17} color="#3b82f6" style={{ flexShrink: 0 }} />
        <span style={{ fontSize: 15, fontWeight: 700, color: '#1a1a2e', marginRight: 4, flexShrink: 0 }}>追溯查询</span>

        {/* ── 模式切换 ── */}
        <div style={{ display: 'flex', borderRadius: 6, border: '1px solid #d1d5db', overflow: 'hidden', flexShrink: 0 }}>
          {(['lot', 'wafer'] as ViewMode[]).map((m) => (
            <button key={m} onClick={() => setViewMode(m)}
              style={{ padding: '5px 12px', border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: viewMode === m ? 600 : 400, background: viewMode === m ? '#3b82f6' : '#fff', color: viewMode === m ? '#fff' : '#6b7280', transition: 'all .15s' }}>
              {m === 'lot' ? '批次' : 'Wafer'}
            </button>
          ))}
        </div>

        {/* ── 批次/Wafer 搜索 ── */}
        <SearchInput
          value={viewMode === 'lot' ? activeLot : activeWafer}
          placeholder={viewMode === 'lot' ? '输入批次号 Enter' : '输入 Wafer 号 Enter'}
          onSubmit={(v) => {
            if (viewMode === 'lot') setActiveLot(v);
            else setActiveWafer(v);
          }}
        />

        {/* ── Wafer 筛选下拉（仅批次模式且有 wafer 时显示）── */}
        {viewMode === 'lot' && waferIdOptions.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
            <span style={{ fontSize: 12, color: '#6b7280', whiteSpace: 'nowrap' }}>筛选 Wafer：</span>
            <select
              value={selectedWafer}
              onChange={(e) => setSelectedWafer(e.target.value)}
              style={selectStyle}
            >
              <option value="all">全部（{waferIdOptions.length} 片）</option>
              {waferIdOptions.map((wid) => (
                <option key={wid} value={wid}>{wid}</option>
              ))}
            </select>
          </div>
        )}

        {/* ── 当前标签 ── */}
        {currentTarget && (
          <span style={{ fontSize: 12, color: '#9ca3af', background: '#f3f4f6', padding: '3px 8px', borderRadius: 10, whiteSpace: 'nowrap' }}>
            {viewMode === 'lot' ? '批次' : 'Wafer'}：{currentTarget}
            {viewMode === 'lot' && selectedWafer !== 'all' && ` · Wafer ${selectedWafer}`}
          </span>
        )}

        <div style={{ marginLeft: 'auto' }}>
          <button onClick={fetchData} disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 12px', borderRadius: 6, border: '1px solid #e5e7eb', background: '#fff', color: '#374151', fontSize: 12, cursor: 'pointer' }}>
            <RefreshCw size={12} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            刷新
          </button>
        </div>
      </header>

      {/* ── 内容区 ── */}
      <div style={{ flex: 1, overflow: 'auto', padding: 20, display: 'flex', gap: 16, minHeight: 0 }}>
        {loading ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 12, color: '#6b7280' }}>
            <Loader2 size={32} color="#3b82f6" style={{ animation: 'spin 1s linear infinite' }} />
            <span style={{ fontSize: 13 }}>正在加载追溯数据...</span>
          </div>
        ) : (
          <>
            {/* 左侧元数据面板 */}
            <div style={{ width: 240, flexShrink: 0 }}>
              <MetaPanel
                title={viewMode === 'lot' ? '批次信息' : 'Wafer 信息'}
                data={viewMode === 'lot' && lotData ? lotData.lot_info : { code: currentTarget }}
              />
              {/* Wafer 列表（批次模式下，供快速点击切换）*/}
              {viewMode === 'lot' && waferIdOptions.length > 0 && (
                <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
                    Wafer 列表（{waferIdOptions.length} 片）
                  </div>
                  <div style={{ maxHeight: 240, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 3 }}>
                    <button
                      onClick={() => setSelectedWafer('all')}
                      style={{ padding: '5px 8px', borderRadius: 5, border: 'none', cursor: 'pointer', textAlign: 'left', fontSize: 12, background: selectedWafer === 'all' ? '#eff6ff' : 'transparent', color: selectedWafer === 'all' ? '#1d4ed8' : '#374151', fontWeight: selectedWafer === 'all' ? 600 : 400 }}>
                      全部
                    </button>
                    {waferIdOptions.map((wid) => (
                      <button key={wid} onClick={() => setSelectedWafer(wid)}
                        style={{ padding: '5px 8px', borderRadius: 5, border: 'none', cursor: 'pointer', textAlign: 'left', fontSize: 12, background: selectedWafer === wid ? '#eff6ff' : 'transparent', color: selectedWafer === wid ? '#1d4ed8' : '#374151', fontWeight: selectedWafer === wid ? 600 : 400 }}>
                        {wid}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {/* 错误提示 */}
              {((viewMode === 'lot' && lotData && !lotData.success) || (viewMode === 'wafer' && waferData && !waferData.success)) && (
                <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: 12, display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 12, color: '#dc2626', marginTop: 12 }}>
                  <AlertCircle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                  <span>数据加载失败：{(viewMode === 'lot' ? lotData?.error : waferData?.error)}</span>
                </div>
              )}
              {!lotData && !waferData && !loading && (
                <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 8, padding: 12, fontSize: 12, color: '#c2410c', marginTop: 12 }}>
                  {currentTarget ? '未找到该追溯数据，请确认编号正确且数据库已连接。' : '请输入批次号或 Wafer 号后按 Enter 查询。'}
                </div>
              )}
            </div>

            {/* 右侧主内容 */}
            <div style={{ flex: 1, background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              {/* Tab 导航 */}
              <div style={{ display: 'flex', borderBottom: '1px solid #e5e7eb', padding: '0 16px', flexShrink: 0 }}>
                {tabs.map((tab) => (
                  <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '10px 14px', border: 'none', borderBottom: activeTab === tab.id ? '2px solid #3b82f6' : '2px solid transparent', background: 'transparent', color: activeTab === tab.id ? '#2563eb' : '#6b7280', fontSize: 13, fontWeight: activeTab === tab.id ? 600 : 400, cursor: 'pointer', marginBottom: -1 }}>
                    {tab.icon}{tab.label}
                  </button>
                ))}
                {/* 记录数提示 */}
                {viewMode === 'lot' && lotData && (
                  <span style={{ marginLeft: 'auto', alignSelf: 'center', fontSize: 11, color: '#9ca3af' }}>
                    {activeTab === 'timeline' && `${filteredPassRecords.length} 条过站`}
                    {activeTab === 'measurement' && `${filteredMeasurements.length} 条量测`}
                    {selectedWafer !== 'all' && ` · Wafer ${selectedWafer}`}
                  </span>
                )}
              </div>
              {/* Tab 内容 */}
              <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
                {renderTabContent()}
              </div>
            </div>
          </>
        )}
      </div>

      {/* spin keyframe */}
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
};
