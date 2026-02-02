# 🚀 快速开始 - Supabase Anon Key 配置

## 一行命令启动（推荐）

```bash
.venv/bin/python setup_anon_key.py
```

这会进入交互式配置，自动：
1. ✅ 要求你输入 SUPABASE_URL
2. ✅ 要求你输入 SUPABASE_ANON_KEY
3. ✅ 验证格式和连接
4. ✅ 保存到 `.env` 文件

## 其他常用命令

```bash
# 验证现有配置
.venv/bin/python setup_anon_key.py --verify

# 测试连接
.venv/bin/python setup_anon_key.py --test

# 生成 Render 环境配置（便于复制到 Render Dashboard）
.venv/bin/python setup_anon_key.py --render-env
```

## 获取密钥位置

1. 打开 [Supabase Dashboard](https://supabase.com/dashboard)
2. 选择你的项目
3. **Settings** → **API**
4. 复制：
   - `Project URL` → SUPABASE_URL
   - `anon (public)` → SUPABASE_ANON_KEY

## 配置后

```bash
# 启动后端
.venv/bin/python run.py
```

## 详细指南

更多细节见 [SETUP_ANON_KEY_GUIDE.md](SETUP_ANON_KEY_GUIDE.md)
