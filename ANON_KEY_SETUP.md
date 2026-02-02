.venv/bin/python setup_anon_key.py --verify-render nl2sql-backend-amok.onrender.com# 使用 SUPABASE_ANON_KEY 配置（推荐）

## 说明

你现在可以**只用 SUPABASE_ANON_KEY 和 SUPABASE_URL**，无需数据库密码。

这是更安全的方式，因为：
- ✅ Anon Key 权限受限（只能读写指定数据）
- ✅ 不需要暴露数据库密码
- ✅ 符合 Supabase 最佳实践
- ✅ 更容易管理和轮换

## Render 环境变量配置

在 Render Dashboard → `nl2sql-backend-amok` → **Environment** 中设置：

### 必需变量

```
SUPABASE_URL = https://kgmyhukvyygudsllypgv.supabase.co
SUPABASE_ANON_KEY = eyJhbGciOiJIUzI1NiIsInR5cCI... (你的 Anon Key)
```

### 可选：删除不需要的变量

这些变量可以删除（如果存在）：
- ~~DB_HOST~~
- ~~DB_PORT~~
- ~~DB_USER~~
- ~~DB_PASSWORD~~
- ~~DB_NAME~~
- ~~SUPABASE_SERVICE_KEY~~

### DeepSeek 配置（保持不变）

```
DEEPSEEK_API_KEY = sk-...
DEEPSEEK_MODEL = deepseek-chat
```

### Flask 配置（保持不变）

```
FLASK_ENV = production
DEBUG = False
```

## 获取 SUPABASE_ANON_KEY

1. 登录 [Supabase Dashboard](https://supabase.com/dashboard)
2. 选择你的项目：`kgmyhukvyygudsllypgv`
3. 左侧菜单 → **Settings** → **API**
4. 找到 **API keys** 部分
5. 复制 **anon (public)** 密钥

```
Example Anon Key:
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV...
```

## 获取 SUPABASE_URL

在同一个 **Settings → API** 页面中：

```
Project URL = https://kgmyhukvyygudsllypgv.supabase.co
```

## 部署步骤

1. ✅ 在 Render 添加 `SUPABASE_URL` 和 `SUPABASE_ANON_KEY`
2. ✅ 删除不需要的 `DB_*` 变量
3. ✅ 点击 "Manual Deploy" 或 "Redeploy latest commit"
4. ✅ 等待 2-3 分钟完成部署
5. ✅ 访问健康检查端点验证：

```
https://nl2sql-backend-amok.onrender.com/api/query/health
```

## 成功的响应

```json
{
  "status": "healthy",
  "service": "NL2SQL Report Backend",
  "supabase": "connected",
  "error": null
}
```

## 本地测试

在本地测试前，创建 `.env` 文件：

```bash
# .env
SUPABASE_URL=https://kgmyhukvyygudsllypgv.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-chat
```

然后运行：

```bash
python run.py
```

## 安全提示

- 🔐 **不要**在代码中硬编码密钥
- 🔐 **不要**在 GitHub 中提交 `.env` 文件
- 🔐 定期轮换密钥（在 Supabase Dashboard 中）
- 🔐 使用行级安全 (RLS) 策略限制 Anon Key 的访问

## 常见错误

| 错误 | 原因 | 解决 |
|------|------|------|
| `SUPABASE_URL: NOT SET` | 环境变量未设置 | 检查 Render 环境配置 |
| `Failed to connect` | 密钥或 URL 无效 | 检查密钥是否正确复制 |
| `Not authenticated` | Anon Key 权限不足 | 检查 RLS 策略，允许 Anon 读取 |
| `Request failed with status 401` | 认证失败 | 验证 SUPABASE_ANON_KEY 是否正确 |

## 查询限制

使用 Anon Key 时，你可以：
- ✅ 读取允许的表（取决于 RLS 策略）
- ✅ 写入允许的数据（取决于 RLS 策略）
- ❌ 访问管理函数
- ❌ 创建/删除表

## 升级后续

当 Supabase 维护完成后，可以升级到 `SUPABASE_SERVICE_KEY`：
- 只需将一个环境变量从 `ANON_KEY` 改为 `SERVICE_KEY`
- 无需改代码
- Service Key 有完全权限
