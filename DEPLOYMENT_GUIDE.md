# NL2SQL 后端部署指南

## 🚀 快速部署到 Render（推荐）

### 前置条件
- GitHub 账户
- Render 账户（免费）

### 步骤 1：推送到 GitHub

```bash
# 创建新的 GitHub 仓库 (https://github.com/new)
# 然后运行：

cd /Users/fupeggy/NL2SQL
git remote add origin https://github.com/YOUR_USERNAME/nl2sql-backend.git
git branch -M main
git push -u origin main
```

### 步骤 2：部署到 Render

1. 访问 https://render.com
2. 点击 "New+" → "Web Service"
3. 连接你的 GitHub 仓库
4. 配置如下：

```
Name: nl2sql-backend
Environment: Python 3.11
Build Command: pip install -r requirements.txt
Start Command: gunicorn --bind 0.0.0.0:$PORT run:app
```

5. 在 "Environment" 标签页添加环境变量：

```
FLASK_ENV=production
DEBUG=False
DEEPSEEK_API_KEY=your_deepseek_key_here
LLM_PROVIDER=deepseek
DB_HOST=your_supabase_host
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_supabase_password
DB_NAME=postgres
```

6. 点击 "Create Web Service"

### 步骤 3：获取部署 URL

部署完成后，Render 会给你一个 URL，格式如：
```
https://nl2sql-backend.onrender.com
```

### 步骤 4：更新前端配置

在 Bolt.new 前端项目中，更新 `src/services/nl2sqlApi.js`：

```javascript
const API_BASE_URL = 'https://nl2sql-backend.onrender.com/api/query';
```

## 其他部署选项

### Railway
- 访问：https://railway.app
- 连接 GitHub 仓库
- 自动部署
- 每月免费额度

### Heroku（需付费）
- 访问：https://www.heroku.com
- 使用 Procfile 配置

## 本地开发

继续使用 Cloudflare Tunnel 进行本地测试：

```bash
# 终端 1：启动后端
cd /Users/fupeggy/NL2SQL
source .venv/bin/activate
python run.py

# 终端 2：启动 Tunnel
cloudflared tunnel --url http://127.0.0.1:8000
```

## 故障排除

### 部署失败
- 检查 `requirements.txt` 是否完整
- 确保 `run.py` 存在且可正常启动
- 查看 Render 日志获取错误信息

### 连接超时
- 确保环境变量正确配置
- 检查 Supabase 凭证
- 验证 DeepSeek API Key

### 性能优化
- 使用 Render 的 Pro 计划增加 RAM
- 启用 automatic scaling
- 考虑使用 CDN 加速

## 成本估算

| 平台 | 免费额度 | 限制 |
|------|--------|------|
| Render | 永久免费 | 部署在免费实例，不活跃 15 分钟后休眠 |
| Railway | $5/月 | 免费试用，之后按使用量计费 |
| Heroku | ❌ 不免费 | 最便宜 $7/月 |

推荐使用 **Render**（完全免费）或 **Railway**（有免费额度）。

## 常见问题

**Q: 为什么我的部署应用不活跃？**
A: Render 免费计划中，不活跃 15 分钟后应用会进入休眠状态。首次访问会比较慢，但之后会恢复正常。

**Q: 如何更新代码？**
A: 推送到 GitHub，Render 会自动检测并重新部署。

**Q: DeepSeek API Key 安全吗？**
A: 安全。API Key 存储在 Render 的环境变量中，不会暴露在代码里。
