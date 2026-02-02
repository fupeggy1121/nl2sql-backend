# 🔧 Supabase 未连接 - 诊断和修复指南

你的 Render 后端在线（`status: healthy`），但 Supabase 未连接（`supabase: disconnected`）。

## 🎯 快速诊断

运行此命令查看详细诊断：

```bash
.venv/bin/python setup_anon_key.py --verify-render nl2sql-backend-amok.onrender.com
```

## 🚨 问题原因（最可能的顺序）

### 1️⃣ SUPABASE_URL 或 SUPABASE_ANON_KEY 未在 Render 上设置

**症状：**
```
supabase_url_set: NO
supabase_key_set: NO
```

**解决方案：**

```bash
# 步骤 1：生成配置
.venv/bin/python setup_anon_key.py --render-env

# 步骤 2：复制输出到 Render Dashboard
# https://dashboard.render.com → nl2sql-backend-amok → Environment

# 步骤 3：添加环境变量
SUPABASE_URL = ...
SUPABASE_ANON_KEY = ...

# 步骤 4：点击 Manual Deploy

# 步骤 5：等待 1-2 分钟部署完成

# 步骤 6：验证
.venv/bin/python setup_anon_key.py --verify-render
```

### 2️⃣ Supabase 密钥已过期或被重新生成

**症状：**
```
supabase_url_set: YES
supabase_key_set: YES
supabase: disconnected  ← 但连接仍然失败
```

**解决方案：**

```bash
# 步骤 1：在本地重新获取密钥
.venv/bin/python setup_anon_key.py

# 步骤 2：输入最新的 SUPABASE_URL 和 SUPABASE_ANON_KEY

# 步骤 3：验证本地连接
.venv/bin/python setup_anon_key.py --verify

# 步骤 4：生成 Render 配置
.venv/bin/python setup_anon_key.py --render-env

# 步骤 5：在 Render Dashboard 更新环境变量

# 步骤 6：Manual Deploy

# 步骤 7：验证 Render 配置
.venv/bin/python setup_anon_key.py --verify-render
```

### 3️⃣ 密钥格式不正确

**症状：**
```
supabase_key_length: < 100  ← Key 太短
```

**解决方案：**

1. 检查你从 Supabase Dashboard 复制的密钥
2. 确保复制的是 **anon (public)** 密钥，不是其他密钥
3. JWT Token 应该以 `eyJ` 开头
4. 完整的密钥通常 200+ 字符

## 📋 完整修复步骤

如果上面的快速修复都不行，跟随这个完整步骤：

### 第 1 步：本地验证

```bash
# 1. 清除旧的配置（可选）
rm .env

# 2. 重新配置
.venv/bin/python setup_anon_key.py

# 3. 验证本地配置
.venv/bin/python setup_anon_key.py --verify

# 确保看到: ✅ Supabase 已连接
```

### 第 2 步：为 Render 生成配置

```bash
# 生成 Render 环境变量
.venv/bin/python setup_anon_key.py --render-env

# 复制输出的两个环境变量
```

### 第 3 步：在 Render Dashboard 更新

1. 打开 https://dashboard.render.com
2. 选择 **nl2sql-backend-amok** 服务
3. 点击 **Environment** 选项卡
4. 更新或添加：
   ```
   SUPABASE_URL = https://xxxxx.supabase.co
   SUPABASE_ANON_KEY = eyJ...
   ```
5. 点击 **Manual Deploy**
6. 等待部署完成（2-3 分钟）

### 第 4 步：验证部署

```bash
# 检查 Render 上的配置
.venv/bin/python setup_anon_key.py --verify-render

# 或者直接 curl
curl https://nl2sql-backend-amok.onrender.com/api/query/health | json_pp
```

**成功的响应：**
```json
{
  "status": "healthy",
  "service": "NL2SQL Report Backend",
  "supabase": "connected",  ← 这里应该是 "connected"
  "diagnosis": {
    "supabase_url_set": "YES",
    "supabase_key_set": "YES"
  }
}
```

## 🆘 仍然不工作？

### 检查清单

- [ ] SUPABASE_URL 格式正确（`https://xxxxx.supabase.co`）
- [ ] SUPABASE_ANON_KEY 不为空且以 `eyJ` 开头
- [ ] 在 Render Dashboard 中确实添加了环境变量
- [ ] 已点击 **Manual Deploy** 并等待完成
- [ ] 刷新浏览器（Render Dashboard）后重新部署
- [ ] 密钥没有复制错误或多余空格

### 从 Supabase 获取密钥

1. 打开 [Supabase Dashboard](https://supabase.com/dashboard)
2. 选择项目 `kgmyhukvyygudsllypgv`
3. 点击 **Settings** → **API**
4. 复制：
   - **Project URL** → `SUPABASE_URL`
   - **anon (public)** → `SUPABASE_ANON_KEY`

### 检查 Supabase 项目状态

1. 确保项目未被暂停或删除
2. 在 Supabase Dashboard 的 **Settings** → **API** 页面检查密钥是否仍然有效
3. 如果需要，可以重新生成密钥

## 📞 高级调试

### 本地测试

```bash
# 在本地测试连接
.venv/bin/python setup_anon_key.py --test

# 运行使用示例
.venv/bin/python examples/skill_usage_example.py
```

### 查看后端日志

```bash
# 在 Render Dashboard
# → nl2sql-backend-amok
# → Logs

# 查看错误信息，通常会显示：
# "Missing SUPABASE_URL or SUPABASE_ANON_KEY"
# 或 "Failed to initialize Supabase: ..."
```

### 重新启动服务

如果所有配置都正确但仍未连接：

```bash
# 在 Render Dashboard
# → nl2sql-backend-amok
# → 点击 "Manual Deploy" 再次部署
```

## 🎯 故障排除树

```
Render 健康检查返回 "disconnected"?
│
├─ supabase_url_set: NO?
│  └─ 在 Render Dashboard 添加 SUPABASE_URL
│
├─ supabase_key_set: NO?
│  └─ 在 Render Dashboard 添加 SUPABASE_ANON_KEY
│
├─ 都已设置但仍未连接?
│  ├─ 检查密钥是否有复制错误
│  ├─ 尝试重新生成 Supabase 密钥
│  └─ 点击 Manual Deploy 重新部署
│
└─ 仍然失败?
   └─ 查看后端日志获取详细错误信息
```

## ✅ 预期时间线

- 生成配置：< 1 分钟
- 更新 Render 环境变量：< 1 分钟
- Render 重新部署：2-3 分钟
- 验证：< 1 分钟

**总计：约 5-10 分钟**

## 💡 提示

- 🔄 如果修改了密钥，务必在 Render 重新部署
- ⏰ Render 冷启动需要时间，第一次访问可能较慢
- 📝 在 Render Dashboard 中记住你的环境变量值，以便对比
- 🔐 不要在代码中硬编码密钥，只在 Render 环境变量中设置
