# 🚀 NL2SQL 快速参考

## ⚡ 一键启动

```bash
cd /Users/fupeggy/NL2SQL
./start-full.sh
```

**输出示例：**
```
Your quick Tunnel has been created! Visit it at:
https://colored-hypothesis-animated-toddler.trycloudflare.com
```

---

## 🔗 前端 API 配置

### 在 Bolt.new 中更新：

**文件：** `src/services/nl2sqlApi.js`

```javascript
// 将这行改为从上面复制的 URL
const API_BASE_URL = 'https://colored-hypothesis-animated-toddler.trycloudflare.com/api/query';
```

**或使用环境变量（Vite 项目）：**

创建 `.env.local`：
```env
VITE_API_URL=https://colored-hypothesis-animated-toddler.trycloudflare.com/api/query
```

然后在 `nl2sqlApi.js` 中：
```javascript
const API_BASE_URL = import.meta.env.VITE_API_URL;
```

---

## ✅ 测试连接

### 方法 1：浏览器控制台
```javascript
fetch('https://colored-hypothesis-animated-toddler.trycloudflare.com/api/query/health')
  .then(r => r.json())
  .then(d => console.log('✅ Connected:', d))
  .catch(e => console.error('❌ Failed:', e))
```

### 方法 2：终端
```bash
curl https://colored-hypothesis-animated-toddler.trycloudflare.com/api/query/health
```

---

## 📡 API 端点

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/nl-execute-supabase` | NL→SQL→执行 |
| POST | `/nl-to-sql` | 仅转换 |
| GET | `/supabase/schema` | 获取表结构 |
| GET | `/supabase/connection` | 检查连接 |

**完整 URL 示例：**
```
https://colored-hypothesis-animated-toddler.trycloudflare.com/api/query/nl-execute-supabase
```

---

## 🛠️ 手动启动（分开启动）

### 终端 1：启动后端
```bash
cd /Users/fupeggy/NL2SQL
source .venv/bin/activate
python run.py
```

### 终端 2：启动隧道
```bash
cloudflared tunnel --url http://localhost:8000
```

---

## 🔍 调试

### 查看后端日志
```bash
tail -f logs/backend.log
```

### 查看隧道日志
```bash
tail -f logs/tunnel.log
```

### 杀死进程
```bash
# 后端
lsof -ti :8000 | xargs kill -9

# 隧道
lsof -ti :5200 | xargs kill -9
```

---

## 📋 检查清单

- [ ] 后端运行：`lsof -i :8000`
- [ ] 隧道运行：查看隧道输出
- [ ] 获取 URL：在隧道输出中查找 `trycloudflare.com`
- [ ] 前端配置：更新 `API_BASE_URL`
- [ ] 刷新页面：F5 或 Cmd+R
- [ ] 测试连接：查看 "✅ 已连接 Supabase"

---

## 🔐 生产部署

详见 `TUNNEL_SETUP_GUIDE.md` 中的**方案 4**

关键步骤：
1. 创建 Cloudflare 账户
2. 添加域名
3. 创建命名隧道
4. 配置 DNS
5. 启用 HTTPS（自动）

---

## 📞 常见问题

**Q: URL 每次启动都变化？**
A: 这是临时隧道的特性。使用方案 4 获取固定 URL。

**Q: 提示 "Failed to fetch"？**
A: 
1. 确认后端运行
2. 确认隧道运行
3. 检查 API_BASE_URL
4. 刷新页面（清除缓存）

**Q: CORS 错误？**
A: 后端已配置，应该没问题。检查 `app/__init__.py` 中的 CORS 设置。

---

## 📚 相关文件

| 文件 | 说明 |
|------|------|
| `start-full.sh` | 一键启动脚本 |
| `start-tunnel.sh` | 仅启动隧道 |
| `TUNNEL_SETUP_GUIDE.md` | 详细配置指南 |
| `FRONTEND_API_CONFIG.js` | 前端 API 配置模板 |
| `.env` | 后端环境变量 |

---

**最后更新：** 2026-02-01
