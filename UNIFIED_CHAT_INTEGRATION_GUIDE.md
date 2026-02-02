# 统一聊天界面 - 集成使用指南

## 📋 概述

这是一个将 **AI 聊天** 和 **NL2SQL 查询** 完整集成的统一界面组件。不需要分开的标签页，用户可以在一个连贯的对话流中完成所有操作。

---

## 🎯 核心功能

### 1. **AI 聊天与 NL2SQL 无缝集成**
- 用户提问 → AI 识别意图 → 自动生成 SQL 建议
- 一键执行查询，结果直接显示在聊天中
- 完整的对话历史记录

### 2. **SQL 查询建议卡片**
```
用户: "查询所有用户"
  ↓
AI: "我来帮您查询用户数据..."
  ↓
[SQL 建议卡片]
  推荐的 SQL 查询
  SELECT * FROM users;
  [复制] [执行查询]
```

### 3. **查询结果可视化**
- 表格展示
- 图表可视化（柱状图、折线图、饼图）
- CSV 导出功能
- 查询元信息（记录数、执行时间等）

### 4. **用户反馈系统**
- 快速反馈（有帮助/不满意）
- 反馈分析仪表板
- 持续改进 AI 效果

### 5. **报表保存功能**
- 一键保存查询为报表
- 重复使用历史查询
- 支持自定义报表名称和描述

---

## 📦 文件结构

```
src/components/
├── UnifiedChat/
│   ├── UnifiedChat.jsx           # 主组件（集成聊天 + NL2SQL）
│   ├── UnifiedChat.css           # 样式文件
│   ├── DataVisualization.jsx     # 数据可视化组件（已有）
│   ├── FeedbackForm.jsx          # 反馈表单组件（已有）
│   ├── FeedbackStats.jsx         # 反馈统计组件（已有）
│   └── ChatHistoryDisplay.jsx    # 聊天历史组件（已有）
├── services/
│   ├── intentRecognizer.ts       # 意图识别服务（已有）
│   ├── queryService.ts           # 查询执行服务（已有）
│   ├── nl2sqlApi.ts              # NL2SQL API 客户端
│   └── chatApi.ts                # AI 聊天 API 客户端
└── hooks/
    └── useData.ts                # 数据管理 Hook（已有）
```

---

## 🚀 快速开始

### 1. 复制文件到项目

```bash
# 复制主组件
cp UNIFIED_CHAT_COMPONENT.jsx src/components/UnifiedChat/UnifiedChat.jsx

# 复制样式
cp UnifiedChat.css src/components/UnifiedChat/
```

### 2. 在主页面中使用

```jsx
import { UnifiedChat } from './components/UnifiedChat/UnifiedChat';

export function MESPage({ sessionId }) {
  return (
    <UnifiedChat
      sessionId={sessionId}
      skipDataGeneration={false}
      setMessages={(msgs) => console.log('Messages updated:', msgs)}
      setIsProcessing={(isProcessing) => console.log('Processing:', isProcessing)}
    />
  );
}
```

### 3. 确保所有依赖服务已实现

```javascript
// services/nl2sqlApi.js - NL2SQL API 客户端
export const nl2sqlApi = {
  checkConnection: async () => {
    // 检查数据库连接状态
    const response = await fetch('/api/query/health');
    return response.json();
  },
  
  executeNLQuery: async (query) => {
    // 执行自然语言查询
    const response = await fetch('/api/query/nl-execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ natural_language: query }),
    });
    return response.json();
  },
};

// services/chatApi.js - AI 聊天 API 客户端
export const chatApi = {
  sendMessage: async (message) => {
    // 调用 AI 聊天接口
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    return response.json();
  },
};
```

---

## 💻 组件 Props

```typescript
interface UnifiedChatProps {
  // 会话 ID（必需）- 用于消息持久化
  sessionId: string;
  
  // 是否跳过数据生成（可选）
  skipDataGeneration?: boolean;
  
  // 向父组件传递消息列表（可选）
  setMessages?: (messages: Message[]) => void;
  
  // 向父组件传递处理状态（可选）
  setIsProcessing?: (isProcessing: boolean) => void;
}
```

---

## 🎨 UI 流程

### 用户交互流程

```
┌─────────────────────────────────────────────────────┐
│  MES 数据智能分析系统                     [反馈分析] │
│  AI 聊天 + NL2SQL 查询集成                [已连接]  │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│  消息区域（可滚动）                                   │
│  ─────────────────────────────────────────────────  │
│  🤖 欢迎消息...                                       │
│                                                      │
│  👤 用户提问：查询所有用户                            │
│                                                      │
│  🤖 AI 响应：我来帮您查询用户数据...                  │
│     ┌──────────────────────────────────────┐        │
│     │ 推荐的 SQL 查询                      │ ▼       │
│     │ SELECT * FROM users;               │        │
│     │ [📋 复制] [▶ 执行查询]               │        │
│     └──────────────────────────────────────┘        │
│                                                      │
│  🤖 查询结果                                          │
│     ┌──────────────────────────────────────┐        │
│     │ ✅ 查询结果（5 条记录）  [📥 导出]   │        │
│     │ ┌─────────────────────────────────┐ │        │
│     │ │ id │ name │ email        │ ...│ │        │
│     │ ├─────────────────────────────────┤ │        │
│     │ │ 1  │ 张三 │ zhangsan@...  │ ...│ │        │
│     │ │ 2  │ 李四 │ lisi@...      │ ...│ │        │
│     │ │ ...                              │ │        │
│     │ └─────────────────────────────────┘ │        │
│     │ [✅ 有帮助] [👎 反馈]               │        │
│     └──────────────────────────────────────┘        │
│                                                      │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│ 快速问题建议                                          │
│ [昨天设备E-001的OEE是多少？] [显示最近一周的OEE...] │
│ [对比A班和B班的生产效率] [查看最近30天的质量...]   │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│ 输入框                                               │
│ [输入您的问题，例如：昨天设备E-001的OEE是多少？] [发送] │
│ 💡 支持自然语言查询 | Shift+Enter 换行 | Enter 发送 │
└─────────────────────────────────────────────────────┘
```

---

## 🔌 API 集成

### 后端 API 要求

组件需要以下后端 API 端点：

#### 1. 健康检查
```
GET /api/query/health

Response:
{
  "service": "NL2SQL Report Backend",
  "status": "healthy",
  "supabase": "connected|disconnected"
}
```

#### 2. NL2SQL 转换与执行
```
POST /api/query/nl-execute

Request:
{
  "natural_language": "查询所有用户"
}

Response:
{
  "success": true,
  "sql": "SELECT * FROM users;",
  "data": [...],
  "count": 5,
  "error": null
}
```

#### 3. AI 聊天（可选）
```
POST /api/chat

Request:
{
  "message": "用户消息",
  "context": {...}
}

Response:
{
  "success": true,
  "content": "AI 响应",
  "actions": ["export", "drilldown"]
}
```

---

## 🎯 使用场景

### 场景 1：简单查询
```
用户: "查询今天的销售额"
  → AI 识别为销售指标查询
  → 生成 SQL: SELECT SUM(amount) FROM sales WHERE DATE(created_at) = TODAY();
  → 用户点击执行
  → 显示结果：总销售额：¥1,234,567
```

### 场景 2：对比分析
```
用户: "对比A班和B班的生产效率"
  → AI 识别为对比分析
  → 生成 SQL 和可视化建议
  → 显示对比结果（柱状图）
  → 用户可以保存为报表供以后使用
```

### 场景 3：趋势分析
```
用户: "显示最近7天的销售趋势"
  → AI 识别为趋势分析
  → 生成 SQL 和折线图
  → 显示趋势可视化
  → 用户可以导出数据或下钻分析
```

---

## 🛠 自定义修改

### 1. 修改快速问题建议

```jsx
const SAMPLE_QUESTIONS = [
  "你的自定义问题 1",
  "你的自定义问题 2",
  // ...
];
```

### 2. 修改样式颜色

```css
/* UnifiedChat.css */
/* 修改主题色 */
--primary-color: #667eea;      /* 改成你想要的颜色 */
--secondary-color: #764ba2;
--success-color: #48bb78;
--error-color: #f56565;
```

### 3. 修改消息持久化方式

```jsx
// 替换 useData hook 的实现
const { createSavedReport, fetchChatMessages, addChatMessage } = useData();

// 改成你自己的数据源
const fetchChatMessages = async (sessionId) => {
  // 从你的数据库或 API 获取
};

const addChatMessage = async (sessionId, message) => {
  // 保存消息到你的数据库或 API
};
```

---

## 🐛 常见问题

### Q1: SQL 建议卡片不显示？
**A:** 检查后端 `nl-to-sql` 端点是否返回 SQL。确保 `result.sql` 不为空。

### Q2: 查询结果不显示？
**A:** 确保数据库连接正常。检查 `checkConnection()` 返回 `connected: true`。

### Q3: 如何添加新的可视化类型？
**A:** 修改 `DataVisualization` 组件，支持更多 `visualizationType` 值。

### Q4: 消息没有保存？
**A:** 检查 `useData` hook 的 `addChatMessage` 实现，确保数据库连接正确。

### Q5: 反馈功能不工作？
**A:** 确保 `FeedbackForm` 和 `FeedbackStats` 组件正确实现，数据库表存在。

---

## 📊 性能优化建议

1. **消息虚拟化**
   - 当消息数量超过 100 时，使用虚拟滚动库（如 `react-window`）

2. **查询结果分页**
   - 显示前 50 条，实现分页或虚拟滚动

3. **API 请求优化**
   - 使用防抖处理输入
   - 实现请求缓存

4. **样式优化**
   - 使用 CSS 变量减少重复代码
   - 按需加载样式

---

## 📝 更新日志

### v1.0 - 2026-02-02
- ✅ 完整的统一聊天界面
- ✅ AI 聊天与 NL2SQL 集成
- ✅ SQL 建议卡片
- ✅ 查询结果可视化
- ✅ 反馈系统
- ✅ 报表保存功能
- ✅ 响应式设计

---

## 🤝 需要帮助？

如有问题或建议，请检查：
1. 所有依赖组件是否正确导入
2. 后端 API 是否正常运行
3. 浏览器控制台是否有错误信息
4. 数据库连接状态

---

## 📄 许可证

MIT License

---

**祝你使用愉快！🎉**
