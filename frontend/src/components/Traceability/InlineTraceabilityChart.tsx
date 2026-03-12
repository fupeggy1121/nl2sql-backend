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
  station?: string;
  time?: string;
  wafer_count?: number;
  operator_id?: string;
  note?: string;
  child_lot?: string;
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
  DONE:     '#6b7280',
};

function nodeStyle(nodeId: string, rootLot: string) {
  if (nodeId.endsWith('@投料'))  return { color: '#1d4ed8', size: 28, symbol: 'roundRect' };
  if (nodeId.endsWith('@完成'))  return { color: '#047857', size: 28, symbol: 'roundRect' };
  if (nodeId.includes('@投料') && !nodeId.startsWith(rootLot)) return { color: '#7c3aed', size: 22, symbol: 'circle' };
  if (nodeId.includes('-进站'))  return { color: '#60a5fa', size: 18, symbol: 'circle' };
  if (nodeId.includes('-出站'))  return { color: '#34d399', size: 18, symbol: 'circle' };
  return { color: '#94a3b8', size: 16, symbol: 'circle' };
}

function buildGenealogyOption(transitions: StateTransition[], rootLot: string) {
  if (!transitions || transitions.length === 0) return null;
  const nodeIds = new Set<string>();
  transitions.forEach((t) => { nodeIds.add(t.from_node); nodeIds.add(t.to_node); });

  const nodes = Array.from(nodeIds).map((id) => {
    const s = nodeStyle(id, rootLot);
    const label = id.includes('@') ? id.split('@')[1] : id;
    const lotPart = id.includes('@') ? id.split('@')[0] : '';
    const isOtherLot = lotPart && lotPart !== rootLot;
    return {
      id, name: id,
      symbolSize: s.size,
      symbol: s.symbol,
      itemStyle: { color: s.color },
      label: {
        show: true,
        formatter: isOtherLot
          ? `{lot|${lotPart.split('-').slice(-2).join('-')}}\n{state|${label}}`
          : `{state|${label}}`,
        rich: {
          lot:   { fontSize: 9,  color: '#6b7280', lineHeight: 14 },
          state: { fontSize: 10, color: '#1f2937', fontWeight: 'bold' },
        },
        position: 'bottom',
      },
    };
  });

  const links = transitions.map((t) => ({
    source: t.from_node,
    target: t.to_node,
    _meta: t,
    label: {
      show: true,
      formatter: t.event,
      fontSize: 9,
      color: '#1f2937',
      backgroundColor: (EVENT_COLOR[t.event_type] ?? '#94a3b8') + '22',
      borderColor: EVENT_COLOR[t.event_type] ?? '#94a3b8',
      borderWidth: 1,
      borderRadius: 4,
      padding: [2, 4],
    },
    lineStyle: {
      color: EVENT_COLOR[t.event_type] ?? '#94a3b8',
      width: ['CHECKIN', 'CHECKOUT'].includes(t.event_type) ? 1.5 : 2.5,
      curveness: ['SPLIT', 'REWORK'].includes(t.event_type) ? 0.3 : 0.1,
      type: t.event_type === 'CHECKIN' ? 'dashed' : 'solid',
    },
  }));

  return {
    backgroundColor: '#f8fafc',
    tooltip: {
      trigger: 'item',
      formatter: (p: any) => {
        if (p.dataType === 'node') return `<b>${p.data.id}</b>`;
        const m = p.data._meta as StateTransition;
        if (!m) return '';
        return [
          `<b>${m.event}</b>`,
          m.time    ? `⏱ ${m.time}` : '',
          m.station ? `🏭 ${m.station}` : '',
          m.operator_id ? `👤 ${m.operator_id}` : '',
          m.wafer_count != null ? `🔢 ${m.wafer_count} 片` : '',
          m.note    ? `📝 ${m.note}` : '',
        ].filter(Boolean).join('<br/>');
      },
    },
    series: [{
      type: 'graph',
      layout: 'force',
      force: { repulsion: 400, gravity: 0.03, edgeLength: [60, 140], layoutAnimation: false },
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
