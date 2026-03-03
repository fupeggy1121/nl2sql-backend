/**
 * QueryTrace — 可折叠的查询管道追踪组件
 *
 * 默认收起，点击展开显示完整流水线步骤：
 *   意图识别 → 语义解析 → 查询规划 → SQL生成 → SQL验证 → 执行 → 分析 → 响应
 *
 * 使用方式：
 *   import QueryTrace from './QueryTrace';
 *   {response.pipeline_trace && <QueryTrace trace={response.pipeline_trace} />}
 */
import React, { useState } from 'react';

export interface TraceStep {
  step: string;
  elapsed_ms: number;
  summary: string;
  status: 'ok' | 'warn' | 'error';
  detail?: Record<string, any>;
}

interface QueryTraceProps {
  trace: TraceStep[];
}

const STEP_LABELS: Record<string, string> = {
  intent_router: '🧭 意图识别',
  semantic_resolver: '🔗 语义解析',
  query_planner: '📋 查询规划',
  sql_generator: '⚙️ SQL 生成',
  sql_validator: '✅ SQL 验证',
  data_executor: '🗄️ 数据执行',
  result_analyzer: '📊 结果分析',
  chart_generator: '📈 图表生成',
  response_builder: '📦 响应构建',
};

const STATUS_COLORS: Record<string, string> = {
  ok: '#52c41a',
  warn: '#faad14',
  error: '#ff4d4f',
};

const QueryTrace: React.FC<QueryTraceProps> = ({ trace }) => {
  const [expanded, setExpanded] = useState(false);
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());

  if (!trace || trace.length === 0) return null;

  const totalMs = trace.reduce((sum, s) => sum + s.elapsed_ms, 0);

  const toggleStep = (idx: number) => {
    setExpandedSteps(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  return (
    <div style={{
      marginTop: 12,
      border: '1px solid #252747',
      borderRadius: 8,
      overflow: 'hidden',
      fontSize: 13,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    }}>
      {/* 折叠标题栏 */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 14px',
          backgroundColor: '#1a1b35',
          cursor: 'pointer',
          userSelect: 'none',
          borderBottom: expanded ? '1px solid #252747' : 'none',
        }}
      >
        <span style={{ fontWeight: 500, color: '#c4c9e8' }}>
          {expanded ? '▼' : '▶'} 查询管道追踪
          <span style={{ color: '#6b7298', fontWeight: 400, marginLeft: 8 }}>
            {trace.length} 步 · {totalMs.toFixed(0)}ms
          </span>
        </span>
        <span style={{
          fontSize: 11,
          color: '#6b7298',
          padding: '2px 8px',
          background: '#252747',
          borderRadius: 10,
        }}>
          {expanded ? '收起' : '展开'}
        </span>
      </div>

      {/* 展开后的步骤列表 */}
      {expanded && (
        <div style={{ padding: '8px 0', background: '#12142a' }}>
          {trace.map((step, idx) => {
            const isStepExpanded = expandedSteps.has(idx);
            const label = STEP_LABELS[step.step] || step.step;
            const color = STATUS_COLORS[step.status] || '#c4c9e8';

            return (
              <div key={idx} style={{ padding: '0 14px' }}>
                {/* 步骤行 */}
                <div
                  onClick={() => step.detail && toggleStep(idx)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    padding: '6px 0',
                    cursor: step.detail ? 'pointer' : 'default',
                    borderBottom: idx < trace.length - 1 ? '1px solid #1e2047' : 'none',
                  }}
                >
                  {/* 状态指示器 */}
                  <span style={{
                    width: 8, height: 8,
                    borderRadius: '50%',
                    backgroundColor: color,
                    marginRight: 10,
                    flexShrink: 0,
                  }} />
                  {/* 步骤名称 */}
                  <span style={{ width: 110, flexShrink: 0, color: '#818cf8' }}>
                    {label}
                  </span>
                  {/* 摘要 */}
                  <span style={{ flex: 1, color: '#c4c9e8', marginRight: 8 }}>
                    {step.summary}
                  </span>
                  {/* 耗时 */}
                  <span style={{
                    color: '#6b7298', fontSize: 12, flexShrink: 0, minWidth: 55, textAlign: 'right',
                  }}>
                    {step.elapsed_ms.toFixed(1)}ms
                  </span>
                  {/* 展开箭头 */}
                  {step.detail && (
                    <span style={{ marginLeft: 8, color: '#474970', fontSize: 10 }}>
                      {isStepExpanded ? '▼' : '▶'}
                    </span>
                  )}
                </div>

                {/* 详情面板 */}
                {isStepExpanded && step.detail && (
                  <div style={{
                    margin: '4px 0 8px 18px',
                    padding: '8px 12px',
                    background: '#070810',
                    border: '1px solid #252747',
                    borderRadius: 6,
                    fontSize: 12,
                    lineHeight: 1.6,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-all',
                    color: '#a5f3fc',
                    maxHeight: 300,
                    overflow: 'auto',
                  }}>
                    {JSON.stringify(step.detail, null, 2)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default QueryTrace;
