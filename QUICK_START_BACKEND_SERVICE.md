# 后端服务快速启动指南

## 🚀 5分钟快速开始

### 1. 启动后端服务

```bash
cd /Users/fupeggy/NL2SQL
source .venv/bin/activate
python run.py
```

### 2. 验证服务运行

```bash
# 检查推荐查询（验证服务正常运行）
curl http://localhost:8000/api/query/unified/query-recommendations

# 应该返回：
# {
#   "success": true,
#   "recommendations": [...]
# }
```

### 3. 测试简单查询

```bash
curl -X POST http://localhost:8000/api/query/unified/explain \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "查询今天的OEE数据"}'
```

### 4. 查看关键文件

| 文件 | 说明 |
|------|------|
| `app/services/unified_query_service.py` | 核心查询服务 |
| `app/routes/unified_query_routes.py` | API端点 |
| `src/services/nl2sqlApi_v2.js` | 前端API客户端 |
| `BACKEND_SERVICE_ARCHITECTURE.md` | 详细文档 |

---

## 📋 核心API端点

### 1. 处理查询 (完整流程)

```bash
POST /api/query/unified/process

请求:
{
  "natural_language": "查询今天各设备的OEE",
  "execution_mode": "explain"  # or "execute"
}

响应:
{
  "success": true,
  "query_plan": {
    "generated_sql": "SELECT ...",
    "explanation": "...",
    "query_intent": {...}
  },
  "query_result": null  # 仅当execution_mode为execute时返回
}
```

### 2. 仅获取SQL (不执行)

```bash
POST /api/query/unified/explain

请求:
{
  "natural_language": "查询今天的OEE"
}

响应: 同上，但query_result为null
```

### 3. 执行SQL

```bash
POST /api/query/unified/execute

请求:
{
  "sql": "SELECT equipment_id, AVG(oee) FROM oee_records WHERE ...",
  "query_intent": {...}  # 可选
}

响应:
{
  "success": true,
  "query_result": {
    "data": [...],
    "rows_count": 10,
    "summary": "...",
    "visualization_type": "bar"
  }
}
```

### 4. 获取推荐

```bash
GET /api/query/unified/query-recommendations

响应:
{
  "success": true,
  "recommendations": [
    {
      "title": "查看今天的OEE",
      "natural_language": "查询今天各设备的OEE数据",
      "category": "metric"
    },
    ...
  ]
}
```

---

## 🔄 完整查询流程

### 步骤1: 用户输入

```javascript
const userQuery = "查询今天各设备的OEE";
```

### 步骤2: 前端调用后端获取SQL

```javascript
const response = await nl2sqlApi.explainQuery(userQuery);
// 返回: query_plan with generated_sql, explanation等
```

### 步骤3: 前端显示SQL等待批准

```javascript
console.log(response.query_plan.generated_sql);
// SELECT equipment_id, AVG(oee) FROM oee_records...

console.log(response.query_plan.explanation);
// "此查询获取今天每个设备的平均OEE值..."
```

### 步骤4: 用户批准，前端执行

```javascript
const result = await nl2sqlApi.executeApprovedQuery(
  response.query_plan.generated_sql,
  response.query_plan.query_intent
);
```

### 步骤5: 前端显示结果

```javascript
// result.data = [{equipment_id: "EQ-001", avg_oee: 92.5}, ...]
// result.visualization_type = "bar"
// 使用chart库绘制柱状图
```

---

## 📊 关键特性

### ✅ 已实现

- [x] **意图识别** - 从自然语言识别查询意图
- [x] **SQL生成** - 使用NL2SQL和Schema标注生成SQL
- [x] **SQL解释** - 用LLM生成人类可读的SQL解释
- [x] **澄清机制** - 当意图不清时自动要求用户澄清
- [x] **结果摘要** - 自动生成查询结果摘要
- [x] **可视化建议** - 根据数据推荐最佳展示方式
- [x] **SQL验证** - 检查SQL语法和合理性
- [x] **SQL变体** - 建议多个SQL选项供用户选择

### 🚀 立即可用

```javascript
// 最简单的方式：一行代码完成整个流程
const result = await nl2sqlApi.executeQueryWithApproval(
  "查询今天的OEE",
  async (sql, explanation) => {
    // 显示SQL和解释给用户
    return confirm(`执行此SQL?\n\n${sql}`);
  }
);
```

---

## 🛠️ 常用命令

### 后端

```bash
# 启动服务
python run.py

# 运行测试
python test_unified_query_service.py

# 检查API状态
curl http://localhost:8000/api/schema/status
```

### 前端

```bash
# 使用新API服务
import nl2sqlApi from '../services/nl2sqlApi_v2.js';

// 处理查询
const response = await nl2sqlApi.processNaturalLanguageQuery(
  userQuery, 
  "explain"
);

// 执行查询
const result = await nl2sqlApi.executeApprovedQuery(
  sql,
  queryIntent
);
```

---

## 📚 深入学习

### 详细文档

1. **[BACKEND_SERVICE_ARCHITECTURE.md](BACKEND_SERVICE_ARCHITECTURE.md)** (600+ 行)
   - 完整的系统架构
   - 所有API端点详细说明
   - 数据流示例
   - 集成指南

2. **[BACKEND_SERVICE_IMPLEMENTATION_SUMMARY.md](BACKEND_SERVICE_IMPLEMENTATION_SUMMARY.md)** (500+ 行)
   - 实现细节
   - 代码结构
   - 部署步骤
   - 性能数据

3. **[BACKEND_SERVICE_COMPLETION_SUMMARY.md](BACKEND_SERVICE_COMPLETION_SUMMARY.md)** (400+ 行)
   - 项目完成总结
   - 交付物清单
   - 后续工作计划

### 示例代码

**前端集成示例**: [FRONTEND_INTEGRATION_EXAMPLE.tsx](FRONTEND_INTEGRATION_EXAMPLE.tsx) (600+ 行)

完整的React组件示例，展示：
- 输入界面
- SQL审核界面
- 结果展示界面
- 数据导出功能

---

## 🔍 故障排除

### 问题: API返回404

**解决**:
```bash
# 确保蓝图已注册
grep "unified_query_routes" app/__init__.py

# 重启后端服务
python run.py
```

### 问题: 意图识别不准确

**原因**: 用户输入过于模糊
**解决**: 系统会自动返回澄清问题，用户可以提供更多信息

### 问题: SQL生成错误

**解决**: 
```bash
# 检查Schema元数据是否正确
curl http://localhost:8000/api/schema/metadata

# 检查NL2SQL转换器是否正常
curl http://localhost:8000/api/query/schema-metadata
```

---

## 💡 最佳实践

### 1. 前端调用模式

```javascript
// ✅ 推荐: 完整流程处理
const result = await nl2sqlApi.executeQueryWithApproval(
  naturalLanguage,
  (sql, explanation) => confirmDialog(sql, explanation)
);

// ⚠️ 可以，但需要手动处理流程
const plan = await nl2sqlApi.explainQuery(userQuery);
// ... 用户审核 ...
const result = await nl2sqlApi.executeApprovedQuery(plan.generated_sql);
```

### 2. 错误处理

```javascript
try {
  const result = await nl2sqlApi.executeQueryWithApproval(query, onApprove);
} catch (error) {
  if (error.message.includes('澄清')) {
    // 显示澄清问题
  } else if (error.message.includes('SQL')) {
    // 显示SQL错误
  } else {
    // 其他错误
  }
}
```

### 3. 性能优化

```javascript
// ✅ 缓存推荐查询（只调用一次）
const recommendations = await nl2sqlApi.getQueryRecommendations();

// ✅ 批量执行时先explain再execute
const plans = [];
for (const query of queries) {
  const plan = await nl2sqlApi.explainQuery(query);
  plans.push(plan);
}
// 用户可以同时审核所有SQL
// 然后批量执行
```

---

## 📈 监控和调试

### 查看日志

```bash
# 后端日志
tail -f /tmp/backend.log

# 查看最近的查询
curl http://localhost:8000/api/query/unified/execution-history?limit=10
```

### 性能监控

```javascript
// 测量查询耗时
const start = performance.now();
const result = await nl2sqlApi.executeApprovedQuery(sql);
const duration = performance.now() - start;
console.log(`查询耗时: ${duration}ms`);
console.log(`返回行数: ${result.query_result.rows_count}`);
```

---

## 🎓 学习路径

### 初级
1. 运行示例查询
2. 查看推荐查询
3. 理解基本流程

### 中级
1. 集成到前端应用
2. 自定义推荐查询
3. 处理澄清流程

### 高级
1. 优化SQL生成
2. 添加权限控制
3. 实现查询模板

---

## 📞 快速参考

| 场景 | 方法 | 文档 |
|------|------|------|
| 解析并执行查询 | `executeQueryWithApproval()` | [nl2sqlApi_v2.js](src/services/nl2sqlApi_v2.js) |
| 只获取SQL | `explainQuery()` | [ARCHITECTURE.md](BACKEND_SERVICE_ARCHITECTURE.md) |
| 执行预定义SQL | `executeApprovedQuery()` | [ARCHITECTURE.md](BACKEND_SERVICE_ARCHITECTURE.md) |
| 获取推荐 | `getQueryRecommendations()` | [API文档](BACKEND_SERVICE_ARCHITECTURE.md) |
| 验证SQL | `validateSQL()` | [API文档](BACKEND_SERVICE_ARCHITECTURE.md) |

---

**准备好了吗？开始使用新的后端服务吧！** 🚀

