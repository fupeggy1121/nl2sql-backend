// modules/mes/MESPage.tsx
import React, { useState, useEffect } from 'react';
import { ChatInterface, Message } from './components/ChatInterface'; // 导入 Message 接口
import { dataGenerator } from './services/dataGenerator';
import { Loader2, AlertCircle } from 'lucide-react';
import { UnifiedChat } from './components/UnifiedChat/UnifiedChat';

interface MESPageProps {
  skipDataGeneration?: boolean; // 可选：跳过数据生成步骤
  setMessages?: (messages: Message[]) => void; // 新增：用于将消息传递给父组件
  setIsProcessing?: (isProcessing: boolean) => void; // 新增：用于将处理状态传递给父组件
  sessionId: string; // 新增：接收会话ID
}

export const MESPage: React.FC<MESPageProps> = ({
  skipDataGeneration = false,
  setMessages,
  setIsProcessing,
  sessionId, // 接收 sessionId
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'chat' | 'nl2sql'>('chat'); // 新增：标签页状态

  useEffect(() => {
    const initializeMES = async () => {
      if (skipDataGeneration) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);
        await dataGenerator.generateAllData();
        setLoading(false);
      } catch (err) {
        console.error('Failed to generate MES initial data:', err);
        setError('MES 模块初始化数据失败。请检查 Supabase 配置或网络连接。');
        setLoading(false);
      }
    };

    initializeMES();
  }, [skipDataGeneration]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[500px] bg-gray-50">
        <div className="flex flex-col items-center space-y-4 p-6 bg-white rounded-lg shadow-md">
          <Loader2 className="w-10 h-10 animate-spin text-blue-600" />
          <p className="text-lg font-medium text-gray-700">正在初始化 MES 模块数据...</p>
          <p className="text-sm text-gray-500">这可能需要一些时间，请稍候。</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[500px] bg-red-50">
        <div className="flex flex-col items-center space-y-4 p-6 bg-white rounded-lg shadow-md border border-red-300">
          <AlertCircle className="w-10 h-10 text-red-600" />
          <p className="text-lg font-medium text-red-800">错误：MES 模块加载失败</p>
          <p className="text-sm text-gray-700">{error}</p>
          <p className="text-sm text-gray-500">请联系管理员或检查控制台获取更多信息。</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
      <UnifiedChat
        sessionId={sessionId}
        setMessages={setMessages}
        setIsProcessing={setIsProcessing}
        skipDataGeneration={skipDataGeneration}
      />
    </div>
  );
};