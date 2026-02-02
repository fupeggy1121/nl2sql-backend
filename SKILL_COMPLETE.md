# Supabase Setup Skill - 完整文档

自动化脚本已创建！现在你有了一个可重用的 Supabase 配置 Skill。

## 📦 包含内容

### 1. 命令行工具：`setup_anon_key.py`
位置：`/Users/fupeggy/NL2SQL/setup_anon_key.py`

```bash
# 交互式配置
python setup_anon_key.py

# 验证配置
python setup_anon_key.py --verify

# 测试连接
python setup_anon_key.py --test

# 生成 Render 配置
python setup_anon_key.py --render-env
```

**特点：**
- ✅ 交互式配置向导
- ✅ 格式验证（URL 和 JWT Token）
- ✅ 连接测试
- ✅ 自动保存到 `.env`
- ✅ 为 Render 生成环境配置
- ✅ 彩色输出和错误提示

### 2. Python 模块：`SupabaseSetupSkill`
位置：`/Users/fupeggy/NL2SQL/app/skills/supabase_setup.py`

在代码中使用：
```python
from app.skills.supabase_setup import SupabaseSetupSkill

skill = SupabaseSetupSkill()

# 检查状态
status = skill.check_status()
if status['connected']:
    print("✅ Supabase 已连接")

# 验证
is_valid, msg = skill.validate_url(url)
is_valid, msg = skill.validate_anon_key(key)

# 测试连接
connected, msg = skill.test_connection()

# 获取 Render 配置
config = skill.get_config_dict()
```

### 3. 使用示例：`examples/skill_usage_example.py`
演示各种使用场景

运行：
```bash
python examples/skill_usage_example.py
```

### 4. 文档

| 文件 | 内容 |
|------|------|
| [ANON_KEY_SETUP.md](ANON_KEY_SETUP.md) | 详细的配置说明 |
| [SETUP_ANON_KEY_GUIDE.md](SETUP_ANON_KEY_GUIDE.md) | 脚本完整文档 |
| [QUICK_SETUP.md](QUICK_SETUP.md) | 快速开始指南 |

## 🚀 使用流程

### 第一次配置（本地）

```bash
# 1. 进入项目目录
cd /Users/fupeggy/NL2SQL

# 2. 运行交互式配置
.venv/bin/python setup_anon_key.py

# 3. 按提示输入 SUPABASE_URL 和 SUPABASE_ANON_KEY

# 4. 脚本会验证和测试连接

# 5. 启动后端
.venv/bin/python run.py
```

### 部署到 Render

```bash
# 1. 生成 Render 环境配置
.venv/bin/python setup_anon_key.py --render-env

# 2. 复制输出到 Render Dashboard
# Render → nl2sql-backend-amok → Environment

# 3. 添加环境变量
SUPABASE_URL = ...
SUPABASE_ANON_KEY = ...

# 4. 点击 Manual Deploy
```

### 验证部署

```bash
# 本地
.venv/bin/python setup_anon_key.py --verify

# 远程（Render）
curl https://nl2sql-backend-amok.onrender.com/api/query/health
```

## 🔍 Skill 功能列表

| 方法 | 功能 | 返回值 |
|------|------|--------|
| `validate_url(url)` | 验证 URL 格式 | `(bool, str)` |
| `validate_anon_key(key)` | 验证 JWT Token 格式 | `(bool, str)` |
| `test_connection()` | 连接到 Supabase | `(bool, str)` |
| `check_status()` | 完整状态检查 | `Dict` |
| `save_to_env(url, key)` | 保存到 .env | `bool` |
| `get_config_dict()` | 获取配置字典 | `Dict` |
| `load_env()` | 加载环境变量 | `None` |

## 💡 高级用法

### 在应用启动时检查配置

```python
# app/__init__.py
from app.skills.supabase_setup import SupabaseSetupSkill

skill = SupabaseSetupSkill()
status = skill.check_status()

if not status['connected']:
    print("⚠️  Warning: Supabase is not connected")
    print(f"   {status['connection_message']}")
else:
    print("✅ Supabase is connected")
```

### 作为 CI/CD 步骤

```bash
#!/bin/bash
# deploy.sh

# 验证配置
.venv/bin/python setup_anon_key.py --verify
if [ $? -ne 0 ]; then
    echo "❌ Configuration validation failed"
    exit 1
fi

# 启动服务
.venv/bin/python run.py
```

### 在 Flask 端点中使用

```python
from flask import Blueprint, jsonify
from app.skills.supabase_setup import SupabaseSetupSkill

@app.route('/api/config/check', methods=['GET'])
def check_config():
    skill = SupabaseSetupSkill()
    status = skill.check_status()
    return jsonify(status)
```

## 🔐 安全考虑

- ✅ Anon Key 权限受限（不需要数据库密码）
- ✅ 密钥自动隐藏在日志中
- ✅ 验证 JWT Token 格式
- ✅ 不会在错误消息中暴露完整密钥
- 🔐 不要在代码中硬编码密钥
- 🔐 定期轮换密钥（Supabase Dashboard）
- 🔐 使用 RLS 限制 Anon Key 权限

## ❓ 常见问题

**Q: 为什么要用 Anon Key 而不是 Service Key？**
A: 权限更少，更安全。Service Key 有完全权限，不适合前端或临时使用。

**Q: 如何升级到 Service Key？**
A: 只需更改一个环境变量，代码无需改动。

**Q: Skill 可以导入到其他项目吗？**
A: 可以！只需复制 `app/skills/` 目录到其他项目。

**Q: 脚本能在 CI/CD 中自动化吗？**
A: 可以，使用 `--verify` 和 `--test` 命令。

## 📊 Skill 工作流程

```
开始
 ↓
加载 .env 文件
 ↓
验证 SUPABASE_URL 格式
 ↓
验证 SUPABASE_ANON_KEY 格式
 ↓
（如果都有效）测试连接
 ↓
返回状态
 ↓
（交互模式）保存到 .env
 ↓
结束
```

## 📈 扩展 Skill

你可以扩展 `SupabaseSetupSkill` 类来添加更多功能：

```python
class ExtendedSupabaseSkill(SupabaseSetupSkill):
    def validate_table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        pass
    
    def validate_rls_policies(self) -> Dict:
        """验证 RLS 策略"""
        pass
    
    def setup_with_service_key(self) -> bool:
        """升级到 Service Key"""
        pass
```

## 📝 下一步

1. ✅ 运行 `setup_anon_key.py` 配置本地环境
2. ✅ 验证配置 `setup_anon_key.py --verify`
3. ✅ 启动后端 `python run.py`
4. ✅ 在 Render 部署时使用 `--render-env` 生成配置
5. ✅ 考虑在应用启动时调用 Skill 检查配置

## 🎯 总结

现在你有了一个完整的 Supabase 配置自动化解决方案，包括：
- 命令行工具
- Python 模块
- 使用示例
- 完整文档

可以在本项目和其他项目中重复使用！
