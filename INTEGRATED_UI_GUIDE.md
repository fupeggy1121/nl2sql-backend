# NL2SQL 与 AI 聊天集成方案

## 推荐架构：统一对话界面

不使用分开的标签页，而是将 NL2SQL 查询功能集成到 AI 聊天中。

---

## 方案 A：聊天中的内联 NL2SQL（推荐）

用户可以在聊天中问问题，AI 识别出数据库查询需求时：
1. 显示提议的 SQL
2. 用户点击"执行查询"按钮
3. 结果以卡片形式插入到聊天中

### 文件结构

```
src/components/
├── UnifiedChat/
│   ├── UnifiedChat.jsx          # 主组件（集成聊天 + NL2SQL）
│   ├── UnifiedChat.css
│   ├── ChatMessage.jsx          # 单个消息组件
│   ├── QueryCard.jsx            # NL2SQL 查询结果卡片
│   └── QuerySuggestion.jsx      # SQL 建议组件
└── services/
    ├── chatApi.js               # AI 聊天 API
    └── nl2sqlApi.js             # NL2SQL API
```

---

## 方案 B：侧边栏查询助手

保持聊天在主区域，右侧边栏显示 NL2SQL 查询工具：

```
┌─────────────────────────────────────┬──────────────┐
│                                     │              │
│         AI 聊天界面                  │ NL2SQL 查询  │
│                                     │   助手       │
│  用户：查询用户数据                  │              │
│  AI：我来帮你构建查询...            │ 输入：查询   │
│                                     │ SQL: ...     │
│                                     │ 执行 ▶        │
└─────────────────────────────────────┴──────────────┘
```

---

## 代码实现示例

### 方案 A 完整代码

#### `src/components/UnifiedChat/UnifiedChat.jsx`

```javascript
import React, { useState, useRef, useEffect } from 'react';
import * as chatApi from '../../services/chatApi';
import * as nlApi from '../../services/nl2sqlApi';
import ChatMessage from './ChatMessage';
import QueryCard from './QueryCard';
import './UnifiedChat.css';

export default function UnifiedChat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // 自动滚动到最新消息
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 处理用户消息
  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    // 添加用户消息
    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: input,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      // 1. 调用 AI 聊天获取响应
      const aiResponse = await chatApi.sendMessage(input);

      // 2. 检查 AI 响应中是否包含数据库查询需求
      const sqlMatch = aiResponse.content.match(/SQL:|```sql\n(.*?)\n```/i);
      
      if (sqlMatch) {
        // 3. 提取 SQL 并添加查询建议
        const sql = sqlMatch[1] || sqlMatch[0];
        
        const aiMessage = {
          id: Date.now() + 1,
          type: 'ai',
          content: aiResponse.content,
          sqlSuggestion: {
            sql: sql,
            originalQuery: input,
          },
          timestamp: new Date(),
        };
        
        setMessages((prev) => [...prev, aiMessage]);
      } else {
        // 4. 普通 AI 响应
        const aiMessage = {
          id: Date.now() + 1,
          type: 'ai',
          content: aiResponse.content,
          timestamp: new Date(),
        };
        
        setMessages((prev) => [...prev, aiMessage]);
      }
    } catch (error) {
      // 错误消息
      const errorMessage = {
        id: Date.now() + 1,
        type: 'error',
        content: '请求失败: ' + error.message,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  // 执行 NL2SQL 查询
  const handleExecuteQuery = async (sql) => {
    setLoading(true);

    try {
      // 注：需要配置 Supabase 凭证才能真正执行
      const result = await nlApi.convertNLToSQL(sql);
      
      const queryMessage = {
        id: Date.now(),
        type: 'query-result',
        content: 'SQL 执行结果',
        queryResult: result,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, queryMessage]);
    } catch (error) {
      const errorMessage = {
        id: Date.now(),
        type: 'error',
        content: '查询执行失败: ' + error.message,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="unified-chat">
      <div className="chat-header">
        <h1>AI 数据查询助手</h1>
        <p>自然语言提问，AI 帮你生成和执行 SQL 查询</p>
      </div>

      <div className="messages-container">
        {messages.map((msg) => (
          <div key={msg.id}>
            {msg.type === 'user' && <ChatMessage message={msg} />}
            
            {msg.type === 'ai' && (
              <>
                <ChatMessage message={msg} />
                {msg.sqlSuggestion && (
                  <QueryCard
                    sql={msg.sqlSuggestion.sql}
                    onExecute={() => handleExecuteQuery(msg.sqlSuggestion.sql)}
                  />
                )}
              </>
            )}
            
            {msg.type === 'query-result' && (
              <QueryCard queryResult={msg.queryResult} />
            )}
            
            {msg.type === 'error' && (
              <div className="message error-message">
                <p>{msg.content}</p>
              </div>
            )}
          </div>
        ))}
        
        {loading && (
          <div className="message ai-message loading">
            <p>处理中...</p>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSendMessage} className="input-area">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="问我任何关于数据的问题... 例如：查询今年的销售数据"
          disabled={loading}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSendMessage(e);
            }
          }}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          {loading ? '处理中...' : '发送'}
        </button>
      </form>
    </div>
  );
}
```

#### `src/components/UnifiedChat/ChatMessage.jsx`

```javascript
import React from 'react';

export default function ChatMessage({ message }) {
  return (
    <div className={`message ${message.type}-message`}>
      <div className="message-avatar">
        {message.type === 'user' ? '👤' : '🤖'}
      </div>
      <div className="message-content">
        <p>{message.content}</p>
        <span className="message-time">
          {message.timestamp?.toLocaleTimeString()}
        </span>
      </div>
    </div>
  );
}
```

#### `src/components/UnifiedChat/QueryCard.jsx`

```javascript
import React, { useState } from 'react';

export default function QueryCard({ sql, onExecute, queryResult }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(sql || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (queryResult) {
    return (
      <div className="query-card result">
        <div className="card-header">
          <h4>查询结果</h4>
        </div>
        <div className="card-body">
          {queryResult.success ? (
            <>
              <p>✅ 查询成功</p>
              {queryResult.data && (
                <pre>{JSON.stringify(queryResult.data, null, 2)}</pre>
              )}
            </>
          ) : (
            <p className="error">❌ {queryResult.error}</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="query-card">
      <div className="card-header">
        <h4>建议的 SQL 查询</h4>
        <button
          type="button"
          className="btn-copy"
          onClick={handleCopy}
          title="复制到剪贴板"
        >
          {copied ? '✅ 已复制' : '📋 复制'}
        </button>
      </div>
      <div className="card-body">
        <pre className="sql-code">{sql}</pre>
      </div>
      <div className="card-footer">
        <button
          type="button"
          className="btn-execute"
          onClick={onExecute}
        >
          ▶ 执行查询
        </button>
      </div>
    </div>
  );
}
```

#### `src/components/UnifiedChat/UnifiedChat.css`

```css
.unified-chat {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
}

.chat-header {
  padding: 20px;
  color: white;
  text-align: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.chat-header h1 {
  margin: 0 0 5px 0;
  font-size: 24px;
}

.chat-header p {
  margin: 0;
  opacity: 0.9;
  font-size: 14px;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.message {
  display: flex;
  gap: 12px;
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.user-message {
  justify-content: flex-end;
}

.user-message .message-avatar {
  order: 2;
}

.user-message .message-content {
  order: 1;
  background: #667eea;
  color: white;
}

.ai-message .message-content {
  background: white;
  color: #333;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.message-avatar {
  font-size: 24px;
  min-width: 32px;
  text-align: center;
}

.message-content {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
}

.message-content p {
  margin: 0 0 8px 0;
  line-height: 1.5;
}

.message-time {
  font-size: 12px;
  opacity: 0.6;
}

.query-card {
  background: white;
  border-radius: 12px;
  border-left: 4px solid #667eea;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-left: 48px;
}

.query-card.result {
  border-left-color: #48bb78;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f7fafc;
  border-bottom: 1px solid #e2e8f0;
}

.card-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.btn-copy {
  background: none;
  border: 1px solid #cbd5e0;
  padding: 4px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.btn-copy:hover {
  background: #edf2f7;
}

.card-body {
  padding: 16px;
  max-height: 300px;
  overflow-y: auto;
}

.sql-code {
  margin: 0;
  padding: 12px;
  background: #2d3748;
  color: #48bb78;
  border-radius: 6px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  overflow-x: auto;
}

.card-footer {
  padding: 12px 16px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  gap: 8px;
}

.btn-execute {
  flex: 1;
  background: #667eea;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  transition: background 0.2s;
}

.btn-execute:hover {
  background: #5568d3;
}

.btn-execute:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-area {
  padding: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  gap: 10px;
}

.input-area textarea {
  flex: 1;
  padding: 12px;
  border: none;
  border-radius: 8px;
  font-family: inherit;
  font-size: 14px;
  resize: none;
  max-height: 120px;
}

.input-area button {
  background: white;
  color: #667eea;
  border: none;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.input-area button:hover:not(:disabled) {
  background: #f7fafc;
  transform: translateY(-2px);
}

.input-area button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-message {
  color: #e53e3e;
  background: #fed7d7;
  border-left: 4px solid #e53e3e;
}

.loading {
  opacity: 0.7;
}
```

---

## 集成步骤

### 1. 在 Bolt.new 中创建新组件
```bash
# 创建文件
src/components/UnifiedChat/UnifiedChat.jsx
src/components/UnifiedChat/ChatMessage.jsx
src/components/UnifiedChat/QueryCard.jsx
src/components/UnifiedChat/UnifiedChat.css
```

### 2. 更新 App.jsx
```javascript
import UnifiedChat from './components/UnifiedChat/UnifiedChat';

function App() {
  return <UnifiedChat />;
}
```

### 3. 确保 API 服务已配置
```javascript
// src/services/chatApi.js
const API_BASE = 'https://your-ai-api.com';

export const sendMessage = async (message) => {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
  return response.json();
};
```

---

## 功能流程

```
用户: "查询今年的销售数据"
  ↓
AI: "我来帮你生成查询..."
  ↓
[显示 SQL 建议卡片]
  ↓
用户: 点击"执行查询"
  ↓
[执行 SQL，显示结果]
```

---

## 优势

✅ **统一体验** - 不需要在标签页间切换
✅ **上下文感知** - AI 可以参考之前的对话
✅ **即时反馈** - SQL 建议和执行结果立即显示
✅ **更好的交互** - 自然的对话流程

需要我帮你调整这个方案吗？
