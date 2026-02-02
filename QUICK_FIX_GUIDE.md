# 🚀 5 分钟快速修复指南

针对前端错误 `Failed to fetch` 和后端 `supabase: disconnected` 的完整解决方案

---

## 问题症状

```
❌ Connection check failed: TypeError: Failed to fetch
⚠️ supabase: disconnected
```

---

## 🔧 解决方案（选择一个）

### 方案 A：完整配置（推荐）- 5 分钟

#### Step 1：获取 Supabase 凭证（2 分钟）

1. 打开 [Supabase Dashboard](https://app.supabase.com)
2. 选择你的项目
3. 进入 **Settings** → **API**
4. 复制这两个值：
   - **Project URL** 
   - **Service Role Secret** （⚠️ 注意不是 `anon key`）

![Supabase API 页面](/path-to-screenshot)

#### Step 2：在 Render 中添加环境变量（2 分钟）

1. 打开 [Render Dashboard](https://dashboard.render.com)
2. 选择 `nl2sql-backend-amok` 服务
3. 进入 **Environment** 标签页
4. 添加两个新变量：

```
SUPABASE_URL = https://你的项目.supabase.co
SUPABASE_SERVICE_KEY = 你的服务密钥
```

5. 点击 **Save Changes** - 自动重新部署

#### Step 3：验证连接（1 分钟）

在浏览器 Console 中运行：

```javascript
fetch('https://nl2sql-backend-amok.onrender.com/api/query/health')
  .then(r => r.json())
  .then(console.log)
```

✅ 如果看到 `"supabase": "connected"` 就成功了！

---

### 方案 B：快速修复（如果不需要 Supabase）- 3 分钟

如果你暂时不需要 Supabase 功能，只想让 NL2SQL 转换正常工作：

#### Step 1：更新前端 API 配置

在你的 Bolt 项目中，找到或创建 `src/services/nl2sqlApi.js`：

```javascript
// 替换为你的后端 URL
const API_BASE_URL = 'https://nl2sql-backend-amok.onrender.com/api/query';

export const nl2sqlApi = {
  checkConnection: async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/health`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Connection check failed:', error);
      return { connected: false, error: error.message };
    }
  },

  executeNLQuery: async (query) => {
    try {
      const response = await fetch(`${API_BASE_URL}/nl-execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ natural_language: query }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Query execution failed:', error);
      return { success: false, error: error.message };
    }
  },
};

export default nl2sqlApi;
```

#### Step 2：在统一聊天组件中使用

确保组件正确导入：

```jsx
import nl2sqlApi from './services/nl2sqlApi';

// 在组件中已经正确使用了
```

#### Step 3：测试

刷新浏览器，应该看到连接状态改善。

---

## 🧪 诊断测试

### 运行诊断脚本

如果你有命令行环境：

```bash
cd /Users/fupeggy/NL2SQL
bash check-connection.sh
```

### 手动测试

在浏览器 Console 中依次运行：

```javascript
// 测试 1：检查后端连接
console.log('🔍 测试 1：后端连接...');
fetch('https://nl2sql-backend-amok.onrender.com/api/query/health')
  .then(r => r.json())
  .then(data => {
    console.log('✅ 后端响应:', data);
    console.log('Supabase 状态:', data.supabase);
  })
  .catch(err => console.error('❌ 失败:', err));

// 测试 2：执行简单查询（30 秒后）
setTimeout(() => {
  console.log('🔍 测试 2：NL 转 SQL...');
  fetch('https://nl2sql-backend-amok.onrender.com/api/query/nl-to-sql', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ natural_language: '查询所有用户' })
  })
    .then(r => r.json())
    .then(data => {
      console.log('✅ 转换结果:', data);
    })
    .catch(err => console.error('❌ 失败:', err));
}, 30000);
```

---

## 📊 预期结果

### ✅ 成功状态

```json
{
  "service": "NL2SQL Report Backend",
  "status": "healthy",
  "supabase": "connected"
}
```

### ⚠️ 部分成功（可以接受）

如果后端响应但 Supabase 未连接：

```json
{
  "service": "NL2SQL Report Backend",
  "status": "healthy",
  "supabase": "disconnected"
}
```

**这是正常的！** 因为：
- NL2SQL 转换功能 ✅ 工作
- 数据库查询功能 ❌ 需要 Supabase 凭证

### ❌ 失败状态

```
TypeError: Failed to fetch
```

**原因排查：**
1. ❌ 网络连接问题
2. ❌ 后端 URL 错误
3. ❌ 后端服务未启动
4. ❌ CORS 配置问题

---

## 🔍 常见问题速查表

| 问题 | 原因 | 解决方案 |
|-----|-----|--------|
| `Failed to fetch` | 网络/后端问题 | 检查 URL，检查 Render 日志 |
| `supabase: disconnected` | 缺少环境变量 | 添加 `SUPABASE_URL` 和 `SUPABASE_SERVICE_KEY` |
| HTTP 404 | 端点错误 | 检查 API URL 格式 |
| HTTP 500 | 服务器错误 | 检查 Render 日志 |
| CORS 错误 | 跨域问题 | 已在后端配置，检查前端 URL |

---

## 📝 检查清单

修复前逐项确认：

- [ ] 我已获取 Supabase 的 Project URL
- [ ] 我已获取 Supabase 的 Service Role Secret
- [ ] 我已在 Render 仪表板添加这两个环境变量
- [ ] Render 服务已重新部署
- [ ] 我已更新前端 `nl2sqlApi.js` 中的 API URL
- [ ] 我已在浏览器 Console 中测试连接
- [ ] 连接测试返回 `status: "healthy"`

---

## 🆘 还是不行？

请收集以下信息：

```javascript
// 1. 复制这个诊断代码
(async () => {
  const diag = {
    timestamp: new Date().toISOString(),
    backend_url: 'https://nl2sql-backend-amok.onrender.com',
  };
  
  try {
    const r = await fetch('https://nl2sql-backend-amok.onrender.com/api/query/health');
    diag.http_status = r.status;
    diag.response = await r.json();
  } catch (e) {
    diag.error = e.message;
  }
  
  console.log(JSON.stringify(diag, null, 2));
})();

// 2. 复制输出结果并告诉我
```

---

## ✨ 成功的标志

当一切正常时，你应该看到：

1. **Render 日志中：**
   ```
   ✅ Supabase client initialized successfully
   ```

2. **浏览器中：**
   ```
   ✅ 已连接 (顶部状态显示)
   ```

3. **功能测试：**
   - 输入自然语言查询 ✅
   - SQL 建议卡片出现 ✅
   - 点击执行返回结果 ✅

---

## 📞 需要更多帮助？

- 查看完整的 `TROUBLESHOOTING_GUIDE.md`
- 检查 Render 服务的实时日志
- 查看浏览器开发者工具的 Network 标签页

祝你修复顺利！🎉
