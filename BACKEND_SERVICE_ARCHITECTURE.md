# 后端服务架构指南

## 概述

本指南描述了完善后的后端服务架构，将意图识别、NL2SQL转换和查询执行从前端迁移到后端，实现更精确和可控的查询流程。

---

## 架构设计

### 整体流程

```
前端                          后端
 │                             │
 ├─ 自然语言查询 ──────────────┤
 │                             ├─ 意图识别
 │                             ├─ Schema语义分析
 │                             ├─ NL2SQL转换
 │                             │
 │◄─ 返回SQL和解释 ────────────┤
 │                             │
 ├─ 用户审核SQL               │
 │                             │
 ├─ 批准执行 ──────────────────┤
 │                             ├─ 执行SQL
 │                             ├─ 数据处理
 │                             │
 │◄─ 返回结果 ────────────────┤
 │                             │
```

### 核心服务

#### 1. UnifiedQueryService (后端)

**位置**: `app/services/unified_query_service.py`

**职责**:
- 集成意图识别、NL2SQL转换、查询执行
- 管理查询计划生成
- 返回结构化的查询结果

**关键方法**:

```python
async def process_natural_language_query(
    natural_language: str,
    user_context: Optional[Dict] = None,
    execution_mode: str = "explain"
) -> Tuple[QueryPlan, Optional[QueryResult]]
```

**参数**:
- `natural_language`: 用户的自然语言查询
- `user_context`: 用户上下文（可选）
- `execution_mode`: 
  - `"explain"`: 只返回SQL解释
  - `"execute"`: 直接执行并返回结果

**返回值**:
- `QueryPlan`: 包含查询意图、生成的SQL、解释等
- `QueryResult`: 执行结果（仅在execution_mode为execute时返回）

#### 2. API端点

**路由前缀**: `/api/query/unified`

##### POST /api/query/unified/process

处理自然语言查询的完整流程

**请求体**:
```json
{
  "natural_language": "查询今天的OEE数据按设备对比",
  "execution_mode": "explain",
  "user_context": {
    "user_id": "123",
    "department": "生产"
  }
}
```

**响应（success且无需澄清）**:
```json
{
  "success": true,
  "query_plan": {
    "query_intent": {
      "query_type": "comparison_query",
      "natural_language": "查询今天的OEE数据按设备对比",
      "metric": "oee",
      "time_range": "today",
      "equipment": ["EQ-001", "EQ-002"],
      "comparison": true,
      "confidence": 0.92,
      "clarification_needed": false
    },
    "generated_sql": "SELECT equipment_id, AVG(oee) as avg_oee FROM oee_records WHERE date='2026-02-03' GROUP BY equipment_id ORDER BY avg_oee DESC",
    "sql_confidence": 0.85,
    "explanation": "这个查询将查询2026年2月3日每个设备的平均OEE值，按降序排列以找到表现最好和最差的设备。",
    "schema_context": {
      "tables": ["oee_records", "equipment", "production_orders"],
      "total_columns": 15
    }
  },
  "query_result": null
}
```

**响应（需要澄清）**:
```json
{
  "success": true,
  "query_plan": {
    "query_intent": {
      "query_type": "unknown",
      "natural_language": "查询数据",
      "clarification_needed": true,
      "clarification_questions": [
        "您想查询哪个指标？(OEE, 良率, 效率, 停机时间等)",
        "您想查询哪个时间段？(今天, 本周, 本月等)"
      ]
    },
    "requires_clarification": true,
    "clarification_message": "为了更准确地理解您的查询，请回答以下问题：..."
  }
}
```

##### POST /api/query/unified/execute

执行已批准的SQL查询

**请求体**:
```json
{
  "sql": "SELECT equipment_id, AVG(oee) as avg_oee FROM oee_records WHERE date='2026-02-03' GROUP BY equipment_id",
  "query_intent": {
    "query_type": "comparison_query",
    "metric": "oee",
    "time_range": "today",
    "comparison": true
  }
}
```

**响应**:
```json
{
  "success": true,
  "query_result": {
    "success": true,
    "data": [
      {"equipment_id": "EQ-001", "avg_oee": 92.5},
      {"equipment_id": "EQ-002", "avg_oee": 88.3}
    ],
    "sql": "SELECT equipment_id, AVG(oee) as avg_oee FROM oee_records...",
    "rows_count": 2,
    "summary": "查询得到 2 条oee的数据记录",
    "visualization_type": "bar",
    "actions": ["export", "detail", "drilldown"],
    "query_time_ms": 125.5,
    "generated_at": "2026-02-03T14:30:00"
  }
}
```

##### POST /api/query/unified/explain

只获取SQL解释（不执行）

**请求体**:
```json
{
  "natural_language": "查询今天的OEE数据"
}
```

**响应**: 同 /process 端点

##### POST /api/query/unified/validate-sql

验证SQL语法和合理性

**请求体**:
```json
{
  "sql": "SELECT * FROM oee_records WHERE date > '2026-01-01' LIMIT 100"
}
```

**响应**:
```json
{
  "success": true,
  "is_valid": true,
  "errors": [],
  "warnings": []
}
```

##### POST /api/query/unified/suggest-variants

为查询建议SQL变体

**请求体**:
```json
{
  "natural_language": "查询OEE数据",
  "base_sql": "SELECT * FROM oee_records"
}
```

**响应**:
```json
{
  "success": true,
  "variants": [
    {
      "sql": "SELECT * FROM oee_records",
      "description": "原始查询",
      "confidence": 0.85
    },
    {
      "sql": "SELECT equipment_id, AVG(oee) FROM oee_records GROUP BY equipment_id",
      "description": "按设备聚合",
      "confidence": 0.75
    }
  ]
}
```

##### GET /api/query/unified/query-recommendations

获取推荐查询

**响应**:
```json
{
  "success": true,
  "recommendations": [
    {
      "title": "查看今天的OEE",
      "natural_language": "查询今天各设备的OEE数据",
      "category": "metric",
      "icon": "chart"
    },
    {
      "title": "对比设备效率",
      "natural_language": "对比本周所有设备的效率差异",
      "category": "comparison",
      "icon": "compare"
    }
  ]
}
```

---

## 前端集成

### 1. 新API服务

**文件**: `src/services/nl2sqlApi_v2.js`

提供高级方法与后端交互:

```typescript
// 解析自然语言，获取SQL解释
const response = await nl2sqlApi.explainQuery("查询今天的OEE");

// 执行已批准的SQL
const result = await nl2sqlApi.executeApprovedQuery(sql, queryIntent);

// 完整流程：解析 -> 审核 -> 执行
const result = await nl2sqlApi.executeQueryWithApproval(
  "查询今天的OEE",
  async (sql, explanation) => {
    // 显示SQL和解释给用户
    // 返回用户是否批准
    return confirm(`执行此SQL? ${sql}`);
  }
);
```

### 2. 前端组件修改

#### UnifiedChat.tsx - 更新交互流程

**新流程**:
1. 用户输入自然语言查询
2. 前端发送到后端 `/api/query/unified/process`
3. 后端返回SQL和解释
4. 前端在Chat中展示SQL供审核
5. 用户点击执行
6. 前端发送 `/api/query/unified/execute`
7. 后端执行并返回结果
8. 前端展示结果

**关键变化**:
```typescript
// 旧方式（前端本地意图识别）
const intent = intentRecognizer.recognize(userQuery);
const result = await queryService.executeQuery(intent);

// 新方式（后端意图识别）
const response = await nl2sqlApi.explainQuery(userQuery);
// 显示SQL等待批准
const result = await nl2sqlApi.executeApprovedQuery(sql, queryPlan.query_intent);
```

#### IntentRecognizer.ts - 移除本地识别

**删除理由**:
- 后端已进行意图识别
- 前端无需重复识别
- 后端可以访问完整的schema信息

**替换方案**:
```typescript
// 移除: frontend/modules/mes/services/intentRecognizer.ts
// 前端不再进行本地意图识别

// 后端处理: app/services/intent_recognizer.py
// 后端进行意图识别和验证
```

#### QueryService.ts - 移除或简化

**删除理由**:
- 直接Supabase查询逻辑应该在后端
- 后端处理器（QueryExecutor）已实现

**保留内容**:
- 如果需要前端本地缓存，保留缓存逻辑
- 数据格式转换

---

## 数据流示例

### 场景1: 查询今天的OEE数据

#### 前端请求
```bash
POST /api/query/unified/process
Content-Type: application/json

{
  "natural_language": "查询今天各设备的OEE",
  "execution_mode": "explain"
}
```

#### 后端处理
1. **意图识别**
   - 识别: 查询类型=METRIC_QUERY，指标=OEE，时间=today
   - 置信度=0.92

2. **Schema分析**
   - 确定相关表: `oee_records`
   - 加载列信息和中文标注

3. **NL2SQL转换**
   - 使用增强转换器处理自然语言
   - 考虑schema中文标注
   - 生成SQL: `SELECT equipment_id, AVG(oee) FROM oee_records WHERE date='2026-02-03' GROUP BY equipment_id`

4. **生成解释**
   - 使用LLM生成人类可读的SQL解释

5. **返回查询计划**
   ```json
   {
     "query_intent": {...},
     "generated_sql": "...",
     "explanation": "这个查询将显示今天每个设备的平均OEE值...",
     "suggested_sql_variants": [...]
   }
   ```

#### 前端展示
- 显示生成的SQL
- 显示SQL解释
- 显示suggested variants（可选）
- 等待用户批准

#### 用户批准后
```bash
POST /api/query/unified/execute
{
  "sql": "SELECT equipment_id, AVG(oee) FROM...",
  "query_intent": {...}
}
```

#### 后端执行
1. 验证SQL
2. 执行查询
3. 处理结果（格式化、聚合等）
4. 返回结果+可视化建议

#### 前端展示结果
- 根据visualization_type显示图表或表格
- 显示available actions（导出、下钻等）
- 保存查询历史

---

## 错误处理

### 意图不清楚的情况

```json
{
  "success": true,
  "query_plan": {
    "requires_clarification": true,
    "clarification_message": "为了更准确地理解您的查询，请回答以下问题...",
    "clarification_questions": [
      "您想查询哪个指标？",
      "您想查询哪个时间段？"
    ]
  }
}
```

前端应该:
1. 显示澄清问题给用户
2. 收集用户回答
3. 重新发送包含更多上下文的查询

### SQL执行失败

```json
{
  "success": false,
  "query_result": {
    "success": false,
    "error_message": "执行查询失败: 表不存在",
    "sql": "SELECT * FROM non_existent_table"
  }
}
```

前端应该:
1. 显示错误信息给用户
2. 提供重试或修改查询的选项
3. 记录错误用于调试

---

## 性能优化

### 1. 缓存元数据
- 后端定期刷新schema元数据
- 避免每次查询都加载

### 2. SQL优化
- 添加必要的LIMIT
- 使用合适的索引
- 避免复杂的JOIN

### 3. 结果缓存
- 前端缓存常见查询结果
- 设置合理的过期时间

---

## 安全性考虑

### 1. SQL注入防护
- 后端验证所有生成的SQL
- 使用参数化查询

### 2. 权限控制
- 验证用户能否访问相关表
- 限制查询的数据范围

### 3. 审计日志
- 记录所有执行的查询
- 追踪数据访问

---

## 迁移计划

### 第1阶段: 部署后端服务
- [ ] 部署UnifiedQueryService
- [ ] 部署新API端点
- [ ] 测试后端功能

### 第2阶段: 前端集成
- [ ] 更新nl2sqlApi
- [ ] 修改UnifiedChat组件
- [ ] 测试前后端交互

### 第3阶段: 移除前端逻辑
- [ ] 删除IntentRecognizer.ts
- [ ] 简化QueryService.ts
- [ ] 清理前端代码

### 第4阶段: 验证和优化
- [ ] 全面测试
- [ ] 性能调优
- [ ] 用户反馈

---

## 常见问题

### Q: 为什么要移到后端?

A: 
- 后端可以访问完整的数据库schema和权限信息
- 后端可以更好地优化SQL
- 集中管理业务逻辑和安全策略
- 便于审计和日志记录

### Q: 前端还需要做意图识别吗?

A: 
不需要。后端负责意图识别。前端只需要将用户输入发送给后端。

### Q: 如何处理复杂查询?

A:
- 后端的澄清机制会要求用户提供更多信息
- 支持suggested_sql_variants让用户选择
- 支持步进式查询

### Q: 性能会受影响吗?

A:
- 后端处理减少了往返次数
- SQL优化在后端进行更高效
- 可以实现结果缓存
- 总体性能应该更好

---

**最后更新**: 2026-02-03
**版本**: 2.0
**状态**: 生产就绪
