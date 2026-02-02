# `/recognize-intent` 端点部署状态

## 📍 当前状态

### ❌ Render 上的 `recognize-intent` 端点
```bash
curl -X POST https://nl2sql-backend-amok.onrender.com/api/query/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{"query":"查询wafers表的前300条数据"}'

# 返回: 404 Not Found
```

### ✅ 本地 Git 中已实现
- 代码已在 `app/routes/query_routes.py` 中完全实现
- 路由已注册：`@bp.route('/recognize-intent', methods=['POST'])`
- 后端服务已完成：`app/services/intent_recognizer.py`

## 🔍 原因分析

**本地有 11 个未推送的提交**（包括 recognize-intent 实现）：
```
04e41ca Add CORS fix documentation
5c803aa Fix CORS OPTIONS 404 error: improve CORS configuration
a8a9ed5 Add Intent Recognizer API to backend
... 其他 8 个提交
```

**当前状态：**
```bash
git log --oneline -1
# 04e41ca Add CORS fix documentation

git status
# Your branch is ahead of 'origin/main' by 11 commits.
```

**Render 仍在运行旧代码**（上一次成功推送的版本）。

## 🚧 推送到 GitHub 的障碍

### 网络连接问题
```bash
git push origin main
# fatal: unable to access 'https://github.com/fupeggy1121/nl2sql-backend.git/':
# Failed to connect to github.com port 443 after 75544 ms
```

**诊断：**
- HTTPS 连接超时（75+ 秒）
- 本地有代理配置（127.0.0.1:7897）
- GitHub 本身可以访问（HTTP/2 200 OK）

## ✅ 解决方案

### 方案 1：修复网络连接（推荐）

#### 检查代理配置
```bash
# 查看 git 代理设置
git config --global http.proxy
git config --global https.proxy

# 清除代理（如果不需要）
git config --global --unset http.proxy
git config --global --unset https.proxy

# 检查系统代理
echo $HTTP_PROXY $HTTPS_PROXY
```

#### 使用 SSH（如果 HTTPS 持续失败）
```bash
# 生成 SSH key（如果还没有）
ssh-keygen -t ed25519 -C "fupeggy@example.com"

# 添加 SSH key 到 GitHub
# Settings → SSH and GPG keys → New SSH key
# 粘贴 ~/.ssh/id_ed25519.pub 内容

# 将 remote 改为 SSH
git remote set-url origin git@github.com:fupeggy1121/nl2sql-backend.git

# 验证连接
ssh -T git@github.com

# 推送
git push origin main
```

#### 禁用 SSL 验证（临时）
```bash
# ⚠️ 仅在网络环境有效且安全的情况下使用
git config --global http.sslVerify false
git push origin main

# 恢复设置
git config --global http.sslVerify true
```

#### 增加超时时间
```bash
# 增加 git 操作超时到 300 秒
git config --global http.postBuffer 524288000
git config --global core.compression 0

# 推送
git push origin main -v
```

### 方案 2：使用 Render Dashboard 手动部署

1. 访问 [Render Dashboard](https://dashboard.render.com)
2. 找到 `nl2sql-backend` 服务
3. 点击 "Manual Deploy" 或 "Clear Build Cache" → Deploy
4. 等待 2-3 分钟部署完成

*注意：这只会重新部署当前代码，不会包含新的 recognize-intent 端点*

### 方案 3：本地测试 recognize-intent

在网络连接修复前，在本地测试端点：

```bash
# 1. 激活虚拟环境
source .venv/bin/activate

# 2. 启动本地后端
python run.py

# 3. 在另一个终端测试（开发中）
curl -X POST http://localhost:5000/api/query/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{"query":"查询wafers表的前300条数据"}'

# 4. 测试所有端点
curl http://localhost:5000/api/query/health
curl -X POST http://localhost:5000/api/query/nl-to-sql \
  -H "Content-Type: application/json" \
  -d '{"natural_language":"查询所有用户"}'
curl http://localhost:5000/api/query/supabase/schema
```

## 📊 推送前检查清单

```bash
# 1. 确保所有更改已提交
git status
# 应该显示 "nothing to commit"

# 2. 查看待推送的提交
git log origin/main..HEAD --oneline
# 应该看到 11 个提交

# 3. 验证本地代码无错误
python -m py_compile app/routes/query_routes.py
python -m py_compile app/services/intent_recognizer.py

# 4. 尝试推送
git push origin main -v

# 5. 验证推送成功
git log --oneline -1
# 最新提交应该显示在 GitHub 上
```

## 🎯 预期部署流程

### Step 1: 修复网络连接
```bash
# 方案：禁用 SSL 验证（临时解决方案）
git config --global http.sslVerify false
```

### Step 2: 推送所有 11 个提交
```bash
git push origin main
# 应该看到:
# Enumerating objects: ...
# Writing objects: ...
# Everything up-to-date (或 successful push)
```

### Step 3: Render 自动部署
- GitHub webhook 触发 Render 构建
- 约 2-3 分钟后部署完成

### Step 4: 验证新端点
```bash
# 测试 recognize-intent 端点
curl -X POST https://nl2sql-backend-amok.onrender.com/api/query/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{"query":"查询wafers表的前300条数据"}'

# 应该返回成功的 JSON 响应，而不是 404
```

## 📝 recognize-intent 端点说明

### 功能
- 混合规则 + LLM 意图识别
- 支持 6 种意图类型：
  - `direct_query` - 直接查询表数据
  - `query_production` - 查询生产数据
  - `query_quality` - 查询质量数据
  - `query_equipment` - 查询设备数据
  - `generate_report` - 生成报表
  - `compare_analysis` - 对比分析

### 请求格式
```bash
POST /api/query/recognize-intent
Content-Type: application/json

{
  "query": "查询wafers表的前300条数据"
}
```

### 响应格式
```json
{
  "success": true,
  "intent": "direct_query",
  "confidence": 0.95,
  "entities": {
    "table": "wafers",
    "limit": 300
  },
  "methodsUsed": ["rule", "llm"],
  "reasoning": "用户明确请求查询 wafers 表的数据"
}
```

## 🔗 相关文件

- `app/routes/query_routes.py` - 路由定义（第 405-450 行）
- `app/services/intent_recognizer.py` - 完整实现
- `INTENT_RECOGNIZER_BACKEND_INTEGRATION.md` - 详细文档

## 📞 故障排查

### 问题：git push 超时
**解决：** 
```bash
git config --global http.sslVerify false
git push origin main
```

### 问题：SSH 连接拒绝
**解决：**
```bash
# 检查 SSH key 是否已添加到 GitHub
ssh -T git@github.com
```

### 问题：Render 部署失败
**检查：**
1. 访问 [Render Dashboard](https://dashboard.render.com)
2. 查看部署日志
3. 确保所有环境变量已设置

---

**优先级：** 🔴 高 - 需要尽快推送包含 recognize-intent 的更新

**状态：** ⏳ 等待网络连接修复
