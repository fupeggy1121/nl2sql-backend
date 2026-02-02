# 修复说明：AI聊天固定回复问题

## 问题描述
前端AI报表页面在用户输入"返回 wafers 表的前300条数据"时，始终返回固定的澄清消息，而不是执行数据库查询。

## 根本原因
在 `UNIFIED_CHAT_COMPONENT.jsx` 的 `handleSendMessage()` 函数中（第154-175行），代码流程如下：

```jsx
const intent = intentRecognizer.recognizeIntent(input);

if (intent.clarifications.length > 0) {
  // 显示澄清消息
  const clarificationMessage: Message = {
    content: `我理解您想查询相关数据。为了更准确地回答，请确认：\n\n${intent.clarifications.join('\n')}`,
  };
  // ...显示澄清消息
} else {
  // 执行查询
  const result = await queryService.executeQuery(intent);
}
```

问题是 `intentRecognizer.recognizeIntent()` 返回的意图对象中 `clarifications` 数组不为空，导致系统进入澄清分支而不是执行查询分支。

## 解决方案
创建了新的 `intentRecognizer` 服务（`services/intentRecognizer.js`），该服务能够：

### 1. 识别直接表查询
检测以下类型的查询，并标记为直接查询（不需要澄清）：
- "返回 wafers 表的前300条数据"
- "查询 wafers 表"
- "显示 wafers 表"
- "SELECT * FROM wafers LIMIT 300"

### 2. 只在必要时请求澄清
对于分析型查询，只在缺少具体指标时才请求澄清：
- ✅ "OEE趋势" → 不需要澄清（已指定指标OEE）
- ❌ "生产数据" → 需要澄清（未指定具体指标）

### 3. 提取查询实体
自动从用户输入中提取：
- 表名：wafers
- 限制：300
- 时间范围：最近7天
- 指标：OEE、良率等

## 关键代码片段

```javascript
function recognizeIntent(input) {
  // 如果是直接表查询，不需要澄清
  if (isDirectTableQuery(input)) {
    return {
      type: 'direct_query',
      clarifications: [], // 空数组 = 不显示澄清消息
      entities: {
        table: extractedTable,
        filters: extractedFilters,
      },
      confidence: 0.95,
    };
  }

  // 对于分析查询，检查是否需要澄清
  if (isAnalysisQuery && !hasSpecificMetric) {
    return {
      type: 'analysis',
      clarifications: [
        '您想了解哪个具体指标？',
        '• OEE',
        '• 良率',
        // ...
      ],
      confidence: 0.6,
    };
  }

  return {
    type: 'other',
    clarifications: [],
    confidence: 0.5,
  };
}
```

## 文件变更

### 新增文件
- `/Users/fupeggy/NL2SQL/services/intentRecognizer.js` - JavaScript 版本
- `/Users/fupeggy/NL2SQL/services/intentRecognizer.ts` - TypeScript 版本

## 预期行为变化

### 修复前
用户输入：`返回 wafers 表的前300条数据`
系统响应：`我理解您想查询相关数据。为了更准确地回答，请确认：您想了解哪个具体指标？（OEE、良率、效率等）`
结果：❌ 查询未执行

### 修复后
用户输入：`返回 wafers 表的前300条数据`
系统响应：直接执行查询，返回 wafers 表的前300条数据
结果：✅ 查询成功执行

## 测试用例

以下输入应该直接执行查询（不显示澄清消息）：
```
✅ "返回 wafers 表的前300条数据"
✅ "查询 wafers 表"
✅ "显示 users 表前100条"
✅ "SELECT * FROM products LIMIT 50"
✅ "获取 orders 表"
```

以下输入应该只在需要时显示澄清消息：
```
❓ "生产数据分析" → 需要澄清指标
❓ "生产效率" → 需要澄清时间范围
✅ "OEE趋势" → 已指定指标，不需要澄清
✅ "最近7天良率" → 已指定指标和时间范围，不需要澄清
```

## 验证步骤

1. 确保 `services/intentRecognizer.js` 文件存在
2. 在浏览器中访问 AI 报表页面
3. 输入：`返回 wafers 表的前300条数据`
4. 验证：应该看到数据结果，而不是澄清消息
5. 测试其他查询以确保澄清功能在需要时仍然正常工作

## 注意事项

- 确保 `intentRecognizer` 文件与 `UNIFIED_CHAT_COMPONENT.jsx` 的导入路径匹配
- 导入路径为 `../services/intentRecognizer`
- 该服务导出一个包含 `recognizeIntent` 方法的对象

## 后续优化建议

1. **增强表名识别** - 支持更多表名变体和别名
2. **改进限制检测** - 支持 OFFSET、ORDER BY 等子句
3. **多语言支持** - 英文和中文混合查询
4. **学习模型** - 基于用户反馈改进意图识别准确度
5. **缓存常用查询** - 加速频繁查询的执行
