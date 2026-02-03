# 前端集成快速参考

## 🎯 核心概念

| 概念 | 旧方式 | 新方式 |
|-----|--------|--------|
| **意图识别** | `intentRecognizer.ts` (前端) | `backend /api/query/unified/process` |
| **SQL生成** | 结合意图在前端生成 | 后端生成，前端审核 |
| **查询执行** | `queryService.ts` (前端) | `POST /api/query/unified/execute` |
| **工作流** | 单步: 意图→执行 | 多步: 意图→SQL→审核→执行→结果 |

## 📦 API 客户端方法

### 导入
```javascript
import nl2sqlApi from '@/services/nl2sqlApi_v2';
```

### 8 个方法

| # | 方法 | 用途 | 返回值 |
|---|------|------|--------|
| 1 | `explainQuery(query)` | 生成SQL（不执行） | `{success, query_plan, error}` |
| 2 | `executeApprovedQuery(sql, intent)` | 执行SQL | `{success, query_result, error}` |
| 3 | `processNaturalLanguageQuery(query, opts)` | 完整流程 | `{success, query_plan, query_result, error}` |
| 4 | `validateSQL(sql)` | 验证SQL语法 | `{success, valid, errors}` |
| 5 | `suggestSQLVariants(query)` | 获取SQL变体 | `{success, variants}` |
| 6 | `getQueryRecommendations()` | 获取推荐查询 | `{success, recommendations}` |
| 7 | `getExecutionHistory()` | 获取执行历史 | `{success, history}` |
| 8 | `executeQueryWithApproval(query)` | 带审核的完整流程 | `{success, query_result, error}` |

## 🔄 工作流

### 基础工作流 (推荐)
```
用户输入查询
  ↓
explainQuery() → 获取 SQL
  ↓
用户审核/编辑 SQL
  ↓
executeApprovedQuery() → 执行
  ↓
显示结果
```

### 完整工作流 (带澄清)
```
用户输入查询
  ↓
processNaturalLanguageQuery()
  ↓
需要澄清? ──是→ 显示问题 → 用户回答
             ↓
             重新查询
  │
  └→ 否 → 显示 SQL
          ↓
          用户审核/编辑
          ↓
          executeApprovedQuery()
          ↓
          显示结果
```

## 💾 状态管理

```typescript
// 删除
// const [intent, setIntent] = useState(null);
// const [isRecognizing, setIsRecognizing] = useState(false);
// const [dbResults, setDbResults] = useState(null);

// 添加
const [step, setStep] = useState('input');           // 'input'|'clarify'|'explain'|'execute'|'results'
const [loading, setLoading] = useState(false);       // 加载状态
const [error, setError] = useState(null);            // 错误信息
const [queryPlan, setQueryPlan] = useState(null);    // 包含 intent、SQL、说明
const [editedSQL, setEditedSQL] = useState('');      // 用户编辑的 SQL
const [queryResult, setQueryResult] = useState(null); // 执行结果
```

## 🛠️ 快速示例

### 1. 最小化示例 (20 行)
```javascript
const handleQuery = async () => {
  const res = await nl2sqlApi.explainQuery(query);
  if (res.success) {
    setSQL(res.query_plan.generated_sql);
  }
};

const handleExecute = async () => {
  const res = await nl2sqlApi.executeApprovedQuery(sql);
  if (res.success) {
    setResults(res.query_result.data);
  }
};
```

### 2. 完整示例 (50 行)
```javascript
const handleInputQuery = async (e) => {
  e.preventDefault();
  setLoading(true);
  
  try {
    const res = await nl2sqlApi.explainQuery(userQuery);
    if (!res.success) throw new Error(res.error);
    
    const plan = res.query_plan;
    if (plan.requires_clarification) {
      setQueryPlan(plan);
      setStep('clarify');
    } else {
      setQueryPlan(plan);
      setEditedSQL(plan.generated_sql);
      setStep('explain');
    }
  } catch (err) {
    setError(err.message);
  } finally {
    setLoading(false);
  }
};

const handleApproveSQL = async () => {
  setLoading(true);
  try {
    const res = await nl2sqlApi.executeApprovedQuery(editedSQL, queryPlan.query_intent);
    if (!res.success) throw new Error(res.error);
    
    setQueryResult(res.query_result);
    setStep('results');
  } catch (err) {
    setError(err.message);
  } finally {
    setLoading(false);
  }
};
```

### 3. 澄清处理 (30 行)
```javascript
if (plan.requires_clarification) {
  return (
    <form onSubmit={handleClarification}>
      <p>{plan.clarification_message}</p>
      {plan.clarification_questions?.map((q, i) => (
        <input 
          key={i}
          placeholder={q}
          onChange={(e) => handleAnswer(q, e.target.value)}
        />
      ))}
      <button type="submit">继续</button>
    </form>
  );
}
```

## ⚠️ 常见错误

| 错误 | 原因 | 修复 |
|-----|-----|------|
| `TypeError: nl2sqlApi is undefined` | 未导入客户端库 | 添加 `import nl2sqlApi from '@/services/nl2sqlApi_v2'` |
| `Cannot POST /api/query/unified/...` | 后端未运行 | 启动后端: `python run.py` |
| `CORS error` | 跨域配置 | 检查后端 CORS 和环境变量 |
| `SQL generation failed` | Schema 未加载 | 检查 `/api/schema/status` |
| `generated_sql is null` | 意图识别失败 | 尝试更具体的查询或检查澄清 |

## 🧪 快速测试

### 在浏览器 Console 中
```javascript
// 导入并测试
import nl2sqlApi from './src/services/nl2sqlApi_v2';

// 测试1: 生成SQL
const res1 = await nl2sqlApi.explainQuery('获取数据');
console.log(res1);

// 测试2: 执行SQL
const res2 = await nl2sqlApi.executeApprovedQuery('SELECT * FROM table LIMIT 1');
console.log(res2);

// 测试3: 获取推荐
const res3 = await nl2sqlApi.getQueryRecommendations();
console.log(res3);
```

### 在 curl 中
```bash
# 生成SQL
curl -X POST http://localhost:8000/api/query/unified/process \
  -H "Content-Type: application/json" \
  -d '{"query":"获取数据","execute":false}' | jq .

# 执行SQL
curl -X POST http://localhost:8000/api/query/unified/execute \
  -H "Content-Type: application/json" \
  -d '{"sql":"SELECT * FROM table"}' | jq .
```

## 📋 删除检查表

```bash
# 1. 找出所有使用旧服务的文件
grep -r "intentRecognizer\|queryService" src/ --include="*.ts" --include="*.tsx"

# 2. 删除 intentRecognizer.ts
rm modules/mes/services/intentRecognizer.ts

# 3. 删除 queryService.ts
rm modules/mes/services/queryService.ts

# 4. 删除旧导入
# 在编辑器中搜索并删除所有的:
# import { ... } from '@/services/intentRecognizer'
# import { ... } from '@/services/queryService'

# 5. 验证清理
grep -r "intentRecognizer\|queryService" src/ || echo "✅ 清理完成"
```

## 🚀 部署清单

- [ ] 后端运行中: `python run.py`
- [ ] 前端环境变量: `REACT_APP_API_URL=http://localhost:8000`
- [ ] 已导入 `nl2sqlApi_v2.js`
- [ ] 已删除旧服务导入
- [ ] 已更新状态管理
- [ ] 已实现工作流
- [ ] 已添加错误处理
- [ ] 已测试所有场景

## 📖 文档导航

| 文档 | 用途 |
|-----|------|
| [FRONTEND_INTEGRATION_ADJUSTMENTS.md](./FRONTEND_INTEGRATION_ADJUSTMENTS.md) | 详细调整指南 |
| [FRONTEND_MIGRATION_EXAMPLES.tsx](./FRONTEND_MIGRATION_EXAMPLES.tsx) | 迁移代码示例 |
| [FRONTEND_INTEGRATION_CHECKLIST.md](./FRONTEND_INTEGRATION_CHECKLIST.md) | 详细检查清单 |
| [FRONTEND_INTEGRATION_EXAMPLE.tsx](./FRONTEND_INTEGRATION_EXAMPLE.tsx) | 完整 UI 组件 |
| [src/services/nl2sqlApi_v2.js](./src/services/nl2sqlApi_v2.js) | API 客户端源码 |

---

**打印此页面或保存为书签！** 📌

