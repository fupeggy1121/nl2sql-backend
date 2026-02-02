# Supabase 连接故障排查清单

## 问题: `supabase: disconnected` 即使重新部署后仍然显示

## 根本原因 ❌

你的后端使用 **PostgreSQL 直接连接**（通过 `DB_HOST`, `DB_PORT` 等），而你只配置了 `SUPABASE_ANON_KEY`，这是 **不兼容的**。

你需要配置数据库凭证，而不是 API 密钥。

## 解决方案 ✅

### 步骤 1: 从 Supabase 获取 PostgreSQL 凭证

1. 登录 [Supabase Dashboard](https://supabase.com/dashboard)
2. 打开你的项目
3. 左侧菜单 → **Settings** → **Database**
4. 找到 "Connection string" 部分
5. 点击 **URI** 标签
6. 复制完整的连接字符串
   ```
   postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres
   ```

### 步骤 2: 在 Render 上添加环境变量

1. 登录 [Render Dashboard](https://dashboard.render.com)
2. 点击你的服务：`nl2sql-backend-amok`
3. 左侧菜单 → **Environment**
4. 删除不需要的变量：
   - 删除 `SUPABASE_ANON_KEY`（如果存在）
   - 删除 `SUPABASE_URL`（如果存在）

5. 添加以下变量（从 PostgreSQL 连接字符串中提取）：
   ```
   DB_HOST = db.xxxxx.supabase.co
   DB_PORT = 5432
   DB_USER = postgres
   DB_PASSWORD = [你的真实数据库密码]
   DB_NAME = postgres
   ```

### 步骤 3: 重新部署

1. 点击页面右上角 "Manual Deploy" 或 "Redeploy latest commit"
2. 等待部署完成（2-3 分钟）
3. 查看日志确保没有错误

## 🧪 验证修复是否成功

在浏览器访问：
```
https://nl2sql-backend-amok.onrender.com/api/query/health
```

成功的响应应该是：
```json
{
  "status": "healthy",
  "service": "NL2SQL Report Backend",
  "supabase": "connected",
  "error": null,
  "diagnosis": {
    "db_host": "db.xxxxx.supabase.co",
    "db_port": "5432",
    "db_user": "postgres",
    "db_name": "postgres",
    "db_password": "***"
  }
}
```

## ⚠️ 常见错误

| 错误 | 原因 | 解决 |
|------|------|------|
| `db_host: "NOT SET"` | 没有配置 DB_HOST | 检查环境变量是否正确添加 |
| `connect timeout` | 无法连接到数据库 | 检查 DB_HOST 是否正确，可能需要重置 Supabase 密码 |
| `password authentication failed` | 密码错误 | 在 Supabase Dashboard 重置数据库密码 |
| `database "xxx" does not exist` | 数据库名称错误 | 使用 `postgres` 作为默认数据库 |

## 🔐 获取 Supabase 数据库密码

如果忘记密码：

1. 登录 Supabase Dashboard
2. Settings → Database → Database Password
3. 点击 "Reset Password" 按钮
4. 会生成新密码，复制并用于 `DB_PASSWORD`

## 📝 预期行为

配置正确后：
- ✅ 前端显示 "Connected to database"
- ✅ 可以执行 NL2SQL 查询
- ✅ 数据库查询返回结果
- ✅ 健康检查返回 `"supabase": "connected"`

## 如果仍然不工作

运行诊断脚本本地检查：
```bash
python diagnose_render_env.py
```

这会显示：
- 所有环境变量是否已设置
- PostgreSQL 连接是否成功
- 后端 API 是否响应
