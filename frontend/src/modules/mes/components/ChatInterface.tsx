// modules/mes/components/ChatInterface.tsx
import { useState, useRef, useEffect } from 'react';
import { Send, MessageSquare, Loader2, Sparkles, ThumbsUp, ThumbsDown, BarChart3, Save } from 'lucide-react'; // 导入 Save 图标
import { EChartsVisualization } from './EChartsVisualization';
import { FeedbackForm } from './FeedbackForm';
import { FeedbackStats } from './FeedbackStats';
import { useData } from '../../../hooks/useData'; // 导入 useData hook
import { SavedReport } from '../../../data/mockSavedReports'; // 导入 SavedReport 接口
import { ChatHistoryDisplay } from './ChatHistoryDisplay'; // 导入 ChatHistoryDisplay

export interface Message { // 导出 Message 接口，供 AIReportsLeftPanel 使用
  id: string;
  type: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  data?: any;
  visualizationType?: 'bar' | 'line' | 'pie' | 'scatter' | 'card' | 'gauge' | 'table' | 'heatmap' | 'radar' | 'funnel' | 'treemap' | 'boxplot' | 'bar-line-combo'; // 添加新的图表类型
  actions?: string[];
  intent?: any; // 新增：存储意图，方便保存报表时使用
}

const SAMPLE_QUESTIONS = [
  "昨天设备E-001的OEE是多少？",
  "显示最近一周所有设备的OEE趋势",
  "对比A班和B班的生产效率",
  "查看最近30天的质量数据",
  "哪些设备的停机时间最长？",
  "显示设备E-002的良率"
];

interface ChatInterfaceProps {
  setMessages?: (messages: Message[]) => void; // 新增：用于将消息传递给父组件
  setIsProcessing?: (isProcessing: boolean) => void; // 新增：用于将处理状态传递给父组件
  sessionId: string; // 新增：会话ID
}

export function ChatInterface({ setMessages: setParentMessages, setIsProcessing: setParentIsProcessing, sessionId }: ChatInterfaceProps) {
  const { createSavedReport, fetchChatMessages, addChatMessage } = useData(); // 获取 createSavedReport, fetchChatMessages, addChatMessage 函数
  const [messages, setMessages] = useState<Message[]>([]); // 初始为空数组，从数据库加载
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [feedbackMessageId, setFeedbackMessageId] = useState<string | null>(null);
  const [showFeedbackStats, setShowFeedbackStats] = useState(false);
  const [currentIntent, setCurrentIntent] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 加载历史消息
  useEffect(() => {
    const loadMessages = async () => {
      const history = await fetchChatMessages(sessionId);
      if (history.length === 0) {
        // 如果没有历史消息，添加欢迎语
        setMessages([
          {
            id: '1',
            type: 'assistant',
            content: '您好！我是MES数据分析助手。我可以帮您分析生产数据、生成报表、监控设备状态。\n\n您可以用自然语言提问，例如：\n• "显示今天各设备的OEE"\n• "对比A班和B班的生产效率"\n• "查看设备E-001的质量数据"',
            timestamp: new Date()
          }
        ]);
      } else {
        setMessages(history);
      }
    };
    loadMessages();
  }, [fetchChatMessages, sessionId]); // 依赖 sessionId，当 sessionId 变化时重新加载消息

  // 将内部消息状态同步到父组件
  useEffect(() => {
    if (setParentMessages) {
      setParentMessages(messages);
    }
  }, [messages, setParentMessages]);

  // 将内部处理状态同步到父组件
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
      timestamp: new Date()
    };

    // 先更新UI
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsProcessing(true);

    try {
      // 保存用户消息到数据库
      await addChatMessage(sessionId, userMessage);

      const intent = intentRecognizer.recognizeIntent(input);
      setCurrentIntent(intent); // 保存当前意图

      if (intent.clarifications.length > 0) {
        const clarificationMessage: Message = {
          id: (Date.now() + 1).toString(),
          type: 'assistant',
          content: `我理解您想查询相关数据。为了更准确地回答，请确认：\n\n${intent.clarifications.join('\n')}`,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, clarificationMessage]);
        // 保存助手消息到数据库
        await addChatMessage(sessionId, clarificationMessage);
      } else {
        const result = await queryService.executeQuery(intent);

        const messageId = (Date.now() + 1).toString();
        const assistantMessage: Message = {
          id: messageId,
          type: 'assistant',
          content: result.summary,
          timestamp: new Date(),
          data: result.data,
          visualizationType: result.visualizationType,
          actions: result.actions,
          intent: intent // 将意图也保存到消息中
        };

        setMessages(prev => [...prev, assistantMessage]);
        // 保存助手消息到数据库
        await addChatMessage(sessionId, assistantMessage);
      }
    } catch (error) {
      console.error('Processing error:', error);
      const errorMessage: Message = {
        id: Date.now().toString(),
        type: 'assistant',
        content: '抱歉，处理您的请求时出现错误。请重试或换一种方式提问。',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
      // 保存错误消息到数据库
      await addChatMessage(sessionId, errorMessage);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleQuickQuestion = (question: string) => {
    setInput(question);
  };

  const handleSaveReport = async (message: Message) => {
    if (!message.intent || !message.data) {
      alert('无法保存此报表，缺少必要的查询信息或数据。');
      return;
    }

    const reportName = prompt('请输入报表名称：', message.intent.entities.metric ? `${message.intent.entities.metric} ${message.intent.entities.timeRange} 报表` : '自定义报表');
    if (!reportName) return;

    const reportDescription = prompt('请输入报表描述（可选）：', message.content.substring(0, 50) + '...');

    // 映射意图的 metric 到 SavedReport 的 type
    let reportType: SavedReport['type'] = 'generic-report';
    if (message.intent.entities.metric === 'oee') reportType = 'oee-report';
    else if (message.intent.entities.metric === 'yield' || message.intent.entities.metric === 'quality') reportType = 'quality-report';
    else if (message.intent.entities.metric === 'downtime') reportType = 'downtime-report';
    // 可以根据需要添加更多映射

    const newReport: Omit<SavedReport, 'id' | 'icon'> = {
      name: reportName,
      type: reportType,
      description: reportDescription || undefined,
      queryParams: message.intent.entities, // 保存查询参数
      created_by: '当前用户' // 实际应用中应替换为真实的用户ID
    };

    try {
      await createSavedReport(newReport);
      alert('报表已成功保存！');
    } catch (error) {
      alert('保存报表失败！');
      console.error('Error saving report:', error);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gradient-to-br from-slate-50 to-blue-50">
      <header className="bg-white border-b border-gray-200 shadow-sm p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-gradient-to-br from-blue-500 to-indigo-600 p-2 rounded-lg">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">MES数据智能分析系统</h1>
              <p className="text-sm text-gray-500">基于自然语言的生产数据分析</p>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            <button
              onClick={() => setShowFeedbackStats(true)}
              className="px-3 py-1 bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-full text-sm font-medium transition-colors flex items-center gap-1"
            >
              <BarChart3 className="w-4 h-4" />
              反馈分析
            </button>
            <div className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">
              在线
            </div>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-auto p-4">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* 使用 ChatHistoryDisplay 渲染消息 */}
          <ChatHistoryDisplay messages={messages} isProcessing={isProcessing} />

          {/* 消息中的数据可视化和操作按钮 */}
          {messages.map((message) => message.data && message.data.length > 0 && (
            <div key={`data-${message.id}`} className="max-w-4xl mx-auto">
              <div className="mt-4 pt-4 border-t border-gray-200">
                <EChartsVisualization
                  data={message.data}
                  type={message.visualizationType || 'table'}
                />
              </div>
              {message.actions && message.actions.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {message.actions.map((action, idx) => (
                    <button
                      key={idx}
                      className="px-3 py-1 text-xs font-medium bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg transition-colors"
                    >
                      {action === 'export' && '导出报表'}
                      {action === 'drilldown' && '下钻分析'}
                      {action === 'schedule' && '定时生成'}
                      {action === 'spc_analysis' && 'SPC分析'}
                      {action === 'trend_analysis' && '趋势分析'}
                      {action === 'root_cause_analysis' && '根因分析'}
                    </button>
                  ))}
                  {message.type === 'assistant' && message.data && message.data.length > 0 && (
                    <button
                      onClick={() => handleSaveReport(message)}
                      className="px-3 py-1 text-xs font-medium bg-purple-50 hover:bg-purple-100 text-purple-700 rounded-lg transition-colors flex items-center gap-1"
                    >
                      <Save className="w-3 h-3" />
                      保存报表
                    </button>
                  )}
                </div>
              )}
              {message.type === 'assistant' && message.content !== '我理解您想查询相关数据。为了更准确地回答，请确认：' && !message.content.includes('澄清') && (
                <div className="mt-3 flex gap-2 border-t border-gray-200 pt-3">
                  <button
                    onClick={() => setFeedbackMessageId(message.id)}
                    className="px-2 py-1 text-xs font-medium bg-green-50 hover:bg-green-100 text-green-700 rounded transition-colors flex items-center gap-1"
                  >
                    <ThumbsUp className="w-3 h-3" />
                    有帮助
                  </button>
                  <button
                    onClick={() => setFeedbackMessageId(message.id)}
                    className="px-2 py-1 text-xs font-medium bg-red-50 hover:bg-red-100 text-red-700 rounded transition-colors flex items-center gap-1"
                  >
                    <ThumbsDown className="w-3 h-3" />
                    反馈
                  </button>
                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="border-t border-gray-200 bg-white p-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex gap-2 mb-3 overflow-x-auto pb-2">
            {SAMPLE_QUESTIONS.map((question, idx) => (
              <button
                key={idx}
                onClick={() => handleQuickQuestion(question)}
                className="px-4 py-2 text-sm bg-gradient-to-r from-blue-50 to-indigo-50 hover:from-blue-100 hover:to-indigo-100 text-blue-700 rounded-lg whitespace-nowrap transition-all border border-blue-200"
              >
                {question}
              </button>
            ))}
          </div>

          <div className="flex items-center space-x-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
              placeholder="输入您的问题，例如：昨天设备E-001的OEE是多少？"
              disabled={isProcessing}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-500"
            />
            <button
              onClick={handleSendMessage}
              disabled={!input.trim() || isProcessing}
              className="px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-xl hover:from-blue-700 hover:to-indigo-700 disabled:from-gray-300 disabled:to-gray-400 disabled:cursor-not-allowed transition-all flex items-center space-x-2 shadow-lg hover:shadow-xl"
            >
              <Send className="w-5 h-5" />
              <span className="font-medium">发送</span>
            </button>
          </div>

          <p className="text-xs text-gray-500 mt-2 text-center">
            支持自然语言查询，如"显示"、"对比"、"分析"、"查看"等
          </p>
        </div>
      </div>

      {feedbackMessageId && (
        <FeedbackForm
          messageId={feedbackMessageId}
          query={messages.find(m => m.type === 'user' && messages.indexOf(messages.find(msg => msg.id === feedbackMessageId)!) > messages.indexOf(m))?.content || ''}
          response={messages.find(m => m.id === feedbackMessageId)?.content || ''}
          intent={currentIntent}
          resultData={messages.find(m => m.id === feedbackMessageId)?.data}
          onClose={() => setFeedbackMessageId(null)}
          onSubmit={() => {
            setFeedbackMessageId(null);
          }}
        />
      )}

      <FeedbackStats
        isOpen={showFeedbackStats}
        onClose={() => setShowFeedbackStats(false)}
      />
    </div>
  );
}
