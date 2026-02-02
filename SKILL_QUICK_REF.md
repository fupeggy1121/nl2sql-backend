# Skill 快速参考卡

## 📂 文件位置

```
/Users/fupeggy/NL2SQL/
├── setup_anon_key.py                  # ⭐ 命令行工具（主程序）
├── app/
│   └── skills/
│       ├── __init__.py
│       └── supabase_setup.py           # ⭐ Python 模块
├── examples/
│   └── skill_usage_example.py          # 使用示例
└── 文档/
    ├── SKILL_COMPLETE.md               # 完整文档（你在这儿）
    ├── ANON_KEY_SETUP.md               # 配置说明
    ├── SETUP_ANON_KEY_GUIDE.md         # 脚本指南
    └── QUICK_SETUP.md                  # 快速开始
```

## ⚡ 快速命令

```bash
# 交互式配置（最常用）
python setup_anon_key.py

# 使用虚拟环境
.venv/bin/python setup_anon_key.py

# 验证本地配置
.venv/bin/python setup_anon_key.py --verify

# 验证 Render 上的配置（新增！）
.venv/bin/python setup_anon_key.py --verify-render

# 测试本地连接
.venv/bin/python setup_anon_key.py --test

# 生成 Render 配置
.venv/bin/python setup_anon_key.py --render-env

# 查看帮助
.venv/bin/python setup_anon_key.py --help

# 运行使用示例
.venv/bin/python examples/skill_usage_example.py
```

## 🎯 使用流程

### 本地配置（第一次）
```bash
.venv/bin/python setup_anon_key.py
# → 输入 URL
# → 输入 Anon Key
# → 验证并测试
# → 自动保存到 .env
```

### 验证配置
```bash
.venv/bin/python setup_anon_key.py --verify
# ✅ 检查 URL 格式
# ✅ 检查 Key 格式
# ✅ 测试 Supabase 连接
```

### Render 部署
```bash
# 1. 生成配置
.venv/bin/python setup_anon_key.py --render-env

# 2. 复制输出到 Render Dashboard
#    https://dashboard.render.com
#    → nl2sql-backend-amok
#    → Environment

# 3. 添加：
#    SUPABASE_URL = ...
#    SUPABASE_ANON_KEY = ...

# 4. Manual Deploy
```

## 💻 Python 代码中使用

```python
from app.skills.supabase_setup import SupabaseSetupSkill

# 创建实例
skill = SupabaseSetupSkill()

# 检查状态
status = skill.check_status()
if status['connected']:
    print("✅ Supabase 已连接")

# 验证 URL
valid, msg = skill.validate_url("https://xxx.supabase.co")

# 验证 Key
valid, msg = skill.validate_anon_key("eyJ...")

# 测试连接
connected, msg = skill.test_connection()

# 获取 Render 配置
config = skill.get_config_dict()
print(config)  # {'SUPABASE_URL': '...', 'SUPABASE_ANON_KEY': '...'}
```

## 🔍 主要功能

| 功能 | 命令 | 说明 |
|------|------|------|
| 交互式设置 | `python setup_anon_key.py` | 一步步配置 |
| 验证本地配置 | `--verify` | 检查本地 .env 中的配置 |
| 验证 Render 配置 | `--verify-render` | 检查 Render 上部署的配置（新增！） |
| 测试本地连接 | `--test` | 测试到 Supabase 的本地连接 |
| Render 配置 | `--render-env` | 生成 Render 环境变量 |
| 显示帮助 | `--help` | 显示所有选项 |

## 📋 Skill 类方法

```python
SupabaseSetupSkill()
  ├─ load_env()                  # 加载 .env 文件
  ├─ validate_url(url)           # 验证 URL 格式
  ├─ validate_anon_key(key)      # 验证 Key 格式
  ├─ test_connection()           # 测试连接
  ├─ check_status()              # 完整状态检查
  ├─ save_to_env(url, key)       # 保存到 .env
  └─ get_config_dict()           # 获取配置字典
```

## ✅ 成功指标

配置成功时应该看到：

```bash
$ .venv/bin/python setup_anon_key.py --verify

============================================================
                    配置验证
============================================================

SUPABASE_URL:
  设置: ✅
  值:   https://kgmyhukvyygudsllypgv.supabase.co
  验证: URL 格式正确

SUPABASE_ANON_KEY:
  设置: ✅
  值:   eyJhbGciOiJIUzI1NiIs...(长度: 250+ 字符)
  验证: Anon Key 格式正确

连接状态:
✅ Supabase 已连接: 连接成功

============================================================
                  ✅ 配置有效
============================================================
```

## ❌ 常见错误及解决

| 错误 | 原因 | 解决 |
|------|------|------|
| `URL 格式不正确` | URL 不是 `https://xxx.supabase.co` | 检查 Supabase Dashboard → Settings → API |
| `Anon Key 格式不正确` | Key 不以 `eyJ` 开头 | 确保复制的是 **anon (public)** |
| `连接失败 401` | Key 无效或过期 | 重新生成或复制正确的 Anon Key |
| `supabase 包未安装` | 缺少依赖 | 运行 `pip install supabase` |

## 🚀 下一步

1. ✅ 运行 `setup_anon_key.py` 配置
2. ✅ 验证 `setup_anon_key.py --verify`
3. ✅ 启动后端 `python run.py`
4. ✅ 部署到 Render（使用 `--render-env`）

## 📚 详细文档

- 完整说明：[SKILL_COMPLETE.md](SKILL_COMPLETE.md)
- 脚本指南：[SETUP_ANON_KEY_GUIDE.md](SETUP_ANON_KEY_GUIDE.md)
- 配置说明：[ANON_KEY_SETUP.md](ANON_KEY_SETUP.md)
- 快速开始：[QUICK_SETUP.md](QUICK_SETUP.md)
