// modules/mes/components/ChatHistoryDisplay.tsx
import React, { useRef, useEffect } from 'react';
import { MessageSquare, Loader2 } from 'lucide-react';

interface Message {
  id: string;
  type: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  data?: any;
  visualizationType?: 'bar' | 'line' | 'pie' | 'scatter' | 'card' | 'gauge' | 'table' | 'heatmap' | 'radar' | 'funnel' | 'treemap';
  actions?: string[];
  intent?: any;
}

interface ChatHistoryDisplayProps {
  messages: Message[];
  isProcessing: boolean;
  isSidebarView?: boolean; // 新增属性：是否在侧边栏视图
}

export const ChatHistoryDisplay: React.FC<ChatHistoryDisplayProps> = ({ messages, isProcessing, isSidebarView }) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 辅助函数：截断消息内容
  const truncateContent = (text: string, maxLength: number = 80) => {
    if (text.length <= maxLength) {
      return text;
    }
    return text.substring(0, maxLength) + '...';
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 bg-gray-50 rounded-lg shadow-inner">
      <div className="space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`flex items-start space-x-2 max-w-full ${message.type === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}>
              {/* 条件渲染图标 */}
              {!isSidebarView && (
                <div className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                  message.type === 'user'
                    ? 'bg-gradient-to-br from-green-400 to-green-600 text-white'
                    : 'bg-gradient-to-br from-blue-500 to-indigo-600 text-white'
                }`}>
                  {message.type === 'user' ? 'U' : <MessageSquare className="w-3 h-3" />}
                </div>
              )}

              <div className={`rounded-lg px-3 py-2 text-sm ${
                message.type === 'user'
                  ? 'bg-gradient-to-br from-green-500 to-green-600 text-white'
                  : 'bg-white border border-gray-200 text-gray-800 shadow-sm'
              }`}>
                <p className="whitespace-pre-wrap leading-snug">
                  {isSidebarView ? truncateContent(message.content) : message.content}
                </p>
                <p className="text-xs text-gray-400 mt-1 text-right">
                  {message.timestamp.toLocaleTimeString('zh-CN', {
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </p>
              </div>
            </div>
          </div>
        ))}

        {isProcessing && (
          <div className="flex justify-start">
            <div className="flex items-start space-x-2">
              {/* 条件渲染图标 */}
              {!isSidebarView && (
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white">
                  <MessageSquare className="w-3 h-3" />
                </div>
              )}
              <div className="bg-white border border-gray-200 rounded-lg px-3 py-2 shadow-sm">
                <div className="flex items-center space-x-1">
                  <Loader2 className="w-3 h-3 animate-spin text-blue-600" />
                  <span className="text-xs text-gray-600">分析中...</span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>
    </div>
  );
};
