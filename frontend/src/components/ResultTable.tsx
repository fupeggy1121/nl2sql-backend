import { useState } from 'react'
import { ChevronLeft, ChevronRight, Download, BarChart2, Table2 } from 'lucide-react'
import type { ExecuteResponse } from '../types/api'

const PAGE_SIZE = 20

interface Props {
  result: ExecuteResponse
}

function isNumericCol(data: Record<string, unknown>[], col: string): boolean {
  return data.slice(0, 5).every(row => {
    const v = row[col]
    return v === null || v === undefined || (typeof v === 'number') || !isNaN(Number(v))
  })
}

function SimpleBarChart({ data, labelCol, valueCol }: {
  data: Record<string, unknown>[]
  labelCol: string
  valueCol: string
}) {
  const items = data.slice(0, 15)
  const values = items.map(r => Number(r[valueCol]) || 0)
  const max = Math.max(...values, 1)
  const W = 600, H = 300, MARGIN = { top: 20, right: 10, bottom: 80, left: 60 }
  const plotW = W - MARGIN.left - MARGIN.right
  const plotH = H - MARGIN.top - MARGIN.bottom
  const barW = Math.max(16, Math.floor(plotW / items.length) - 6)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: W, display: 'block', margin: '0 auto' }}>
      <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
        {/* Y axis labels */}
        {[0, 0.25, 0.5, 0.75, 1].map(t => {
          const y = plotH * (1 - t)
          const v = (max * t).toFixed(0)
          return (
            <g key={t}>
              <line x1={0} x2={plotW} y1={y} y2={y} stroke="#e5e7eb" strokeWidth={1} />
              <text x={-6} y={y + 4} textAnchor="end" fontSize={11} fill="#9ca3af">{v}</text>
            </g>
          )
        })}
        {/* Bars */}
        {items.map((row, i) => {
          const v = Number(row[valueCol]) || 0
          const bh = Math.max(1, (v / max) * plotH)
          const x = i * (plotW / items.length) + (plotW / items.length - barW) / 2
          const label = String(row[labelCol] ?? '')
          const shortLabel = label.length > 8 ? label.slice(0, 7) + '…' : label
          return (
            <g key={i}>
              <rect
                x={x} y={plotH - bh} width={barW} height={bh}
                fill="#4f46e5" rx={3} opacity={0.85}
              />
              <text
                x={x + barW / 2} y={plotH + 14}
                textAnchor="middle" fontSize={11} fill="#6b7280"
                transform={`rotate(-30,${x + barW / 2},${plotH + 14})`}
              >
                {shortLabel}
              </text>
            </g>
          )
        })}
      </g>
    </svg>
  )
}

export function ResultTable({ result }: Props) {
  const [page, setPage] = useState(0)
  const [viewMode, setViewMode] = useState<'table' | 'chart'>('table')
  const [sortCol, setSortCol] = useState<string | null>(null)
  const [sortAsc, setSortAsc] = useState(true)

  if (!result.success) {
    return (
      <div style={{ padding: 24, color: '#ef4444', background: 'rgba(239,68,68,0.1)', borderRadius: 10 }}>
        ❌ 查询失败：{result.error ?? '未知错误'}
      </div>
    )
  }

  if (!result.data || result.data.length === 0) {
    return (
      <div style={{ padding: 24, color: '#6b7280', textAlign: 'center', background: '#12142a', borderRadius: 10 }}>
        查询未返回数据
      </div>
    )
  }

  const cols = Object.keys(result.data[0])
  const numCols = cols.filter(c => isNumericCol(result.data, c))

  // Sort
  let sorted = [...result.data]
  if (sortCol) {
    sorted.sort((a, b) => {
      const av = a[sortCol], bv = b[sortCol]
      if (av == null && bv == null) return 0
      if (av == null) return sortAsc ? 1 : -1
      if (bv == null) return sortAsc ? -1 : 1
      const n = typeof av === 'number' && typeof bv === 'number'
        ? av - bv
        : String(av).localeCompare(String(bv), 'zh')
      return sortAsc ? n : -n
    })
  }

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE)
  const pageData = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  const handleSort = (col: string) => {
    if (sortCol === col) setSortAsc(a => !a)
    else { setSortCol(col); setSortAsc(true) }
  }

  const exportCsv = () => {
    const header = cols.join(',')
    const rows = result.data.map(r => cols.map(c => {
      const v = r[c]
      const s = v == null ? '' : String(v)
      return s.includes(',') || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s
    }).join(','))
    const blob = new Blob(['\uFEFF' + [header, ...rows].join('\n')], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `query_result_${Date.now()}.csv`
    a.click(); URL.revokeObjectURL(url)
  }

  // Auto-pick chart columns
  const labelCol = cols.find(c => !numCols.includes(c)) ?? cols[0]
  const valueCol = numCols[0] ?? cols[1]

  return (
    <div style={{ background: '#12142a', borderRadius: 12, border: '1px solid #2d284e', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 16px', background: '#0d0e1a', borderBottom: '1px solid #2d284e',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontWeight: 600, fontSize: 14, color: '#c4c9d6' }}>
            查询结果
          </span>
          <span style={{
            padding: '2px 8px', borderRadius: 10,
            background: 'rgba(99,102,241,0.2)', color: '#4338ca', fontSize: 12, fontWeight: 600,
          }}>
            {result.rows_count} 行
          </span>
          <span style={{ fontSize: 12, color: '#9ca3af' }}>
            {(result.query_time_ms / 1000).toFixed(2)}s
          </span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {numCols.length > 0 && (
            <div style={{ display: 'flex', border: '1px solid #2d284e', borderRadius: 6, overflow: 'hidden' }}>
              {(['table', 'chart'] as const).map(m => (
                <button
                  key={m}
                  onClick={() => setViewMode(m)}
                  style={{
                    padding: '4px 10px', border: 'none', cursor: 'pointer', fontSize: 12,
                    background: viewMode === m ? '#4f46e5' : '#1e1b4b',
                    color: viewMode === m ? '#fff' : '#6b7280',
                    display: 'flex', alignItems: 'center', gap: 4,
                  }}
                >
                  {m === 'table' ? <Table2 size={13} /> : <BarChart2 size={13} />}
                  {m === 'table' ? '表格' : '图表'}
                </button>
              ))}
            </div>
          )}
          <button
            onClick={exportCsv}
            style={{
              display: 'flex', alignItems: 'center', gap: 4,
              padding: '4px 10px', borderRadius: 6, border: '1px solid #2d284e',
              background: '#12142a', color: '#c4c9d6', fontSize: 12, cursor: 'pointer',
            }}
          >
            <Download size={13} />
            导出 CSV
          </button>
        </div>
      </div>

      {viewMode === 'chart' && numCols.length > 0 ? (
        <div style={{ padding: 24 }}>
          <SimpleBarChart data={result.data} labelCol={labelCol} valueCol={valueCol} />
          <div style={{ textAlign: 'center', fontSize: 12, color: '#9ca3af', marginTop: 8 }}>
            X: {labelCol} &nbsp;|&nbsp; Y: {valueCol}（前 15 条）
          </div>
        </div>
      ) : (
        <>
          <div style={{ overflowX: 'auto' }}>
            <table style={{
              width: '100%', borderCollapse: 'collapse',
              fontSize: 13, lineHeight: 1.5,
            }}>
              <thead>
                <tr style={{ background: '#0d0e1a' }}>
                  {cols.map(col => (
                    <th
                      key={col}
                      onClick={() => handleSort(col)}
                      style={{
                        padding: '10px 14px', textAlign: 'left',
                        borderBottom: '2px solid #e5e7eb', whiteSpace: 'nowrap',
                        fontWeight: 600, color: '#c4c9d6', cursor: 'pointer',
                        userSelect: 'none',
                      }}
                    >
                      {col}
                      {sortCol === col ? (sortAsc ? ' ▲' : ' ▼') : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageData.map((row, i) => (
                  <tr
                    key={i}
                    style={{ background: i % 2 === 0 ? '#12142a' : '#161830' }}
                    onMouseEnter={e => (e.currentTarget.style.background = '#f0f4ff')}
                    onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 0 ? '#12142a' : '#161830')}
                  >
                    {cols.map(col => {
                      const v = row[col]
                      return (
                        <td key={col} style={{
                          padding: '9px 14px',
                          borderBottom: '1px solid #1e1b4b',
                          maxWidth: 260, overflow: 'hidden',
                          textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          color: v == null ? '#d1d5db' : '#111827',
                        }}>
                          {v == null ? 'null' : String(v)}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              gap: 12, padding: '12px 16px', borderTop: '1px solid #2d284e',
              fontSize: 13, color: '#6b7280',
            }}>
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
                style={{
                  padding: '4px 8px', borderRadius: 6, border: '1px solid #2d284e',
                  background: page === 0 ? '#f3f4f6' : '#12142a', cursor: page === 0 ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center',
                }}
              >
                <ChevronLeft size={15} />
              </button>
              第 {page + 1} / {totalPages} 页
              <button
                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                disabled={page === totalPages - 1}
                style={{
                  padding: '4px 8px', borderRadius: 6, border: '1px solid #2d284e',
                  background: page === totalPages - 1 ? '#f3f4f6' : '#12142a',
                  cursor: page === totalPages - 1 ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center',
                }}
              >
                <ChevronRight size={15} />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
