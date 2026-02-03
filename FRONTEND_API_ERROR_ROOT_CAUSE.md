# 前端 API 错误 - 问题分析和解决方案

## 🔍 问题分析

### 症状
- 前端显示"后端服务已连接" ✅
- 输入查询后报错 ❌
- 错误信息: `TypeError: Failed to fetch`
- 错误来自: `/src/services/nl2sqlApi.js:56:15`

### 诊断结果

**后端状态**: ✅ **完全正常**
```
✅ 后端服务: 运行中 (http://localhost:8000)
✅ OPTIONS 预检: 返回 200 OK
✅ /explain 端点: 返回有效响应
✅ /process 端点: 返回有效响应
✅ /query-recommendations 端点: 返回有效响应
✅ CORS 配置: 正确
```

**问题根源**: 🚨 **前端代码问题**

前端的 UnifiedChat 组件在使用**错误的 API 调用方式**：

1. **导入了错误的文件**
   - ❌ 使用: `/src/services/nl2sqlApi.js` (旧文件)
   - ✅ 应该: `/src/services/nl2sqlApi_v2.js` (新文件)

2. **调用了错误的端点**
   - ❌ 调用: `/api/query/explain-query` (不存在)
   - ✅ 应该: `/api/query/unified/explain` (正确端点)

3. **前端 API URL 配置错误**
   - ❌ 配置: `http://localhost:8000/api` 
   - ✅ 应该: `http://localhost:8000/api/query/unified`

## 📋 解决方案

### 步骤 1: 检查您的前端文件结构

前端应该有这个文件:
```
src/
├── services/
│   └── nl2sqlApi_v2.js ← ✅ 新的 API 服务文件
└── components/
    └── UnifiedChat/
        └── UnifiedChat.tsx
```

**验证**:
```bash
# 检查文件是否存在
ls -la src/services/nl2sqlApi_v2.js

# 如果不存在，您需要创建它（文件内容见下面）
```

### 步骤 2: 更新 UnifiedChat 组件

**文件**: `src/components/UnifiedChat/UnifiedChat.tsx` (或相应路径)

**改动**:
```typescript
// ❌ 旧的导入方式
import { explainQuery } from '../../services/nl2sqlApi';

// ✅ 新的导入方式
import { explainQuery, processNaturalLanguageQuery } from '../../services/nl2sqlApi_v2';
```

### 步骤 3: 创建或更新 nl2sqlApi_v2.js

如果您的前端没有 `nl2sqlApi_v2.js`，需要创建它。

**文件**: `src/services/nl2sqlApi_v2.js`

```javascript
/**
 * NL2SQL 统一 API 服务
 * 与后端统一查询服务交互
 */

// 获取 API 基础 URL（支持环境变量）
const getApiBaseUrl = () => {
  // Vite 环境变量
  if (import.meta?.env?.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  // React 环境变量
  if (process.env.REACT_APP_API_URL) {
    return `${process.env.REACT_APP_API_URL}/api/query/unified`;
  }
  // 默认值
  return 'http://localhost:8000/api/query/unified';
};

const API_URL = getApiBaseUrl();

/**
 * 处理自然语言查询（完整流程）
 */
export async function processNaturalLanguageQuery(
  naturalLanguage,
  executionMode = 'explain',
  userContext = null
) {
  try {
    const response = await fetch(`${API_URL}/process`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        natural_language: naturalLanguage,
        execution_mode: executionMode,
        user_context: userContext
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error processing query:', error);
    throw error;
  }
}

/**
 * 只获取 SQL 解释（不执行）
 */
export async function explainQuery(naturalLanguage) {
  try {
    const response = await fetch(`${API_URL}/explain`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        natural_language: naturalLanguage
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error explaining query:', error);
    throw error;
  }
}

/**
 * 执行 SQL 查询
 */
export async function executeQuery(naturalLanguage) {
  try {
    const response = await fetch(`${API_URL}/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        natural_language: naturalLanguage
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error executing query:', error);
    throw error;
  }
}

/**
 * 获取 SQL 变体
 */
export async function suggestVariants(sql) {
  try {
    const response = await fetch(`${API_URL}/suggest-variants`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ sql })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error suggesting variants:', error);
    throw error;
  }
}

/**
 * 验证 SQL
 */
export async function validateSQL(sql) {
  try {
    const response = await fetch(`${API_URL}/validate-sql`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ sql })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error validating SQL:', error);
    throw error;
  }
}

/**
 * 获取查询推荐
 */
export async function getQueryRecommendations() {
  try {
    const response = await fetch(`${API_URL}/query-recommendations`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error getting recommendations:', error);
    throw error;
  }
}

/**
 * 获取执行历史
 */
export async function getExecutionHistory() {
  try {
    const response = await fetch(`${API_URL}/execution-history`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error getting execution history:', error);
    throw error;
  }
}

// 导出所有函数
export default {
  processNaturalLanguageQuery,
  explainQuery,
  executeQuery,
  suggestVariants,
  validateSQL,
  getQueryRecommendations,
  getExecutionHistory
};
```

### 步骤 4: 更新 UnifiedChat 组件的错误处理

**关键改动**:
```typescript
// ❌ 旧的错误处理
try {
  const response = await explainQuery(userQuery);
  // ... 处理响应
} catch (error) {
  console.error('Query explanation failed:', error);
}

// ✅ 新的错误处理
try {
  const response = await explainQuery(userQuery);
  
  if (response.success) {
    // 成功处理
    const { query_plan, query_result } = response;
    
    if (query_plan.requires_clarification) {
      // 显示澄清问题
      console.log(query_plan.clarification_message);
    } else if (query_plan.generated_sql) {
      // 显示生成的 SQL
      console.log(query_plan.generated_sql);
    }
  } else {
    // 错误处理
    console.error('API Error:', response.error);
  }
} catch (error) {
  // 网络错误或其他异常
  console.error('Failed to fetch:', error);
  
  // 详细诊断信息
  if (error.message === 'Failed to fetch') {
    console.error('网络错误或 CORS 问题 - 检查:');
    console.error('1. 后端是否运行: python run.py');
    console.error('2. API URL 是否正确');
    console.error('3. 浏览器控制台中的 CORS 错误信息');
  }
}
```

## 🧪 测试步骤

### 1. 验证后端运行

```bash
# 后端应该在运行
curl http://localhost:8000/api/schema/status
# 应该返回 200 和 JSON 数据
```

### 2. 检查前端导入

在您的浏览器控制台中运行:
```javascript
// 检查 API 服务是否正确导入
import * as nl2sqlApi from './src/services/nl2sqlApi_v2.js';
console.log(nl2sqlApi);  // 应该显示所有导出的函数
```

### 3. 手动测试 API 调用

在浏览器控制台运行:
```javascript
// 测试 API 调用
fetch('http://localhost:8000/api/query/unified/explain', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ natural_language: '查询OEE' })
})
.then(r => r.json())
.then(data => console.log('Success:', data))
.catch(e => console.error('Error:', e));
```

### 4. 在前端测试

1. 刷新前端页面
2. 输入查询
3. 检查浏览器开发者工具 (F12) → Network 标签
4. 验证请求 URL 是否为 `http://localhost:8000/api/query/unified/explain`
5. 验证响应状态码是否为 200

## ✅ 验证修复

修复完成后应该看到:

✅ 前端可以正常输入查询
✅ 网络请求返回 200 OK
✅ 看到澄清问题或生成的 SQL
✅ 可以执行查询并看到结果
✅ 浏览器控制台没有 "Failed to fetch" 错误

## 📞 遇到问题

### 问题: 仍然显示 "Failed to fetch"

**检查**:
```bash
# 1. 确认后端运行
ps aux | grep "python.*run.py"

# 2. 测试 API 端点
curl http://localhost:8000/api/query/unified/explain \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "查询"}'

# 3. 诊断前端-后端连接
bash diagnose_frontend_api.sh
```

### 问题: 仍然看到 CORS 错误

**解决**:
1. 确保后端已完全启动
2. 检查 `.env.frontend` 中的 API URL
3. 清除浏览器缓存和 localStorage
4. 重新加载页面

### 问题: 网络请求到达错误的端点

**原因**: API URL 配置不正确
**解决**: 检查 `VITE_API_BASE_URL` 或 `REACT_APP_API_URL` 是否正确

---

**总结**: 后端完全正常，问题在于前端代码使用了旧的 API 调用方式。按照上面的步骤更新前端代码后，问题应该会解决。

参考文档:
- [FRONTEND_API_FETCH_ERROR_FIX.md](./FRONTEND_API_FETCH_ERROR_FIX.md) - 详细修复指南
- [FRONTEND_API_CONFIGURATION.md](./FRONTEND_API_CONFIGURATION.md) - API 配置说明
- [QUICK_START_5MIN.md](./QUICK_START_5MIN.md) - 快速开始

