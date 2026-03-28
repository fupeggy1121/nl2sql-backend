/**
 * AnalysisPage — 自助数据分析
 *
 * 设计原则：面向工艺/质量工程师，屏蔽算法细节
 *   ① 选分析场景（业务语言）
 *   ② 选数据来源（预置数据集 or 自然语言 or SQL）
 *   ③ 确认参数（自动填入，可微调）
 *   ④ 查看结果
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { listMethods, runAnalysis, previewData } from '../../api/analytics'
import type { MethodInfo, DataSourceConfig, AnalysisResponse } from '../../types/analytics'
import { ParamsForm } from './ParamsForm'
import { ResultView } from './ResultView'

// ── 场景定义（业务语言 → 分析方法映射）─────────────────────────────
interface Scenario {
  id: string
  method: string
  icon: string
  label: string
  description: string
  /** 推荐数据集（nlquery 描述） */
  presets: { label: string; nlquery: string }[]
  /** 针对该场景的参数自动填充提示 */
  autoParams?: Record<string, unknown>
}

const SCENARIOS: Scenario[] = [
  {
    id: 'distribution',
    method: 'descriptive',
    icon: '📊',
    label: '参数分布分析',
    description: '了解某批数据的集中趋势、分散程度、分布形态，判断是否正常',
    presets: [
      { label: '来料检验参数（近30天）', nlquery: '查询近30天所有物料来料检验的参数实测记录，包含参数名称、实测值' },
      { label: '过站量测数据', nlquery: '查询近30天过站量测参数数据，包含工站、参数名、测量值' },
      { label: '制程工艺参数', nlquery: '查询近7天制程参数录入数据，包含工站、参数名称和数值' },
    ],
  },
  {
    id: 'comparison',
    method: 'hypothesis',
    icon: '⚖️',
    label: '两组数据对比',
    description: '比较两批产品、两条产线或改善前后的差异是否具有统计显著性',
    presets: [
      { label: '两批次量测值对比', nlquery: '查询量测数据按批次分组，包含批次编码、参数名、测量值' },
      { label: '两条产线良率对比', nlquery: '查询各产线良率数据，按产线分组' },
    ],
    autoParams: { test_type: 't_test', alpha: 0.05 },
  },
  {
    id: 'correlation',
    method: 'correlation',
    icon: '🔗',
    label: '相关性分析',
    description: '找出哪些工艺参数之间存在关联，或哪些参数与良率/不良率相关',
    presets: [
      { label: '工艺参数与良率相关', nlquery: '查询近90天按批次汇总的工艺参数均值和该批次最终良率' },
      { label: '来料参数相关性', nlquery: '查询来料检验中所有数值类参数的实测值（按批次行展开）' },
    ],
    autoParams: { method: 'pearson', top_n: 10 },
  },
  {
    id: 'spc',
    method: 'spc',
    icon: '⚙️',
    label: '过程稳定性（SPC）',
    description: '绘制控制图，判断工艺参数是否处于受控状态，计算过程能力 Cpk/Ppk',
    presets: [
      { label: '量测参数 SPC', nlquery: '查询某量测参数近90天的每批次均值，按时间顺序排列，包含批次号、测量值' },
      { label: '制程参数控制图', nlquery: '查询制程参数记录按检测时间排序，包含设备、参数值' },
    ],
    autoParams: { chart_type: 'xbar_r', subgroup_size: 5 },
  },
  {
    id: 'pareto',
    method: 'pareto',
    icon: '🎯',
    label: '不良帕累托分析',
    description: '找出占80%不良的主要缺陷类型或问题工站，聚焦改善重点',
    presets: [
      { label: '按缺陷代码分析', nlquery: '查询近30天各不良代码的不良数量汇总' },
      { label: '按工站不良数分析', nlquery: '查询近30天各工站不良数量汇总，按工站分组' },
    ],
  },
  {
    id: 'yield',
    method: 'yield_report',
    icon: '📈',
    label: '良率趋势报表',
    description: '统计各工站良率趋势与分布，识别低良率工站，对照目标线',
    presets: [
      { label: '近30天良率明细', nlquery: '查询近30天各工站良率明细数据，包含日期、工站编码、工站名称、进站片数、不良片数' },
      { label: '近7天良率数据', nlquery: '查询近7天各工站良率数据，包含日期、工站、进站和不良片数' },
      { label: '指定产品良率', nlquery: '查询近30天良率数据，包含产品编码、工站、日期、进站片数、不良片数' },
    ],
    autoParams: { target_yield: 95.0, top_n: 20 },
  },
  {
    id: 'oee',
    method: 'oee_report',
    icon: '🏭',
    label: 'OEE 设备效率报表',
    description: '统计设备综合效率（OEE），生成日趋势图和设备排名，对标目标值',
    presets: [
      { label: '近30天设备事件', nlquery: '查询近30天设备进出站事件记录，包含事件时间、操作类型、设备编码、批次编码' },
      { label: '近7天设备数据', nlquery: '查询近7天设备进出站操作记录' },
    ],
    autoParams: { oee_target: 65.0, planned_hours_per_day: 24.0 },
  },
]

// ── 自动列名检测规则 ──────────────────────────────────────────────
const COLUMN_DETECT_RULES: { patterns: string[]; paramKey: string }[] = [
  { patterns: ['date', 'time', '日期', 'gmt', 'report_date', 'created'], paramKey: 'date_column' },
  { patterns: ['yield', '良率', 'yld', 'pass_rate'], paramKey: 'yield_column' },
  { patterns: ['input', '进站', 'wafer_in', 'input_wafers'], paramKey: 'input_col' },
  { patterns: ['ng', '不良', 'defect', 'fail', 'ng_wafers'], paramKey: 'ng_col' },
  { patterns: ['process', 'station', '工站', 'process_code'], paramKey: 'process_column' },
  { patterns: ['process_name', '工站名', 'station_name'], paramKey: 'process_name_column' },
  { patterns: ['product', '产品', 'product_code'], paramKey: 'product_column' },
  { patterns: ['eqp', '设备', 'equipment', 'eqp_id'], paramKey: 'eqp_id_col' },
  { patterns: ['event_time', 'operation_time'], paramKey: 'event_time_col' },
  { patterns: ['operation_type', 'op_type'], paramKey: 'operation_type_col' },
  { patterns: ['lot', '批次', 'lot_code'], paramKey: 'lot_col' },
  { patterns: ['group', 'category', '分组', '类别'], paramKey: 'group_column' },
]

function autoDetectParams(columns: string[], schema: MethodInfo['params_schema']): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  // 字段映射
  for (const rule of COLUMN_DETECT_RULES) {
    if (!(rule.paramKey in schema)) continue
    const matched = columns.find(col =>
      rule.patterns.some(pat =>
        col.toLowerCase().includes(pat.toLowerCase()) || pat.toLowerCase().includes(col.toLowerCase())
      )
    )
    if (matched) result[rule.paramKey] = matched
  }
  // 数值列检测（用于 SPC value_column、相关性等）
  return result
}

// ── 子组件 ────────────────────────────────────────────────────────

function ScenarioCard({ s, active, onClick }: { s: Scenario; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 6,
        padding: '14px 16px', borderRadius: 12, cursor: 'pointer', textAlign: 'left',
        border: active ? '2px solid #2563eb' : '2px solid #e5e7eb',
        background: active ? '#eff6ff' : '#fff',
        boxShadow: active ? '0 0 0 3px #2563eb22' : 'none',
        transition: 'all .15s', width: '100%',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 24 }}>{s.icon}</span>
        <span style={{ fontSize: 14, fontWeight: 600, color: active ? '#1d4ed8' : '#111827' }}>{s.label}</span>
      </div>
      <span style={{ fontSize: 12, color: '#6b7280', lineHeight: 1.5 }}>{s.description}</span>
    </button>
  )
}

function PresetDatasetPicker({ presets, onSelect }: {
  presets: Scenario['presets']
  onSelect: (cfg: DataSourceConfig) => void
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>快速选择常用数据集：</div>
      {presets.map((p, i) => (
        <button key={i} onClick={() => onSelect({ type: 'nlquery', nlquery: p.nlquery, limit: 2000 })}
          style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px',
            borderRadius: 8, border: '1px solid #e5e7eb', background: '#f9fafb',
            color: '#374151', fontSize: 13, cursor: 'pointer', textAlign: 'left',
            transition: 'all .15s',
          }}
        >
          <span style={{ fontSize: 16 }}>📋</span>
          {p.label}
          <span style={{ marginLeft: 'auto', fontSize: 11, color: '#9ca3af' }}>点击加载 →</span>
        </button>
      ))}
    </div>
  )
}

interface DataPreviewProps {
  columns: string[]
  sample: Record<string, unknown>[]
  rowsCount: number
}

function DataPreview({ columns, sample, rowsCount }: DataPreviewProps) {
  if (columns.length === 0) return null
  return (
    <div>
      <div style={{ fontSize: 12, color: '#059669', fontWeight: 600, marginBottom: 8 }}>
        ✅ 数据加载成功：{rowsCount} 行 × {columns.length} 列
      </div>
      <div style={{ overflowX: 'auto', border: '1px solid #e5e7eb', borderRadius: 8 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, whiteSpace: 'nowrap' }}>
          <thead>
            <tr style={{ background: '#f9fafb' }}>
              {columns.slice(0, 10).map(col => (
                <th key={col} style={{ padding: '6px 10px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', color: '#374151', fontWeight: 600 }}>
                  {col}
                </th>
              ))}
              {columns.length > 10 && <th style={{ padding: '6px 10px', color: '#9ca3af' }}>+{columns.length - 10} 列</th>}
            </tr>
          </thead>
          <tbody>
            {sample.slice(0, 5).map((row, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                {columns.slice(0, 10).map(col => (
                  <td key={col} style={{ padding: '5px 10px', color: '#4b5563', fontFamily: 'monospace' }}>
                    {String(row[col] ?? '—').slice(0, 30)}
                  </td>
                ))}
                {columns.length > 10 && <td style={{ padding: '5px 10px', color: '#9ca3af' }}>…</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 4 }}>显示前5行，共{rowsCount}行</div>
    </div>
  )
}

// ── 主页面 ────────────────────────────────────────────────────────

export function AnalysisPage() {
  const [methods, setMethods] = useState<MethodInfo[]>([])
  const [loadingMethods, setLoadingMethods] = useState(true)

  const [selectedScenario, setSelectedScenario] = useState<Scenario | null>(null)
  const [dataSource, setDataSource] = useState<DataSourceConfig>({ type: 'nlquery', nlquery: '', limit: 2000 })
  const [nlInput, setNlInput] = useState('')
  const [params, setParams] = useState<Record<string, unknown>>({})

  // 数据预览
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState('')
  const [previewCols, setPreviewCols] = useState<string[]>([])
  const [previewSample, setPreviewSample] = useState<Record<string, unknown>[]>([])
  const [previewRowsCount, setPreviewRowsCount] = useState(0)
  const [dataReady, setDataReady] = useState(false)

  // 运行结果
  const [running, setRunning] = useState(false)
  const [response, setResponse] = useState<AnalysisResponse | null>(null)
  const [runError, setRunError] = useState('')

  const resultRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    listMethods()
      .then(list => setMethods(list))
      .catch(() => {})
      .finally(() => setLoadingMethods(false))
  }, [])

  const currentMethod = methods.find(m => m.name === selectedScenario?.method)

  // 选择场景时自动填入业务默认参数
  const handleSelectScenario = useCallback((s: Scenario) => {
    setSelectedScenario(s)
    setResponse(null)
    setRunError('')
    setDataReady(false)
    setPreviewCols([])
    setPreviewSample([])
    // 初始化参数
    const method = methods.find(m => m.name === s.method)
    const defaults: Record<string, unknown> = {}
    if (method) {
      for (const [k, schema] of Object.entries(method.params_schema ?? {})) {
        if (schema.default !== undefined) defaults[k] = schema.default
      }
    }
    setParams({ ...defaults, ...(s.autoParams ?? {}) })
    setDataSource({ type: 'nlquery', nlquery: '', limit: 2000 })
    setNlInput('')
  }, [methods])

  // 加载预置数据集
  const handlePresetSelect = useCallback(async (cfg: DataSourceConfig) => {
    setDataSource(cfg)
    setNlInput(cfg.nlquery ?? '')
    await loadPreview(cfg)
  }, []) // eslint-disable-line

  const loadPreview = useCallback(async (cfg: DataSourceConfig) => {
    if (!cfg.nlquery && !cfg.sql && !cfg.table) return
    setPreviewLoading(true)
    setPreviewError('')
    setDataReady(false)
    setPreviewCols([])
    setPreviewSample([])
    try {
      const res = await previewData(cfg, 20)
      if (!res.success) throw new Error(res.error ?? '预览失败')
      setPreviewCols(res.columns ?? [])
      setPreviewSample(res.sample ?? [])
      setPreviewRowsCount(res.rows_count ?? 0)
      setDataReady(true)
      // 自动检测列名并填入参数
      if (currentMethod && res.columns) {
        const detected = autoDetectParams(res.columns, currentMethod.params_schema ?? {})
        setParams(prev => ({ ...prev, ...detected }))
      }
    } catch (e) {
      setPreviewError(String(e))
    } finally {
      setPreviewLoading(false)
    }
  }, [currentMethod])

  const handleRun = useCallback(async () => {
    if (!selectedScenario || !dataReady) return
    setRunning(true)
    setRunError('')
    setResponse(null)
    try {
      const res = await runAnalysis({ method: selectedScenario.method, data_source: dataSource, params })
      setResponse(res)
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100)
    } catch (e) {
      setRunError(String(e))
    } finally {
      setRunning(false)
    }
  }, [selectedScenario, dataSource, params, dataReady])

  // ── 渲染 ────────────────────────────────────────────────────────

  if (loadingMethods) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6b7280' }}>
        加载分析模块…
      </div>
    )
  }

  const card = (title: string, children: React.ReactNode, extra?: React.ReactNode) => (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, overflow: 'hidden', marginBottom: 16 }}>
      <div style={{ padding: '12px 20px', borderBottom: '1px solid #f3f4f6', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#111827' }}>{title}</div>
        {extra}
      </div>
      <div style={{ padding: '16px 20px' }}>{children}</div>
    </div>
  )

  const btnPrimary = (disabled: boolean): React.CSSProperties => ({
    padding: '9px 24px', borderRadius: 8, border: 'none',
    cursor: disabled ? 'not-allowed' : 'pointer',
    fontSize: 13, fontWeight: 600,
    background: disabled ? '#e5e7eb' : '#2563eb',
    color: disabled ? '#9ca3af' : '#fff',
  })

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: 24, background: '#f8fafc' }}>
      <div style={{ maxWidth: 960, margin: '0 auto' }}>
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#111827' }}>自助数据分析</div>
          <div style={{ fontSize: 13, color: '#6b7280', marginTop: 3 }}>
            选择分析场景，系统自动加载推荐数据、填入参数，开箱即用
          </div>
        </div>

        {/* ── Step 1: 场景选择 ── */}
        {card(
          '① 选择分析场景',
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
            {SCENARIOS.map(s => (
              <ScenarioCard key={s.id} s={s} active={selectedScenario?.id === s.id} onClick={() => handleSelectScenario(s)} />
            ))}
          </div>,
          selectedScenario ? (
            <span style={{ fontSize: 12, background: '#d1fae5', color: '#065f46', padding: '3px 10px', borderRadius: 12, fontWeight: 600 }}>
              已选：{selectedScenario.label}
            </span>
          ) : undefined
        )}

        {/* ── Step 2: 数据来源 ── */}
        {selectedScenario && card(
          '② 选择数据来源',
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <PresetDatasetPicker
              presets={selectedScenario.presets}
              onSelect={cfg => handlePresetSelect(cfg)}
            />

            <div style={{ borderTop: '1px solid #f3f4f6', paddingTop: 14 }}>
              <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>或自定义描述数据需求（自然语言）：</div>
              <div style={{ display: 'flex', gap: 8 }}>
                <textarea
                  rows={2}
                  value={nlInput}
                  onChange={e => setNlInput(e.target.value)}
                  placeholder={`例：查询近30天${selectedScenario.label}相关数据…`}
                  style={{
                    flex: 1, padding: '8px 10px', borderRadius: 6, border: '1px solid #d1d5db',
                    fontSize: 13, resize: 'none', fontFamily: 'inherit',
                  }}
                />
                <button
                  onClick={() => {
                    const cfg: DataSourceConfig = { type: 'nlquery', nlquery: nlInput, limit: 2000 }
                    setDataSource(cfg)
                    loadPreview(cfg)
                  }}
                  disabled={!nlInput.trim() || previewLoading}
                  style={{ ...btnPrimary(!nlInput.trim() || previewLoading), alignSelf: 'flex-start', whiteSpace: 'nowrap' }}
                >
                  {previewLoading ? '加载中…' : '加载数据'}
                </button>
              </div>
            </div>

            {previewLoading && (
              <div style={{ color: '#6b7280', fontSize: 13 }}>⏳ 正在查询数据，请稍候…</div>
            )}
            {previewError && (
              <div style={{ color: '#dc2626', fontSize: 13, background: '#fef2f2', padding: '8px 12px', borderRadius: 6 }}>
                ❌ {previewError}
              </div>
            )}
            {dataReady && (
              <DataPreview columns={previewCols} sample={previewSample} rowsCount={previewRowsCount} />
            )}
          </div>,
          dataReady ? (
            <span style={{ fontSize: 12, background: '#d1fae5', color: '#065f46', padding: '3px 10px', borderRadius: 12, fontWeight: 600 }}>
              ✅ 数据已就绪
            </span>
          ) : undefined
        )}

        {/* ── Step 3: 参数确认 ── */}
        {selectedScenario && dataReady && card(
          '③ 确认分析参数',
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ fontSize: 12, color: '#6b7280' }}>
              系统已根据数据列名自动填入参数，请确认无误后运行分析。带 ⓘ 的字段悬停可查看说明。
            </div>
            <ParamsForm
              method={currentMethod}
              params={params}
              onChange={setParams}
              detectedColumns={previewCols}
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4 }}>
              <button
                onClick={handleRun}
                disabled={running}
                style={btnPrimary(running)}
              >
                {running ? '⏳ 分析中…' : '▶ 运行分析'}
              </button>
              {runError && (
                <span style={{ fontSize: 12, color: '#dc2626' }}>❌ {runError}</span>
              )}
            </div>
          </div>
        )}

        {/* ── Step 4: 结果 ── */}
        {response && (
          <div ref={resultRef}>
            {card(
              '④ 分析结果',
              response.success && response.result ? (
                <ResultView result={response.result} answer={response.answer} />
              ) : (
                <div style={{ padding: 16, background: '#fef2f2', borderRadius: 8, color: '#dc2626', fontSize: 13 }}>
                  分析失败：{response.error ?? '未知错误'}
                </div>
              ),
              <button
                onClick={() => { setResponse(null); setRunError('') }}
                style={{ padding: '4px 12px', borderRadius: 6, border: '1px solid #d1d5db', background: '#fff', fontSize: 12, cursor: 'pointer', color: '#374151' }}
              >
                重新分析
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

