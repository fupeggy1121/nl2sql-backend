// src/components/Reports/AIReportsLeftPanel.tsx
import React from 'react';
import { SavedReportsSidebar } from './SavedReportsSidebar';
import { ChatHistoryDisplay } from '../../modules/mes/components/ChatHistoryDisplay'; // Import ChatHistoryDisplay
import { Message } from '../../modules/mes/components/ChatInterface'; // Import Message interface
import { Sparkles, BarChart, Plus, MessageSquare } from 'lucide-react'; // 导入 Plus 和 MessageSquare 图标

// Define ChatSession interface (consistent with App.tsx and LeftSidebar.tsx)
interface ChatSession {
  id: string;
  name: string;
}

interface AIReportsLeftPanelProps {
  activeReportId: string;
  onSelectReport: (reportId: string) => void;
  // Props for ChatHistoryDisplay (these are no longer directly used here, but kept for interface consistency if needed elsewhere)
  chatMessages: Message[];
  isChatProcessing: boolean;
  currentSessionId: string; // Now required
  startNewConversation: () => void; // Now required
  chatSessions: ChatSession[]; // New prop
  onSelectChatSession: (sessionId: string) => void; // New prop
}

export const AIReportsLeftPanel: React.FC<AIReportsLeftPanelProps> = ({
  activeReportId,
  onSelectReport,
  // chatMessages, // No longer directly used here
  // isChatProcessing, // No longer directly used here
  currentSessionId,
  startNewConversation,
  chatSessions, // Destructure new prop
  onSelectChatSession, // Destructure new prop
}) => {
  return (
    <div className="w-80 bg-white shadow-sm border-r border-gray-200 h-full flex flex-col">
      {/* 上半部分：对话历史记录列表 */}
      <div className="h-96 flex flex-col p-4 border-b border-gray-200 flex-shrink">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center">
            <Sparkles className="w-5 h-5 text-blue-600 mr-2" />
            <h3 className="text-lg font-semibold text-gray-900">对话历史</h3>
          </div>
          {/* 新增：创建新对话按钮 */}
          <button
            onClick={startNewConversation}
            className="p-1 rounded-full hover:bg-gray-100 text-gray-600 hover:text-blue-600 transition-colors"
            title="开始新对话"
          >
            <Plus className="w-5 h-5" />
          </button>
        </div>
        {/* List of chat sessions */}
        <div className=" overflow-y-auto space-y-1">
          {chatSessions.length === 0 ? (
            <div className="text-center py-4 text-gray-500 text-sm">
              暂无对话历史。
              <br />
              点击上方 "+" 开始新对话。
            </div>
          ) : (
            chatSessions.map(session => (
              <button
                key={session.id}
                onClick={() => onSelectChatSession(session.id)}
                className={`
                  w-full flex items-center px-3 py-2 rounded-md text-sm font-medium
                  transition-colors duration-200
                  ${
                    currentSessionId === session.id
                      ? 'bg-blue-50 text-blue-700 border-r-2 border-blue-700'
                      : 'text-gray-700 hover:bg-gray-100 hover:text-blue-600'
                  }
                `}
              >
                <MessageSquare className={`w-4 h-4 mr-3 ${currentSessionId === session.id ? 'text-blue-700' : 'text-gray-500'}`} />
                <span className="text-left truncate">{session.name}</span>
              </button>
            ))
          )}
        </div>
      </div>

      {/* 下半部分：保存的报表列表 */}
      <div className="h-1/2 p-4 overflow-y-auto">
        <div className="flex items-center mb-3">
          <BarChart className="w-5 h-5 text-purple-600 mr-2" />
          <h3 className="text-lg font-semibold text-gray-900">保存的报表</h3>
        </div>
        <SavedReportsSidebar activeReportId={activeReportId} onSelectReport={onSelectReport} />
      </div>
    </div>
  );
};
