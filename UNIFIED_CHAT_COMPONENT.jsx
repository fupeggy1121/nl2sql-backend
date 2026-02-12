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
} from 'lucide-react';
import { intentRecognizer } from '../services/intentRecognizer';
import { queryService } from '../services/queryService';
import { nl2sqlApi } from '../services/nl2sqlApi';
import { processNaturalLanguageQuery } from '../services/nl2sqlApi_v2';
import { DataVisualization } from './DataVisualization';
import { FeedbackForm } from './FeedbackForm';
import { FeedbackStats } from './FeedbackStats';
import { useData } from '../../../src/hooks/useData';
import './UnifiedChat.css';

export interface Message {
  id: string;
  type: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  data?: any;
  visualizationType?: 'table' | 'bar' | 'line' | 'pie';
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
}

const SAMPLE_QUESTIONS = [
  '昨天设备E-001的OEE是多少？',
  '显示最近一周所有设备的OEE趋势',
  '对比A班和B班的生产效率',
  '查看最近30天的质量数据',
  '哪些设备的停机时间最长？',
  '显示设备E-002的良率',
];

interface UnifiedChatProps {
  setMessages?: (messages: Message[]) => void;
  setIsProcessing?: (isProcessing: boolean) => void;
  sessionId: string;
  skipDataGeneration?: boolean;
}

export function UnifiedChat({
  setMessages: setParentMessages,
  setIsProcessing: setParentIsProcessing,
  sessionId,
  skipDataGeneration = false,
}: UnifiedChatProps) {
  const { createSavedReport, fetchChatMessages, addChatMessage } = useData();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [feedbackMessageId, setFeedbackMessageId] = useState<string | null>(null);
  const [showFeedbackStats, setShowFeedbackStats] = useState(false);
  const [currentIntent, setCurrentIntent] = useState<any>(null);
  const [dbConnected, setDbConnected] = useState(false);
  const [expandedSqlId, setExpandedSqlId] = useState<string | null>(null);
  const [copiedSqlId, setCopiedSqlId] = useState<string | null>(null);
  // ★ 多轮对话: 保存后端返回的 session_id，追问时回传
  const [backendSessionId, setBackendSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 检查数据库连接
  useEffect(() => {
    const checkConnection = async () => {
      try {
        const result = await nl2sqlApi.checkConnection();
        // 即使 supabase 未连接，只要后端响应就算连接正常
        setDbConnected(result.connected !== false && result.status === 'healthy');
      } catch (error) {
        console.error('Connection check failed:', error);
        setDbConnected(false);
      }
    };
    
    checkConnection();
    const interval = setInterval(checkConnection, 30000);
    return () => clearInterval(interval);
  }, []);

  // 加载历史消息
  useEffect(() => {
    const loadMessages = async () => {
      const history = await fetchChatMessages(sessionId);
      if (history.length === 0) {
        setMessages([
          {
            id: '1',
            type: 'assistant',
            content:
              '您好！我是 MES 数据智能分析助手。我可以帮您分析生产数据、生成报表、监控设备状态。\n\n您可以用自然语言提问，例如：\n• "显示今天各设备的OEE"\n• "对比A班和B班的生产效率"\n• "查看设备E-001的质量数据"\n\n我会自动识别查询需求并生成 SQL，您可以在聊天中直接执行查询。',
            timestamp: new Date(),
          },
        ]);
      } else {
        setMessages(history);
      }
    };
    loadMessages();
  }, [fetchChatMessages, sessionId]);

  // 同步到父组件
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

  const handleSendMessage = async () => {
    if (!input.trim() || isProcessing) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsProcessing(true);

    try {
      await addChatMessage(sessionId, userMessage);

      // ★ 使用新 API（自动多轮对话）: 传入 backendSessionId 启用追问记忆
      const response = await processNaturalLanguageQuery(
        input,
        'execute',
        undefined,
        backendSessionId || undefined  // 首次为 null → 后端生成新 session_id
      );

      // ★ 保存后端返回的 session_id，后续追问自动复用
      if (response.session_id) {
        setBackendSessionId(response.session_id);
      }

      const queryPlan = response.query_plan || {};
      const queryResult = response.query_result;

      const messageId = (Date.now() + 1).toString();
      const assistantMessage: Message = {
        id: messageId,
        type: 'assistant',
        content: queryResult?.summary || queryPlan?.explanation || '查询已完成',
        timestamp: new Date(),
        data: queryResult?.data,
        visualizationType: queryResult?.visualization_type || 'table',
        actions: queryResult?.actions || [],
        intent: queryPlan?.query_intent,
        sqlSuggestion: queryPlan?.generated_sql ? {
          sql: queryPlan.generated_sql,
          originalQuery: input,
        } : undefined,
        queryResult: queryResult ? {
          success: queryResult.success,
          data: queryResult.data,
          rowCount: queryResult.rows_count,
        } : undefined,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      await addChatMessage(sessionId, assistantMessage);
    } catch (error) {
      console.error('Processing error:', error);
      const errorMessage: Message = {
        id: Date.now().toString(),
        type: 'assistant',
        content: '抱歉，处理您的请求时出现错误。请重试或换一种方式提问。',
        timestamp: new Date(),
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

    setIsProcessing(true);

    try {
      const response = await nl2sqlApi.executeNLQuery(message.sqlSuggestion.originalQuery);

      if (response.success) {
        const resultMessage: Message = {
          id: (Date.now() + 2).toString(),
          type: 'assistant',
          content: `✅ 查询成功执行，返回 ${response.count || 0} 条数据`,
          timestamp: new Date(),
          queryResult: {
            success: true,
            data: response.data,
            rowCount: response.count,
          },
          data: response.data,
          visualizationType: 'table',
        };

        setMessages((prev) => [...prev, resultMessage]);
        await addChatMessage(sessionId, resultMessage);
      } else {
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
    if (!message.intent || !message.data) {
      alert('无法保存此报表，缺少必要的查询信息或数据。');
      return;
    }

    const reportName = prompt(
      '请输入报表名称：',
      message.intent.entities.metric
        ? `${message.intent.entities.metric} ${message.intent.entities.timeRange} 报表`
        : '自定义报表'
    );
    if (!reportName) return;

    const reportDescription = prompt(
      '请输入报表描述（可选）：',
      message.content.substring(0, 50) + '...'
    );

    try {
      const newReport = {
        name: reportName,
        type: 'generic-report',
        description: reportDescription || undefined,
        queryParams: message.intent.entities,
        created_by: '当前用户',
      };

      await createSavedReport(newReport);
      alert('报表已成功保存！');
    } catch (error) {
      alert('保存报表失败！');
      console.error('Error saving report:', error);
    }
  };

  const handleQuickQuestion = (question: string) => {
    setInput(question);
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
              <h1>MES 数据智能分析系统</h1>
              <p>AI 聊天 + NL2SQL 查询集成</p>
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

      {/* 消息区域 */}
      <div className="messages-area">
        <div className="messages-container">
          {messages.map((message) => (
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

              {/* 查询结果展示 */}
              {message.queryResult && (
                <div className={`result-card ${message.queryResult.success ? 'success' : 'error'}`}>
                  <div className="result-header">
                    <h4>
                      {message.queryResult.success ? '✅ 查询结果' : '❌ 查询失败'}
                    </h4>
                    {message.queryResult.success && message.queryResult.data && (
                      <button
                        onClick={() => handleExportResults(message.queryResult.data)}
                        className="export-btn"
                      >
                        <Download className="icon" />
                        导出
                      </button>
                    )}
                  </div>
                  {message.queryResult.success ? (
                    <div className="result-body">
                      {message.queryResult.data && message.queryResult.data.length > 0 ? (
                        <>
                          <DataVisualization
                            data={message.queryResult.data}
                            type={message.visualizationType || 'table'}
                          />
                          <p className="result-meta">
                            共 {message.queryResult.rowCount || message.queryResult.data.length} 条数据
                          </p>
                        </>
                      ) : (
                        <p className="no-data">查询返回 0 条数据</p>
                      )}
                    </div>
                  ) : (
                    <div className="error-body">
                      <p>{message.queryResult.error}</p>
                    </div>
                  )}
                </div>
              )}

              {/* 数据可视化 */}
              {message.data &&
                message.data.length > 0 &&
                !message.queryResult &&
                message.type === 'assistant' && (
                  <div className="visualization-card">
                    <DataVisualization
                      data={message.data}
                      type={message.visualizationType || 'table'}
                    />
                    <div className="visualization-actions">
                      {message.actions &&
                        message.actions.length > 0 &&
                        message.actions.map((action, idx) => (
                          <button key={idx} className="action-btn">
                            {action === 'export' && '📥 导出报表'}
                            {action === 'drilldown' && '🔍 下钻分析'}
                            {action === 'schedule' && '⏱️ 定时生成'}
                            {action === 'spc_analysis' && '📊 SPC 分析'}
                            {action === 'trend_analysis' && '📈 趋势分析'}
                            {action === 'root_cause_analysis' && '🔎 根因分析'}
                          </button>
                        ))}
                      {message.type === 'assistant' &&
                        message.data &&
                        message.data.length > 0 && (
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

              {/* 反馈按钮 */}
              {message.type === 'assistant' &&
                message.content &&
                !message.content.includes('澄清') &&
                !message.content.includes('为了更准确') && (
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
          ))}

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

      {/* 快速问题建议 */}
      <div className="quick-questions">
        <div className="quick-questions-container">
          {SAMPLE_QUESTIONS.map((question, idx) => (
            <button
              key={idx}
              onClick={() => handleQuickQuestion(question)}
              className="quick-btn"
              disabled={isProcessing}
            >
              {question}
            </button>
          ))}
        </div>
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
            onClick={handleSendMessage}
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
        <p className="input-hint">
          💡 支持自然语言查询 | Shift+Enter 换行 | Enter 发送
        </p>
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
