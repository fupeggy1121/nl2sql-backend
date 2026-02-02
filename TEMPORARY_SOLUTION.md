# 临时解决方案：本地测试 recognize-intent

由于网络连接问题导致无法 push 到 GitHub，Render 上的后端仍然运行旧代码。

## ✅ 本地测试 recognize-intent 端点

### Step 1: 启动本地后端
```bash
# 激活虚拟环境
source .venv/bin/activate

# 启动 Flask 应用
python run.py

# 输出应该显示:
# * Serving Flask app 'run'
# * Running on http://127.0.0.1:5000
```

### Step 2: 在新终端中测试端点

#### 测试健康检查
```bash
curl http://localhost:5000/api/query/health
```

#### 测试意图识别（recognize-intent）
```bash
curl -X POST http://localhost:5000/api/query/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{"query":"查询wafers表的前300条数据"}'
```

**预期响应:**
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
  "reasoning": "用户明确请求查询 wafers 表的前 300 条数据"
}
```

#### 测试其他端点
```bash
# NL 转 SQL
curl -X POST http://localhost:5000/api/query/nl-to-sql \
  -H "Content-Type: application/json" \
  -d '{"natural_language":"查询所有用户"}'

# Supabase Schema
curl http://localhost:5000/api/query/supabase/schema

# 执行 NL 查询
curl -X POST http://localhost:5000/api/query/nl-execute \
  -H "Content-Type: application/json" \
  -d '{"natural_language":"查询所有用户"}'
```

---

## 🔧 解决网络推送问题

### 问题诊断
```bash
git push origin main
# fatal: Failed to connect to github.com port 443 after 75000 ms
```

### 已尝试的解决方案
1. ❌ 禁用 SSL 验证 - 无效
2. ❌ 增加超时时间 - 无效
3. ❌ SSH 推送 - 需要配置 SSH key
4. ❌ GitHub CLI - 使用的仍是 HTTPS

### 解决方案清单

#### 方案 A: 检查代理设置（推荐）
```bash
# 检查系统代理
echo "HTTP_PROXY: $HTTP_PROXY"
echo "HTTPS_PROXY: $HTTPS_PROXY"

# 如果有代理，可能需要配置 git
git config --global http.proxy [proxy_url]
git config --global https.proxy [proxy_url]

# 或者移除代理
unset HTTP_PROXY
unset HTTPS_PROXY
git config --global --unset http.proxy
git config --global --unset https.proxy

# 重试推送
git push origin main
```

#### 方案 B: 重启网络连接
```bash
# 重启 WiFi 或网络连接
# 可以尝试切换 WiFi 网络

# 重试推送
git push origin main
```

#### 方案 C: 配置 SSH 推送（长期方案）
```bash
# 1. 生成 SSH key
ssh-keygen -t ed25519 -C "fupeggy@example.com"
# 按 Enter 三次接受默认选项

# 2. 添加到 SSH agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

# 3. 添加到 GitHub
# 复制公钥
cat ~/.ssh/id_ed25519.pub

# 访问 https://github.com/settings/keys
# 点击 "New SSH key"
# 粘贴公钥内容，保存

# 4. 验证连接
ssh -T git@github.com

# 5. 推送
git push origin main
```

#### 方案 D: 使用公司网络或 VPN
```bash
# 如果在公司网络，可能需要 VPN
# 连接 VPN 后重试推送
git push origin main
```

#### 方案 E: 分块推送（如果提交太多）
```bash
# 只推送最后 5 个提交
git push origin HEAD~5..HEAD

# 然后推送剩余的
git push origin main
```

---

## 📊 当前 Git 状态

### 本地分支
```bash
git branch -v
# * main b04e41ca [ahead 11] Add CORS fix documentation
```

### 待推送的提交
```bash
git log origin/main..HEAD --oneline
# 04e41ca Add CORS fix documentation
# 5c803aa Fix CORS OPTIONS 404 error
# a8a9ed5 Add Intent Recognizer API to backend
# ... 其他 8 个提交
```

包括的重要更新：
- ✅ `/recognize-intent` 端点实现
- ✅ CORS 配置修复
- ✅ `check-connection` 路由
- ✅ 意图识别服务

---

## 📝 重要说明

**本地测试：** 通过 `python run.py` 启动的本地后端**已支持** `/recognize-intent` 端点

**生产部署：** 一旦推送成功：
1. GitHub 会收到 11 个新提交
2. Render webhook 会自动触发部署
3. 2-3 分钟后 Render 后端会更新
4. `https://nl2sql-backend-amok.onrender.com/api/query/recognize-intent` 将可用

---

## 🎯 下一步

1. **立即：** 尝试本地测试 recognize-intent
   ```bash
   python run.py
   # 在新终端中
   curl -X POST http://localhost:5000/api/query/recognize-intent \
     -H "Content-Type: application/json" \
     -d '{"query":"查询wafers表的前300条数据"}'
   ```

2. **待网络恢复：** 推送代码到 GitHub
   ```bash
   git push origin main
   ```

3. **部署后：** 验证 Render 上的端点
   ```bash
   curl -X POST https://nl2sql-backend-amok.onrender.com/api/query/recognize-intent \
     -H "Content-Type: application/json" \
     -d '{"query":"查询wafers表的前300条数据"}'
   ```

---

## 💡 提示

- 本地 Flask 服务器运行在 `http://127.0.0.1:5000`
- Render 生产服务器运行在 `https://nl2sql-backend-amok.onrender.com`
- 如果需要前端测试，更新 API_BASE_URL 为 `http://localhost:5000/api/query`（开发环境）

---

**优先级：** 🟡 中 - 可以先本地测试，待网络恢复后推送到生产

**状态：** ⏳ 等待网络连接恢复或 SSH 配置完成
