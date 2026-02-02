# 意图识别 API 格式对应指南

## 概述

本文档说明后端意图识别 API 如何返回与前端 `UserIntent` 接口兼容的数据格式。

## 前端 UserIntent 接口定义

前端在 `modules/mes/services/intentRecognizer.ts` 中定义的接口：

```typescript
export interface UserIntent {
  type: 'query' | 'report' | 'analysis' | 'comparison' | 'direct_table_query';
  entities: {
    metric: string;
    timeRange: string;
    equipment: string[];
    shift: string[];
    comparison: boolean;
    tableName?: string;
    limit?: number;
  };
  confidence: number;
  clarifications: string[];
}
```

## 后端 API 端点

**URL**: `POST /api/query/recognize-intent`

**请求格式**:
```json
{
  "query": "查询wafers表的前300条数据"
}
```

**响应格式** (已转换为前端兼容格式):
```json
{
  "type": "direct_table_query",
  "entities": {
    "metric": "general",
    "timeRange": "",
    "equipment": [],
    "shift": [],
    "comparison": false,
    "tableName": "wafers",
    "limit": 300
  },
  "confidence": 0.95,
  "clarifications": []
}
```

## 格式转换规则

### 1. 意图类型映射

后端内部使用的意图类型 → 前端期望的 UserIntent.type

| 后端意图 | 前端类型 | 场景 |
|---------|---------|------|
| `direct_query` | `direct_table_query` | 用户直接查询表数据 |
| `query_production` | `query` | 查询生产数据 |
| `query_quality` | `query` | 查询质量数据 |
| `query_equipment` | `query` | 查询设备数据 |
| `generate_report` | `report` | 生成报表 |
| `compare_analysis` | `analysis` | 分析对比 |

### 2. 实体字段映射

#### metric (指标)
```python
后端: result.get('entities', {}).get('metric', 'general')
前端: entities.metric

示例值: 'oee', 'yield', 'efficiency', 'availability', 'quality', 'downtime', 'general'
```

#### timeRange (时间范围)
```python
后端: result.get('entities', {}).get('timeRange', '')
前端: entities.timeRange

示例值: 'today', 'yesterday', 'this_week', 'last_week', 'this_month', 'last_month', 'last_7_days', 'last_30_days'
```

#### equipment (设备列表)
```python
后端: 
  - 来自 result['entities']['equipment'] 或
  - 来自 result['entities']['equipmentId']
前端: entities.equipment

必须是数组格式，如: ['E-001', 'E-002']
```

#### shift (班次列表)
```python
后端: result.get('entities', {}).get('shift', [])
前端: entities.shift

必须是数组格式，如: ['A', 'B', 'C']
```

#### comparison (是否对比)
```python
后端: result.get('entities', {}).get('comparison', False)
前端: entities.comparison

布尔值，自动检测用户意图中是否有对比关键词
```

#### tableName (可选 - 直接查询)
```python
后端: result.get('entities', {}).get('tableName', '')
前端: entities.tableName?

仅在 type === 'direct_table_query' 时包含
示例值: 'wafers', 'users', 'chat_sessions'
```

#### limit (可选 - 直接查询)
```python
后端: result.get('entities', {}).get('limit')
前端: entities.limit?

仅在 type === 'direct_table_query' 时包含
示例值: 100, 300, 500 等
```

### 3. 置信度 (confidence)

```python
后端返回: 0.0 - 1.0 之间的浮点数
前端期望: 相同格式

含义:
- 0.9 - 1.0: 非常高的置信度 (规则精确匹配或 LLM 确认)
- 0.8 - 0.9: 高置信度 (规则匹配或部分 LLM 确认)
- 0.5 - 0.8: 中等置信度 (需要澄清)
- 0.0 - 0.5: 低置信度 (建议进一步询问用户)
```

### 4. 澄清问题 (clarifications)

```python
后端返回: 字符串数组
前端期望: 相同格式

当置信度较低或信息不完整时，自动生成澄清问题

示例:
[
  "请指定具体的产品线",
  "您想了解哪个具体指标？• OEE • 良率 • 稼动率"
]
```

## 实现细节

### 后端转换流程

```python
# 1. 用户发送请求
POST /api/query/recognize-intent
{
  "query": "查询今天的产量"
}

# 2. 后端识别意图
recognizer.recognize(query)
# 返回:
# {
#   'intent': 'query_production',
#   'confidence': 0.92,
#   'entities': {...},
#   'clarifications': [...],
#   'methodsUsed': ['rule', 'llm']
# }

# 3. 转换为前端格式
recognizer.to_frontend_format(result)
# 返回:
# {
#   'type': 'query',  # 转换后
#   'entities': {...},  # 标准化
#   'confidence': 0.92,
#   'clarifications': [...]
# }

# 4. 返回给前端
return jsonify(user_intent)
```

### 前端集成示例

```typescript
// 调用后端 API
const response = await fetch('/api/query/recognize-intent', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: userInput })
});

const userIntent: UserIntent = await response.json();

// 根据 type 处理
switch (userIntent.type) {
  case 'direct_table_query':
    // 直接执行表查询
    queryTable(userIntent.entities.tableName, userIntent.entities.limit);
    break;
  
  case 'query':
    // 执行数据查询
    queryData(userIntent.entities);
    break;
  
  case 'report':
    // 生成报表
    generateReport(userIntent.entities);
    break;
  
  case 'analysis':
    // 执行分析
    analyzeData(userIntent.entities);
    break;
}

// 处理澄清问题
if (userIntent.clarifications.length > 0) {
  showClarificationDialog(userIntent.clarifications);
}
```

## 完整示例

### 示例 1: 直接表查询

**输入**:
```json
{
  "query": "返回 wafers 表的前300条数据"
}
```

**后端处理**:
```python
result = recognizer.recognize("返回 wafers 表的前300条数据")
# {
#   'success': True,
#   'intent': 'direct_query',
#   'confidence': 0.95,
#   'entities': {
#     'tableName': 'wafers',
#     'limit': 300,
#     'metric': 'general',
#     'timeRange': '',
#     'equipment': [],
#     'shift': [],
#     'comparison': False
#   },
#   'clarifications': [],
#   'methodsUsed': ['rule']
# }

frontend_result = recognizer.to_frontend_format(result)
```

**返回给前端**:
```json
{
  "type": "direct_table_query",
  "entities": {
    "metric": "general",
    "timeRange": "",
    "equipment": [],
    "shift": [],
    "comparison": false,
    "tableName": "wafers",
    "limit": 300
  },
  "confidence": 0.95,
  "clarifications": []
}
```

### 示例 2: 复杂分析

**输入**:
```json
{
  "query": "比较最近7天和上月的设备OEE"
}
```

**后端处理**:
```python
result = recognizer.recognize("比较最近7天和上月的设备OEE")
# {
#   'success': True,
#   'intent': 'compare_analysis',
#   'confidence': 0.88,
#   'entities': {
#     'metric': 'oee',
#     'timeRange': 'last_7_days',
#     'equipment': [],
#     'shift': [],
#     'comparison': True
#   },
#   'clarifications': ['请指定具体的设备ID'],
#   'methodsUsed': ['rule', 'llm']
# }

frontend_result = recognizer.to_frontend_format(result)
```

**返回给前端**:
```json
{
  "type": "analysis",
  "entities": {
    "metric": "oee",
    "timeRange": "last_7_days",
    "equipment": [],
    "shift": [],
    "comparison": true
  },
  "confidence": 0.88,
  "clarifications": ["请指定具体的设备ID"]
}
```

### 示例 3: 不完整的质量查询

**输入**:
```json
{
  "query": "本月的质量数据"
}
```

**后端处理**:
```python
result = recognizer.recognize("本月的质量数据")
# {
#   'success': True,
#   'intent': 'query_quality',
#   'confidence': 0.65,
#   'entities': {
#     'metric': 'general',
#     'timeRange': 'this_month',
#     'equipment': [],
#     'shift': [],
#     'comparison': False
#   },
#   'clarifications': [
#     '您想了解哪个质量指标？• 良品率 • 合格率 • 缺陷率'
#   ],
#   'methodsUsed': ['rule']
# }

frontend_result = recognizer.to_frontend_format(result)
```

**返回给前端**:
```json
{
  "type": "query",
  "entities": {
    "metric": "general",
    "timeRange": "this_month",
    "equipment": [],
    "shift": [],
    "comparison": false
  },
  "confidence": 0.65,
  "clarifications": ["您想了解哪个质量指标？• 良品率 • 合格率 • 缺陷率"]
}
```

## 验证工具

### 运行格式验证测试

```bash
# 离线测试格式转换
TEST_OFFLINE=1 python test_intent_api_format.py

# 在线测试 API 端点
python test_intent_api_format.py
```

### 检查列表

前端集成时的检查清单：

- [ ] API 端点 `/api/query/recognize-intent` 已部署
- [ ] 响应格式中 `type` 字段值是否为: `query`, `report`, `analysis`, `comparison`, `direct_table_query` 之一
- [ ] `entities` 对象包含所有必需字段：`metric`, `timeRange`, `equipment`, `shift`, `comparison`
- [ ] `equipment` 和 `shift` 都是数组格式
- [ ] `confidence` 是 0-1 之间的数字
- [ ] `clarifications` 是字符串数组
- [ ] 对于 `direct_table_query` 类型，确保包含 `tableName` 和 `limit` 字段
- [ ] 对于其他类型，这两个字段应该不存在或为 null
- [ ] 后端返回的 HTTP 状态码是 200（成功）或 400/500（错误）

## 错误处理

### 前端应该如何处理错误

```typescript
try {
  const response = await fetch('/api/query/recognize-intent', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: userInput })
  });

  if (!response.ok) {
    // 处理 HTTP 错误
    const error = await response.json();
    console.error('API Error:', error.error || error.message);
    return;
  }

  const userIntent: UserIntent = await response.json();
  
  // 验证必需字段
  if (!userIntent.type || !userIntent.entities || userIntent.confidence === undefined) {
    console.error('Invalid UserIntent format');
    return;
  }

  // 处理意图
  handleUserIntent(userIntent);

} catch (error) {
  console.error('Network error:', error);
}
```

## 常见问题

**Q1: 为什么后端意图和前端类型不一样？**

A: 后端使用更细粒度的意图分类（如 `query_production`, `query_quality` 等），而前端将它们合并为通用类型 (`query`)。这样可以在前端进行统一的 UI 处理，同时保持后端的灵活性。

**Q2: clarifications 什么时候会显示？**

A: 当识别的置信度较低或缺少关键信息时，系统会自动生成澄清问题。前端应该在 `clarifications.length > 0` 时显示这些问题。

**Q3: equipment 为什么是数组而不是字符串？**

A: 因为用户可能查询多个设备的数据（如对比分析），因此使用数组格式以支持多值情况。

**Q4: tableName 和 limit 什么时候出现？**

A: 仅当 `type === 'direct_table_query'` 时，这两个字段才会在 `entities` 对象中出现。其他类型不会包含这两个字段。

## 相关资源

- 前端服务: `modules/mes/services/intentRecognizer.ts`
- 后端服务: `app/services/intent_recognizer.py`
- API 路由: `app/routes/query_routes.py` → `/api/query/recognize-intent`
- 测试脚本: `test_intent_api_format.py`
