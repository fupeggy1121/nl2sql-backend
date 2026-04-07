// modules/mes/components/UnifiedChat/UnifiedChat.tsx
import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  MessageSquare,
  Loader2,
  Sparkles,
  ThumbsUp,
  ThumbsDown,
  BarChart3,
  Save,
  Copy,
  Download,
  ChevronDown,
  Database,
  AlertCircle,
  Table,
  BarChart,
  LineChart,
  PieChart,
  LayoutDashboard,
  Radar,
  BoxSelect,
} from 'lucide-react';
import { nl2sqlApi } from "../../../../services/nl2sqlApi";
import type { PlotlyChartSpec, AnalysisResultPayload } from "../../../../services/nl2sqlApi";
import { EChartsVisualization } from "../EChartsVisualization";
import { FeedbackForm } from "../FeedbackForm";
import { FeedbackStats } from "../FeedbackStats";
import QueryTrace, { TraceStep } from "../QueryTrace";
import { useData } from "../../../../hooks/useData";
import InlineTraceabilityChart from '../../../../components/Traceability/InlineTraceabilityChart';
import AnalysisChartPanel from '../../../../components/Analysis/AnalysisChartPanel';
import './UnifiedChat.css';

export interface Message {
  id: string;
  type: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  data?: any;
  visualizationType?: 'bar' | 'line' | 'pie' | 'scatter' | 'card' | 'gauge' | 'table' | 'heatmap' | 'radar' | 'funnel' | 'treemap' | 'boxplot' | 'bar-line-combo' | 'grouped_bar' | 'pareto' | 'traceability';
  traceabilityData?: { lotCode?: string; waferCode?: string };
  chartConfig?: {
    title?: string;
    xAxisField?: string;
    yAxisField?: string;
    colorField?: string;
    valueField?: string;
    seriesField?: string;    // 分组系列字段（用于 grouped_bar）
    cardTheme?: 'success' | 'warning' | 'danger' | 'info';
    trend?: { direction: 'up' | 'down' | 'stable'; value: number };
    comparisonValue?: { label: string; value: number };
    gaugeMin?: number;
    gaugeMax?: number;
    gaugeThresholds?: number[];
    thresholds?: Array<{ value: number; level: string; label: string; color?: string }>;
    thresholdDirection?: 'above' | 'below';
  };
  actions?: string[];
  intent?: any;
  sqlSuggestion?: {
    sql: string;
    originalQuery: string;
  };
  queryResult?: {
    success: boolean;
    data?: any;
    error?: string;
    rowCount?: number;
  };
  analysisResult?: AnalysisResultPayload;
  analysisCharts?: PlotlyChartSpec[];
  pipeline_trace?: TraceStep[];
}

const SAMPLE_QUESTIONS = [
  '昨天设备E-001的OEE是多少？',
  '显示最近一周所有设备的OEE趋势',
  '对比A班和B班的生产效率',
  '哪些设备的停机时间最长？',
  '显示设备E-002的良率',
];

// ── 追溯意图检测 ────────────────────────────────────────────────────
const TRACEABILITY_TRIGGERS = [
  '批次追溯', '追溯批次', '批次履历', '追溯', '生产履历',
  '批次谱系', '谱系', 'wafer追溯', '追踪批次', 'wafer履历',
];

// ── 图表类型切换 ─────────────────────────────────────────────────
const CHART_TYPE_MAP: Partial<Record<string, Message['visualizationType']>> = {
  '柱状图': 'bar', '条形图': 'bar', '直方图': 'bar',
  '折线图': 'line', '趋势图': 'line', '曲线图': 'line',
  '饼图': 'pie', '圆饼图': 'pie', '环形图': 'pie',
  '散点图': 'scatter',
  '热力图': 'heatmap',
  '雷达图': 'radar',
  '漏斗图': 'funnel',
  '分组柱状图': 'grouped_bar', '分组图': 'grouped_bar', '多维柱状图': 'grouped_bar',
  '柏拉图': 'pareto', '帕累托图': 'pareto', 'pareto': 'pareto',
  '表格': 'table',
};

const CHART_TYPE_LABELS: Record<string, string> = {
  bar: '柱状图', line: '折线图', pie: '饼图', scatter: '散点图',
  table: '表格', heatmap: '热力图', radar: '雷达图', funnel: '漏斗图',
  grouped_bar: '分组柱状图',
  pareto: '柏拉图',
};

// 包含这些关键字时视为「数据查询」，不拦截
const DATA_QUERY_KEYWORDS = ['统计', '查询', '查找', '获取', '计算', 'select', '列出', '找出', '过滤', '排序', '分组'];

/**
 * 判断输入是否是纯粹的「切换图表类型」请求。
 * 返回目标图表类型及可选的 X/Y 轴字段提示；若不是则返回 null。
 */
function detectChartChangeIntent(text: string): {
  chartType: Message['visualizationType'];
  xAxisHint: string | null;
  yAxisHint: string | null;
} | null {
  // 含数据查询词 → 是新查询，不拦截
  if (DATA_QUERY_KEYWORDS.some((k) => text.includes(k))) return null;

  let chartType: Message['visualizationType'] | undefined;
  const textLower = text.toLowerCase();
  for (const [keyword, type] of Object.entries(CHART_TYPE_MAP)) {
    if (text.includes(keyword) || textLower.includes(keyword.toLowerCase())) {
      chartType = type;
      break;
    }
  }
  if (!chartType) return null;

  // 必须有表示「切换/展示」的动词
  const displayVerbs = ['展示', '显示', '改成', '切换', '用', '以', '换成', '改为', '变成', '换为'];
  if (!displayVerbs.some((v) => text.includes(v))) return null;

  // 提取轴字段提示
  const xMatch = text.match(/[xX]轴[为是](.+?)(?=[，,。；\s]|[yY]轴|$)/);
  const yMatch = text.match(/[yY]轴[为是](.+?)(?=[，,。；\s]|[xX]轴|$)/);

  return {
    chartType,
    xAxisHint: xMatch ? xMatch[1].trim() : null,
    yAxisHint: yMatch ? yMatch[1].trim() : null,
  };
}

/** 从用户输入中提取批次号或 Wafer 号（支持 LOT-xxx / DEMO-xxx / L+多位数 / 批次关键字后跟码 等） */
function extractTraceCode(text: string): { lotCode?: string; waferCode?: string } {
  // 优先匹配明确标注的 wafer 代号
  const waferMatch = text.match(/[Ww][Aa][Ff][Ee][Rr][-_]?\s*([A-Za-z0-9-]+)/);
  if (waferMatch) return { waferCode: waferMatch[1] };

  // 匹配各种批次号格式（所有 pattern 均用 group 1 捕获完整代码）
  const lotPatterns = [
    /[Ll][Oo][Tt][-_]?\s*([A-Za-z0-9-]+)/,           // LOT-xxx
    /([Dd][Ee][Mm][Oo][-_][A-Za-z0-9][-A-Za-z0-9]*)/,// DEMO-2026-A01 完整代码
    /[Ll](\d{4,})/,                                   // L + 4位以上数字
    /批次[号码]?\s*[:：]?\s*([A-Za-z0-9-]{3,})/,      // 批次号: xxx
    /([A-Z]{2,}-\d{4}-[A-Z]\d{2})/,                  // CC-1234-A01 工厂格式
  ];
  for (const pat of lotPatterns) {
    const m = text.match(pat);
    if (m && m[1]) return { lotCode: m[1] };
  }
  return {};
}

interface UnifiedChatProps {
  setMessages?: (messages: Message[]) => void;
  setIsProcessing?: (isProcessing: boolean) => void;
  onNavigateToTraceability?: (params: { lotCode?: string; waferCode?: string }) => void;
  sessionId: string;
  skipDataGeneration?: boolean;
  onRenameSession?: (name: string) => void;
}

type ChatStep = 'input' | 'clarify' | 'explain' | 'execute' | 'results';

export function UnifiedChat({
  setMessages: setParentMessages,
  setIsProcessing: setParentIsProcessing,
  onNavigateToTraceability,
  sessionId,
  skipDataGeneration = false,
  onRenameSession,
}: UnifiedChatProps) {
  const { createSavedReport, fetchChatMessages, addChatMessage, refetchSavedReports } = useData();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [feedbackMessageId, setFeedbackMessageId] = useState<string | null>(null);
  const [showFeedbackStats, setShowFeedbackStats] = useState(false);
  const [currentIntent, setCurrentIntent] = useState<any>(null);
  const [dbConnected, setDbConnected] = useState(false);
  const [expandedSqlId, setExpandedSqlId] = useState<string | null>(null);
  const [copiedSqlId, setCopiedSqlId] = useState<string | null>(null);
  
  const [step, setStep] = useState<ChatStep>('input');
  const [queryPlan, setQueryPlan] = useState<any>(null);
  const [editedSQL, setEditedSQL] = useState<string>('');
  const [currentSQL, setCurrentSQL] = useState<string>('');
  
  const [activeChartTypeOverrides, setActiveChartTypeOverrides] = useState<Record<string, Message['visualizationType']>>({});
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const checkConnection = async () => {
      const result = await nl2sqlApi.checkConnection();
      setDbConnected(result.connected);
    };
    checkConnection();
    const interval = setInterval(checkConnection, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const loadMessages = async () => {
      const history = await fetchChatMessages(sessionId);
      if (history.length === 0) {
        setMessages([
          {
            id: '1',
            type: 'assistant',
            content:
              '您好！我是 MES 数据智能分析助手。我可以帮您分析生产数据、生成报表、监控设备状态。\n\n您可以用自然语言提问，我会先分析您的意图并为您生成SQL查询语句。在您确认SQL语句后，我会执行查询并展示结果。',
            timestamp: new Date(),
          },
        ]);
      } else {
        setMessages(history);
      }
    };
    loadMessages();
  }, [fetchChatMessages, sessionId]);

  useEffect(() => {
    if (setParentMessages) {
      setParentMessages(messages);
    }
  }, [messages, setParentMessages]);

  useEffect(() => {
    if (setParentIsProcessing) {
      setParentIsProcessing(isProcessing);
    }
  }, [isProcessing, setParentIsProcessing]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async (messageContent?: string) => {
    const content = messageContent || input;
    if (!content.trim() || isProcessing) return;

    // ── 追溯意图检测（优先于 NL2SQL 流程）──────────────────────────
    const isTraceabilityQuery = TRACEABILITY_TRIGGERS.some((t) =>
      content.includes(t)
    );
    if (isTraceabilityQuery) {
      const traceParams = extractTraceCode(content);
      const userMessage: Message = {
        id: Date.now().toString(),
        type: 'user',
        content: content,
        timestamp: new Date(),
      };
      const replyMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: traceParams.lotCode
          ? `批次 ${traceParams.lotCode} 追溯履历`
          : traceParams.waferCode
          ? `Wafer ${traceParams.waferCode} 追溯履历`
          : '批次追溯查询',
        timestamp: new Date(),
        visualizationType: 'traceability',
        traceabilityData: traceParams,
      };
      setMessages((prev) => [...prev, userMessage, replyMessage]);
      setInput('');
      await addChatMessage(sessionId, userMessage);
      await addChatMessage(sessionId, replyMessage);
      return;
    }
    // ────────────────────────────────────────────────────────────────

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: content,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsProcessing(true);
    setStep('execute');

    // Auto-name session from the first real question
    if (onRenameSession && messages.filter(m => m.type === 'user').length === 0) {
      const title = content.trim().replace(/\s+/g, ' ');
      onRenameSession(title.length > 20 ? title.slice(0, 18) + '\u2026' : title);
    }

    try {
      await addChatMessage(sessionId, userMessage);

      // ── 图表切换拦截：不调用后端，直接在前端改变最近一条结果的可视化类型 ──
      const chartIntent = detectChartChangeIntent(content);
      if (chartIntent) {
        const lastDataMsg = [...messages].reverse().find(
          (m) => m.type === 'assistant' && Array.isArray(m.data) && m.data.length > 0
        );
        if (lastDataMsg) {
          // 尝试从实际列名模糊匹配坐标轴字段
          const columns = Object.keys(lastDataMsg.data![0]);
          const resolveField = (hint: string | null) => {
            if (!hint) return undefined;
            return (
              columns.find((c) => c.toLowerCase().includes(hint.toLowerCase())) ||
              columns.find((c) => hint.toLowerCase().includes(c.toLowerCase())) ||
              hint
            );
          };

          setActiveChartTypeOverrides((prev) => ({
            ...prev,
            [lastDataMsg.id]: chartIntent.chartType,
          }));

          if (chartIntent.xAxisHint || chartIntent.yAxisHint) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id !== lastDataMsg.id
                  ? m
                  : {
                      ...m,
                      chartConfig: {
                        ...m.chartConfig,
                        ...(chartIntent.xAxisHint
                          ? { xAxisField: resolveField(chartIntent.xAxisHint) }
                          : {}),
                        ...(chartIntent.yAxisHint
                          ? { yAxisField: resolveField(chartIntent.yAxisHint) }
                          : {}),
                      },
                    }
              )
            );
          }

          const label = CHART_TYPE_LABELS[chartIntent.chartType] ?? chartIntent.chartType;
          const axisInfo = [
            chartIntent.xAxisHint ? `X轴：${chartIntent.xAxisHint}` : '',
            chartIntent.yAxisHint ? `Y轴：${chartIntent.yAxisHint}` : '',
          ]
            .filter(Boolean)
            .join('，');
          const replyMsg: Message = {
            id: (Date.now() + 1).toString(),
            type: 'assistant',
            content: `已切换为${label}${axisInfo ? `（${axisInfo}）` : ''}。`,
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, replyMsg]);
          await addChatMessage(sessionId, replyMsg);
          setIsProcessing(false);
          setStep('input');
          return;
        }
        // 没有上文数据时继续走后端（后端会报错），友好提示
        const noDataMsg: Message = {
          id: (Date.now() + 1).toString(),
          type: 'assistant',
          content: '暂无可切换的查询结果，请先执行一次数据查询。',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, noDataMsg]);
        await addChatMessage(sessionId, noDataMsg);
        setIsProcessing(false);
        setStep('input');
        return;
      }
      // ── end 图表切换拦截 ──

      const response = await nl2sqlApi.explainQuery(content, sessionId);
      
      if (!response.success) {
        throw new Error(response.error || 'Failed to process query.');
      }

// ── Clarification 分支：后端意图模糊，需要向用户反问 ──
if (response.type === 'clarification' && response.clarification_question) {
  setStep('clarify');
  const clarificationMessage: Message = {
    id: (Date.now() + 1).toString(),
    type: 'assistant',
    content: response.clarification_question,
    timestamp: new Date(),
    pipeline_trace: response.pipeline_trace,
  };
  setMessages((prev) => [...prev, clarificationMessage]);
  await addChatMessage(sessionId, clarificationMessage);
  setIsProcessing(false);
  return;
}

// ── 分析报表分支：analysis_agent 直接返回结果（良率/OEE 等），无 query_plan ──
if (response.analysis || response.answer) {
  const reportMsg: Message = {
    id: (Date.now() + 1).toString(),
    type: 'assistant',
    content: response.answer || response.analysis?.summary || '分析完成',
    timestamp: new Date(),
    analysisResult: response.analysis,
    analysisCharts: response.charts,
    pipeline_trace: response.pipeline_trace,
  };
  setMessages((prev) => [...prev, reportMsg]);
  await addChatMessage(sessionId, reportMsg);
  setIsProcessing(false);
  setStep('input');
  return;
}

// ── 普通查询分支：query_agent 已在第一次请求中执行 SQL 并返回结果 ──
// 后端始终自动执行，无需用户手动确认 SQL；SQL 细节在 pipeline_trace 中可查
if (response.query_result?.success && Array.isArray(response.query_result.data)) {
  setStep('results');
  const qr = response.query_result;
  const resultMsg: Message = {
    id: (Date.now() + 1).toString(),
    type: 'assistant',
    content: `✅ 查询返回 ${qr.rows_count ?? qr.data.length} 条数据`,
    timestamp: new Date(),
    queryResult: {
      success: true,
      data: qr.data,
      rowCount: qr.rows_count ?? qr.data.length,
    },
    data: qr.data,
    visualizationType: (response.visualization?.type || qr.visualization_type || 'table') as Message['visualizationType'],
    chartConfig: {
      xAxisField: response.visualization?.xAxisField,
      yAxisField: response.visualization?.yAxisField,
      seriesField: response.visualization?.seriesField,
      colorField: response.visualization?.colorField,
      thresholds: response.visualization?.thresholds,
      thresholdDirection: response.visualization?.thresholdDirection,
    },
    intent: response.query_plan?.query_intent,
    pipeline_trace: response.pipeline_trace,
  };
  setMessages((prev) => [...prev, resultMsg]);
  await addChatMessage(sessionId, resultMsg);
  setIsProcessing(false);
  setStep('input');
  return;
}

// ── 基线设定分支：baseline_manager 返回 intent=set_baseline ──
if (response.intent === 'set_baseline') {
  const baselineMsg: Message = {
    id: (Date.now() + 1).toString(),
    type: 'assistant',
    content: response.text || '✅ 基线已设定',
    timestamp: new Date(),
    pipeline_trace: response.pipeline_trace,
  };
  setMessages((prev) => [...prev, baselineMsg]);
  await addChatMessage(sessionId, baselineMsg);
  setIsProcessing(false);
  setStep('input');
  return;
}

const queryPlan = response.query_plan;
if (!queryPlan) {
  const errorMessage: Message = {
    id: (Date.now() + 1).toString(),
    type: 'assistant',
    content: '抱歉，后端未能生成查询计划。请尝试换一种方式提问或联系管理员。',
    timestamp: new Date(),
  };
  setMessages((prev) => [...prev, errorMessage]);
  await addChatMessage(sessionId, errorMessage);
  setIsProcessing(false);
  setStep('input');
  return;
}
setQueryPlan(queryPlan);
setCurrentIntent(queryPlan.query_intent || null);

      if (queryPlan.clarification_message) {
        setStep('clarify');
        const clarificationMessage: Message = {
          id: (Date.now() + 1).toString(),
          type: 'assistant',
          content: queryPlan.clarification_message,
          timestamp: new Date(),
          intent: queryPlan.query_intent || null,
        };
        setMessages((prev) => [...prev, clarificationMessage]);
        await addChatMessage(sessionId, clarificationMessage);
      } 
      else if (queryPlan.generated_sql) {
        setStep('explain');
        setCurrentSQL(queryPlan.generated_sql);
        setEditedSQL(queryPlan.generated_sql);
        
        const messageId = (Date.now() + 1).toString();
        const assistantMessage: Message = {
          id: messageId,
          type: 'assistant',
          content: '我已经为您分析了查询意图并生成了SQL查询语句，请确认后执行：',
          timestamp: new Date(),
          sqlSuggestion: {
            sql: queryPlan.generated_sql,
            originalQuery: content,
          },
          intent: queryPlan.query_intent || null,
          pipeline_trace: response.pipeline_trace,
        };

        setMessages((prev) => [...prev, assistantMessage]);
        await addChatMessage(sessionId, assistantMessage);
      }
      else if (response.content) {
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          type: 'assistant',
          content: response.content,
          timestamp: new Date(),
          intent: queryPlan.query_intent || null,
          pipeline_trace: response.pipeline_trace,
        };
        setMessages((prev) => [...prev, assistantMessage]);
        await addChatMessage(sessionId, assistantMessage);
      }
      else {
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          type: 'assistant',
          content: '我已经理解了您的查询意图，正在处理中...',
          timestamp: new Date(),
          intent: queryPlan.query_intent || null,
          pipeline_trace: response.pipeline_trace,
        };
        setMessages((prev) => [...prev, assistantMessage]);
        await addChatMessage(sessionId, assistantMessage);
      }
    } catch (error) {
      console.error('Processing error:', error);
      setStep('input');
      const errorMessage: Message = {
        id: Date.now().toString(),
        type: 'assistant',
        content: `抱歉，处理您的请求时出现错误：${error.message}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
      await addChatMessage(sessionId, errorMessage);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleExecuteSQL = async (sql: string, messageId: string, queryIntent?: typeof currentIntent) => {
    if (!dbConnected) {
      alert('数据库连接已断开，请稍后重试');
      return;
    }

    setIsProcessing(true);
    setStep('execute');

    try {
      const response = await nl2sqlApi.executeApprovedQuery(sql, queryIntent ?? currentIntent ?? undefined);

      if (response.success) {
        setStep('results');
        const resultMessage: Message = {
          id: (Date.now() + 2).toString(),
          type: 'assistant',
          content: `✅ 查询成功执行，返回 ${response.query_result?.rows_count || 0} 条数据`,
          timestamp: new Date(),
          queryResult: {
            success: true,
            data: response.query_result?.data,
            rowCount: response.query_result?.rows_count,
          },
          data: response.query_result?.data,
          visualizationType: (response.visualization?.type || response.query_result?.visualization_type || 'table') as Message['visualizationType'],
          chartConfig: {
            title: response.chartTitle,
            xAxisField: response.visualization?.xAxisField,
            yAxisField: response.visualization?.yAxisField,
            seriesField: response.visualization?.seriesField,
            colorField: response.visualization?.colorField,
            thresholds: response.visualization?.thresholds,
            thresholdDirection: response.visualization?.thresholdDirection,
          },
          intent: currentIntent,
          pipeline_trace: response.pipeline_trace,
          sqlSuggestion: { sql, originalQuery: '' },
        };

        setMessages((prev) => [...prev, resultMessage]);
        await addChatMessage(sessionId, resultMessage);
      } else {
        setStep('explain');
        const errorResultMessage: Message = {
          id: (Date.now() + 2).toString(),
          type: 'assistant',
          content: `❌ 查询执行失败: ${response.error}`,
          timestamp: new Date(),
          queryResult: {
            success: false,
            error: response.error,
          },
        };

        setMessages((prev) => [...prev, errorResultMessage]);
        await addChatMessage(sessionId, errorResultMessage);
      }
    } catch (error) {
      setStep('explain');
      const errorMessage: Message = {
        id: Date.now().toString(),
        type: 'assistant',
        content: `❌ 执行失败: ${error.message}`,
        timestamp: new Date(),
        queryResult: {
          success: false,
          error: error.message,
        },
      };
      setMessages((prev) => [...prev, errorMessage]);
      await addChatMessage(sessionId, errorMessage);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleExecuteQuery = async (message: Message) => {
    if (!message.sqlSuggestion || !dbConnected) {
      alert(dbConnected ? '无法执行此查询' : '数据库连接已断开，请稍后重试');
      return;
    }

    // 传递原始查询的 intent（含 query_type），确保 result_analyzer 能正确推断图表类型
    await handleExecuteSQL(message.sqlSuggestion.sql, message.id, message.intent ?? undefined);
  };

  const handleCopySQL = (sql: string, sqlId: string) => {
    navigator.clipboard.writeText(sql);
    setCopiedSqlId(sqlId);
    setTimeout(() => setCopiedSqlId(null), 2000);
  };

  const handleExportResults = (data: any) => {
    if (!data || data.length === 0) {
      alert('没有数据可导出');
      return;
    }

    const headers = Object.keys(data[0]);
    const csvContent = [
      headers.join(','),
      ...data.map((row) =>
        headers
          .map((header) => {
            const value = row[header];
            return typeof value === 'string' && value.includes(',')
              ? `"${value}"`
              : value;
          })
          .join(',')
      ),
    ].join('\n');

    const element = document.createElement('a');
    element.setAttribute(
      'href',
      'data:text/csv;charset=utf-8,' + encodeURIComponent(csvContent)
    );
    element.setAttribute('download', `query-results-${Date.now()}.csv`);
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  const handleSaveReport = async (message: Message) => {
    console.log('handleSaveReport: message.intent =', message.intent);
    if (!message.intent) {
      alert('无法保存此报表，缺少查询意图信息。');
      return;
    }

    const dataToSave = message.queryResult?.success ? 
      message.queryResult.data : 
      message.data;

    if (!dataToSave || dataToSave.length === 0) {
      alert('无法保存此报表，缺少必要的查询数据。');
      return;
    }

    const reportName = prompt(
      '请输入报表名称：',
      message.intent.entities && message.intent.entities.metric
        ? `${message.intent.entities.metric} ${message.intent.entities.timeRange} 报表`
        : '自定义报表'
    );
    if (!reportName) return;

    const reportDescription = prompt(
      '请输入报表描述（可选）：',
      message.content.substring(0, 50) + '...'
    );

    try {
      const chartType = activeChartTypeOverrides[message.id] || message.visualizationType || 'table';
      
      const newReport = {
        name: reportName,
        type: 'generic-report',
        description: reportDescription || undefined,
        queryParams: message.intent.entities || {},
        sqlQuery: message.sqlSuggestion?.sql,
        data: dataToSave,
        visualizationType: chartType,
        chartConfig: message.chartConfig,
        created_by: '当前用户',
      };

      await createSavedReport(newReport);
      alert('报表已成功保存！');
      await refetchSavedReports();
    } catch (error) {
      alert('保存报表失败！');
      console.error('Error saving report:', error);
    }
  };

  const handleQuickQuestion = (question: string) => {
    setInput(question);
    setTimeout(() => {
      const sendBtn = document.querySelector('.send-btn') as HTMLButtonElement;
      if (sendBtn && !sendBtn.disabled) {
        sendBtn.click();
      }
    }, 100);
  };

  const handleSQLEdit = (sql: string) => {
    setEditedSQL(sql);
  };

  const handleChartTypeChange = (messageId: string, chartType: Message['visualizationType']) => {
    setActiveChartTypeOverrides(prev => ({
      ...prev,
      [messageId]: chartType
    }));
  };

  return (
    <div className="unified-chat-container">
      {/* 顶部标题栏 */}
      <header className="unified-chat-header">
        <div className="header-content">
          <div className="header-left">
            <div className="header-icon">
              <Sparkles className="icon" />
            </div>
            <div className="header-title">
              <h1>X</h1>
            </div>
          </div>
          <div className="header-right">
            <button
              onClick={() => setShowFeedbackStats(true)}
              className="header-btn"
              title="查看反馈分析"
            >
              <BarChart3 className="icon" />
              反馈分析
            </button>
            <div className={`status-indicator ${dbConnected ? 'connected' : 'disconnected'}`}>
              {dbConnected ? '✅ 已连接' : '❌ 未连接'}
            </div>
          </div>
        </div>
      </header>

      <div className="messages-area">
        <div className="messages-container">
          {messages.map((message) => {
            const currentChartType = activeChartTypeOverrides[message.id] || message.visualizationType;
            const visualizationData = message.queryResult?.success ? message.queryResult.data : message.data;
            const hasVisualizationData = visualizationData && visualizationData.length > 0;

            return (
              <div key={message.id} className="message-group">
                {/* 消息气泡 */}
                <div className={`message ${message.type}`}>
                  <div className="message-avatar">
                    {message.type === 'user' ? '👤' : message.type === 'system' ? 'ℹ️' : '🤖'}
                  </div>
                  <div className="message-content">
                    <p className="message-text">{message.content}</p>
                    <span className="message-time">
                      {message.timestamp.toLocaleTimeString('zh-CN', {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>
                </div>

                {/* 批次追溯内联图表 */}
                {message.visualizationType === 'traceability' && (
                  <InlineTraceabilityChart
                    lotCode={message.traceabilityData?.lotCode}
                    waferCode={message.traceabilityData?.waferCode}
                  />
                )}

                {/* 分析报表图表（良率/OEE 等 analysis_agent 返回） */}
                {message.type === 'assistant' && message.analysisCharts && message.analysisCharts.length > 0 && (
                  <AnalysisChartPanel charts={message.analysisCharts} />
                )}

                {/* 查询追踪组件 - 当存在 pipeline_trace 时渲染 */}
                {message.type === 'assistant' && message.pipeline_trace && message.pipeline_trace.length > 0 && (
                  <QueryTrace trace={message.pipeline_trace} />
                )}

                {/* SQL 查询建议卡片 */}
                {message.sqlSuggestion && message.type === 'assistant' && (
                  <div className="sql-card">
                    <div className="sql-card-header">
                      <div className="sql-card-title">
                        <Database className="icon" />
                        <span>推荐的 SQL 查询</span>
                      </div>
                      <button
                        onClick={() => setExpandedSqlId(expandedSqlId === message.id ? null : message.id)}
                        className="expand-btn"
                      >
                        <ChevronDown
                          className={`icon ${expandedSqlId === message.id ? 'expanded' : ''}`}
                        />
                      </button>
                    </div>

                    {expandedSqlId === message.id && (
                      <div className="sql-card-body">
                        <pre className="sql-code">{message.sqlSuggestion.sql}</pre>
                        
                        {step === 'explain' && (
                          <textarea
                            value={editedSQL}
                            onChange={(e) => handleSQLEdit(e.target.value)}
                            className="sql-edit-textarea"
                            rows={4}
                            placeholder="如果需要，您可以编辑上面的SQL语句..."
                          />
                        )}
                        
                        <div className="sql-actions">
                          <button
                            onClick={() =>
                              handleCopySQL(message.sqlSuggestion.sql, message.id)
                            }
                            className="action-btn copy-btn"
                          >
                            <Copy className="icon" />
                            {copiedSqlId === message.id ? '已复制' : '复制'}
                          </button>
                          <button
                            onClick={() => handleExecuteQuery(message)}
                            disabled={isProcessing || !dbConnected}
                            className="action-btn execute-btn"
                          >
                            <Send className="icon" />
                            执行查询
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* 查询结果展示和数据可视化 (整合工具栏) */}
                {(message.queryResult || (message.data && message.data.length > 0)) && (
                  <div className={`visualization-container ${message.queryResult && !message.queryResult.success ? 'error' : ''}`}>
                    {/* 可视化工具栏 - 新增多种图表按钮 */}
                    {hasVisualizationData && (
                      <div className="visualization-controls-toolbar">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-gray-700">数据可视化</span>
                          <div className="chart-type-selector">
                            <button
                              className={`chart-type-btn ${currentChartType === 'table' ? 'active' : ''}`}
                              onClick={() => handleChartTypeChange(message.id, 'table')}
                              title="表格视图"
                            >
                              <Table size={16} />
                              <span>表格</span>
                            </button>
                            <button
                              className={`chart-type-btn ${currentChartType === 'bar' ? 'active' : ''}`}
                              onClick={() => handleChartTypeChange(message.id, 'bar')}
                              title="柱状图"
                            >
                              <BarChart size={16} />
                              <span>柱状图</span>
                            </button>
                            <button
                              className={`chart-type-btn ${currentChartType === 'line' ? 'active' : ''}`}
                              onClick={() => handleChartTypeChange(message.id, 'line')}
                              title="折线图"
                            >
                              <LineChart size={16} />
                              <span>折线图</span>
                            </button>
                            <button
                              className={`chart-type-btn ${currentChartType === 'pie' ? 'active' : ''}`}
                              onClick={() => handleChartTypeChange(message.id, 'pie')}
                              title="饼图"
                            >
                              <PieChart size={16} />
                              <span>饼图</span>
                            </button>
                            {/* 新增图表类型按钮 */}
                            <button
                              className={`chart-type-btn ${currentChartType === 'card' ? 'active' : ''}`}
                              onClick={() => handleChartTypeChange(message.id, 'card')}
                              title="单值图"
                            >
                              <LayoutDashboard size={16} />
                              <span>单值图</span>
                            </button>
                            <button
                              className={`chart-type-btn ${currentChartType === 'radar' ? 'active' : ''}`}
                              onClick={() => handleChartTypeChange(message.id, 'radar')}
                              title="雷达图"
                            >
                              <Radar size={16} />
                              <span>雷达图</span>
                            </button>
                            <button
                              className={`chart-type-btn ${currentChartType === 'boxplot' ? 'active' : ''}`}
                              onClick={() => handleChartTypeChange(message.id, 'boxplot')}
                              title="箱线图"
                            >
                              <BoxSelect size={16} />
                              <span>箱线图</span>
                            </button>
                            <button
                              className={`chart-type-btn ${currentChartType === 'bar-line-combo' ? 'active' : ''}`}
                              onClick={() => handleChartTypeChange(message.id, 'bar-line-combo')}
                              title="柱状折线组合图"
                            >
                              <LineChart size={16} />
                              <span>组合图</span>
                            </button>
                            <button
                              className={`chart-type-btn ${currentChartType === 'grouped_bar' ? 'active' : ''}`}
                              onClick={() => handleChartTypeChange(message.id, 'grouped_bar')}
                              title="分组柱状图（二维）"
                            >
                              <BarChart size={16} />
                              <span>分组图</span>
                            </button>
                            <button
                              className={`chart-type-btn ${currentChartType === 'pareto' ? 'active' : ''}`}
                              onClick={() => handleChartTypeChange(message.id, 'pareto')}
                              title="柏拉图（不良分析）"
                            >
                              <BarChart3 size={16} />
                              <span>柏拉图</span>
                            </button>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          {message.queryResult?.success && message.queryResult.data && (
                            <button
                              onClick={() => handleExportResults(message.queryResult.data)}
                              className="action-btn export-btn"
                            >
                              <Download className="icon" />
                              导出
                            </button>
                          )}
                          {message.type === 'assistant' && hasVisualizationData && (
                            <button
                              onClick={() => handleSaveReport(message)}
                              className="action-btn save-btn"
                            >
                              <Save className="icon" />
                              保存报表
                            </button>
                          )}
                        </div>
                      </div>
                    )}

                    {message.queryResult && message.queryResult.success ? (
                      <div className="result-body">
                        {hasVisualizationData ? (
                          <>
                            <EChartsVisualization
                              data={visualizationData}
                              type={currentChartType || 'table'}
                              title={message.chartConfig?.title}
                              xAxisField={message.chartConfig?.xAxisField}
                              yAxisField={message.chartConfig?.yAxisField}
                              seriesField={message.chartConfig?.seriesField}
                              colorField={message.chartConfig?.colorField}
                              valueField={message.chartConfig?.valueField}
                              cardTheme={message.chartConfig?.cardTheme}
                              trend={message.chartConfig?.trend}
                              comparisonValue={message.chartConfig?.comparisonValue}
                              gaugeMin={message.chartConfig?.gaugeMin}
                              gaugeMax={message.chartConfig?.gaugeMax}
                              gaugeThresholds={message.chartConfig?.gaugeThresholds}
                              thresholds={message.chartConfig?.thresholds}
                              thresholdDirection={message.chartConfig?.thresholdDirection}
                            />
                            <p className="result-meta">
                              共 {message.queryResult.rowCount || visualizationData.length} 条数据
                            </p>
                          </>
                        ) : (
                          <p className="no-data">查询返回 0 条数据</p>
                        )}
                      </div>
                    ) : message.queryResult && !message.queryResult.success ? (
                      <div className="error-body">
                        <p>{message.queryResult.error}</p>
                      </div>
                    ) : hasVisualizationData ? (
                      <div className="result-body">
                        <EChartsVisualization
                          data={visualizationData}
                          type={currentChartType || 'table'}
                          title={message.chartConfig?.title}
                          xAxisField={message.chartConfig?.xAxisField}
                          yAxisField={message.chartConfig?.yAxisField}
                          seriesField={message.chartConfig?.seriesField}
                          colorField={message.chartConfig?.colorField}
                          valueField={message.chartConfig?.valueField}
                          cardTheme={message.chartConfig?.cardTheme}
                          trend={message.chartConfig?.trend}
                          comparisonValue={message.chartConfig?.comparisonValue}
                          gaugeMin={message.chartConfig?.gaugeMin}
                          gaugeMax={message.chartConfig?.gaugeMax}
                          gaugeThresholds={message.chartConfig?.gaugeThresholds}
                          thresholds={message.chartConfig?.thresholds}
                          thresholdDirection={message.chartConfig?.thresholdDirection}
                        />
                        <p className="result-meta">
                          共 {visualizationData.length} 条数据
                        </p>
                      </div>
                    ) : null}
                  </div>
                )}

                {/* 反馈按钮 (如果不是可视化消息) */}
                {message.type === 'assistant' &&
                  message.content &&
                  !message.sqlSuggestion &&
                  !message.queryResult &&
                  !(message.data && message.data.length > 0) && (
                    <div className="feedback-actions">
                      <button
                        onClick={() => setFeedbackMessageId(message.id)}
                        className="feedback-btn positive"
                      >
                        <ThumbsUp className="icon" />
                        有帮助
                      </button>
                      <button
                        onClick={() => setFeedbackMessageId(message.id)}
                        className="feedback-btn negative"
                      >
                        <ThumbsDown className="icon" />
                        反馈
                      </button>
                    </div>
                  )}
              </div>
            );
          })}

          {isProcessing && (
            <div className="message-group">
              <div className="message assistant loading">
                <div className="message-avatar">🤖</div>
                <div className="message-content">
                  <div className="loading-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* 步骤指示器 */}
      <div className="step-indicator">
        <div className={`step ${step === 'input' ? 'active' : ''}`}>输入查询</div>
        <div className={`step ${step === 'clarify' ? 'active' : ''}`}>澄清意图</div>
        <div className={`step ${step === 'execute' ? 'active' : ''}`}>处理中</div>
        <div className={`step ${step === 'results' ? 'active' : ''}`}>查看结果</div>
      </div>

      {/* 输入框 */}
      <footer className="chat-footer">
        <div className="input-area">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
            placeholder="输入您的问题，例如：昨天设备E-001的OEE是多少？"
            disabled={isProcessing}
            rows={3}
            className="input-textarea"
          />
          <button
            onClick={() => handleSendMessage()}
            disabled={!input.trim() || isProcessing}
            className="send-btn"
          >
            {isProcessing ? (
              <Loader2 className="icon loading" />
            ) : (
              <Send className="icon" />
            )}
          </button>
        </div>
      </footer>

      {/* 反馈表单 */}
      {feedbackMessageId && (
        <FeedbackForm
          messageId={feedbackMessageId}
          query={
            messages.find(
              (m) =>
                m.type === 'user' &&
                messages.indexOf(messages.find((msg) => msg.id === feedbackMessageId)!) >
                  messages.indexOf(m)
            )?.content || ''
          }
          response={messages.find((m) => m.id === feedbackMessageId)?.content || ''}
          intent={currentIntent}
          resultData={messages.find((m) => m.id === feedbackMessageId)?.data}
          onClose={() => setFeedbackMessageId(null)}
          onSubmit={() => {
            setFeedbackMessageId(null);
          }}
        />
      )}

      {/* 反馈统计 */}
      <FeedbackStats isOpen={showFeedbackStats} onClose={() => setShowFeedbackStats(false)} />
    </div>
  );
}