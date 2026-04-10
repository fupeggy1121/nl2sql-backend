/**
 * QueryTrace — 统一的查询管道追踪组件（合并版）
 *
 * 融合原 QueryTrace（深色主题）+ PipelineTrace（富样式 SQL 面板）：
 * - sql_generator：SQL 代码高亮块 + 置信度 + Token 用量 + 语义/few-shot 标记
 * - semantic_resolver：匹配类列表 + JOIN/过滤/指标数量徽章
 * - intent_router：意图 + 置信度徽章
 * - sql_validator：验证失败时高亮错误信息
 * - 其他步骤：JSON 原始详情
 * - status 支持 "ok" | "warn" | "error" | "skip"
 * - llm_tokens 在 sql_generator 面板中展示
 */
import React, { useState } from 'react';
import type { PipelineStep } from '../../../types/api';

/** 向后兼容 UnifiedChat 中对 TraceStep 的 import */
export type TraceStep = PipelineStep;

interface QueryTraceProps {
  trace: TraceStep[];
}

// ── 步骤标签（完整覆盖所有节点名） ─────────────────────────
const STEP_LABELS: Record<string, string> = {
  // query_agent 节点
  intent_router:              '🧭 意图识别',
  semantic_resolver:          '🔗 语义解析',
  query_planner:              '📋 查询规划',
  sql_generator:              '⚙️ SQL 生成',
  sql_validator:              '✅ SQL 验证',
  query_executor:             '🗄️ 查询执行',
  data_executor:              '🗄️ 数据执行',
  result_analyzer:            '📊 结果分析',
  chart_generator:            '📈 图表生成',
  response_builder:           '📦 响应构建',
  rag_chat:                   '💬 智能问答',
  clarification_node:         '❓ 意图澄清',
  action_executor:            '⚡ 写操作执行',
  baseline_manager:           '🎯 基线管理',
  // analysis_agent 节点
  analysis_method_selector:   '🔍 分析方法识别',
  analysis_data_loader:       '🗄️ 数据加载 SQL',
  analysis_preprocessor:      '🔧 数据预处理',
  analysis_executor:          '🐍 Python 数据分析',
  analysis_viz_generator:     '📈 图表生成',
};

// ── 状态颜色（含 skip）────────────────────────────────────
const STATUS_COLORS: Record<string, string> = {
  ok:    '#52c41a',
  warn:  '#faad14',
  error: '#ff4d4f',
  skip:  '#555577',
};

// ── sql_generator 专属详情面板 ────────────────────────────
function SqlDetail({ step }: { step: TraceStep }) {
  const d = step.detail as Record<string, unknown> | undefined;
  const tokens = step.llm_tokens;
  const sql = (d?.sql as string) ?? '';
  const confidence = (d?.confidence as number) ?? 0;
  const retryCount = (d?.retry_count as number) ?? 0;
  const hasSemanticCtx = !!(d?.has_semantic_context);
  const hasFewShot = !!(d?.has_few_shot);
  const confColor = confidence >= 0.8 ? '#4ade80' : confidence >= 0.6 ? '#fbbf24' : '#f87171';

  return (
    <div style={{ padding: '10px 14px 14px', borderTop: '1px solid #1e2047', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ fontSize: 12, color: '#818cf8' }}>{step.summary}</div>
      {sql && (
        <>
          <div style={{ fontSize: 11, color: '#6b7298', fontWeight: 600, letterSpacing: 0.5, textTransform: 'uppercase' }}>
            生成的 SQL
          </div>
          <pre style={{
            fontSize: 12, background: '#070810', color: '#7dd3fc',
            padding: '12px 14px', borderRadius: 6, overflowX: 'auto',
            margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
            lineHeight: 1.7, fontFamily: '"JetBrains Mono","Fira Code",Menlo,monospace',
            border: '1px solid #1e3a5f',
          }}>
            {sql}
          </pre>
        </>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {confidence > 0 && (
          <span style={{ fontSize: 12, padding: '2px 10px', borderRadius: 20, background: `${confColor}22`, color: confColor, fontWeight: 600 }}>
            置信度 {(confidence * 100).toFixed(0)}%
          </span>
        )}
        {retryCount > 0 && (
          <span style={{ fontSize: 12, padding: '2px 10px', borderRadius: 20, background: '#451a03', color: '#fbbf24', fontWeight: 500 }}>
            重试 #{retryCount}
          </span>
        )}
        {tokens && tokens.total > 0 && (
          <span style={{ fontSize: 12, padding: '2px 10px', borderRadius: 20, background: '#1e1b4b', color: '#a5b4fc' }}>
            Tokens {tokens.input}↑ {tokens.output}↓ / {tokens.total}
          </span>
        )}
        {hasSemanticCtx && (
          <span style={{ fontSize: 12, padding: '2px 10px', borderRadius: 20, background: '#052e16', color: '#4ade80' }}>
            + 语义上下文
          </span>
        )}
        {hasFewShot && (
          <span style={{ fontSize: 12, padding: '2px 10px', borderRadius: 20, background: '#2e1065', color: '#c4b5fd' }}>
            + Few-shot
          </span>
        )}
      </div>
    </div>
  );
}

// ── semantic_resolver 专属详情面板 ────────────────────────
function SemanticDetail({ step }: { step: TraceStep }) {
  const d = step.detail as Record<string, unknown> | undefined;
  if (!d) return <GenericDetail step={step} />;
  const classes = (d.matched_classes as any[]) ?? [];
  const joins   = (d.joins    as any[]) ?? [];
  const filters = (d.filters  as any[]) ?? [];
  const rules   = (d.business_rules as any[]) ?? [];
  const metrics = (d.metrics  as any[]) ?? [];
  const cacheHit = d.cache_hit as boolean | undefined;

  return (
    <div style={{ padding: '8px 14px 14px', borderTop: '1px solid #1e2047' }}>
      <div style={{ fontSize: 12, color: '#818cf8', marginBottom: 8 }}>{step.summary}</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: classes.length > 0 ? 8 : 0 }}>
        {classes.length > 0  && <Badge bg="#052e16"  fg="#4ade80">{classes.length} 个本体类</Badge>}
        {joins.length > 0    && <Badge bg="#1e1b4b"  fg="#a5b4fc">{joins.length} 个 JOIN</Badge>}
        {filters.length > 0  && <Badge bg="#422006"  fg="#fda4af">{filters.length} 个过滤条件</Badge>}
        {metrics.length > 0  && <Badge bg="#1c1917"  fg="#fed7aa">{metrics.length} 个指标</Badge>}
        {rules.length > 0    && <Badge bg="#1c1917"  fg="#fde68a">{rules.length} 条业务规则</Badge>}
        {cacheHit !== undefined && (
          <Badge bg={cacheHit ? '#052e16' : '#1e1b4b'} fg={cacheHit ? '#4ade80' : '#94a3b8'}>
            {cacheHit ? '✓ 缓存命中' : '缓存未命中'}
          </Badge>
        )}
      </div>
      {classes.length > 0 && (
        <div style={{ fontSize: 12, lineHeight: 1.8 }}>
          {classes.map((c: any, i: number) => (
            <div key={i}>
              <span style={{ color: '#818cf8' }}>{c.label_cn || c.logic_class}</span>
              {c.physical_table && <>
                <span style={{ color: '#4b5563' }}> → </span>
                <span style={{ color: '#7dd3fc', fontFamily: 'monospace' }}>{c.physical_table}</span>
              </>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── intent_router 专属详情面板 ────────────────────────────
function IntentDetail({ step }: { step: TraceStep }) {
  const d = step.detail as Record<string, unknown> | undefined;
  if (!d) return <GenericDetail step={step} />;
  const intent     = d.intent     as string | undefined;
  const confidence = d.confidence as number | undefined;
  const queryType  = d.query_type as string | undefined;

  return (
    <div style={{ padding: '8px 14px 14px', borderTop: '1px solid #1e2047' }}>
      <div style={{ fontSize: 12, color: '#818cf8', marginBottom: 8 }}>{step.summary}</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {intent     && <Badge bg="#052e16" fg="#4ade80" mono>{intent}</Badge>}
        {queryType  && <Badge bg="#1e1b4b" fg="#a5b4fc" mono>{queryType}</Badge>}
        {confidence !== undefined && (
          <Badge bg="#1c1917" fg="#fde68a">置信度 {(confidence * 100).toFixed(0)}%</Badge>
        )}
      </div>
    </div>
  );
}

// ── sql_validator 专属详情面板 ────────────────────────────
function ValidatorDetail({ step }: { step: TraceStep }) {
  const d = step.detail as Record<string, unknown> | undefined;
  const errorMsg  = d?.error_message  as string  | undefined;
  const corrected = d?.auto_corrected as boolean | undefined;

  return (
    <div style={{ padding: '8px 14px 14px', borderTop: '1px solid #1e2047' }}>
      <div style={{ fontSize: 12, color: step.status === 'error' ? '#f87171' : '#818cf8', marginBottom: errorMsg ? 8 : 0 }}>
        {step.summary}
      </div>
      {errorMsg && (
        <pre style={{
          fontSize: 11, background: '#1c0005', color: '#fca5a5',
          padding: '8px 12px', borderRadius: 6, overflowX: 'auto',
          margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
          border: '1px solid #7f1d1d',
        }}>
          {errorMsg}
        </pre>
      )}
      {corrected && (
        <span style={{ marginTop: 6, display: 'inline-block', fontSize: 12, padding: '2px 10px', borderRadius: 20, background: '#052e16', color: '#4ade80' }}>
          ✓ 已自动修正
        </span>
      )}
    </div>
  );
}

// ── 通用 JSON 详情面板 ────────────────────────────────────
function GenericDetail({ step }: { step: TraceStep }) {
  return (
    <div style={{ padding: '8px 14px 12px', borderTop: '1px solid #1e2047' }}>
      <div style={{ fontSize: 12, color: '#818cf8', marginBottom: step.detail ? 8 : 0 }}>{step.summary}</div>
      {step.detail && (
        <pre style={{
          fontSize: 11, background: '#070810', color: '#a5f3fc',
          padding: '10px 12px', borderRadius: 6, overflowX: 'auto',
          margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
          lineHeight: 1.6, maxHeight: 280, overflow: 'auto',
          border: '1px solid #1e2047',
        }}>
          {JSON.stringify(step.detail, null, 2)}
        </pre>
      )}
    </div>
  );
}

// ── 徽章小工具 ───────────────────────────────────────────
function Badge({ children, bg, fg, mono }: { children: React.ReactNode; bg: string; fg: string; mono?: boolean }) {
  return (
    <span style={{
      fontSize: 12, padding: '2px 10px', borderRadius: 20,
      background: bg, color: fg,
      fontFamily: mono ? 'monospace' : undefined,
    }}>
      {children}
    </span>
  );
}

// ── analysis_executor (Python 逻辑) 专属面板 ──────────────
function PythonDetail({ step }: { step: TraceStep }) {
  const d = step.detail as Record<string, unknown> | undefined;
  const logic = d?.logic as string | undefined;
  const pythonScript = d?.python_script as string | undefined;
  const error = d?.error as string | undefined;
  const [scriptExpanded, setScriptExpanded] = React.useState(false);

  return (
    <div style={{ padding: '10px 14px 14px', borderTop: '1px solid #1e2047', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ fontSize: 12, color: step.status === 'error' ? '#f87171' : '#818cf8' }}>{step.summary}</div>
      {logic && (
        <pre style={{
          fontSize: 12, background: '#070810', color: '#bbf7d0',
          padding: '12px 14px', borderRadius: 6, overflowX: 'auto',
          margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
          lineHeight: 1.7, fontFamily: '"JetBrains Mono","Fira Code",Menlo,monospace',
          border: '1px solid #14532d',
        }}>
          {logic}
        </pre>
      )}
      {pythonScript && (
        <div>
          <div
            onClick={() => setScriptExpanded(v => !v)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              cursor: 'pointer', userSelect: 'none',
              fontSize: 11, color: '#6b7298', fontWeight: 600,
              letterSpacing: 0.5, textTransform: 'uppercase',
              padding: '4px 0',
            }}
          >
            <span>{scriptExpanded ? '▼' : '▶'}</span>
            <span>Python 计算脚本（点击展开）</span>
            <span style={{ marginLeft: 4, padding: '1px 7px', borderRadius: 8, background: '#1e1b4b', color: '#a5b4fc', fontSize: 10 }}>
              {pythonScript.split('\n').length} 行
            </span>
          </div>
          {scriptExpanded && (
            <pre style={{
              fontSize: 11.5, background: '#070810', color: '#c4b5fd',
              padding: '12px 14px', borderRadius: 6, overflowX: 'auto',
              margin: 0, whiteSpace: 'pre', wordBreak: 'normal',
              lineHeight: 1.65, fontFamily: '"JetBrains Mono","Fira Code",Menlo,monospace',
              border: '1px solid #2e1065', maxHeight: 480, overflow: 'auto',
            }}>
              {pythonScript}
            </pre>
          )}
        </div>
      )}
      {error && (
        <pre style={{ fontSize: 11, background: '#1c0005', color: '#fca5a5', padding: '8px 12px', borderRadius: 6, margin: 0, whiteSpace: 'pre-wrap', border: '1px solid #7f1d1d' }}>
          {error}
        </pre>
      )}
    </div>
  );
}

// ── analysis_data_loader SQL 面板（复用 SqlDetail 结构但用 detail.sql） ──
function AnalysisSqlDetail({ step }: { step: TraceStep }) {
  const d = step.detail as Record<string, unknown> | undefined;
  const sql = d?.sql as string | undefined;
  const error = d?.error as string | undefined;
  return (
    <div style={{ padding: '10px 14px 14px', borderTop: '1px solid #1e2047', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ fontSize: 12, color: step.status === 'error' ? '#f87171' : '#818cf8' }}>{step.summary}</div>
      {sql && (
        <>
          <div style={{ fontSize: 11, color: '#6b7298', fontWeight: 600, letterSpacing: 0.5, textTransform: 'uppercase' }}>数据取数 SQL</div>
          <pre style={{
            fontSize: 12, background: '#070810', color: '#7dd3fc',
            padding: '12px 14px', borderRadius: 6, overflowX: 'auto',
            margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
            lineHeight: 1.7, fontFamily: '"JetBrains Mono","Fira Code",Menlo,monospace',
            border: '1px solid #1e3a5f',
          }}>
            {sql}
          </pre>
        </>
      )}
      {error && (
        <pre style={{ fontSize: 11, background: '#1c0005', color: '#fca5a5', padding: '8px 12px', borderRadius: 6, margin: 0, whiteSpace: 'pre-wrap', border: '1px solid #7f1d1d' }}>
          {error}
        </pre>
      )}
    </div>
  );
}

// ── 根据步骤名选择详情面板 ───────────────────────────────
function StepDetail({ step }: { step: TraceStep }) {
  switch (step.step) {
    case 'sql_generator':              return <SqlDetail step={step} />;
    case 'analysis_data_loader':       return <AnalysisSqlDetail step={step} />;
    case 'analysis_executor':          return <PythonDetail step={step} />;
    case 'semantic_resolver':          return <SemanticDetail step={step} />;
    case 'intent_router':              return <IntentDetail step={step} />;
    case 'sql_validator':              return <ValidatorDetail step={step} />;
    default:                           return <GenericDetail step={step} />;
  }
}

// ── 主组件 ───────────────────────────────────────────────
const QueryTrace: React.FC<QueryTraceProps> = ({ trace }) => {
  const [expanded, setExpanded] = useState(false);
  const [expandedStep, setExpandedStep] = useState<string | null>(null);

  if (!trace || trace.length === 0) return null;

  const totalMs = trace.reduce((sum, s) => sum + (s.elapsed_ms ?? 0), 0);
  const hasError = trace.some(s => s.status === 'error');
  const showTiming = totalMs > 0;

  return (
    <div style={{
      marginTop: 10,
      border: '1px solid #252747',
      borderRadius: 8,
      overflow: 'hidden',
      fontSize: 13,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    }}>
      {/* 标题栏 */}
      <div
        onClick={() => setExpanded(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 14px', backgroundColor: '#1a1b35',
          cursor: 'pointer', userSelect: 'none',
          borderBottom: expanded ? '1px solid #252747' : 'none',
        }}
      >
        <span style={{ fontWeight: 500, color: '#c4c9e8' }}>
          {expanded ? '▼' : '▶'} 查询管道追踪
          <span style={{ color: '#6b7298', fontWeight: 400, marginLeft: 8 }}>
            {trace.length} 步{showTiming ? ` · ${totalMs.toFixed(0)}ms` : ''}
          </span>
          {hasError && (
            <span style={{ marginLeft: 8, fontSize: 11, padding: '1px 6px', borderRadius: 8, background: '#7f1d1d', color: '#fca5a5' }}>
              有错误
            </span>
          )}
        </span>
        <span style={{ fontSize: 11, color: '#6b7298', padding: '2px 8px', background: '#252747', borderRadius: 10 }}>
          {expanded ? '收起' : '展开'}
        </span>
      </div>

      {/* 步骤列表 */}
      {expanded && (
        <div style={{ background: '#12142a' }}>
          {trace.map((step, idx) => {
            const isExpanded = expandedStep === `${step.step}-${idx}`;
            const label    = STEP_LABELS[step.step] || step.step;
            const dotColor = STATUS_COLORS[step.status] ?? '#818cf8';
            const isSqlGen = step.step === 'sql_generator' || step.step === 'analysis_data_loader';
            const isError  = step.status === 'error';

            return (
              <div
                key={`${step.step}-${idx}`}
                style={{
                  borderBottom: idx < trace.length - 1 ? '1px solid #1a1c36' : 'none',
                  background: isSqlGen ? '#14164a' : isError ? '#1c0714' : 'transparent',
                }}
              >
                {/* 步骤行 */}
                <div
                  onClick={() => setExpandedStep(isExpanded ? null : `${step.step}-${idx}`)}
                  style={{ display: 'flex', alignItems: 'center', padding: '7px 14px', cursor: 'pointer' }}
                >
                  <span style={{
                    width: 8, height: 8, borderRadius: '50%', background: dotColor,
                    marginRight: 10, flexShrink: 0,
                    boxShadow: isError ? `0 0 6px ${dotColor}` : 'none',
                  }} />
                  <span style={{
                    width: 130, flexShrink: 0,
                    color: isSqlGen ? '#a5b4fc' : isError ? '#fca5a5' : '#818cf8',
                    fontWeight: isSqlGen ? 600 : 400,
                  }}>
                    {label}
                  </span>
                  {!isExpanded && (
                    <span style={{ flex: 1, color: '#6b7298', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginRight: 8 }}>
                      {step.summary}
                    </span>
                  )}
                  {isExpanded && <span style={{ flex: 1 }} />}
                  <span style={{ color: '#474970', fontSize: 12, flexShrink: 0, minWidth: 60, textAlign: 'right' }}>
                    {step.elapsed_ms?.toFixed(1)}ms
                  </span>
                  <span style={{ marginLeft: 8, color: '#474970', fontSize: 10, flexShrink: 0 }}>
                    {isExpanded ? '▼' : '▶'}
                  </span>
                </div>

                {/* 详情面板 */}
                {isExpanded && <StepDetail step={step} />}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default QueryTrace;
