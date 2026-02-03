# 前端 API 调用错误修复指南

## 问题症状

前端显示"后端服务已连接"，但查询时报错：
```
TypeError: Failed to fetch
at Object.explainQuery (/src/services/nl2sqlApi.js:56:15)
```

## 根本原因

前端的 UnifiedChat 组件使用的是旧的 API 服务文件或调用了错误的端点。

## 解决方案

### 方案 1: 更新 API 导入 (推荐)

如果前端在使用旧的 `nl2sqlApi.js`，需要改为使用 `nl2sqlApi_v2.js`：

**文件**: `src/services/UnifiedChat.tsx` 或 `modules/mes/components/UnifiedChat/UnifiedChat.tsx`

**修改**:
```typescript
// ❌ 旧的导入
import { explainQuery } from '../../services/nl2sqlApi';

// ✅ 新的导入
import { 
  explainQuery,
  processNaturalLanguageQuery,
  executeQuery,
  suggestVariants,
  validateSQL
} from '../../services/nl2sqlApi_v2';
```

### 方案 2: 检查 API 端点

如果前端仍然在使用旧的端点路径，需要更新：

**错误的端点**:
```javascript
// ❌ 这些端点不存在
fetch('/api/query/explain-query')
fetch('/api/explain-query')
fetch('/api/sql-generation')
```

**正确的端点**:
```javascript
// ✅ 使用统一查询 API
fetch('http://localhost:8000/api/query/unified/explain', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ natural_language: '查询OEE' })
})

// ✅ 或使用 API 服务函数
import { explainQuery } from './services/nl2sqlApi_v2';
const response = await explainQuery('查询OEE');
```

### 方案 3: 检查环境变量

确保前端设置了正确的 API 基础 URL：

**检查 `.env` 或 `.env.frontend`**:
```env
# ✅ 正确的配置
VITE_API_BASE_URL=http://localhost:8000/api/query/unified
REACT_APP_API_URL=http://localhost:8000
```

**在代码中使用**:
```javascript
const API_BASE = process.env.VITE_API_BASE_URL || 'http://localhost:8000/api/query/unified';

// 使用例子
const response = await fetch(`${API_BASE}/explain`, {
  method: 'POST',
  body: JSON.stringify({ natural_language: query })
});
```

## 正确的 API 调用示例

### 1. 使用 API 服务函数 (推荐)

```typescript
import { explainQuery, processNaturalLanguageQuery } from './services/nl2sqlApi_v2';

// 获取 SQL 解释
async function handleExplain(query: string) {
  try {
    const response = await explainQuery(query);
    if (response.success) {
      console.log('Generated SQL:', response.query_plan.generated_sql);
    } else {
      console.error('Error:', response.error);
    }
  } catch (error) {
    console.error('Failed to fetch:', error);
  }
}

// 处理自然语言查询 (完整流程)
async function handleQuery(query: string) {
  try {
    const response = await processNaturalLanguageQuery(
      query,
      'explain'  // 或 'execute'
    );
    console.log(response);
  } catch (error) {
    console.error('Failed:', error);
  }
}
```

### 2. 直接调用 API 端点

```typescript
async function explainQuery(naturalLanguage: string) {
  const response = await fetch(
    'http://localhost:8000/api/query/unified/explain',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ natural_language: naturalLanguage })
    }
  );
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  
  return await response.json();
}
```

## 完整的 UnifiedChat 组件修复

如果您的 UnifiedChat 组件需要更新，以下是关键部分：

```typescript
import React, { useState } from 'react';
import {
  explainQuery,
  processNaturalLanguageQuery,
  executeQuery
} from '../../services/nl2sqlApi_v2';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sql?: string;
}

export function UnifiedChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSendMessage = async () => {
    if (!input.trim()) return;

    try {
      setLoading(true);
      
      // 1. 添加用户消息
      setMessages(prev => [...prev, { role: 'user', content: input }]);

      // 2. 调用后端 API
      const response = await processNaturalLanguageQuery(
        input,
        'explain'  // 先只解释，不执行
      );

      if (response.success) {
        const plan = response.query_plan;
        
        // 3. 处理澄清问题
        if (plan.requires_clarification) {
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: plan.clarification_message || '需要更多信息来精确处理您的查询'
          }]);
        } else if (plan.generated_sql) {
          // 4. 显示生成的 SQL
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: '已生成 SQL，请审核',
            sql: plan.generated_sql
          }]);
        }
      } else {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: `错误: ${response.error}`
        }]);
      }
    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Failed to fetch: ${error.message}`
      }]);
    } finally {
      setLoading(false);
      setInput('');
    }
  };

  return (
    <div className="unified-chat">
      <div className="messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            <p>{msg.content}</p>
            {msg.sql && <pre className="sql">{msg.sql}</pre>}
          </div>
        ))}
      </div>
      <div className="input-area">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
          disabled={loading}
          placeholder="输入查询..."
        />
        <button onClick={handleSendMessage} disabled={loading}>
          发送
        </button>
      </div>
    </div>
  );
}
```

## 调试步骤

### 1. 检查浏览器控制台

打开浏览器开发者工具 (F12)：

1. 切换到 **Network** 标签
2. 输入查询
3. 检查网络请求：
   - 应该看到 POST 请求到 `http://localhost:8000/api/query/unified/explain`
   - 或其他统一查询端点
   - 响应应该是 200 OK 和 JSON 数据

### 2. 检查 API 响应

```bash
# 在终端中测试
curl -X POST http://localhost:8000/api/query/unified/explain \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "查询OEE"}'

# 应该返回：
{
  "success": true,
  "query_plan": {...}
}
```

### 3. 检查 CORS 错误

如果看到 CORS 相关错误，确保：

1. 后端已启动且配置了 CORS
2. 前端的 API 地址与后端监听的地址一致
3. 浏览器没有阻止跨域请求

## 常见错误和解决

| 错误 | 原因 | 解决 |
|-----|------|------|
| `TypeError: Failed to fetch` | 端点不存在或网络错误 | 检查 API 端点路径是否正确 |
| `CORS error` | 跨域请求被阻止 | 确保后端配置了 CORS |
| `404 Not Found` | 端点不存在 | 检查是否使用了统一查询 API 路由 `/api/query/unified/*` |
| `500 Internal Server Error` | 服务器错误 | 检查后端日志 |

## 确认修复成功

1. ✅ 前端可以正常输入查询
2. ✅ 网络请求返回 200 OK
3. ✅ 看到澄清问题或生成的 SQL
4. ✅ 可以执行查询并看到结果

---

如果问题仍未解决，请检查：
1. 后端是否正在运行 (`python run.py`)
2. 前端和后端的 API URL 是否匹配
3. 浏览器控制台中的具体错误信息

