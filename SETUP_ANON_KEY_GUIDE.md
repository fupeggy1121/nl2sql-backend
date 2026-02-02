# setup_anon_key.py 使用指南

一个自动化的 Supabase Anon Key 配置脚本，可以验证、测试和配置环境变量。

## 快速开始

### 方式 1: 交互式配置（推荐新手）

```bash
python setup_anon_key.py
```

脚本会：
1. ✅ 要求输入 SUPABASE_URL
2. ✅ 验证 URL 格式
3. ✅ 要求输入 SUPABASE_ANON_KEY
4. ✅ 验证 Key 格式
5. ✅ 测试 Supabase 连接
6. ✅ 自动保存到 `.env` 文件

### 方式 2: 仅验证现有配置

```bash
python setup_anon_key.py --verify
```

检查 `.env` 中的配置是否正确：
- URL 格式是否有效
- Anon Key 是否有效
- 是否能连接到 Supabase

### 方式 3: 测试连接

```bash
python setup_anon_key.py --test
```

仅测试与 Supabase 的连接（不修改任何内容）

### 方式 4: 生成 Render 配置

```bash
python setup_anon_key.py --render-env
```

显示需要在 Render Dashboard 上设置的环境变量，便于复制粘贴。

## 完整命令列表

```bash
# 交互式设置
python setup_anon_key.py

# 验证配置
python setup_anon_key.py --verify

# 测试连接
python setup_anon_key.py --test

# 生成 Render 配置
python setup_anon_key.py --render-env

# 显示帮助
python setup_anon_key.py --help

# 使用自定义 .env 文件
python setup_anon_key.py --env-file /path/to/.env
```

## 脚本功能详解

### ✅ 验证 SUPABASE_URL

检查：
- 格式是否为 `https://xxxxx.supabase.co`
- 不能为空

### ✅ 验证 SUPABASE_ANON_KEY

检查：
- 是否为有效的 JWT Token（以 `eyJ` 开头）
- 长度是否足够（至少 100 字符）
- 是否包含 3 个部分（用点号分隔）

### ✅ 测试连接

通过 Supabase 官方 SDK：
- 连接到项目
- 查询系统表
- 验证认证是否成功

### ✅ 错误诊断

如果失败会提示：
- 缺少变量
- 格式不正确
- 认证失败（401）
- 网络问题

## 获取 SUPABASE_URL 和 ANON_KEY

1. 登录 [Supabase Dashboard](https://supabase.com/dashboard)
2. 选择你的项目（例：`kgmyhukvyygudsllypgv`）
3. 点击 **Settings** → **API**
4. 找到 **API keys** 部分

```
Project URL (SUPABASE_URL)
https://kgmyhukvyygudsllypgv.supabase.co

anon (public) (SUPABASE_ANON_KEY)
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## 输出示例

### ✅ 成功的交互式设置

```
============================================================
         Supabase Anon Key 交互式配置
============================================================

步骤 1: 获取 SUPABASE_URL
ℹ️   访问: https://supabase.com/dashboard
ℹ️   选择项目 → Settings → API → Project URL

请输入 SUPABASE_URL (当前: NOT SET): https://kgmyhukvyygudsllypgv.supabase.co
✅ URL 验证通过: URL 格式正确

步骤 2: 获取 SUPABASE_ANON_KEY
ℹ️   在同一个 Settings → API 页面
ℹ️   复制 'anon (public)' 密钥

请输入 SUPABASE_ANON_KEY (当前: NOT SET): eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
✅ Anon Key 验证通过: Anon Key 格式正确

步骤 3: 测试连接
ℹ️   连接到 Supabase...
✅ Supabase 连接成功！

============================================================
                  ✅ 配置完成
============================================================
环境文件已更新: .env
ℹ️   现在可以运行后端: python run.py
```

### ✅ 验证配置

```
============================================================
                    配置验证
============================================================

SUPABASE_URL:
  设置: ✅
  值:   https://kgmyhukvyygudsllypgv.supabase.co
  验证: URL 格式正确

SUPABASE_ANON_KEY:
  设置: ✅
  值:   eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ...
  验证: Anon Key 格式正确

连接状态:
✅ Supabase 已连接: 连接成功

============================================================
                  ✅ 配置有效
============================================================
```

### ❌ 常见错误

**错误：URL 格式不正确**
```
❌ URL 验证失败: URL 格式不正确。应该是: https://xxxxx.supabase.co
```
→ 检查 URL 是否以 `https://` 开头，以 `.supabase.co` 结尾

**错误：Anon Key 格式不正确**
```
❌ Anon Key 验证失败: Anon Key 格式不正确。JWT Token 应该以 'eyJ' 开头
```
→ 确保复制的是 **anon (public)** 密钥，而不是其他密钥

**错误：连接失败 - 认证失败**
```
❌ 连接失败: 认证失败。检查 Anon Key 是否正确: 401 Unauthorized
```
→ 检查 Anon Key 是否正确，或尝试重新生成

**错误：supabase 包未安装**
```
❌ 连接失败: supabase 包未安装。运行: pip install supabase
```
→ 运行：`pip install supabase`

## 在 Render 上使用

1. 本地运行脚本验证配置
   ```bash
   python setup_anon_key.py --verify
   ```

2. 生成 Render 环境配置
   ```bash
   python setup_anon_key.py --render-env
   ```

3. 在 Render Dashboard 中手动添加环境变量

4. 重新部署
   ```bash
   # Render 自动部署或手动点击 "Manual Deploy"
   ```

## 与项目集成

这个脚本可以作为 CI/CD 流程的一部分：

```bash
#!/bin/bash
# deploy.sh

# 验证配置
python setup_anon_key.py --verify
if [ $? -ne 0 ]; then
    echo "Configuration validation failed"
    exit 1
fi

# 启动后端
python run.py
```

## 安全建议

- 🔐 **不要**在 GitHub 中提交 `.env` 文件
- 🔐 **不要**在代码中硬编码密钥
- 🔐 定期轮换 Anon Key（Supabase Dashboard）
- 🔐 使用行级安全 (RLS) 限制 Anon Key 权限
- 🔐 在生产环境中，升级到 Service Role Key

## 故障排除

**脚本说找不到 supabase 包？**

```bash
pip install -r requirements.txt
```

**想要修改 .env 文件位置？**

```bash
python setup_anon_key.py --env-file path/to/.env
```

**想要重新设置所有变量？**

```bash
# 删除旧的 .env
rm .env

# 重新运行脚本
python setup_anon_key.py
```

## 脚本原理

这是一个 `SupabaseSetupSkill` 类的命令行包装，提供以下功能：

| 方法 | 功能 |
|------|------|
| `validate_url()` | 验证 URL 格式 |
| `validate_anon_key()` | 验证 JWT Token 格式 |
| `test_connection()` | 连接到 Supabase |
| `check_status()` | 完整的状态检查 |
| `setup_interactive()` | 交互式设置 |
| `verify_config()` | 验证现有配置 |
| `generate_render_env()` | 生成 Render 配置 |

可以将其作为 Python 模块导入：

```python
from setup_anon_key import SupabaseSetupSkill

skill = SupabaseSetupSkill()
skill.setup_interactive()
```
