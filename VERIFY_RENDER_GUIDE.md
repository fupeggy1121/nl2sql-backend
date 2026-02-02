# --verify-render 功能说明

新增了验证 Render 上配置的功能！

## 使用方式

### 方式 1：使用默认 URL（推荐）

```bash
.venv/bin/python setup_anon_key.py --verify-render
```

默认检查：`https://nl2sql-backend-amok.onrender.com`

### 方式 2：指定自定义 URL

```bash
.venv/bin/python setup_anon_key.py --verify-render https://your-backend-url.onrender.com
```

## 功能说明

`--verify-render` 会：

1. **检查后端是否在线** - 调用 `/api/query/health` 端点
2. **检查 Supabase 连接** - 验证 Render 上的 SUPABASE_URL 和 SUPABASE_ANON_KEY 是否有效
3. **显示诊断信息** - 告诉你具体配置了什么
4. **提供错误提示** - 如果有问题会告诉你可能的原因

## 输出示例

### ✅ 配置正确

```
============================================================
                   验证 Render 上的配置
============================================================

🌐 Render 后端: https://nl2sql-backend-amok.onrender.com
健康状态: ✅ healthy
Supabase: ✅ connected

详细信息:
  service: NL2SQL Report Backend

  诊断信息:
    db_host: db.kgmyhukvyygudsllypgv.supabase.co
    db_port: 5432
    db_user: postgres
    db_name: postgres
    db_password: ***

============================================================
                 ✅ Render 配置有效
============================================================

Supabase 已连接，可以正常使用
```

### ❌ Supabase 未连接

```
============================================================
                   验证 Render 上的配置
============================================================

🌐 Render 后端: https://nl2sql-backend-amok.onrender.com
健康状态: ✅ healthy
Supabase: ❌ disconnected

============================================================
                  ❌ Render 配置有问题
============================================================

可能的原因:
1. 检查 SUPABASE_URL 是否设置
2. 检查 SUPABASE_ANON_KEY 是否设置
3. 检查认证信息是否正确
```

### ❌ 无法连接到 Render

```
❌ 发生错误: 无法连接到 Render。检查网络和 URL
```

## 常见问题

**Q: 为什么连接超时？**
A: Render 的免费计划可能需要几秒钟才能启动。请等待几秒后再试。

**Q: 如何知道我的 Render URL？**
A: 
1. 打开 Render Dashboard
2. 选择 nl2sql-backend-amok 服务
3. 在顶部看到 "URL" 字段
4. 通常是 https://nl2sql-backend-amok.onrender.com

**Q: 与 --verify 有什么区别？**
A: 
- `--verify` - 检查本地 `.env` 文件中的配置
- `--verify-render` - 检查 Render 上部署的配置

## 使用场景

### 场景 1：部署后验证

```bash
# 1. 在 Render 上添加环境变量
# 2. 点击 Manual Deploy
# 3. 等待部署完成
# 4. 验证配置
.venv/bin/python setup_anon_key.py --verify-render

# ✅ 如果显示 "Render 配置有效"，说明部署成功
```

### 场景 2：故障排查

```bash
# 如果前端无法连接到后端：

# 1. 检查本地配置（用于本地开发）
.venv/bin/python setup_anon_key.py --verify

# 2. 检查 Render 上的配置（用于生产环境）
.venv/bin/python setup_anon_key.py --verify-render

# 如果 Render 配置有效，但前端还是无法连接，问题可能在：
# - CORS 配置
# - 网络连接
# - 前端的 API URL 设置
```

## 在 Python 代码中使用

```python
from app.skills.supabase_setup import SupabaseSetupSkill

skill = SupabaseSetupSkill()

# 验证 Render 上的配置
result = skill.verify_render_config('https://nl2sql-backend-amok.onrender.com')

if result['connected']:
    print("✅ Render 上的 Supabase 已连接")
else:
    print(f"❌ 连接失败: {result['error']}")

# 查看完整的诊断信息
print(result['response'])
```

## 所有命令速查

```bash
# 交互式配置本地环境
.venv/bin/python setup_anon_key.py

# 验证本地配置
.venv/bin/python setup_anon_key.py --verify

# 验证 Render 上的配置
.venv/bin/python setup_anon_key.py --verify-render

# 指定自定义 Render URL
.venv/bin/python setup_anon_key.py --verify-render https://custom-url.onrender.com

# 生成 Render 环境变量配置
.venv/bin/python setup_anon_key.py --render-env

# 显示帮助
.venv/bin/python setup_anon_key.py --help
```
