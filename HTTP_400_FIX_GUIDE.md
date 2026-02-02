# 🔧 HTTP 400 Bad Request 错误诊断和修复指南

## 问题症状

前端调用 `/api/query/recognize-intent` 端点时返回：
```
HTTP 400: Bad Request
```

浏览器控制台错误：
```
HTTP error! status: 400
```

## 🔍 问题根本原因

### 原因 1️⃣: 字段名不匹配 ⭐ **最可能的原因**

**后端期望：**
```json
{
  "query": "用户的查询内容"
}
```

**前端可能发送：**
```json
{
  "natural_language": "用户的查询内容"
}
```

**结果：** 后端找不到 `query` 字段，返回 400 错误

### 原因 2️⃣: 请求体为空

```json
{}  // 空对象
```

### 原因 3️⃣: 查询内容为空或仅空格

```json
{
  "query": ""  // 或 "   "
}
```

### 原因 4️⃣: Content-Type 错误

**正确：**
```
Content-Type: application/json
```

**错误：**
```
Content-Type: text/plain
Content-Type: application/x-www-form-urlencoded
```

## ✅ 已应用的修复

### 修复 1️⃣: 支持多种字段名称

**文件:** `app/routes/query_routes.py` (第 405-480 行)

```python
# 支持多种字段名称（兼容前端不同的实现）
query = data.get('query') or data.get('natural_language')
```

**效果：**
- ✅ 支持 `{"query": "..."}`
- ✅ 支持 `{"natural_language": "..."}`
- ✅ 自动兼容前端的不同实现

### 修复 2️⃣: 详细的诊断日志

```python
# 详细诊断日志
logger.info(f"=== recognize-intent 请求诊断 ===")
logger.info(f"Content-Type: {request.content_type}")
logger.info(f"完整请求体: {data}")
logger.info(f"请求体键: {list(data.keys()) if data else 'None'}")
```

**效果：**
- ✅ 记录完整请求体
- ✅ 记录接收到的字段名
- ✅ 记录 Content-Type
- ✅ 便于后续调试

### 修复 3️⃣: 更好的错误消息

```python
# 返回的 400 错误中包含诊断信息
{
  "success": false,
  "error": "Missing required field: query or natural_language",
  "received_keys": ["natural_language"],  # 告诉前端实际接收到了什么
  "expected_format": {
    "option1": {"query": "your query here"},
    "option2": {"natural_language": "your query here"}
  }
}
```

**效果：**
- ✅ 前端能看到实际接收到的字段
- ✅ 知道应该发送什么格式
- ✅ 更容易调试问题

### 修复 4️⃣: 完整的异常日志

```python
# 捕捉并详细记录所有异常
except Exception as e:
    logger.error(f"=== Error in recognize_intent ===")
    logger.error(f"异常类型: {type(e).__name__}")
    logger.error(f"异常信息: {str(e)}")
    logger.error(f"完整堆栈:", exc_info=True)  # 包含完整堆栈跟踪
```

**效果：**
- ✅ 详细的错误信息
- ✅ 完整的堆栈跟踪
- ✅ 容易定位问题

## 🧪 验证修复

### Step 1: 部署修复到 Render

```bash
cd /Users/fupeggy/NL2SQL

# 确认更改
git status

# 提交
git add app/routes/query_routes.py
git commit -m "Fix HTTP 400 error: support multiple field names and add detailed diagnostics"

# 推送
git push origin main

# 等待 Render 部署（2-3 分钟）
```

### Step 2: 测试新的错误消息

**测试 1️⃣: 发送错误的字段名**

```bash
curl -X POST https://nl2sql-backend-amok.onrender.com/api/query/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{"wrong_field": "查询数据"}'

# 预期响应（现在会告诉你应该发送什么）：
{
  "success": false,
  "error": "Missing required field: query or natural_language",
  "received_keys": ["wrong_field"],
  "expected_format": {
    "option1": {"query": "your query here"},
    "option2": {"natural_language": "your query here"}
  }
}
```

**测试 2️⃣: 使用正确的格式**

```bash
# 格式 1: 使用 "query" 字段
curl -X POST https://nl2sql-backend-amok.onrender.com/api/query/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{"query":"查询wafers表的前300条数据"}'

# 格式 2: 使用 "natural_language" 字段
curl -X POST https://nl2sql-backend-amok.onrender.com/api/query/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{"natural_language":"查询wafers表的前300条数据"}'

# 两个格式都应该返回 200 OK + 意图识别结果
```

### Step 3: 在浏览器中验证

前端应用 → 打开浏览器控制台 (F12) → 运行：

```javascript
// 测试 1: 使用 "query" 字段
fetch('https://nl2sql-backend-amok.onrender.com/api/query/recognize-intent', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: '查询wafers表' })
})
  .then(r => {
    console.log('状态码:', r.status);
    return r.json();
  })
  .then(d => console.log('✅ 成功:', d))
  .catch(e => console.error('❌ 错误:', e));

// 测试 2: 使用 "natural_language" 字段
fetch('https://nl2sql-backend-amok.onrender.com/api/query/recognize-intent', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ natural_language: '查询wafers表' })
})
  .then(r => {
    console.log('状态码:', r.status);
    return r.json();
  })
  .then(d => console.log('✅ 成功:', d))
  .catch(e => console.error('❌ 错误:', e));
```

## 📊 前端修复建议

### 前端应该发送的格式

```javascript
// src/services/nl2sqlApi.js

export async function recognizeIntent(query) {
  try {
    const response = await fetch(
      'https://nl2sql-backend-amok.onrender.com/api/query/recognize-intent',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'  // ← 关键：必须设置这个
        },
        body: JSON.stringify({
          query: query  // ← 使用 "query" 字段
          // 或使用:
          // natural_language: query  // ← 后端也支持这个
        })
      }
    );
    
    if (!response.ok) {
      const error = await response.json();
      console.error('后端错误信息:', error);
      
      // 如果是 400 错误，查看诊断信息
      if (response.status === 400 && error.received_keys) {
        console.error('收到的字段:', error.received_keys);
        console.error('期望格式:', error.expected_format);
      }
      
      throw new Error(`HTTP ${response.status}: ${error.error}`);
    }
    
    const data = await response.json();
    console.log('✅ 意图识别成功:', data);
    
    return data;
    
  } catch (error) {
    console.error('❌ 意图识别失败:', error);
    throw error;
  }
}
```

## 🔍 后端日志查看

### 如何查看 Render 上的日志

1. 访问 [Render Dashboard](https://dashboard.render.com)
2. 找到 `nl2sql-backend-amok` 服务
3. 点击 "Logs" 标签
4. 搜索关键字：`recognize-intent` 或 `Bad Request`
5. 查看详细的诊断日志

### 本地测试时的日志

```bash
# 启动后端
python run.py

# 后台会输出详细日志：
# INFO: === recognize-intent 请求诊断 ===
# INFO: Content-Type: application/json
# INFO: 完整请求体: {'query': '查询数据'}
# INFO: 请求体键: ['query']
# INFO: 处理查询: 查询数据...
# INFO: Intent recognized: direct_query (confidence: 0.95, methods: ['rule', 'llm'])
```

## 🎯 完整的问题解决流程

### 如果仍然收到 400 错误

**Step 1️⃣: 检查请求格式**

```javascript
// 确保发送的是这样的格式：
{
  "query": "你的查询"
}

// 而不是这样：
{
  "natural_language": "你的查询"  // ← 只是选项，两个都支持
}
{
  "q": "你的查询"  // ← 错误的字段名
}
{}  // ← 空对象
```

**Step 2️⃣: 检查 Content-Type**

```javascript
// 必须设置：
headers: {
  'Content-Type': 'application/json'
}

// 检查浏览器 DevTools → Network 标签 → 查看请求头
```

**Step 3️⃣: 检查查询内容**

```javascript
// 查询不能为空
{
  "query": "某个查询"  // ← 正确
}

{
  "query": ""  // ← 错误：空字符串
}

{
  "query": "   "  // ← 错误：仅空格
}
```

**Step 4️⃣: 查看诊断信息**

如果返回 400，检查响应体中的 `received_keys` 和 `expected_format` 字段，了解：
- 实际接收到了什么字段名
- 应该发送什么格式

**Step 5️⃣: 检查 Render 日志**

如果问题仍未解决，查看 Render Dashboard 的日志：
- 搜索 `recognize-intent`
- 查看 `异常类型` 和 `异常信息`
- 查看完整的堆栈跟踪

## 📝 请求/响应示例

### ✅ 成功的请求

```bash
curl -X POST https://nl2sql-backend-amok.onrender.com/api/query/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{"query":"查询wafers表的前300条数据"}'
```

**响应（200 OK）：**
```json
{
  "success": true,
  "intent": "direct_query",
  "confidence": 0.95,
  "entities": {
    "table": "wafers",
    "limit": 300
  },
  "methodsUsed": ["rule", "llm"],
  "reasoning": "用户明确请求查询 wafers 表的前 300 条数据"
}
```

### ❌ 失败的请求

**请求 1: 缺少字段**
```bash
curl -X POST https://nl2sql-backend-amok.onrender.com/api/query/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{}'
```

**响应（400 Bad Request）：**
```json
{
  "success": false,
  "error": "Missing required field: query or natural_language",
  "received_keys": [],
  "expected_format": {
    "option1": {"query": "your query here"},
    "option2": {"natural_language": "your query here"}
  }
}
```

**请求 2: 字段名错误**
```bash
curl -X POST https://nl2sql-backend-amok.onrender.com/api/query/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{"q":"查询数据"}'
```

**响应（400 Bad Request）：**
```json
{
  "success": false,
  "error": "Missing required field: query or natural_language",
  "received_keys": ["q"],  // ← 告诉你发送了什么
  "expected_format": {
    "option1": {"query": "your query here"},
    "option2": {"natural_language": "your query here"}
  }
}
```

## ✨ 修复要点总结

| 修复 | 说明 | 效果 |
|------|------|------|
| 支持多字段 | 同时支持 `query` 和 `natural_language` | ✅ 更灵活 |
| 详细日志 | 记录完整请求体和字段信息 | ✅ 更容易调试 |
| 诊断信息 | 400 错误中包含收到的字段和期望格式 | ✅ 自解释的错误消息 |
| 异常捕捉 | 完整的异常日志和堆栈跟踪 | ✅ 快速定位问题 |

## 🚀 部署步骤

```bash
# 1. 提交修改
git add app/routes/query_routes.py
git commit -m "Fix HTTP 400 error: support multiple field names and add detailed diagnostics"

# 2. 推送到 GitHub
git push origin main

# 3. 等待 Render 部署（2-3 分钟）

# 4. 测试修复
curl -X POST https://nl2sql-backend-amok.onrender.com/api/query/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{"query":"测试"}'
```

---

**版本:** 2026-02-03  
**修复内容:** HTTP 400 错误诊断和多字段支持  
**优先级:** 🔴 高
