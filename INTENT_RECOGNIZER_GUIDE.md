# Intent Recognizer Service - 混合规则+LLM意图识别

## 概述

This service implements a **hybrid approach** combining rule-based matching and LLM for intelligent user intent recognition in MES (Manufacturing Execution System) applications.

### 核心特性

✅ **轻量级规则引擎** - 毫秒级响应
✅ **LLM 确认** - 不确定时调用 DeepSeek API
✅ **实体提取** - 自动提取时间、指标、表名等信息
✅ **动态澄清** - 根据意图自动生成澄清问题
✅ **TypeScript 类型安全** - 完整的类型定义

## 架构

```
User Input
    ↓
[Rule-based Matching] ← Fast, low latency
    ↓
Confidence > 0.8?
    ├─ YES → Return Result
    ├─ NO → Continue
    ↓
[LLM Confirmation] ← Accurate, handles complex cases
    ↓
[Merge Results] ← Combine both methods
    ↓
[Determine Clarifications] ← Auto-generate if needed
    ↓
Return Intent + Clarifications + Entities
```

## 支持的意图类型

| Intent | 关键词 | 实体示例 |
|--------|--------|---------|
| `direct_query` | 查询、返回、显示、SELECT | table, limit |
| `query_production` | 产量、生产、产出 | timeRange, productLine |
| `query_quality` | 良品率、合格率、质量 | timeRange, metrics, defectType |
| `query_equipment` | 设备、OEE、稼动率、故障 | timeRange, equipment, metrics |
| `generate_report` | 报表、生成、导出、汇总 | reportType, timeRange |
| `compare_analysis` | 对比、比较、同比、趋势 | timeRange, metrics |

## 使用方法

### 1. 异步方式（推荐用于后端和React异步操作）

```typescript
import { recognizeIntent } from './services/intentRecognizer';

// 带 LLM 确认的完整分析
const result = await recognizeIntent('查询本月各产线的良品率');

console.log(result);
// {
//   type: 'compare_analysis',
//   confidence: 0.92,
//   entities: {
//     timeRange: 'this_month',
//     metrics: ['yield_rate'],
//     productLine: undefined
//   },
//   clarifications: ['请指定具体的产品线或产品类型'],
//   methodsUsed: ['rule', 'llm']
// }
```

### 2. 同步方式（快速响应，规则引擎只）

```typescript
import { recognizeIntentSync } from './services/intentRecognizer';

// 快速规则匹配（无 LLM 调用）
const result = recognizeIntentSync('返回 wafers 表的前300条数据');

console.log(result);
// {
//   type: 'direct_query',
//   confidence: 0.95,
//   entities: {
//     table: 'wafers',
//     limit: 300
//   },
//   clarifications: [],
//   methodsUsed: ['rule']
// }
```

### 3. 在 React 组件中使用

```typescript
import { recognizeIntentSync, recognizeIntent } from './services/intentRecognizer';

function ChatInput() {
  const [userInput, setUserInput] = useState('');
  const [intent, setIntent] = useState<Intent | null>(null);

  const handleInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const input = e.target.value;
    setUserInput(input);

    // 第一步：快速规则匹配
    const syncResult = recognizeIntentSync(input);
    
    if (syncResult.confidence > 0.8) {
      // 高置信度：直接使用规则结果
      setIntent(syncResult);
    } else {
      // 低置信度：调用 LLM 确认（异步）
      const asyncResult = await recognizeIntent(input);
      setIntent(asyncResult);
    }
  };

  return (
    <div>
      <input 
        value={userInput}
        onChange={handleInputChange}
        placeholder="输入您的查询..."
      />
      
      {intent && (
        <div>
          <p>Intent Type: {intent.type}</p>
          <p>Confidence: {(intent.confidence * 100).toFixed(0)}%</p>
          
          {intent.clarifications.length > 0 && (
            <div className="clarifications">
              <h4>需要澄清：</h4>
              {intent.clarifications.map((c, i) => (
                <p key={i}>• {c}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

## 环境配置

### 如果使用 LLM 功能（可选）

在 `.env` 或 `.env.local` 中设置：

```bash
REACT_APP_DEEPSEEK_API_KEY=sk_your_deepseek_api_key_here
```

如果未配置或 API 不可用，系统会自动降级到规则引擎只模式。

## 返回值详解

### Intent 接口

```typescript
export interface Intent {
  type: 'direct_query' | 'analysis' | 'report' | 'query_equipment' | 'compare_analysis' | 'other';
  clarifications: string[];  // 需要澄清的问题
  entities: {
    table?: string;           // 表名
    metric?: string;          // 指标名
    timeRange?: string;       // 时间范围
    filters?: Record<string, any>;
    productLine?: string;     // 产品线
    equipment?: string;       // 设备ID
    defectType?: string;      // 缺陷类型
    metrics?: string[];       // 多个指标
  };
  confidence: number;         // 置信度 0-1
  methodsUsed: ('rule' | 'llm')[]; // 使用的方法
}
```

## 性能特性

| 方法 | 响应时间 | 准确率 | 用途 |
|------|---------|--------|------|
| 规则引擎 | 1-5ms | 85%+ | 直接查询、明确指令 |
| LLM | 500-2000ms | 95%+ | 复杂查询、模糊意图 |
| 混合 | 5-2000ms | 95%+ | 平衡速度和准确率 |

## 实体提取规则

### 时间范围提取

```
今天、昨天 → 'today' / 'yesterday'
本周、上周 → 'this_week' / 'last_week'
本月、上月 → 'this_month' / 'last_month'
最近7天、过去30天 → '7 天' / '30 天'
2024年2月 → '2024-02'
```

### 指标提取

```
产量 → 'output_qty'
良品率、良率 → 'yield_rate'
OEE → 'oee'
稼动率 → 'utilization_rate'
效率 → 'efficiency'
停机 → 'downtime'
```

## 澄清问题生成逻辑

系统根据意图类型自动生成澄清问题：

### 生产查询
- 缺少时间范围？→ "请指定您想查询的时间范围（如：今天、本周、上月）"
- 缺少产品线？→ "请指定具体的产品线或产品类型"

### 质量查询
- 缺少指标？→ "您想了解哪个质量指标？• 良品率 • 合格率 • 缺陷率"

### 设备查询
- 缺少指标？→ "您想了解哪个设备指标？• OEE • 稼动率 • 故障时间"

### 报表生成
- 缺少报表类型？→ "请指定报表类型（如：日报、周报、月报）"

## 集成示例

### 后端 Express 集成

```typescript
import express from 'express';
import { recognizeIntent } from './services/intentRecognizer';

const app = express();

app.post('/api/intent-analysis', async (req, res) => {
  const { userInput } = req.body;
  
  try {
    const result = await recognizeIntent(userInput);
    res.json({
      success: true,
      intent: result
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});
```

### 前端 React 集成

```typescript
async function analyzeUserInput(input: string) {
  const response = await fetch('/api/intent-analysis', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ userInput: input })
  });
  
  const data = await response.json();
  return data.intent;
}
```

## 测试

运行测试套件：

```bash
# 运行同步测试
npm run test:intent:sync

# 运行异步测试（需要 API key）
npm run test:intent:async

# 性能测试
npm run test:intent:performance
```

## 最佳实践

### 1. 选择合适的方法

```typescript
// ✅ 直接查询 → 使用同步方法
if (input.includes('表') && input.includes('查询')) {
  const result = recognizeIntentSync(input);
}

// ✅ 复杂分析 → 使用异步方法
if (needsHighAccuracy) {
  const result = await recognizeIntent(input);
}
```

### 2. 处理澄清问题

```typescript
const result = await recognizeIntent(userInput);

if (result.clarifications.length > 0) {
  // 向用户显示澄清问题
  showClarificationDialog(result.clarifications);
  // 等待用户输入后再执行查询
} else {
  // 直接执行查询
  executeQuery(result);
}
```

### 3. 缓存和重用结果

```typescript
// 缓存意图识别结果（相同输入 5 分钟内复用）
const intentCache = new Map<string, Intent>();
const CACHE_TTL = 5 * 60 * 1000;

async function getIntent(input: string): Promise<Intent> {
  const cached = intentCache.get(input);
  if (cached) return cached;
  
  const result = await recognizeIntent(input);
  intentCache.set(input, result);
  setTimeout(() => intentCache.delete(input), CACHE_TTL);
  
  return result;
}
```

## 故障排查

### 问题 1: LLM 调用失败

**症状**: LLM 方法总是返回 confidence: 0

**解决方案**:
1. 检查 API Key: `console.log(process.env.REACT_APP_DEEPSEEK_API_KEY)`
2. 检查网络连接
3. 查看浏览器控制台错误日志
4. 系统会自动降级到规则引擎

### 问题 2: 实体提取不准确

**症状**: 提取的 timeRange 为 undefined

**解决方案**:
1. 检查时间表达是否符合支持的格式
2. 使用标准表达："最近7天" 而不是 "最近一个礼拜"
3. 考虑添加自定义时间解析规则

### 问题 3: 意图识别错误

**症状**: 意图类型错误或置信度过低

**解决方案**:
1. 在 INTENT_CONFIG 中添加更多关键词
2. 调整规则的权重
3. 对于持续问题的输入，使用 LLM 确认
4. 收集错误样本，用于改进模型

## 扩展开发

### 添加新的意图类型

```typescript
// 1. 在 INTENT_CONFIG 中添加
const INTENT_CONFIG = {
  // ...existing intents...
  query_inventory: {
    keywords: ['库存', '库存量', '库位', '货物'],
    entities: ['timeRange', 'productType', 'location']
  }
};

// 2. 在澄清逻辑中添加
case 'query_inventory':
  if (!entities.productType) {
    clarifications.push('请指定产品类型');
  }
  break;

// 3. 更新 Intent 类型
type IntentType = 'direct_query' | ... | 'query_inventory';
```

### 自定义实体提取

```typescript
function extractCustomEntities(input: string): Record<string, any> {
  const customEntities: Record<string, any> = {};
  
  // 提取工序号
  const processMatch = input.match(/工序(\d+)/);
  if (processMatch) {
    customEntities.processId = processMatch[1];
  }
  
  return customEntities;
}
```

## 许可证

MIT
