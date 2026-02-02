# OPTIONS 404 错误修复指南

## 问题诊断

### 症状
```
前端请求错误:
OPTIONS /api/query/check-connection
404 Not Found
```

### 根本原因

1. **缺少路由** ❌
   - 前端请求 `/api/query/check-connection`
   - 后端只有 `/api/query/supabase/connection` 路由
   - 浏览器的 CORS 预检请求（OPTIONS）返回 404

2. **CORS 中间件配置** ⚠️
   - 虽然配置了 CORS 中间件
   - 但对不存在的路由，中间件无法处理 OPTIONS 请求
   - 路由不存在 → 404 → 预检失败 → 浏览器阻止实际请求

### 浏览器行为流程

```
前端发送 POST /api/query/check-connection
    ↓
浏览器发送 OPTIONS 预检请求
    ├─ 请求头: Origin: https://...
    ├─ 请求头: Access-Control-Request-Method: POST
    ├─ 请求头: Access-Control-Request-Headers: Content-Type
    ↓
后端响应
    ├─ 404 Not Found ← 路由不存在！
    ├─ 无 CORS 响应头
    ↓
浏览器阻止实际请求
    ├─ 预检失败 = 跨域不安全
    ├─ 拒绝发送实际 POST 请求
    ↓
前端收到错误
```

## 解决方案

### 1️⃣ 添加缺失的路由

在 `app/routes/query_routes.py` 中添加：

```python
@bp.route('/check-connection', methods=['GET'])
def check_connection():
    """
    检查后端连接状态
    这是 /supabase/connection 的别名端点
    """
    return check_supabase_connection()
```

✅ **效果**:
- 现在 `/api/query/check-connection` 路由存在
- OPTIONS 预检请求会命中这个路由
- CORS 中间件可以正确处理 OPTIONS 请求
- 返回正确的 CORS 响应头

### 2️⃣ 改进 CORS 中间件配置

在 `app/__init__.py` 中改进配置：

```python
# 之前：使用 resources 模式（容易出问题）
CORS(app, resources={
    r"/api/*": {...}
})

# 之后：直接应用全局 CORS（更可靠）
CORS(app, 
     origins=cors_origins,
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
     allow_headers=["Content-Type", "Authorization"],
     expose_headers=["Content-Type"],
     supports_credentials=True,
     max_age=3600)
```

✅ **优势**:
- 对所有路由自动处理 OPTIONS 请求
- 明确包含 "HEAD" 和 "OPTIONS" 方法
- 更好的浏览器兼容性
- 支持缓存预检结果（max_age）

### 3️⃣ 环境检测改进

在 Render 部署时，确保正确的环境配置：

```python
# 获取环境变量
flask_env = os.getenv('FLASK_ENV', 'development')

# 根据环境选择 CORS 策略
if flask_env == 'production':
    # 允许特定域名
    cors_origins = [
        "https://bolt.new",
        "https://*.local-credentialless.webcontainer-api.io",
        # ... 其他允许的源
    ]
else:
    # 开发环境允许所有
    cors_origins = "*"
```

✅ **好处**:
- 支持多个部署环境
- 生产环境安全（仅特定来源）
- 开发环境灵活（允许所有来源）

## 验证修复

### 方法 1: 运行诊断脚本

```bash
python diagnose_cors.py
```

脚本会测试：
- 所有关键端点的 OPTIONS 预检请求
- 实际的 GET/POST 请求
- CORS 响应头的完整性
- 端点是否存在

### 方法 2: 手动测试

```bash
# 测试 OPTIONS 预检
curl -X OPTIONS https://nl2sql-backend-amok.onrender.com/api/query/check-connection \
  -H "Origin: https://your-frontend.com" \
  -H "Access-Control-Request-Method: GET" \
  -v

# 应该看到:
# HTTP/1.1 200 OK  ← 成功！
# Access-Control-Allow-Origin: ...
# Access-Control-Allow-Methods: GET, POST, OPTIONS
```

### 方法 3: 在浏览器中测试

```javascript
// 在前端控制台中运行
fetch('https://nl2sql-backend-amok.onrender.com/api/query/check-connection', {
  method: 'GET',
  headers: {
    'Content-Type': 'application/json'
  }
})
.then(r => r.json())
.then(d => console.log('✅ Success:', d))
.catch(e => console.error('❌ Error:', e))
```

应该看到：
- ✅ 预检请求成功 (OPTIONS 200)
- ✅ 实际请求成功 (GET 200)
- ✅ 返回连接状态数据

## 部署步骤

### 在 Render 上部署修复

1. **本地测试** ✓
   ```bash
   python run.py
   # 访问 http://localhost:5000/api/query/health
   ```

2. **提交更改**
   ```bash
   git add .
   git commit -m "Fix CORS OPTIONS 404 error"
   git push origin main
   ```

3. **Render 自动部署**
   - Render 会自动检测 push
   - 自动重新部署应用
   - 约 2-3 分钟部署完成

4. **验证部署**
   ```bash
   python diagnose_cors.py
   ```

## 文件清单

### 已修改的文件

| 文件 | 修改内容 |
|------|---------|
| `app/__init__.py` | 改进 CORS 中间件配置，支持环境变量 |
| `app/routes/query_routes.py` | 添加 `/check-connection` 别名路由 |

### 新增文件

| 文件 | 用途 |
|------|------|
| `diagnose_cors.py` | CORS 诊断工具，测试所有端点 |

## 相关端点清单

现在支持的连接检查端点：

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/query/check-connection` | GET | 通用连接检查（推荐前端使用） |
| `/api/query/supabase/connection` | GET | Supabase 连接检查（后端内部） |
| `/api/query/health` | GET | 应用健康检查 |

## CORS 流程图

### 修复前（失败）
```
前端 → OPTIONS 请求 → 后端
                      ↓
                  路由不存在 (404)
                      ↓
               预检失败
                      ↓
            浏览器阻止实际请求 ❌
```

### 修复后（成功）
```
前端 → OPTIONS 请求 → 后端
                      ↓
                  路由存在 ✓
                      ↓
               CORS 中间件处理
                      ↓
               返回 CORS 头 + 200
                      ↓
          预检成功 → 浏览器允许
                      ↓
          前端发送实际请求
                      ↓
               后端处理并返回数据 ✅
```

## 常见问题

### Q1: 为什么需要 OPTIONS 请求？

**A:** 这是浏览器的跨域安全机制（CORS）。当前端和后端不同源时，浏览器会先发送 OPTIONS 预检请求，确保后端允许跨域访问。

### Q2: 为什么 304 其他路由正常，只有这个 404？

**A:** 因为 `/check-connection` 路由不存在。其他路由（如 `/health`）存在，所以 OPTIONS 预检成功。

### Q3: 修复后为什么还是不工作？

**A:** 可能原因：
1. 修改后没有重新部署（等待 Render 自动部署）
2. 浏览器缓存了旧的响应（清除缓存或用无痕模式）
3. Render 部署失败（检查部署日志）

### Q4: 如何在生产环境中限制 CORS？

**A:** 在 `app/__init__.py` 中配置生产环境的允许源：

```python
if flask_env == 'production':
    cors_origins = [
        "https://yourdomain.com",
        "https://app.yourdomain.com",
    ]
```

## 下一步

1. ✅ 确保文件已提交到 Git
2. ✅ 等待 Render 自动部署（2-3 分钟）
3. ✅ 运行诊断脚本验证：`python diagnose_cors.py`
4. ✅ 在浏览器中测试前端应用
5. ✅ 检查浏览器 DevTools → Network，确认没有 OPTIONS 404

## 支持文件

- `diagnose_cors.py` - 运行诊断测试
- `app/__init__.py` - CORS 配置
- `app/routes/query_routes.py` - 端点定义

---

**修复完成！** 🎉 现在 OPTIONS 预检请求应该返回 200，前端应该能正常连接后端。
