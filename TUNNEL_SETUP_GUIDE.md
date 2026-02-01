# NL2SQL 前后端集成配置指南

## 🌉 前端与后端连接方案

由于前端在 WebContainer（云环境），后端在本地，需要通过公网隧道连接。本文档说明所有可用方案。

---

## 📋 快速对比

| 方案 | URL | 可用范围 | 稳定性 | 何时用 |
|------|-----|---------|--------|--------|
| **方案1：本地回环** | `http://localhost:8000` | 🏠 仅本地 | ⭐⭐⭐⭐⭐ | 本地开发 |
| **方案2：内网 IP** | `http://192.168.2.13:8000` | 🏢 同一网络 | ⭐⭐⭐⭐ | 内网应用 |
| **方案3：Cloudflare 临时** | `https://colored-...trycloudflare.com` | 🌐 全球 | ⭐⭐⭐ | 快速测试 |
| **方案4：Cloudflare 固定** | `https://nl2sql-api.xxx.com` | 🌐 全球 | ⭐⭐⭐⭐⭐ | 生产环境 ✅ |

---

## 🚀 快速开始（推荐：方案3 - Cloudflare 临时）

### 后端设置（本地）

1. **启动后端 + 隧道**
   ```bash
   # 方法1：使用提供的脚本
   cd /Users/fupeggy/NL2SQL
   ./start-tunnel.sh
   
   # 方法2：手动启动
   # 终端1：启动后端
   source .venv/bin/activate && python run.py
   
   # 终端2：启动隧道
   cloudflared tunnel --url http://localhost:8000
   ```

2. **获取公网 URL**
   - 脚本输出中查看类似：
   ```
   Your quick Tunnel has been created! Visit it at:
   https://colored-hypothesis-animated-toddler.trycloudflare.com
   ```

### 前端设置（Bolt.new）

3. **更新 `src/services/nl2sqlApi.js`**
   ```javascript
   // 将这一行改为你的实际 URL
   const API_BASE_URL = 'https://colored-hypothesis-animated-toddler.trycloudflare.com/api/query';
   ```

4. **刷新页面测试**
   - 应看到 "✅ 已连接 Supabase" 状态

---

## 🔧 方案4：Cloudflare 固定 URL（生产推荐）

### 创建固定隧道步骤

#### 步骤 1：创建 Cloudflare 账户
- 访问 https://dash.cloudflare.com
- 注册免费账户

#### 步骤 2：添加域名（如果没有）
- 使用 Cloudflare Worker 子域
- 或购买/转移域名到 Cloudflare

#### 步骤 3：创建隧道配置

在后端项目根目录创建 `~/.cloudflared/config.yml`：

```yaml
tunnel: nl2sql-backend
credentials-file: /Users/fupeggy/.cloudflared/nl2sql-backend.json

ingress:
  - hostname: nl2sql-api.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
```

#### 步骤 4：创建隧道
```bash
# 登录 Cloudflare
cloudflared tunnel login

# 创建隧道
cloudflared tunnel create nl2sql-backend

# 使用配置启动
cloudflared tunnel run nl2sql-backend
```

#### 步骤 5：配置 DNS
- 访问 Cloudflare 仪表板
- 添加 CNAME 记录指向隧道

---

## 📝 配置文件更新

### 后端配置 (`.env`)

```env
# 数据库配置
DB_HOST=aws-0-ap-south-1.pooler.supabase.com
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password
DB_NAME=postgres

# LLM 配置
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
LLM_PROVIDER=deepseek
```

### 前端配置 (`.env.local` 或 `.env`)

**Vite 项目：**
```env
VITE_API_URL=https://your-tunnel-url.com/api/query
VITE_DEBUG_API=true
```

**React + Create React App：**
```env
REACT_APP_API_URL=https://your-tunnel-url.com/api/query
REACT_APP_DEBUG_API=true
```

**Bolt.new（编辑环境变量）：**
```javascript
// 在 src/services/nl2sqlApi.js 中直接修改
const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://...';
```

---

## 🔍 调试技巧

### 检查后端连接

```bash
# 检查后端是否运行
curl http://localhost:8000/api/query/health

# 通过隧道测试
curl https://your-tunnel-url/api/query/health
```

### 前端控制台测试

```javascript
// 在浏览器控制台执行
fetch('https://your-tunnel-url.com/api/query/health')
  .then(r => r.json())
  .then(d => console.log('✅ Connected:', d))
  .catch(e => console.error('❌ Failed:', e))
```

### 查看日志

```bash
# 后端日志
tail -f /Users/fupeggy/NL2SQL/nohup.out

# 隧道日志
# 查看启动隧道的终端输出
```

---

## 🆘 常见问题

### Q: 前端提示 "Failed to fetch"
**A:** 
1. 检查后端是否运行：`lsof -i :8000`
2. 检查隧道是否运行：查看隧道终端输出
3. 检查 API_BASE_URL 是否正确
4. 检查浏览器控制台是否有 CORS 错误

### Q: 隧道 URL 每次启动都变化
**A:** 使用方案4（固定隧道）。临时隧道（方案3）不会保持 URL。

### Q: Supabase 无法连接
**A:**
1. 检查 `.env` 中的 Supabase 凭证
2. 测试连接：访问 `/api/query/supabase/connection`
3. 检查 Supabase 项目是否有效

### Q: CORS 错误
**A:** 后端已配置允许 WebContainer 跨域请求，应该没问题。如有问题，检查 `app/__init__.py` 中的 CORS 配置。

---

## 📚 相关文件

- **后端启动脚本**: `start-tunnel.sh`
- **API 配置**: `FRONTEND_API_CONFIG.js`
- **环境示例**: `.env.frontend.example`
- **后端配置**: `.env`

---

## ✅ 验证清单

启动前检查：
- [ ] 后端已启动（`python run.py`）
- [ ] 隧道已启动（`cloudflared tunnel --url ...`）
- [ ] 前端 API_BASE_URL 已更新
- [ ] 前端已刷新页面

连接测试：
- [ ] 访问 `{API_URL}/health` 返回状态
- [ ] 前端显示 "✅ 已连接"
- [ ] 可以执行 NL2SQL 查询

---

## 📞 需要帮助？

检查以下资源：
1. 后端日志：`/Users/fupeggy/NL2SQL/run.py`
2. 前端浏览器控制台（F12）
3. Cloudflare Tunnel 文档：https://developers.cloudflare.com/cloudflare-one/
