# Render 环境变量配置指南

## 📋 问题诊断

目前 Supabase 显示 `disconnected` 是因为：
- 后端代码使用 **PostgreSQL 直接连接**（不是 Supabase SDK）
- 需要配置：`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- 但这些凭证可能没有正确设置在 Render 上

## ✅ Render 需要配置的环境变量

在 Render Dashboard → Your Service → Environment 中添加以下变量：

### PostgreSQL 连接凭证（从 Supabase 获取）
```
DB_HOST=db.XXXXX.supabase.co
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your-super-secret-password
DB_NAME=postgres
```

**获取这些凭证的方法：**

1. 登录 Supabase Dashboard
2. 找到你的项目
3. 点击 "Settings" → "Database"
4. 找到 "Connection string"
5. 选择 "URI" 格式，复制 PostgreSQL 连接字符串
6. 格式为：`postgresql://postgres:password@db.xxxxx.supabase.co:5432/postgres`
7. 从中提取：
   - `DB_HOST` = `db.xxxxx.supabase.co`
   - `DB_PORT` = `5432`
   - `DB_USER` = `postgres`
   - `DB_PASSWORD` = 你的密码
   - `DB_NAME` = `postgres`

### DeepSeek API 凭证（已配置）
```
DEEPSEEK_API_KEY=sk-xxxxxxxx
DEEPSEEK_MODEL=deepseek-chat
```

### Flask 配置（已配置）
```
FLASK_ENV=production
DEBUG=False
```

## ⚠️ 不需要的变量

这些变量**不需要**在 Render 上设置（只用于 Anon Key 方式，而我们用的是 PostgreSQL 直接连接）：
- ~~SUPABASE_URL~~
- ~~SUPABASE_ANON_KEY~~
- ~~SUPABASE_SERVICE_KEY~~

## 🔧 配置步骤

1. 登录 [Render Dashboard](https://dashboard.render.com)
2. 选择你的服务 `nl2sql-backend-amok`
3. 点击 "Environment"
4. 添加或更新以下变量：
   ```
   DB_HOST
   DB_PORT
   DB_USER
   DB_PASSWORD
   DB_NAME
   ```
5. 点击 "Save Changes"
6. 等待服务自动重新部署（通常 2-3 分钟）
7. 重新加载前端页面测试

## ✔️ 验证配置是否正确

访问后端健康检查端点：
```
https://nl2sql-backend-amok.onrender.com/api/query/health
```

应该返回：
```json
{
  "service": "NL2SQL Report Backend",
  "status": "healthy",
  "supabase": "connected"
}
```

## 🔐 安全提示

- **不要**在代码中硬编码凭证
- 从 Supabase 复制密码时，确保是正确的数据库密码（通常是在项目创建时设置的）
- 可以通过 Supabase Dashboard 重置密码：Settings → Database → Reset password
