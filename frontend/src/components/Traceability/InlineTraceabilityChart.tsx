// InlineTraceabilityChart.tsx
// 嵌入在 Chat 气泡中的批次追溯图表
// 数据一次性从后端拿全量，所有筛选均在前端内存中完成（无额外 API 调用）
import React, { useEffect, useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { Search, ChevronRight, Clock, Cpu, Loader2, AlertCircle, Maximize2, Minimize2 } from 'lucide-react';

// ── 类型 ─────────────────────────────────────────────────────────
interface StateTransition {
  id: string;
  from_node: string;
  to_node: string;
  event: string;
  event_type: string;
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

interface LotData {
  success: boolean;
  lot_code: string;
  lot_info: Record<string, any>;
  wafer_ids: string[];
  genealogy_events: Array<Record<string, any>>;
  state_transitions: StateTransition[];
  pass_records: Array<Record<string, any>>;
  measurement_records: Array<Record<string, any>>;
  error?: string;
}

// ── 颜色 & 节点样式 ──────────────────────────────────────────────
const EVENT_COLOR: Record<string, string> = {
  CHECKIN:  '#3b82f6',
  CHECKOUT: '#10b981',
  SPLIT:    '#f59e0b',
  MERGE:    '#8b5cf6',
  REWORK:   '#ef4444',
  NG:       '#dc2626',
  HOLD:     '#d97706',
  RELEASE:  '#059669',
  DONE:     '#047857',
  OTHER:    '#94a3b8',
};

function nodeStyle(nodeId: string, _rootLot: string) {
  const atIdx = nodeId.indexOf('@');
  const label = atIdx >= 0 ? nodeId.substring(atIdx + 1) : nodeId;
  if (label === '投料' || label === '创建')           return { color: '#6b7280', size: 24, symbol: 'roundRect' };
  if (label === '完成' || label === '完成批次')        return { color: '#047857', size: 24, symbol: 'roundRect' };
  if (label.endsWith('-进站') || label === '进站')     return { color: '#3b82f6', size: 20, symbol: 'circle' };
  if (label.endsWith('-出站') || label === '出站')     return { color: '#10b981', size: 20, symbol: 'circle' };
  if (label.includes('拆'))                           return { color: '#f59e0b', size: 22, symbol: 'diamond' };
  if (label.includes('并') || label.includes('攒'))   return { color: '#8b5cf6', size: 22, symbol: 'diamond' };
  if (label === '返工')                               return { color: '#ef4444', size: 22, symbol: 'triangle' };
  if (label === '不良录入')                           return { color: '#dc2626', size: 20, symbol: 'circle' };
  if (label === '暂停')                               return { color: '#d97706', size: 18, symbol: 'circle' };
  return { color: '#94a3b8', size: 18, symbol: 'circle' };
}

function computeDAGLayout(transitions: StateTransition[]): Map<string, { x: number; y: number }> {
  const outEdges = new Map<string, Set<string>>();
  const inDegree  = new Map<string, number>();
  const allNodes  = new Set<string>();
  for (const t of transitions) {
    allNodes.add(t.from_node); allNodes.add(t.to_node);
    if (!outEdges.has(t.from_node)) outEdges.set(t.from_node, new Set());
    outEdges.get(t.from_node)!.add(t.to_node);
    inDegree.set(t.to_node, (inDegree.get(t.to_node) ?? 0) + 1);
  }
  for (const n of allNodes) if (!inDegree.has(n)) inDegree.set(n, 0);
  const level = new Map<string, number>();
  const tempIn = new Map(inDegree);
  const queue: string[] = [];
  for (const [n, d] of inDegree) if (d === 0) { queue.push(n); level.set(n, 0); }
  while (queue.length) {
    const node = queue.shift()!;
    const lv = level.get(node) ?? 0;
    for (const nb of outEdges.get(node) ?? []) {
      level.set(nb, Math.max(level.get(nb) ?? 0, lv + 1));
      const deg = (tempIn.get(nb) ?? 1) - 1; tempIn.set(nb, deg);
      if (deg === 0) queue.push(nb);
    }
  }
  for (const n of allNodes) if (!level.has(n)) level.set(n, 0);
  const byLevel = new Map<number, string[]>();
  for (const [n, lv] of level) { if (!byLevel.has(lv)) byLevel.set(lv, []); byLevel.get(lv)!.push(n); }
  for (const nodes of byLevel.values()) nodes.sort();

  const LEVEL_GAP = 200; const NODE_GAP = 260;
  const positions = new Map<string, { x: number; y: number }>();
  for (const [lv, nodesAtLevel] of byLevel) {
    const totalW = (nodesAtLevel.length - 1) * NODE_GAP;
    nodesAtLevel.forEach((n, i) => positions.set(n, { x: i * NODE_GAP - totalW / 2, y: lv * LEVEL_GAP }));
  }
  return positions;
}

function buildGenealogyOption(transitions: StateTransition[], rootLot: string) {
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
  const OX = -minX + 60;
  const OY = 50;

  const nodeIds = new Set<string>();
  transitions.forEach((t) => { nodeIds.add(t.from_node); nodeIds.add(t.to_node); });

  const nodes = Array.from(nodeIds).map((id) => {
    const s = nodeStyle(id, rootLot);
    const atIdx     = id.indexOf('@');
    const stateLabel = atIdx >= 0 ? id.substring(atIdx + 1) : id;
    const lotCode   = atIdx >= 0 ? id.substring(0, atIdx) : '';
    const lotShort  = lotCode.split('-').pop() ?? lotCode;
    const dashIdx   = stateLabel.lastIndexOf('-');
    const eventKind  = dashIdx >= 0 ? stateLabel.substring(dashIdx + 1) : stateLabel;
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
          bold:  { fontSize: 10, color: '#1f2937', fontWeight: 'bold', lineHeight: 15 },
          state: { fontSize: 10, color: '#1f2937', fontWeight: 'bold', lineHeight: 15 },
          proc:  { fontSize: 8,  color: '#6b7280', lineHeight: 13 },
        },
        position: 'bottom',
      },
      _incoming: incoming,
    };
  });

  const links = transitions.map((t) => ({
    source: t.from_node,
    target: t.to_node,
    label: { show: false },
    lineStyle: {
      color: EVENT_COLOR[t.event_type] ?? '#94a3b8',
      width: ['CHECKIN', 'CHECKOUT'].includes(t.event_type) ? 1.5 : 2.5,
      curveness: ['SPLIT', 'REWORK'].includes(t.event_type) ? 0.25 : 0,
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
        if (p.dataType !== 'node') return '';
        const id = p.data.id as string;
        const incoming = (p.data._incoming ?? []) as StateTransition[];
        const atIdx     = id.indexOf('@');
        const stateLabel = atIdx >= 0 ? id.substring(atIdx + 1) : id;
        const lotCode   = atIdx >= 0 ? id.substring(0, atIdx) : id;
        const lotShort  = lotCode.split('-').slice(-2).join('-');
        const dashIdx   = stateLabel.lastIndexOf('-');
        const eventKind  = dashIdx >= 0 ? stateLabel.substring(dashIdx + 1) : stateLabel;
        const stationStr = dashIdx >= 0 ? stateLabel.substring(0, dashIdx) : '';
        const t = incoming[0];
        const row = (label: string, val: string | number | undefined, icon = '') =>
          val != null && val !== '' && val !== 0
            ? `<tr><td style="color:#9ca3af;padding:2px 8px 2px 0;white-space:nowrap">${icon}${label}</td><td style="color:#1f2937">${val}</td></tr>`
            : '';
        let html = `<div style="max-width:280px;font-size:11px;line-height:1.6;font-family:sans-serif">`;
        html += `<div style="font-weight:700;font-size:12px;color:#111827;margin-bottom:5px;border-bottom:1px solid #e5e7eb;padding-bottom:3px">`;
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
          html += row('批次规模', t.wafer_count ? `${t.wafer_count} 片` : '', '📦 ');
          html += row('子批次',   t.child_lot, '🔀 ');
          html += `</table>`;
          if (t.event_type === 'CHECKIN' && t.wafer_count) {
            html += `<div style="margin-top:6px;border-top:1px solid #e5e7eb;padding-top:5px">`;
            html += `<div style="font-size:10px;font-weight:600;color:#6b7280;margin-bottom:2px">📸 进站快照</div>`;
            html += `<div style="font-size:10px;color:#374151">批次: <b>${lotShort}</b> · ${t.wafer_count} 片 Wafer</div>`;
            html += `</div>`;
          } else if (t.event_type === 'SPLIT' && t.child_lot) {
            html += `<div style="margin-top:6px;border-top:1px solid #e5e7eb;padding-top:5px">`;
            html += `<div style="font-size:10px;font-weight:600;color:#6b7280;margin-bottom:2px">🔀 拆批快照</div>`;
            html += `<div style="font-size:10px;color:#374151">母批 <b>${lotShort}</b> → 子批 <b>${t.child_lot.split('-').slice(-2).join('-')}</b></div>`;
            html += `</div>`;
          }
        } else {
          html += `<div style="color:#6b7280;font-size:10px">${lotCode}</div>`;
        }
        html += `</div>`;
        return html;
      },
    },
    series: [{
      type: 'graph',
      layout: 'none',
      data: nodes,
      links,
      roam: true,
      draggable: true,
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: [0, 8],
      emphasis: { focus: 'adjacency' },
    }],
  };
}

// ── 子组件：过站时间轴 ────────────────────────────────────────────
const PassTimeline: React.FC<{ records: Array<Record<string, any>> }> = ({ records }) => {
  if (records.length === 0)
    return <div style={{ textAlign: 'center', padding: '24px 0', color: '#9ca3af', fontSize: 12 }}>暂无过站记录</div>;
  return (
    <div style={{ position: 'relative', paddingLeft: 20 }}>
      <div style={{ position: 'absolute', left: 7, top: 6, bottom: 6, width: 2, background: '#e5e7eb', borderRadius: 1 }} />
      {records.map((rec, idx) => (
        <div key={rec.id || idx} style={{ position: 'relative', marginBottom: 10 }}>
          <div style={{ position: 'absolute', left: -20, top: 4, width: 8, height: 8, borderRadius: '50%', background: '#3b82f6', border: '2px solid #fff', boxShadow: '0 0 0 1px #93c5fd', zIndex: 1 }} />
          <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 6, padding: '6px 10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
              <Cpu size={11} color="#6b7280" />
              <span style={{ fontWeight: 600, fontSize: 11, color: '#1f2937' }}>
                {rec.station_id || rec.station_name || `#${idx + 1}`}
              </span>
              {rec.equipment_id && (
                <><ChevronRight size={10} color="#9ca3af" /><span style={{ fontSize: 10, color: '#6b7280' }}>{rec.equipment_id}</span></>
              )}
              {rec.wafer_id && (
                <span style={{ marginLeft: 'auto', fontSize: 9, color: '#6b7280', background: '#f3f4f6', padding: '1px 5px', borderRadius: 10 }}>
                  W-{rec.wafer_id}
                </span>
              )}
            </div>
            <div style={{ display: 'flex', gap: 12, fontSize: 10, color: '#9ca3af' }}>
              {rec.in_time  && <span><Clock size={9} style={{ verticalAlign: 'middle', marginRight: 2 }} />IN: {rec.in_time}</span>}
              {rec.out_time && <span>OUT: {rec.out_time}</span>}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

// ── 子组件：量测数据表格 ──────────────────────────────────────────
const MeasTable: React.FC<{ rows: Array<Record<string, any>> }> = ({ rows }) => {
  if (rows.length === 0)
    return <div style={{ textAlign: 'center', padding: '24px 0', color: '#9ca3af', fontSize: 12 }}>暂无量测记录</div>;
  const cols = Object.keys(rows[0]);
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
        <thead><tr style={{ background: '#f9fafb' }}>
          {cols.map((c) => <th key={c} style={{ padding: '5px 8px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontWeight: 600, color: '#6b7280', whiteSpace: 'nowrap' }}>{c}</th>)}
        </tr></thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{ background: i % 2 === 0 ? '#fff' : '#f9fafb', borderBottom: '1px solid #f3f4f6' }}>
              {cols.map((c) => <td key={c} style={{ padding: '5px 8px', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#374151' }}>{row[c] == null ? '—' : String(row[c])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// ── 主组件 ────────────────────────────────────────────────────────
const API_BASE = 'http://localhost:8000/api/v1/traceability';

type ActiveTab = 'genealogy' | 'timeline' | 'measurement';

interface Props {
  lotCode?: string;
  waferCode?: string;
}

const InlineTraceabilityChart: React.FC<Props> = ({ lotCode: initLot, waferCode: initWafer }) => {
  const [queryLot, setQueryLot]     = useState(initLot || '');
  const [draftLot, setDraftLot]     = useState(initLot || '');
  const [data, setData]             = useState<LotData | null>(null);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState<string | null>(null);

  // ── 前端筛选状态（不触发 API 调用）────────────────────────────
  const [selectedWafer, setSelectedWafer] = useState<string>('all');
  const [activeTab, setActiveTab]         = useState<ActiveTab>('genealogy');
  const [maximized, setMaximized]         = useState(false);

  // ── 批次号变更时才调用后端 ────────────────────────────────────
  useEffect(() => {
    if (!queryLot) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);
    setSelectedWafer('all');
    fetch(`${API_BASE}/lot/${encodeURIComponent(queryLot)}`)
      .then((r) => r.json())
      .then((d: LotData) => {
        if (!cancelled) {
          setData(d);
          if (!d.success) setError(d.error || '查询失败');
        }
      })
      .catch((e) => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [queryLot]);

  // ── 前端筛选（纯内存操作，0 网络延迟）────────────────────────
  const filteredPass = data?.pass_records
    ? (selectedWafer === 'all' ? data.pass_records : data.pass_records.filter((r) => String(r.wafer_id) === selectedWafer))
    : [];
  const filteredMeas = data?.measurement_records
    ? (selectedWafer === 'all' ? data.measurement_records : data.measurement_records.filter((r) => String(r.wafer_id) === selectedWafer))
    : [];

  const handleSearch = () => {
    const t = draftLot.trim();
    if (t && t !== queryLot) setQueryLot(t);
  };

  // ── tab 定义 ──
  const tabs: { id: ActiveTab; label: string; count?: number }[] = [
    { id: 'genealogy',    label: '谱系 DAG' },
    { id: 'timeline',     label: '过站时间轴', count: filteredPass.length },
    { id: 'measurement',  label: '量测数据',  count: filteredMeas.length },
  ];

  // useMemo 确保 data 不变时不重新构建 ECharts option 对象，避免触发 ECharts 重渲染
  const dagOption = useMemo(
    () => data?.success ? buildGenealogyOption(data.state_transitions ?? [], data.lot_code) : null,
    [data], // eslint-disable-line react-hooks/exhaustive-deps
  );

  const dagHeight   = maximized ? 'calc(100vh - 210px)' : 340;
  const panelHeight = maximized ? 'calc(100vh - 160px)' : 380;

  const Header = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: '#f8fafc', borderBottom: '1px solid #e5e7eb', flexWrap: 'wrap' }}>
      <span style={{ fontSize: 12, fontWeight: 600, color: '#4b5563', whiteSpace: 'nowrap' }}>📦 批次追溯</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1, minWidth: 180 }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <input
            value={draftLot}
            onChange={(e) => setDraftLot(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="输入批次号…"
            style={{ width: '100%', padding: '4px 28px 4px 8px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 12, outline: 'none', boxSizing: 'border-box' }}
          />
          <button onClick={handleSearch}
            style={{ position: 'absolute', right: 5, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: '#9ca3af', display: 'flex' }}>
            <Search size={12} />
          </button>
        </div>
      </div>
      {data?.success && data.wafer_ids.length > 0 && (
        <select value={selectedWafer} onChange={(e) => setSelectedWafer(e.target.value)}
          style={{ padding: '4px 24px 4px 8px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 12, background: '#fff', cursor: 'pointer', appearance: 'none', backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`, backgroundRepeat: 'no-repeat', backgroundPosition: 'right 6px center' }}>
          <option value="all">全部 Wafer ({data.wafer_ids.length})</option>
          {data.wafer_ids.map((w) => <option key={w} value={w}>Wafer {w}</option>)}
        </select>
      )}
      <button onClick={() => setMaximized((v) => !v)} title={maximized ? '还原' : '最大化'}
        style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', padding: 4, color: '#6b7280', display: 'flex', alignItems: 'center', borderRadius: 4, flexShrink: 0 }}>
        {maximized ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
      </button>
    </div>
  );

  const DataPanel = (
    <>
      {!loading && data?.success && (
        <>
          <div style={{ display: 'flex', gap: 16, padding: '8px 14px', background: '#f0fdf4', borderBottom: '1px solid #e5e7eb', fontSize: 11, color: '#374151', flexWrap: 'wrap' }}>
            {Object.entries(data.lot_info).slice(0, 6).map(([k, v]) => (
              <span key={k}><span style={{ color: '#9ca3af' }}>{k}:</span> {String(v ?? '—')}</span>
            ))}
            <span style={{ marginLeft: 'auto', color: '#9ca3af' }}>{data.wafer_ids.length} 片Wafer</span>
          </div>
          <div style={{ display: 'flex', borderBottom: '1px solid #e5e7eb', background: '#fff' }}>
            {tabs.map((t) => (
              <button key={t.id} onClick={() => setActiveTab(t.id)}
                style={{ padding: '8px 14px', border: 'none', borderBottom: activeTab === t.id ? '2px solid #3b82f6' : '2px solid transparent', background: 'transparent', color: activeTab === t.id ? '#2563eb' : '#6b7280', fontSize: 12, fontWeight: activeTab === t.id ? 600 : 400, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
                {t.label}
                {t.count !== undefined && (
                  <span style={{ fontSize: 10, background: activeTab === t.id ? '#dbeafe' : '#f3f4f6', color: activeTab === t.id ? '#1d4ed8' : '#9ca3af', borderRadius: 10, padding: '1px 5px' }}>{t.count}</span>
                )}
              </button>
            ))}
          </div>
          <div style={{ padding: '10px 14px', maxHeight: panelHeight, overflowY: 'auto' }}>
            {activeTab === 'genealogy' && (
              dagOption
                ? <ReactECharts option={dagOption} style={{ height: dagHeight }} notMerge lazyUpdate />
                : <div style={{ textAlign: 'center', padding: '32px 0', color: '#9ca3af', fontSize: 12 }}>暂无谱系数据</div>
            )}
            {activeTab === 'timeline'    && <PassTimeline records={filteredPass} />}
            {activeTab === 'measurement' && <MeasTable rows={filteredMeas} />}
          </div>
        </>
      )}
    </>
  );

  const StatusArea = (
    <>
      {loading && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '32px 0', color: '#6b7280' }}>
          <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} />
          <span style={{ fontSize: 12 }}>正在查询批次 {queryLot}…</span>
        </div>
      )}
      {!loading && error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '16px', color: '#ef4444', fontSize: 12 }}>
          <AlertCircle size={14} />{error}
        </div>
      )}
      {!loading && !error && !data && (
        <div style={{ textAlign: 'center', padding: '28px 0', color: '#9ca3af', fontSize: 12 }}>输入批次号后按 Enter 查询追溯履历</div>
      )}
    </>
  );

  if (maximized) {
    return (
      <div
        style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        onClick={(e) => { if (e.target === e.currentTarget) setMaximized(false); }}
      >
        <div style={{ width: 'calc(100vw - 48px)', maxWidth: 1200, maxHeight: 'calc(100vh - 48px)', background: '#fff', borderRadius: 12, overflow: 'hidden', display: 'flex', flexDirection: 'column', boxShadow: '0 20px 60px rgba(0,0,0,0.3)' }}>
          {Header}
          <div style={{ flex: 1, overflowY: 'auto' }}>{StatusArea}{DataPanel}</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 10, overflow: 'hidden', background: '#fff', marginTop: 8, fontSize: 13 }}>
      {Header}

      {StatusArea}
      {DataPanel}
    </div>
  );
};

export default InlineTraceabilityChart;
