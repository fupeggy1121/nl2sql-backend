# 🎯 Render 环境变量配置详细步骤

## 📍 第一步：获取 Supabase 凭证

### 访问 Supabase 仪表板

```
https://app.supabase.com
```

1. 登录你的 Supabase 账户
2. 选择你的项目（通常命名为 NL2SQL 或类似）
3. 左侧菜单中找到 **Settings** (⚙️ 图标)
4. 点击 **API**

### 在 API 页面找到：

```
┌─────────────────────────────────────────────┐
│ Supabase API Reference                      │
├─────────────────────────────────────────────┤
│                                             │
│ Project URL:                                │
│ https://kgmyhukvyygudsllypgv.supabase.co    │ ← 复制这个
│                                             │
│ Service Role Secret:                        │
│ eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...   │ ← 复制这个
│                                             │
│ Anon Public:                                │
│ eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...   │ ⚠️ 不要用这个
│                                             │
└─────────────────────────────────────────────┘
```

**注意：**
- ✅ 使用 **Service Role Secret**（权限完整）
- ❌ 不要使用 **Anon Public**（权限受限）

### 复制示例

```
SUPABASE_URL = https://kgmyhukvyygudsllypgv.supabase.co

SUPABASE_SERVICE_KEY = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtmbXloG...
```

---

## 🔧 第二步：在 Render 中配置

### 访问 Render 仪表板

```
https://dashboard.render.com
```

1. 登录你的 Render 账户
2. 找到你的后端服务

### 定位你的服务

```
┌────────────────────────────────────────┐
│ Services (服务列表)                    │
├────────────────────────────────────────┤
│ 🔵 nl2sql-backend-amok (你的服务)     │ ← 点击它
├────────────────────────────────────────┤
│ 🔵 其他服务...                         │
└────────────────────────────────────────┘
```

### 进入服务详情页面

点击服务后，你应该看到：

```
┌─────────────────────────────────────────┐
│ nl2sql-backend-amok                     │
├──────────┬──────────┬──────────┬────────┤
│ Deploy   │ Logs     │ Metrics  │ Events │
├──────────┼──────────┼──────────┼────────┤
│ Health   │ Manual   │ ...      │ ...    │
└──────────┴──────────┴──────────┴────────┘
```

### 找到环境变量设置

在顶部导航中找到 **Environment** 选项卡：

```
Render 服务主页
    ↓
Services → nl2sql-backend-amok → Environment
```

或者直接查找侧边栏中的选项：

```
左侧菜单
├── Settings ⚙️
│   ├── General
│   ├── Environment    ← 点击这里
│   ├── Deploys
│   └── ...
└── ...
```

---

## ✏️ 第三步：添加环境变量

在 Environment 页面，你应该看到现有的变量列表：

```
┌──────────────────────────────────────────────┐
│ Environment Variables                        │
├────────────────────┬────────────────────────┤
│ Key                │ Value                  │
├────────────────────┼────────────────────────┤
│ FLASK_ENV          │ production             │
│ DEBUG              │ False                  │
│ DEEPSEEK_API_KEY   │ ••••••••••••••••       │
│ DB_HOST            │ ••••••••••••••••       │
│ ...                │ ...                    │
└────────────────────┴────────────────────────┘

┌─────────────────────────────────────────────┐
│ [+ Add Environment Variable]                │ ← 点击这个
└─────────────────────────────────────────────┘
```

### 添加第一个变量：SUPABASE_URL

1. 点击 **+ Add Environment Variable**
2. 在弹出的表单中填入：

```
Key:   SUPABASE_URL
Value: https://kgmyhukvyygudsllypgv.supabase.co
```

3. 点击 **Save**

### 添加第二个变量：SUPABASE_SERVICE_KEY

1. 再次点击 **+ Add Environment Variable**
2. 在弹出的表单中填入：

```
Key:   SUPABASE_SERVICE_KEY
Value: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

⚠️ **完整的密钥内容** - 不要截断！

3. 点击 **Save**

### 变量添加完成

完成后应该看到：

```
┌──────────────────────────────────────────────┐
│ Environment Variables                        │
├────────────────────────┬────────────────────┤
│ Key                    │ Value              │
├────────────────────────┼────────────────────┤
│ FLASK_ENV              │ production         │
│ DEBUG                  │ False              │
│ DEEPSEEK_API_KEY       │ ••••••••••••••••   │
│ DB_HOST                │ ••••••••••••••••   │
│ SUPABASE_URL           │ https://...        │ ← 新添加
│ SUPABASE_SERVICE_KEY   │ ••••••••••••••••   │ ← 新添加
│ ...                    │ ...                │
└────────────────────────┴────────────────────┘
```

---

## 🔄 第四步：等待重新部署

在 Render 中保存环境变量后，服务会自动重新部署。

### 查看部署进度

1. 点击 **Deploys** 标签页
2. 应该看到新的部署进行中：

```
┌─────────────────────────────────────┐
│ Deployments                         │
├─────────────────────────────────────┤
│ ⏳ In Progress (正在部署)            │
│    Started: 2 minutes ago           │
│    Branch: main                     │
├─────────────────────────────────────┤
│ ✅ Success                          │
│    Completed: 5 minutes ago         │
└─────────────────────────────────────┘
```

部署完成后状态会变为 ✅ **Success**

### 预期时间
- 部署通常需要 **1-3 分钟**
- 等待直到看到绿色 ✅ 标记

---

## ✅ 第五步：验证配置

### 在浏览器中测试

打开浏览器，访问：

```
https://nl2sql-backend-amok.onrender.com/api/query/health
```

你应该看到：

```json
{
  "service": "NL2SQL Report Backend",
  "status": "healthy",
  "supabase": "connected"
}
```

如果看到：
- ✅ `"supabase": "connected"` → 配置成功！
- ⚠️ `"supabase": "disconnected"` → 检查凭证是否正确
- ❌ 404 或其他错误 → 等待部署完成或检查 URL

### 在浏览器 Console 中测试

按 `F12` 打开开发者工具，在 **Console** 标签页运行：

```javascript
fetch('https://nl2sql-backend-amok.onrender.com/api/query/health')
  .then(response => response.json())
  .then(data => {
    console.log('🔍 后端响应:');
    console.log(data);
    
    if (data.supabase === 'connected') {
      console.log('✅ Supabase 已连接！');
    } else {
      console.log('⚠️ Supabase 未连接，检查环境变量');
    }
  })
  .catch(error => console.error('❌ 错误:', error));
```

---

## 🎯 检查清单

完成以下步骤后打勾：

- [ ] 从 Supabase 获取了 Project URL
- [ ] 从 Supabase 获取了 Service Role Secret（不是 Anon）
- [ ] 在 Render 中添加了 SUPABASE_URL 环境变量
- [ ] 在 Render 中添加了 SUPABASE_SERVICE_KEY 环境变量
- [ ] 服务已重新部署（状态为 ✅）
- [ ] 测试 /health 端点返回 `"supabase": "connected"`
- [ ] 前端在 Bolt 中已更新 nl2sqlApi.js 配置

---

## 🆘 问题排查

### ❌ 仍然显示 `"supabase": "disconnected"`

**检查这些：**

1. **环境变量是否正确保存？**
   ```
   Render Services → nl2sql-backend-amok → Environment
   ↓
   确认 SUPABASE_URL 和 SUPABASE_SERVICE_KEY 都在列表中
   ```

2. **URL 格式是否正确？**
   ```
   ✅ 正确: https://kgmyhukvyygudsllypgv.supabase.co
   ❌ 错误: https://kgmyhukvyygudsllypgv.supabase.co/
          (不要在末尾加/)
   ```

3. **使用的是 Service Role Secret 吗？**
   ```
   ✅ 正确: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9... (长字符串)
   ❌ 错误: anon public key
          (应该更长，通常 200+ 字符)
   ```

4. **密钥是否完整？**
   ```
   ❌ 错误: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
          (可能被截断了)
   
   ✅ 正确: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtmbXloG...
          (完整的密钥)
   ```

### 📋 检查 Render 日志

点击 **Logs** 标签页查看错误信息：

```
Logs
├── Build Logs (构建日志)
└── Runtime Logs (运行日志) ← 这里看 Supabase 错误
```

搜索关键字：`supabase`, `error`, `connection`

---

## 🎉 成功后的下一步

当 Supabase 连接成功后：

1. ✅ 后端能正常执行数据库查询
2. ✅ 前端 `nl2sql` 组件不再报错
3. ✅ 用户可以执行真实的数据库查询

现在你可以：
- 在 Bolt 中使用完整的 UnifiedChat 组件
- 执行 NL2SQL 查询
- 查看实时数据库数据

---

## 📞 需要帮助？

如果还是不行，请准备以下信息：

1. **Render 日志中的错误信息**（Runtime Logs）
2. **Supabase 项目 URL**（可以安全分享）
3. **浏览器 Console 的完整错误信息**（F12 → Console）

记住：**永远不要公开分享 SUPABASE_SERVICE_KEY！**

---

祝配置顺利！🚀
