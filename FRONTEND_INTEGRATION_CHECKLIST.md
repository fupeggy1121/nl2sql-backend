# 前端集成检查清单

按照以下步骤逐项完成前端集成工作。

## 📋 集成前检查

### 1. 验证后端服务运行状态

```bash
# 检查后端是否运行
curl http://localhost:8000/api/schema/status -s | jq .

# 输出应该类似:
# {
#   "status": "connected",
#   "message": "Schema loaded successfully",
#   "tables": 15,
#   "columns": 234
# }
```

### 2. 测试后端统一查询API

```bash
# 测试基础查询端点
curl -X POST http://localhost:8000/api/query/unified/process \
  -H "Content-Type: application/json" \
  -d '{
    "query": "获取OEE数据",
    "execute": false
  }' | jq .

# 输出应该包含:
# {
#   "success": true,
#   "query_plan": {
#     "query_intent": {...},
#     "generated_sql": "SELECT ...",
#     "explanation": "..."
#   }
# }
```

### 3. 检查前端环境变量配置

```bash
# 查看 .env.local 或 frontend/.env
cat .env.local | grep API_URL

# 应该包含:
# REACT_APP_API_URL=http://localhost:8000
```

---

## ✅ 集成步骤检查表

### Step 1: 删除旧的服务文件

- [ ] 确认已删除 `modules/mes/services/intentRecognizer.ts`
  ```bash
  ls modules/mes/services/intentRecognizer.ts 2>/dev/null || echo "✅ 已删除"
  ```

- [ ] 确认已删除 `modules/mes/services/queryService.ts`
  ```bash
  ls modules/mes/services/queryService.ts 2>/dev/null || echo "✅ 已删除"
  ```

- [ ] 移除项目中对这两个文件的所有导入
  ```bash
  # 搜索残留导入
  grep -r "intentRecognizer\|queryService" src/ --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx"
  # 如果有结果，需要删除这些导入
  ```

### Step 2: 添加新的API客户端

- [ ] 复制 `src/services/nl2sqlApi_v2.js` 到你的前端项目
  ```bash
  cp src/services/nl2sqlApi_v2.js /path/to/your/frontend/src/services/
  ```

- [ ] 验证文件存在且完整
  ```bash
  # 应该包含所有8个导出方法
  grep -c "async function\|export" src/services/nl2sqlApi_v2.js
  # 输出应该 >= 15
  ```

- [ ] 确保环境变量配置正确
  ```javascript
  // src/services/nl2sqlApi_v2.js 中检查
  const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  ```

### Step 3: 更新各个使用旧服务的组件

对于每个使用了 `intentRecognizer` 或 `queryService` 的组件:

- [ ] **组件1**: `modules/mes/components/QueryInput.tsx` (或类似)
  ```typescript
  // 旧代码
  import { recognizeIntent } from '@/services/intentRecognizer';
  
  // 新代码
  import nl2sqlApi from '@/services/nl2sqlApi_v2';
  ```

- [ ] **组件2**: `modules/mes/components/ResultsDisplay.tsx` (或类似)
  ```typescript
  // 旧代码
  const results = await queryService.executeQuery(intent);
  
  // 新代码
  const response = await nl2sqlApi.executeApprovedQuery(sql, intent);
  ```

- [ ] **组件3**: 任何其他使用这些服务的组件
  ```bash
  # 查找所有可能的文件
  grep -r "intentRecognizer\|queryService" src/ --include="*.tsx" | cut -d: -f1 | sort -u
  ```

### Step 4: 更新组件状态管理

对于包含查询逻辑的主组件:

- [ ] 移除旧的 state
  ```typescript
  // ❌ 删除这些
  // const [intent, setIntent] = useState(null);
  // const [isRecognizing, setIsRecognizing] = useState(false);
  // const [dbResults, setDbResults] = useState(null);
  ```

- [ ] 添加新的 state
  ```typescript
  // ✅ 添加这些
  const [step, setStep] = useState('input');
  const [loading, setLoading] = useState(false);
  const [queryPlan, setQueryPlan] = useState(null);
  const [editedSQL, setEditedSQL] = useState('');
  const [queryResult, setQueryResult] = useState(null);
  ```

### Step 5: 更新事件处理程序

- [ ] 更新查询输入处理程序
  ```typescript
  // 旧方式
  // const intent = await recognizeIntent(userQuery);
  
  // 新方式
  const response = await nl2sqlApi.explainQuery(userQuery);
  if (response.success) {
    const plan = response.query_plan;
    // 处理结果
  }
  ```

- [ ] 更新SQL审核处理程序
  ```typescript
  // 旧方式
  // const result = await queryService.executeQuery(intent);
  
  // 新方式
  const response = await nl2sqlApi.executeApprovedQuery(editedSQL, intent);
  if (response.success) {
    const result = response.query_result;
    // 处理结果
  }
  ```

- [ ] 实现澄清流程（新增）
  ```typescript
  if (plan.requires_clarification) {
    // 显示澄清问题
    setStep('clarify');
  }
  ```

### Step 6: 更新UI流程

- [ ] 实现多步工作流 UI
  ```typescript
  {step === 'input' && <QueryInput />}
  {step === 'clarify' && <ClarificationForm />}
  {step === 'explain' && <SQLReview />}
  {step === 'execute' && <LoadingSpinner />}
  {step === 'results' && <ResultsDisplay />}
  ```

- [ ] 添加错误处理
  ```typescript
  {error && <ErrorMessage message={error} />}
  ```

- [ ] 添加加载状态
  ```typescript
  <button disabled={loading}>
    {loading ? '处理中...' : '生成SQL'}
  </button>
  ```

### Step 7: 测试集成

#### 7.1 单元测试

- [ ] 测试 API 客户端方法
  ```javascript
  describe('nl2sqlApi', () => {
    test('explainQuery 返回有效响应', async () => {
      const response = await nl2sqlApi.explainQuery('获取数据');
      expect(response.success).toBe(true);
      expect(response.query_plan).toBeDefined();
    });

    test('executeApprovedQuery 执行 SQL', async () => {
      const response = await nl2sqlApi.executeApprovedQuery(
        'SELECT * FROM table',
        null
      );
      expect(response.success).toBe(true);
    });
  });
  ```

#### 7.2 集成测试

- [ ] 测试完整工作流
  ```javascript
  describe('Query Workflow', () => {
    test('完整流程: 输入 -> 生成 -> 执行 -> 结果', async () => {
      // 1. 生成SQL
      const explainRes = await nl2sqlApi.explainQuery('获取OEE');
      expect(explainRes.success).toBe(true);

      // 2. 执行SQL
      const executeRes = await nl2sqlApi.executeApprovedQuery(
        explainRes.query_plan.generated_sql,
        explainRes.query_plan.query_intent
      );
      expect(executeRes.success).toBe(true);

      // 3. 验证结果
      expect(executeRes.query_result.data).toBeDefined();
    });
  });
  ```

#### 7.3 手动测试

按以下场景进行手动测试:

| # | 测试场景 | 预期结果 | 状态 |
|---|----------|----------|------|
| 1 | 简单查询 (如: "获取数据") | 显示生成的SQL，可执行 | [ ] |
| 2 | 澄清查询 (如: "获取产量") | 显示澄清问题，用户回答后重新生成 | [ ] |
| 3 | 编辑SQL | 用户可编辑SQL后执行 | [ ] |
| 4 | 执行查询 | 显示结果表格 | [ ] |
| 5 | 导出结果 | 可导出为CSV | [ ] |
| 6 | 错误处理 | 无效查询显示友好错误 | [ ] |
| 7 | 加载状态 | 显示加载动画 | [ ] |
| 8 | 获取推荐 | 显示推荐查询列表 | [ ] |
| 9 | 查看历史 | 显示过去的查询 | [ ] |
| 10 | 图表展示 | 根据数据自动选择合适的图表 | [ ] |

---

## 🔍 常见问题检查

### 问题1: 后端API无响应

**症状**: 
```
Error: Cannot reach API at http://localhost:8000
```

**检查步骤**:
```bash
# 1. 确认后端运行
ps aux | grep "python.*run.py"

# 2. 测试API连接
curl http://localhost:8000/api/schema/status

# 3. 检查防火墙
lsof -i :8000

# 4. 查看后端日志
tail -f backend.log
```

**解决方案**:
- 启动后端: `python run.py`
- 检查 `REACT_APP_API_URL` 环境变量
- 检查 CORS 配置

### 问题2: API 返回 CORS 错误

**症状**:
```
Access to XMLHttpRequest at 'http://localhost:8000/...' 
has been blocked by CORS policy
```

**检查步骤**:
```bash
# 查看后端 CORS 配置
grep -n "CORS\|cors\|cross_origin" app/__init__.py

# 应该包含:
# from flask_cors import CORS
# CORS(app)
```

**解决方案**:
- 确保后端已启用 CORS
- 前端 `REACT_APP_API_URL` 应为完整 URL (包含 protocol)

### 问题3: 生成的SQL为空

**症状**:
```javascript
response.query_plan.generated_sql === null
```

**检查步骤**:
```bash
# 测试后端意图识别
curl -X POST http://localhost:8000/api/query/unified/process \
  -H "Content-Type: application/json" \
  -d '{"query": "你的查询", "execute": false}' | jq .query_plan
```

**解决方案**:
- 确保 schema 已加载: `curl http://localhost:8000/api/schema/status`
- 尝试更具体的查询
- 检查后端日志

### 问题4: 澄清问题未显示

**症状**:
```javascript
plan.requires_clarification === false
// 但你期望需要澄清
```

**检查步骤**:
```javascript
// 打印完整的plan对象
console.log('Query Plan:', JSON.stringify(plan, null, 2));

// 检查clarification_questions
console.log('Questions:', plan.clarification_questions);
```

**解决方案**:
- 尝试更模糊的查询
- 检查后端是否能识别澄清场景

### 问题5: 执行结果为空

**症状**:
```javascript
response.query_result.data === []
```

**检查步骤**:
```bash
# 手动执行SQL
psql postgresql://user:pass@host/db -c "SELECT ..."

# 或测试后端
curl -X POST http://localhost:8000/api/query/unified/execute \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM table LIMIT 1"}' | jq .
```

**解决方案**:
- 验证数据库中有数据
- 检查 SQL 语法
- 查看后端日志中的 SQL 执行情况

---

## 🚀 集成验收标准

完成以下所有检查才能认为集成成功:

### 功能验收

- [ ] **查询输入**: 用户可输入自然语言查询
- [ ] **SQL生成**: 后端正确生成 SQL
- [ ] **澄清处理**: 模糊查询时显示澄清问题
- [ ] **SQL审核**: 用户可查看并编辑生成的 SQL
- [ ] **查询执行**: 点击执行后返回结果
- [ ] **结果显示**: 结果表格正确显示
- [ ] **错误处理**: 错误时显示友好提示
- [ ] **导出功能**: 可导出结果为 CSV

### 性能验收

- [ ] **响应时间**: 查询生成 < 3 秒
- [ ] **加载状态**: 执行时显示加载动画
- [ ] **无阻塞**: UI 不应在等待时冻结

### 代码质量验收

- [ ] **无编译错误**: `npm run build` 成功
- [ ] **无运行时错误**: 浏览器控制台无红色错误
- [ ] **导入清晰**: 所有导入均来自 `nl2sqlApi_v2.js`
- [ ] **状态管理**: 使用新的 state 字段
- [ ] **异步处理**: 正确处理 async/await

### 代码审查检查

- [ ] **移除了旧导入**: 无 `intentRecognizer` 或 `queryService` 导入
- [ ] **API 调用正确**: 所有 API 调用都使用正确的方法
- [ ] **错误处理完整**: 所有 API 调用都有 try-catch
- [ ] **加载状态处理**: 按钮和输入在加载时禁用
- [ ] **类型安全**: 如果使用 TypeScript，所有类型都正确

---

## 📊 集成进度追踪

```
删除旧服务        [████████░░] 80%
添加新客户端      [██████████] 100%
更新主组件        [████░░░░░░] 40%
更新子组件        [██░░░░░░░░] 20%
实现工作流        [██████░░░░] 60%
错误处理          [████░░░░░░] 40%
单元测试          [░░░░░░░░░░] 0%
集成测试          [░░░░░░░░░░] 0%
手动测试          [██░░░░░░░░] 20%
代码审查          [░░░░░░░░░░] 0%

总体进度: [███░░░░░░░] 30%
```

---

## 📚 相关文档

- [FRONTEND_INTEGRATION_ADJUSTMENTS.md](./FRONTEND_INTEGRATION_ADJUSTMENTS.md) - 调整指南
- [FRONTEND_MIGRATION_EXAMPLES.tsx](./FRONTEND_MIGRATION_EXAMPLES.tsx) - 迁移示例
- [FRONTEND_INTEGRATION_EXAMPLE.tsx](./FRONTEND_INTEGRATION_EXAMPLE.tsx) - 完整示例
- [src/services/nl2sqlApi_v2.js](./src/services/nl2sqlApi_v2.js) - API 客户端源码
- [QUICK_START_BACKEND_SERVICE.md](./QUICK_START_BACKEND_SERVICE.md) - 后端快速启动

---

## 💡 技巧和最佳实践

### 1. 调试技巧

```javascript
// 在任何组件中添加调试日志
console.log('API URL:', process.env.REACT_APP_API_URL);
console.log('Query Plan:', JSON.stringify(queryPlan, null, 2));
console.log('Query Result:', JSON.stringify(queryResult, null, 2));
```

### 2. 浏览器开发工具

- 打开 Network 标签查看 API 请求
- 检查 Request/Response payloads
- 在 Console 中直接调用 API

```javascript
// 在浏览器 Console 中
const result = await fetch('http://localhost:8000/api/query/unified/process', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: '获取数据', execute: false })
}).then(r => r.json());
console.log(result);
```

### 3. 后端日志查看

```bash
# 查看后端日志
tail -f backend.log

# 或者搜索特定错误
grep ERROR backend.log | tail -20
```

### 4. 性能优化

- 使用 React DevTools Profiler 识别性能瓶颈
- 对 API 响应进行缓存
- 使用 useMemo 和 useCallback 优化组件

---

**更新时间**: 2026-02-03  
**检查版本**: 1.0  
**下一步**: 按照检查清单逐项完成集成

