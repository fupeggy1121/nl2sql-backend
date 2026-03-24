// modules/mes/components/ChatInterface.tsx
// ⚠ 本组件已停用（页面改用 UnifiedChat）。保留仅供向后兼容类型 / 组件导入。
// Message 类型由 UnifiedChat 提供，此处 re-export 保持所有引用方不变。

import React from 'react';
import type { Message as _Message } from './UnifiedChat/UnifiedChat';
export type { Message } from './UnifiedChat/UnifiedChat';

interface ChatInterfaceProps {
  setMessages?: (messages: _Message[]) => void;
  setIsProcessing?: (isProcessing: boolean) => void;
  sessionId: string;
}

/** @deprecated 请改用 UnifiedChat 组件 */
export function ChatInterface(_props: ChatInterfaceProps): React.ReactElement {
  return <div />;
}
