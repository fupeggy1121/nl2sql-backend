/**
 * NLTestManager.tsx — NL 语义查询端到端测试管理
 *
 * 功能：
 *   - 维护测试用例列表（增删改，持久化到 localStorage）
 *   - 单条/全量执行：直接调用 POST /api/v1/chat
 *   - 多次运行验证稳健性（run_count）
 *   - SQL 断言检查（sql_contains / sql_excludes / tables_present）
 *   - 稳健性 diff：多次运行 SQL 不一致时高亮差异
 *   - JSON 报告导出
 */
import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  Play, Plus, Trash2, Edit2, Download, RefreshCw, X, Check,
  ChevronRight, ChevronDown, AlertCircle, CheckCircle, Clock,
  Loader2, FlaskConical, ListChecks, BarChart2, Copy
} from 'lucide-react';

// ── API base ──────────────────────────────────────────────────────
const API_BASE: string = (() => {
  const env = (import.meta as any)?.env?.VITE_API_BASE_URL;
  if (env) return env.replace(/\/api\/.*$/, '');
  return 'http://localhost:8000';
})();

const CHAT_URL = `${API_BASE}/api/v1/chat`;
const LS_KEY   = 'nl_test_cases_v2';

// ── Types ─────────────────────────────────────────────────────────
export interface TestCase {
  id: string;
  nl: string;
  intent: string;
  run_count: number;
  expected: {
    sql_contains:   string[];
    sql_excludes:   string[];
    tables_present: string[];
    sql_pattern?:   string;
  };
}

interface RunResult {
  run_idx:        number;
  sql:            string;
  physical_tables: string[];
  matched_classes: string[];
  success:        boolean;
  failures:       string[];
  error:          string;
  latency_ms:     number;
  sql_retry_count: number;
}

interface CaseState {
  status:   'idle' | 'running' | 'done';
  runs:     RunResult[];
  stable:   boolean | null;
}

// ── Default cases ─────────────────────────────────────────────────
const DEFAULT_CASES: TestCase[] = [
  {
    id: 'wip_by_station',
    nl: '统计各站点的在制品数量',
    intent: '按工艺站点分组，统计 WIP(status=50) 批次数量',
    run_count: 3,
    expected: {
      sql_contains:   ['GROUP BY', 'status'],
      sql_excludes:   ['local_production_batch'],
      tables_present: ['matrix_routerx_operation_lot'],
    },
  },
  {
    id: 'wafer_wip_count',
    nl: '当前在制的晶圆总数是多少',
    intent: 'WIP 状态下所有晶圆数量（wafer 粒度）',
    run_count: 3,
    expected: {
      sql_contains:   ['COUNT', 'wafer'],
      sql_excludes:   ['local_production_batch'],
      tables_present: ['matrix_routerx_operation_lot_wafer'],
    },
  },
  {
    id: 'wafer_wip_by_station',
    nl: '各站点在制晶圆数量分布',
    intent: 'Wafer→Sublot(atStation)→ProcessStation，按站点 GROUP BY COUNT(wafer)',
    run_count: 3,
    expected: {
      sql_contains:   ['COUNT', 'GROUP BY'],
      sql_excludes:   ['local_production_batch'],
      tables_present: ['matrix_routerx_operation_lot_wafer'],
    },
  },
  {
    id: 'equipment_list',
    nl: '查询所有设备信息',
    intent: '直接查设备表，不带过滤',
    run_count: 2,
    expected: {
      sql_contains:   ['equipment'],
      sql_excludes:   [],
      tables_present: ['equipment'],
    },
  },
  {
    id: 'carrier_available',
    nl: '当前可用的片篮数量',
    intent: '统计状态可用的 carrier 数量',
    run_count: 2,
    expected: {
      sql_contains:   ['COUNT', 'carrier'],
      sql_excludes:   [],
      tables_present: ['carrier'],
    },
  },
  {
    id: 'completed_lots',
    nl: '已完结的批次有多少条',
    intent: '统计 status=100 的批次数量',
    run_count: 2,
    expected: {
      sql_contains:   ['COUNT', 'status'],
      sql_excludes:   ['local_production_batch'],
      tables_present: ['matrix_routerx_operation_lot'],
    },
  },
  {
    id: 'wip_with_equipment',
    nl: '统计每台设备上当前处理的批次数量',
    intent: 'Equipment + Sublot 双类关联，按设备聚合 WIP（边界测试）',
    run_count: 3,
    expected: {
      sql_contains:   ['GROUP BY', 'equipment'],
      sql_excludes:   ['local_production_batch'],
      tables_present: [],
    },
  },
  {
    id: 'nonexistent_station',
    nl: '查询 XX不存在站点 的在制数量',
    intent: '不存在站点名的过滤——SQL 能生成，结果应为空行',
    run_count: 2,
    expected: {
      sql_contains:   ['status'],
      sql_excludes:   ['local_production_batch'],
      tables_present: [],
    },
  },
];

// ── Helpers ───────────────────────────────────────────────────────
function loadCases(): TestCase[] {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return DEFAULT_CASES;
}

function saveCases(cases: TestCase[]) {
  localStorage.setItem(LS_KEY, JSON.stringify(cases));
}

function checkExpected(
  sql: string,
  tables: string[],
  expected: TestCase['expected'],
): string[] {
  const failures: string[] = [];
  const up = sql.toUpperCase();
  for (const kw of expected.sql_contains ?? []) {
    if (!up.includes(kw.toUpperCase())) failures.push(`sql_contains 缺失: "${kw}"`);
  }
  for (const kw of expected.sql_excludes ?? []) {
    if (up.includes(kw.toUpperCase())) failures.push(`sql_excludes 禁止词出现: "${kw}"`);
  }
  for (const tbl of expected.tables_present ?? []) {
    if (!tables.includes(tbl)) failures.push(`tables_present 缺失: "${tbl}" (实际: ${tables.join(', ') || '无'})`);
  }
  if (expected.sql_pattern) {
    try {
      if (!new RegExp(expected.sql_pattern, 'is').test(sql))
        failures.push(`sql_pattern 不匹配: /${expected.sql_pattern}/`);
    } catch { failures.push(`sql_pattern 正则无效: ${expected.sql_pattern}`); }
  }
  return failures;
}

function sqlDiff(a: string, b: string): string[] {
  const la = a.split('\n');
  const lb = b.split('\n');
  const result: string[] = [];
  const maxLen = Math.max(la.length, lb.length);
  for (let i = 0; i < maxLen; i++) {
    const lineA = la[i] ?? '';
    const lineB = lb[i] ?? '';
    if (lineA !== lineB) {
      if (lineA) result.push(`- ${lineA}`);
      if (lineB) result.push(`+ ${lineB}`);
    }
  }
  return result;
}

// ── API call ──────────────────────────────────────────────────────
async function callChat(nl: string): Promise<{
  sql: string; physical_tables: string[]; matched_classes: string[];
  success: boolean; error: string; sql_retry_count: number;
}> {
  const session_id = crypto.randomUUID();
  const resp = await fetch(CHAT_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: nl, session_id }),
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const json = await resp.json();
  const data = json.data ?? {};
  // SQL 可能在 data.query_plan.generated_sql 或 data.query_result.sql
  const sql  = data.query_plan?.generated_sql
            ?? data.query_result?.sql
            ?? data.generated_sql
            ?? data.sql
            ?? '';

  let physical_tables: string[] = [];
  let matched_classes: string[] = [];
  for (const step of data.pipeline_trace ?? []) {
    // 响应中字段名为 "step" 而非 "node"
    if (step.step === 'semantic_resolver') {
      physical_tables = step.detail?.physical_tables ?? [];
      matched_classes = (step.detail?.matched_classes ?? []).map((mc: any) => mc.logic_class ?? '');
      break;
    }
  }
  return {
    sql, physical_tables, matched_classes,
    success: json.success || data.success || false,
    error: data.error ?? '',
    sql_retry_count: data.sql_retry_count ?? 0,
  };
}

// ═════════════════════════════════════════════════════════════════
// Main Component
// ═════════════════════════════════════════════════════════════════
const NLTestManager: React.FC = () => {
  const [cases,     setCases]     = useState<TestCase[]>(loadCases);
  const [states,    setStates]    = useState<Record<string, CaseState>>({});
  const [selected,  setSelected]  = useState<string | null>(null);
  const [editItem,  setEditItem]  = useState<TestCase | null>(null);
  const [isNew,     setIsNew]     = useState(false);
  const [globalRunning, setGlobalRunning] = useState(false);
  const [expandedRun, setExpandedRun] = useState<Record<string, number | null>>({});
  const abortRef = useRef(false);

  // persist to localStorage
  useEffect(() => { saveCases(cases); }, [cases]);

  // ── run single case ──────────────────────────────────────────
  const runCase = useCallback(async (tc: TestCase) => {
    setStates(prev => ({
      ...prev,
      [tc.id]: { status: 'running', runs: [], stable: null },
    }));

    const runs: RunResult[] = [];
    for (let i = 1; i <= tc.run_count; i++) {
      if (abortRef.current) break;
      const t0 = performance.now();
      try {
        const info = await callChat(tc.nl);
        const failures = checkExpected(info.sql, info.physical_tables, tc.expected);
        runs.push({
          run_idx: i,
          sql: info.sql,
          physical_tables: info.physical_tables,
          matched_classes:  info.matched_classes,
          success: failures.length === 0,
          failures,
          error: info.error,
          latency_ms: performance.now() - t0,
          sql_retry_count: info.sql_retry_count,
        });
      } catch (e: any) {
        runs.push({
          run_idx: i, sql: '', physical_tables: [], matched_classes: [],
          success: false, failures: [`请求失败: ${e.message}`],
          error: e.message, latency_ms: performance.now() - t0,
          sql_retry_count: 0,
        });
      }
      // update progressively
      setStates(prev => ({
        ...prev,
        [tc.id]: { status: 'running', runs: [...runs], stable: null },
      }));
    }
    const sqls   = runs.filter(r => r.sql).map(r => r.sql.trim().toUpperCase());
    const stable = sqls.length > 0 ? new Set(sqls).size === 1 : null;
    setStates(prev => ({
      ...prev,
      [tc.id]: { status: 'done', runs, stable },
    }));
  }, []);

  const runAll = useCallback(async () => {
    abortRef.current = false;
    setGlobalRunning(true);
    for (const tc of cases) {
      if (abortRef.current) break;
      await runCase(tc);
    }
    setGlobalRunning(false);
  }, [cases, runCase]);

  const stopAll = () => { abortRef.current = true; setGlobalRunning(false); };

  // ── export JSON ──────────────────────────────────────────────
  const exportReport = () => {
    const report = {
      generated_at: new Date().toISOString(),
      summary: {
        total: cases.length,
        full_pass: cases.filter(tc => {
          const s = states[tc.id];
          return s && s.status === 'done' && s.runs.every(r => r.success);
        }).length,
      },
      cases: cases.map(tc => ({ ...tc, result: states[tc.id] ?? null })),
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `nl_eval_report_${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
    a.click();
  };

  // ── summary stats ────────────────────────────────────────────
  const done  = cases.filter(tc => states[tc.id]?.status === 'done');
  const passed = done.filter(tc => states[tc.id]!.runs.every(r => r.success));
  const failed = done.filter(tc => states[tc.id]!.runs.some(r => !r.success));
  const running_n = cases.filter(tc => states[tc.id]?.status === 'running').length;

  // ── selected case state ──────────────────────────────────────
  const selCase  = cases.find(tc => tc.id === selected) ?? null;
  const selState = selected ? states[selected] : null;

  // ── edit helpers ─────────────────────────────────────────────
  const openNew = () => {
    setEditItem({
      id: `case_${Date.now()}`,
      nl: '', intent: '', run_count: 2,
      expected: { sql_contains: [], sql_excludes: [], tables_present: [] },
    });
    setIsNew(true);
  };
  const openEdit = (tc: TestCase) => { setEditItem({ ...tc, expected: { ...tc.expected } }); setIsNew(false); };
  const saveEdit = () => {
    if (!editItem) return;
    if (isNew) {
      setCases(prev => [...prev, editItem]);
    } else {
      setCases(prev => prev.map(tc => tc.id === editItem.id ? editItem : tc));
    }
    setEditItem(null);
  };
  const deleteCase = (id: string) => {
    setCases(prev => prev.filter(tc => tc.id !== id));
    if (selected === id) setSelected(null);
  };

  // ═══════════════════════════════════════════════════════════════
  // Render
  // ═══════════════════════════════════════════════════════════════
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#f8fafc' }}>

      {/* ── Top bar ── */}
      <div style={{ background: '#fff', borderBottom: '1px solid #e5e7eb', padding: '12px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <FlaskConical size={18} color="#7c3aed" />
          <span style={{ fontSize: 15, fontWeight: 700, color: '#111827' }}>NL 语义测试</span>
          <span style={{ fontSize: 12, color: '#6b7280', marginLeft: 4 }}>端到端 SQL 生成质量验证</span>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {/* summary badges */}
          {done.length > 0 && (
            <>
              <Badge color="#16a34a" bg="#f0fdf4">{passed.length} 通过</Badge>
              {failed.length > 0 && <Badge color="#dc2626" bg="#fef2f2">{failed.length} 失败</Badge>}
              {running_n > 0 && <Badge color="#d97706" bg="#fffbeb">{running_n} 进行中</Badge>}
            </>
          )}
          <Btn icon={Download} onClick={exportReport} disabled={done.length === 0}>导出报告</Btn>
          <Btn icon={Plus} onClick={openNew}>添加用例</Btn>
          {globalRunning
            ? <Btn icon={X} variant="danger" onClick={stopAll}>停止</Btn>
            : <Btn icon={Play} variant="primary" onClick={runAll}>运行全部</Btn>
          }
        </div>
      </div>

      {/* ── Body ── */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>

        {/* ── Left: case list ── */}
        <div style={{ width: 340, flexShrink: 0, background: '#fff', borderRight: '1px solid #e5e7eb', overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '10px 14px 8px', fontSize: 11, fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.5px', borderBottom: '1px solid #f3f4f6' }}>
            用例列表 ({cases.length})
          </div>
          {cases.map(tc => {
            const st = states[tc.id];
            const isActive = selected === tc.id;
            const passAll = st?.status === 'done' && st.runs.every(r => r.success);
            const failAny = st?.status === 'done' && st.runs.some(r => !r.success);
            const isRunning = st?.status === 'running';
            return (
              <div key={tc.id}
                onClick={() => setSelected(tc.id)}
                style={{ padding: '10px 14px', cursor: 'pointer', background: isActive ? '#eff6ff' : 'transparent', borderLeft: isActive ? '3px solid #2563eb' : '3px solid transparent', borderBottom: '1px solid #f3f4f6', display: 'flex', flexDirection: 'column', gap: 3 }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <StatusDot running={isRunning} pass={passAll} fail={failAny} idle={!st} />
                    <span style={{ fontSize: 12, fontWeight: 600, color: '#374151' }}>{tc.id}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <IconBtn title="编辑" onClick={e => { e.stopPropagation(); openEdit(tc); }}><Edit2 size={12} /></IconBtn>
                    <IconBtn title="运行" onClick={e => { e.stopPropagation(); setSelected(tc.id); runCase(tc); }}><Play size={12} color="#7c3aed" /></IconBtn>
                    <IconBtn title="删除" onClick={e => { e.stopPropagation(); deleteCase(tc.id); }}><Trash2 size={12} color="#dc2626" /></IconBtn>
                  </div>
                </div>
                <div style={{ fontSize: 12, color: '#1d4ed8', fontStyle: 'italic', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {tc.nl}
                </div>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <PillTag>×{tc.run_count} 次</PillTag>
                  {st?.status === 'done' && (
                    <>
                      <PillTag color={passAll ? '#16a34a' : '#dc2626'} bg={passAll ? '#f0fdf4' : '#fef2f2'}>
                        {st.runs.filter(r => r.success).length}/{st.runs.length} pass
                      </PillTag>
                      {tc.run_count > 1 && st.stable !== null && (
                        <PillTag color={st.stable ? '#0891b2' : '#d97706'} bg={st.stable ? '#ecfeff' : '#fffbeb'}>
                          {st.stable ? '稳定' : '不稳定'}
                        </PillTag>
                      )}
                    </>
                  )}
                  {isRunning && (
                    <PillTag color="#7c3aed" bg="#f5f3ff">
                      <Loader2 size={9} style={{ animation: 'spin 1s linear infinite' }} />运行中
                    </PillTag>
                  )}
                </div>
              </div>
            );
          })}
          {cases.length === 0 && (
            <div style={{ padding: 24, textAlign: 'center', color: '#9ca3af', fontSize: 12 }}>
              暂无用例，点击"添加用例"新建
            </div>
          )}
        </div>

        {/* ── Right: detail/results ── */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 24, minWidth: 0 }}>
          {!selCase ? (
            <EmptyHint />
          ) : (
            <CaseDetail
              tc={selCase}
              st={selState}
              expandedRun={expandedRun[selCase.id] ?? null}
              setExpandedRun={(idx) => setExpandedRun(prev => ({ ...prev, [selCase.id]: idx }))}
              onRun={() => runCase(selCase)}
            />
          )}
        </div>
      </div>

      {/* ── Edit modal ── */}
      {editItem && (
        <EditModal
          item={editItem}
          isNew={isNew}
          onChange={setEditItem}
          onSave={saveEdit}
          onClose={() => setEditItem(null)}
        />
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
};

// ═════════════════════════════════════════════════════════════════
// CaseDetail
// ═════════════════════════════════════════════════════════════════
const CaseDetail: React.FC<{
  tc: TestCase; st: CaseState | undefined | null;
  expandedRun: number | null; setExpandedRun: (i: number | null) => void;
  onRun: () => void;
}> = ({ tc, st, expandedRun, setExpandedRun, onRun }) => {
  const isRunning = st?.status === 'running';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* header */}
      <div style={{ background: '#fff', borderRadius: 8, border: '1px solid #e5e7eb', padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 4 }}>{tc.id}</div>
            <div style={{ fontSize: 14, color: '#1d4ed8', fontWeight: 500, marginBottom: 6 }}>"{tc.nl}"</div>
            <div style={{ fontSize: 12, color: '#6b7280' }}>{tc.intent}</div>
          </div>
          <button onClick={onRun} disabled={isRunning}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', background: isRunning ? '#e5e7eb' : '#7c3aed', color: isRunning ? '#9ca3af' : '#fff', border: 'none', borderRadius: 6, cursor: isRunning ? 'default' : 'pointer', fontSize: 12, fontWeight: 600 }}>
            {isRunning ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <Play size={13} />}
            {isRunning ? '运行中…' : `运行 ×${tc.run_count}`}
          </button>
        </div>

        {/* assertions */}
        <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {tc.expected.sql_contains.map(kw => (
            <PillTag key={kw} color="#0891b2" bg="#ecfeff">must: {kw}</PillTag>
          ))}
          {tc.expected.sql_excludes.map(kw => (
            <PillTag key={kw} color="#dc2626" bg="#fef2f2">no: {kw}</PillTag>
          ))}
          {tc.expected.tables_present.map(t => (
            <PillTag key={t} color="#7c3aed" bg="#f5f3ff">table: {t}</PillTag>
          ))}
        </div>
      </div>

      {/* runs */}
      {st && st.runs.length > 0 && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
            <ListChecks size={13} /> 运行结果
            {st.status === 'done' && tc.run_count > 1 && st.stable !== null && (
              <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 9999, background: st.stable ? '#ecfeff' : '#fffbeb', color: st.stable ? '#0891b2' : '#d97706', fontWeight: 600 }}>
                {st.stable ? '✓ 输出稳定' : '⚠ 多次输出不一致'}
              </span>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {st.runs.map(run => (
              <RunCard key={run.run_idx} run={run} total={tc.run_count}
                expanded={expandedRun === run.run_idx}
                onToggle={() => setExpandedRun(expandedRun === run.run_idx ? null : run.run_idx)}
              />
            ))}
          </div>

          {/* diff section */}
          {st.status === 'done' && !st.stable && tc.run_count > 1 && (
            <DiffPanel runs={st.runs} />
          )}
        </div>
      )}

      {(!st || st.runs.length === 0) && (
        <div style={{ background: '#fff', borderRadius: 8, border: '1px solid #e5e7eb', padding: 32, textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>
          点击"运行"按钮开始测试
        </div>
      )}
    </div>
  );
};

// ─── RunCard ──────────────────────────────────────────────────────
const RunCard: React.FC<{ run: RunResult; total: number; expanded: boolean; onToggle: () => void }> = ({ run, total, expanded, onToggle }) => {
  const [copied, setCopied] = useState(false);

  const copySQL = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(run.sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div style={{ background: '#fff', border: `1px solid ${run.success ? '#bbf7d0' : '#fecaca'}`, borderRadius: 8, overflow: 'hidden' }}>
      <div onClick={onToggle} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', cursor: 'pointer', background: run.success ? '#f0fdf4' : '#fef2f2' }}>
        {run.success
          ? <CheckCircle size={14} color="#16a34a" />
          : <AlertCircle size={14} color="#dc2626" />
        }
        <span style={{ fontSize: 12, fontWeight: 600, color: '#374151' }}>Run {run.run_idx}/{total}</span>
        {run.sql_retry_count > 0 && (
          <PillTag color="#d97706" bg="#fffbeb">retry ×{run.sql_retry_count}</PillTag>
        )}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 11, color: '#9ca3af', display: 'flex', alignItems: 'center', gap: 3 }}><Clock size={10} />{run.latency_ms.toFixed(0)}ms</span>
          {expanded ? <ChevronDown size={13} color="#6b7280" /> : <ChevronRight size={13} color="#6b7280" />}
        </div>
      </div>

      {expanded && (
        <div style={{ padding: '12px 14px', borderTop: '1px solid #e5e7eb', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {run.failures.length > 0 && (
            <div style={{ background: '#fef2f2', borderRadius: 6, padding: '8px 10px' }}>
              {run.failures.map((f, i) => (
                <div key={i} style={{ fontSize: 12, color: '#dc2626', display: 'flex', gap: 6 }}>
                  <span>✗</span><span>{f}</span>
                </div>
              ))}
              {run.error && !run.failures.some(f => f.includes(run.error)) && (
                <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>backend error: {run.error}</div>
              )}
            </div>
          )}

          {run.physical_tables.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              <span style={{ fontSize: 11, color: '#6b7280', marginRight: 4 }}>物理表:</span>
              {run.physical_tables.map(t => <PillTag key={t} color="#7c3aed" bg="#f5f3ff">{t}</PillTag>)}
            </div>
          )}
          {run.matched_classes.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              <span style={{ fontSize: 11, color: '#6b7280', marginRight: 4 }}>本体类:</span>
              {run.matched_classes.map(c => <PillTag key={c} color="#0891b2" bg="#ecfeff">{c}</PillTag>)}
            </div>
          )}

          {run.sql ? (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: '#6b7280' }}>生成 SQL</span>
                <button onClick={copySQL} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: copied ? '#16a34a' : '#6b7280', background: 'none', border: 'none', cursor: 'pointer', padding: '2px 6px' }}>
                  {copied ? <Check size={11} /> : <Copy size={11} />}{copied ? '已复制' : '复制'}
                </button>
              </div>
              <pre style={{ background: '#1e1e2e', color: '#cdd6f4', borderRadius: 6, padding: '10px 12px', fontSize: 11, lineHeight: 1.6, overflowX: 'auto', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {run.sql}
              </pre>
            </div>
          ) : (
            <div style={{ fontSize: 12, color: '#9ca3af' }}>无生成 SQL（可能查询失败）</div>
          )}
        </div>
      )}
    </div>
  );
};

// ─── DiffPanel ────────────────────────────────────────────────────
const DiffPanel: React.FC<{ runs: RunResult[] }> = ({ runs }) => {
  const sqls = runs.filter(r => r.sql).map(r => r.sql);
  if (sqls.length < 2) return null;
  const diffs = sqls.slice(1).map((s, i) => ({
    label: `run-1 vs run-${i + 2}`,
    lines: sqlDiff(sqls[0], s),
  })).filter(d => d.lines.length > 0);
  if (diffs.length === 0) return null;

  return (
    <div style={{ marginTop: 12, background: '#fff', border: '1px solid #fde68a', borderRadius: 8, overflow: 'hidden' }}>
      <div style={{ background: '#fffbeb', padding: '8px 14px', fontSize: 12, fontWeight: 600, color: '#92400e', display: 'flex', alignItems: 'center', gap: 6 }}>
        <BarChart2 size={13} /> SQL 差异分析（多次运行不一致）
      </div>
      {diffs.map(d => (
        <div key={d.label} style={{ padding: '10px 14px', borderTop: '1px solid #fde68a' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#6b7280', marginBottom: 6 }}>{d.label}</div>
          <pre style={{ margin: 0, fontSize: 11, lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {d.lines.map((line, i) => (
              <div key={i} style={{ background: line.startsWith('-') ? '#fef2f2' : line.startsWith('+') ? '#f0fdf4' : 'transparent', color: line.startsWith('-') ? '#b91c1c' : line.startsWith('+') ? '#15803d' : '#374151', padding: '0 4px' }}>
                {line}
              </div>
            ))}
          </pre>
        </div>
      ))}
    </div>
  );
};

// ═════════════════════════════════════════════════════════════════
// EditModal
// ═════════════════════════════════════════════════════════════════
const EditModal: React.FC<{
  item: TestCase; isNew: boolean;
  onChange: (tc: TestCase) => void;
  onSave: () => void; onClose: () => void;
}> = ({ item, isNew, onChange, onSave, onClose }) => {
  const set = (key: keyof TestCase, val: any) => onChange({ ...item, [key]: val });
  const setExp = (key: keyof TestCase['expected'], val: string) => {
    const arr = val.split('\n').map(s => s.trim()).filter(Boolean);
    onChange({ ...item, expected: { ...item.expected, [key]: arr } });
  };

  const fldStyle: React.CSSProperties = {
    width: '100%', padding: '7px 10px', border: '1px solid #d1d5db', borderRadius: 6,
    fontSize: 12, fontFamily: 'inherit', background: '#fff', boxSizing: 'border-box',
  };
  const lbl: React.CSSProperties = { fontSize: 11, fontWeight: 600, color: '#6b7280', display: 'block', marginBottom: 4 };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
      <div style={{ background: '#fff', borderRadius: 10, width: 580, maxHeight: '85vh', overflow: 'auto', boxShadow: '0 20px 60px rgba(0,0,0,0.2)' }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 14, fontWeight: 700 }}>{isNew ? '添加测试用例' : '编辑测试用例'}</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280' }}><X size={16} /></button>
        </div>
        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={lbl}>用例 ID *</label>
              <input value={item.id} onChange={e => set('id', e.target.value)} style={fldStyle} placeholder="wip_by_station" />
            </div>
            <div>
              <label style={lbl}>重复次数</label>
              <input type="number" min={1} max={10} value={item.run_count} onChange={e => set('run_count', Number(e.target.value))} style={fldStyle} />
            </div>
          </div>
          <div>
            <label style={lbl}>NL 查询语句 *</label>
            <input value={item.nl} onChange={e => set('nl', e.target.value)} style={fldStyle} placeholder="统计各站点的在制品数量" />
          </div>
          <div>
            <label style={lbl}>意图说明</label>
            <textarea value={item.intent} onChange={e => set('intent', e.target.value)} style={{ ...fldStyle, height: 56, resize: 'vertical' }} placeholder="按工艺站点分组，统计 WIP 批次数量" />
          </div>
          <div style={{ background: '#f8fafc', borderRadius: 8, padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#374151', textTransform: 'uppercase', letterSpacing: '0.5px' }}>断言规则（每行一个）</div>
            <div>
              <label style={lbl}>sql_contains — SQL 必须包含的关键字</label>
              <textarea
                value={(item.expected.sql_contains ?? []).join('\n')}
                onChange={e => setExp('sql_contains', e.target.value)}
                style={{ ...fldStyle, height: 64, resize: 'vertical', fontFamily: 'monospace' }}
                placeholder={'GROUP BY\nCOUNT\nstatus'}
              />
            </div>
            <div>
              <label style={lbl}>sql_excludes — SQL 禁止出现的字符串</label>
              <textarea
                value={(item.expected.sql_excludes ?? []).join('\n')}
                onChange={e => setExp('sql_excludes', e.target.value)}
                style={{ ...fldStyle, height: 48, resize: 'vertical', fontFamily: 'monospace' }}
                placeholder="local_production_batch"
              />
            </div>
            <div>
              <label style={lbl}>tables_present — 物理表列表中必须包含</label>
              <textarea
                value={(item.expected.tables_present ?? []).join('\n')}
                onChange={e => setExp('tables_present', e.target.value)}
                style={{ ...fldStyle, height: 48, resize: 'vertical', fontFamily: 'monospace' }}
                placeholder="matrix_routerx_operation_lot"
              />
            </div>
            <div>
              <label style={lbl}>sql_pattern — SQL 正则（可选）</label>
              <input
                value={item.expected.sql_pattern ?? ''}
                onChange={e => onChange({ ...item, expected: { ...item.expected, sql_pattern: e.target.value || undefined } })}
                style={{ ...fldStyle, fontFamily: 'monospace' }}
                placeholder="(?i)SELECT.*FROM.*WHERE"
              />
            </div>
          </div>
        </div>
        <div style={{ padding: '12px 20px', borderTop: '1px solid #e5e7eb', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button onClick={onClose} style={{ padding: '7px 16px', border: '1px solid #d1d5db', borderRadius: 6, background: '#fff', fontSize: 12, cursor: 'pointer', color: '#374151' }}>取消</button>
          <button onClick={onSave} disabled={!item.id || !item.nl}
            style={{ padding: '7px 16px', border: 'none', borderRadius: 6, background: (!item.id || !item.nl) ? '#e5e7eb' : '#7c3aed', color: (!item.id || !item.nl) ? '#9ca3af' : '#fff', fontSize: 12, cursor: (!item.id || !item.nl) ? 'default' : 'pointer', fontWeight: 600 }}>
            {isNew ? '添加' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
};

// ═════════════════════════════════════════════════════════════════
// Micro-components
// ═════════════════════════════════════════════════════════════════
const Badge: React.FC<{ color: string; bg: string; children: React.ReactNode }> = ({ color, bg, children }) => (
  <span style={{ fontSize: 11, fontWeight: 600, padding: '3px 8px', borderRadius: 9999, background: bg, color }}>{children}</span>
);

const PillTag: React.FC<{ color?: string; bg?: string; children: React.ReactNode }> = ({ color = '#6b7280', bg = '#f3f4f6', children }) => (
  <span style={{ fontSize: 10, fontWeight: 500, padding: '2px 6px', borderRadius: 9999, background: bg, color, display: 'inline-flex', alignItems: 'center', gap: 3 }}>{children}</span>
);

const Btn: React.FC<{ icon: any; variant?: 'primary' | 'danger' | 'default'; onClick: () => void; disabled?: boolean; children: React.ReactNode }> = ({ icon: Icon, variant = 'default', onClick, disabled, children }) => {
  const colors = {
    primary: { bg: '#7c3aed', color: '#fff' },
    danger:  { bg: '#fee2e2', color: '#dc2626' },
    default: { bg: '#f3f4f6', color: '#374151' },
  };
  const style = colors[variant];
  return (
    <button onClick={onClick} disabled={disabled}
      style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 12px', borderRadius: 6, border: 'none', background: disabled ? '#f3f4f6' : style.bg, color: disabled ? '#9ca3af' : style.color, fontSize: 12, fontWeight: 500, cursor: disabled ? 'default' : 'pointer' }}>
      <Icon size={12} />{children}
    </button>
  );
};

const IconBtn: React.FC<{ onClick: (e: React.MouseEvent) => void; title?: string; children: React.ReactNode }> = ({ onClick, title, children }) => (
  <button title={title} onClick={onClick} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '3px 4px', borderRadius: 4, color: '#9ca3af', display: 'flex', alignItems: 'center' }}
    onMouseEnter={e => (e.currentTarget.style.background = '#f3f4f6')}
    onMouseLeave={e => (e.currentTarget.style.background = 'none')}
  >{children}</button>
);

const StatusDot: React.FC<{ running: boolean; pass: boolean; fail: boolean; idle: boolean }> = ({ running, pass, fail, idle }) => {
  const color = running ? '#7c3aed' : pass ? '#16a34a' : fail ? '#dc2626' : '#d1d5db';
  const anim  = running ? 'spin 1s linear infinite' : 'none';
  return running
    ? <Loader2 size={9} style={{ color, animation: anim, flexShrink: 0 }} />
    : <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0, display: 'inline-block' }} />;
};

const EmptyHint: React.FC = () => (
  <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 10, color: '#9ca3af' }}>
    <FlaskConical size={40} style={{ opacity: 0.3 }} />
    <div style={{ fontSize: 13 }}>选择左侧用例查看详情</div>
  </div>
);

export default NLTestManager;
