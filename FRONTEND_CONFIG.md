# 前端配置指南

## Bolt.new 前端连接配置

### 后端 API 地址
```
https://nl2sql-backend-amok.onrender.com/api/query
```

---

## 1. 更新 API 客户端配置

在 **Bolt.new** 项目中，编辑 `src/services/nl2sqlApi.js`：

```javascript
// src/services/nl2sqlApi.js

// 更新 API_BASE_URL 为：
const API_BASE_URL = 'https://nl2sql-backend-amok.onrender.com/api/query';

// 或者使用环境变量（推荐）：
const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://nl2sql-backend-amok.onrender.com/api/query';

// 健康检查
export const checkHealth = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    return await response.json();
  } catch (error) {
    console.error('Health check failed:', error);
    return { status: 'error', message: error.message };
  }
};

// NL 转 SQL（无数据库执行）
export const convertNLToSQL = async (naturalLanguage) => {
  try {
    const response = await fetch(`${API_BASE_URL}/nl-to-sql`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ natural_language: naturalLanguage }),
    });
    return await response.json();
  } catch (error) {
    return { success: false, error: error.message };
  }
};

// NL 直接执行查询（本地数据库）
export const executeNLQuery = async (naturalLanguage) => {
  try {
    const response = await fetch(`${API_BASE_URL}/nl-execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ natural_language: naturalLanguage }),
    });
    return await response.json();
  } catch (error) {
    return { success: false, error: error.message };
  }
};

// NL 执行 Supabase 查询（需要配置数据库凭证）
export const executeSupabaseQuery = async (naturalLanguage) => {
  try {
    const response = await fetch(`${API_BASE_URL}/nl-execute-supabase`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ natural_language: naturalLanguage }),
    });
    return await response.json();
  } catch (error) {
    return { success: false, error: error.message };
  }
};

// 获取 Supabase Schema
export const getSupabaseSchema = async (tableName = null) => {
  try {
    let url = `${API_BASE_URL}/supabase/schema`;
    if (tableName) url += `?table=${tableName}`;
    const response = await fetch(url);
    return await response.json();
  } catch (error) {
    return { success: false, error: error.message };
  }
};

// 检查 Supabase 连接
export const checkSupabaseConnection = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/supabase/connection`);
    return await response.json();
  } catch (error) {
    return { success: false, error: error.message };
  }
};
```

---

## 2. 在 React 组件中使用

在你的组件中导入并使用这些函数：

```javascript
// src/components/NL2SQL/NL2SQLQueryModule.jsx

import React, { useState, useEffect } from 'react';
import * as nlApi from '../../services/nl2sqlApi';

export default function NL2SQLQueryModule() {
  const [naturalLanguage, setNaturalLanguage] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isConnected, setIsConnected] = useState(false);

  // 检查后端连接
  useEffect(() => {
    const checkConnection = async () => {
      const health = await nlApi.checkHealth();
      setIsConnected(health.status === 'healthy');
    };
    checkConnection();
  }, []);

  // 处理查询提交
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!naturalLanguage.trim()) {
      setError('请输入自然语言查询');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      // 方式1: 仅转换为 SQL（推荐先试这个）
      const converted = await nlApi.convertNLToSQL(naturalLanguage);
      
      if (converted.success) {
        setResult({
          sql: converted.sql,
          message: '转换成功！'
        });
      } else {
        setError(converted.error || '转换失败');
      }
    } catch (err) {
      setError('请求失败: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="nl2sql-module">
      <div className="connection-status">
        {isConnected ? (
          <span className="status-connected">✅ 已连接</span>
        ) : (
          <span className="status-disconnected">❌ 未连接</span>
        )}
      </div>

      <form onSubmit={handleSubmit}>
        <textarea
          value={naturalLanguage}
          onChange={(e) => setNaturalLanguage(e.target.value)}
          placeholder="输入自然语言查询，例如：查询所有用户的名称和邮箱"
          rows="4"
        />
        <button type="submit" disabled={loading || !isConnected}>
          {loading ? '处理中...' : '转换为 SQL'}
        </button>
      </form>

      {error && <div className="error">{error}</div>}
      
      {result && (
        <div className="result">
          <h3>生成的 SQL：</h3>
          <pre>{result.sql}</pre>
          <p>{result.message}</p>
        </div>
      )}
    </div>
  );
}
```

---

## 3. 测试端点

### 在浏览器开发者工具中测试：

```javascript
// 测试健康检查
fetch('https://nl2sql-backend-amok.onrender.com/api/query/health')
  .then(r => r.json())
  .then(console.log);

// 测试 NL 转 SQL
fetch('https://nl2sql-backend-amok.onrender.com/api/query/nl-to-sql', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ natural_language: '查询所有用户' })
})
  .then(r => r.json())
  .then(console.log);
```

---

## 4. 环境变量配置（可选）

在 Bolt.new 项目中创建 `.env.local`：

```
REACT_APP_API_URL=https://nl2sql-backend-amok.onrender.com/api/query
REACT_APP_ENV=production
```

然后在代码中使用：
```javascript
const API_BASE_URL = process.env.REACT_APP_API_URL;
```

---

## 5. 可用的 API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/nl-to-sql` | POST | 将自然语言转换为 SQL |
| `/nl-execute` | POST | 转换并执行查询（本地） |
| `/nl-execute-supabase` | POST | 转换并执行查询（Supabase） |
| `/supabase/schema` | GET | 获取数据库 Schema |
| `/supabase/connection` | GET | 检查 Supabase 连接状态 |

---

## 故障排查

### 问题 1: CORS 错误
**解决**: 后端已配置 CORS，确保从正确的域名访问

### 问题 2: 504 Gateway Timeout
**解决**: Render 免费层可能需要预热，稍等几秒后重试

### 问题 3: 连接拒绝
**解决**: 确认后端正在运行（检查 Render 仪表板）

---

## 下一步

1. ✅ 在 Bolt.new 中更新 API 地址
2. ✅ 测试 `/health` 端点
3. ✅ 测试 `/nl-to-sql` 功能
4. 📋 如需启用数据库查询，配置 Supabase 凭证
