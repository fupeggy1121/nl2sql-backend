# 🔧 CORS 完整修复指南 - 解决"❌ 未连接"问题

## 问题症状

前端 AI 报表页面右上角状态显示：**❌ 未连接**

即使后端服务运行正常，前端也无法正确识别连接状态。

## 根本原因

CORS 预检（OPTIONS）请求失败，导致浏览器阻止跨域请求。

### 浏览器 CORS 预检流程

```
前端请求 → 浏览器发送 OPTIONS 预检 → 后端响应
                                    ↓
                    检查 Access-Control-Allow-Origin
                    检查 Access-Control-Allow-Methods
                    检查 Access-Control-Allow-Headers
                                    ↓
                            都正确 ✅ → 发送实际请求
                            任一缺失 ❌ → 阻止实际请求
```

## ✅ 已应用的修复

### 修复 1: 优化 CORS 中间件配置

**文件:** `app/__init__.py` (第 28-50 行)

```python
CORS(app, 
     origins="*",                    # ← 允许所有源（解决源限制问题）
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
     allow_headers=["*"],            # ← 允许所有请求头（而非仅 Content-Type）
     expose_headers=["*"],           # ← 暴露所有响应头（而非仅 Content-Type）
     supports_credentials=False,     # ← 与 origins="*" 配合
     max_age=3600,
     send_wildcard=False,
     always_send=True)              # ← 始终发送 CORS 头
```

**关键改进:**
- ✅ `origins="*"` 允许所有来源的请求
- ✅ `allow_headers=["*"]` 允许所有请求头（包括自定义头）
- ✅ `expose_headers=["*"]` 暴露所有响应头给前端
- ✅ `always_send=True` 确保即使不是跨域请求也发送 CORS 头

### 修复 2: 添加 CORS 诊断端点

**文件:** `app/routes/query_routes.py` (第 487-525 行)

```python
@bp.route('/cors-check', methods=['GET', 'OPTIONS'])
def cors_check():
    """
    CORS 诊断端点
    支持 GET 和 OPTIONS 请求
    用于前端验证 CORS 配置是否正确
    """
```

**新端点使用:**
```bash
# 测试 OPTIONS 预检
curl -X OPTIONS https://nl2sql-backend-amok.onrender.com/api/query/cors-check -v

# 测试 GET 请求
curl https://nl2sql-backend-amok.onrender.com/api/query/cors-check
```

**预期响应:**
```json
{
  "cors_enabled": true,
  "method": "GET|OPTIONS",
  "request_origin": "...",
  "message": "CORS is properly configured",
  "timestamp": "2026-02-03T..."
}
```

## 🔍 验证修复

### 本地验证

```bash
# 1. 启动本地后端
python run.py

# 2. 测试 CORS 诊断端点
curl -X OPTIONS http://localhost:5000/api/query/cors-check -v

# 3. 检查响应头中是否包含：
#    Access-Control-Allow-Origin: *
#    Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS, HEAD
#    Access-Control-Allow-Headers: *
```

### 生产环境验证（Render）

```bash
# 测试 OPTIONS 预检请求
curl -X OPTIONS https://nl2sql-backend-amok.onrender.com/api/query/cors-check \
  -H "Origin: https://zp1v56uxy8rdx5ypatb0ockcb9tr6a-oci3--5173--31fc58ec.local-credentialless.webcontainer-api.io" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  -v

# 检查响应（HTTP 200 和 CORS 头）
```

### 浏览器控制台验证

```javascript
// 在前端应用的浏览器控制台中运行：

// 1. 测试 CORS 诊断端点
fetch('https://nl2sql-backend-amok.onrender.com/api/query/cors-check')
  .then(r => {
    console.log('✅ CORS 预检成功');
    console.log('状态码:', r.status);
    console.log('Access-Control-Allow-Origin:', r.headers.get('access-control-allow-origin'));
    return r.json();
  })
  .then(d => console.log('响应:', d))
  .catch(e => console.error('❌ CORS 失败:', e.message));

// 2. 测试健康检查端点
fetch('https://nl2sql-backend-amok.onrender.com/api/query/health')
  .then(r => r.json())
  .then(d => console.log('✅ 健康检查:', d.status))
  .catch(e => console.error('❌ 错误:', e.message));

// 3. 测试连接检查端点
fetch('https://nl2sql-backend-amok.onrender.com/api/query/check-connection')
  .then(r => r.json())
  .then(d => console.log('✅ 连接状态:', d.connected))
  .catch(e => console.error('❌ 错误:', e.message));
```

## 📊 CORS 头部验证清单

### OPTIONS 预检响应应该包含：

```
✅ HTTP/1.1 200 OK
✅ Access-Control-Allow-Origin: *
✅ Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS, HEAD
✅ Access-Control-Allow-Headers: *
✅ Access-Control-Max-Age: 3600
```

### 实际请求响应应该包含：

```
✅ HTTP/1.1 200 OK
✅ Access-Control-Allow-Origin: *
✅ Content-Type: application/json
✅ （其他响应头）
```

## 🧪 测试所有关键端点

### 完整测试脚本

```bash
#!/bin/bash

BASE_URL="https://nl2sql-backend-amok.onrender.com/api/query"

echo "🧪 NL2SQL 后端 CORS 完整测试"
echo "========================================"

# 1. 测试 CORS 诊断端点
echo ""
echo "1️⃣ 测试 CORS 诊断端点..."
curl -X GET "$BASE_URL/cors-check" -v 2>&1 | grep -E "< HTTP|< Access-Control|cors_enabled"

# 2. 测试 OPTIONS 预检
echo ""
echo "2️⃣ 测试 OPTIONS 预检请求..."
curl -X OPTIONS "$BASE_URL/health" \
  -H "Origin: https://bolt.new" \
  -H "Access-Control-Request-Method: GET" \
  -v 2>&1 | grep -E "< HTTP|< Access-Control"

# 3. 测试健康检查
echo ""
echo "3️⃣ 测试健康检查端点..."
curl "$BASE_URL/health" -s | python -m json.tool | head -10

# 4. 测试连接检查
echo ""
echo "4️⃣ 测试连接检查端点..."
curl "$BASE_URL/check-connection" -s | python -m json.tool | head -5

# 5. 测试意图识别
echo ""
echo "5️⃣ 测试意图识别端点..."
curl -X POST "$BASE_URL/recognize-intent" \
  -H "Content-Type: application/json" \
  -d '{"query":"测试"}' \
  -s | python -m json.tool | head -15
```

## 🎯 前端集成

### 前端状态检查代码

```javascript
// src/services/nl2sqlApi.js

const API_BASE_URL = 'https://nl2sql-backend-amok.onrender.com/api/query';

/**
 * 检查后端连接状态
 * 返回: { connected: boolean, status?: string, error?: string }
 */
export async function checkConnection() {
  try {
    // 先测试 CORS 诊断端点
    const corsResponse = await fetch(`${API_BASE_URL}/cors-check`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (!corsResponse.ok) {
      throw new Error(`CORS 检查失败: ${corsResponse.status}`);
    }
    
    const corsData = await corsResponse.json();
    console.log('✅ CORS 正常:', corsData.cors_enabled);
    
    // 然后测试健康检查端点
    const healthResponse = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (!healthResponse.ok) {
      throw new Error(`健康检查失败: ${healthResponse.status}`);
    }
    
    const healthData = await healthResponse.json();
    
    // 检查 Supabase 连接
    const isConnected = healthData.supabase === 'connected';
    
    return {
      connected: isConnected,
      status: healthData.status,
      supabase: healthData.supabase,
      cors: corsData.cors_enabled
    };
    
  } catch (error) {
    console.error('❌ 连接检查失败:', error);
    return {
      connected: false,
      error: error.message,
      cors: false
    };
  }
}
```

## 🚀 部署步骤

### 1. 提交更改

```bash
cd /Users/fupeggy/NL2SQL

# 确认所有更改
git status

# 提交
git add app/__init__.py app/routes/query_routes.py
git commit -m "Optimize CORS configuration to fix frontend connection status display issue"

# 推送
git push origin main
```

### 2. 等待 Render 部署

- Render 自动检测 GitHub 推送
- 部署时间：2-3 分钟
- 可在 [Render Dashboard](https://dashboard.render.com) 查看状态

### 3. 验证部署

```bash
# 等待 2-3 分钟后测试
curl https://nl2sql-backend-amok.onrender.com/api/query/cors-check -v

# 检查响应中的 CORS 头
```

### 4. 测试前端

- 打开前端应用
- 检查右上角的连接状态
- 应该显示 **✅ 已连接** 而不是 **❌ 未连接**

## 📋 检查清单

### 配置检查

- ✅ `origins="*"` - 允许所有源
- ✅ `allow_headers=["*"]` - 允许所有请求头
- ✅ `expose_headers=["*"]` - 暴露所有响应头
- ✅ `always_send=True` - 始终发送 CORS 头
- ✅ `send_wildcard=False` - 与凭证配合
- ✅ 蓝图在 CORS 后注册 - 正确顺序

### 路由检查

- ✅ `/cors-check` - CORS 诊断端点
- ✅ `/health` - 健康检查端点
- ✅ `/check-connection` - 连接检查端点
- ✅ `/recognize-intent` - 意图识别端点

### 测试检查

- ✅ OPTIONS 返回 200 OK
- ✅ CORS 头正确返回
- ✅ GET 请求成功
- ✅ POST 请求成功

## 🐛 如果仍有问题

### 问题 1: OPTIONS 仍然返回 404

**原因:** 代码未部署到 Render  
**解决:**
```bash
git push origin main
# 等待 2-3 分钟
curl https://nl2sql-backend-amok.onrender.com/api/query/cors-check -v
```

### 问题 2: CORS 头缺失

**原因:** CORS 中间件未正确应用  
**解决:**
```bash
# 检查 app/__init__.py 中 CORS() 的配置
# 确保在 register_blueprints() 之前

python run.py  # 本地测试
curl -X OPTIONS http://localhost:5000/api/query/cors-check -v
```

### 问题 3: 浏览器仍显示"❌ 未连接"

**原因:** 可能是前端代码的连接检查逻辑  
**解决:**
```javascript
// 在浏览器控制台检查
fetch('https://nl2sql-backend-amok.onrender.com/api/query/cors-check')
  .then(r => r.json())
  .then(d => console.log('✅ CORS OK:', d))
  .catch(e => console.error('❌ CORS 失败:', e))
```

### 问题 4: Render 部署失败

**检查:**
- 访问 [Render Dashboard](https://dashboard.render.com)
- 查看 nl2sql-backend 的构建日志
- 查找错误信息

**常见错误:**
```
- ImportError: 某个模块未找到
  → 解决: pip install 缺失的模块

- SyntaxError: 代码有语法错误
  → 解决: python -m py_compile 检查语法

- PermissionError: 权限不足
  → 解决: 检查文件权限
```

## 📚 参考资源

- [Flask-CORS 文档](https://flask-cors.readthedocs.io/)
- [MDN CORS 指南](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [Render 部署指南](https://render.com/docs)

## ✨ 总结

这个修复通过以下方式解决"❌ 未连接"问题：

1. **宽松的 CORS 策略** - `origins="*"` 接受所有来源
2. **完整的请求头** - `allow_headers=["*"]` 允许所有请求头
3. **完整的响应头** - `expose_headers=["*"]` 暴露所有响应头
4. **始终发送 CORS** - `always_send=True` 确保响应中包含 CORS 头
5. **诊断端点** - `/cors-check` 便于快速验证配置

**部署后，前端应该能正确连接到后端，状态显示应为 ✅ 已连接。**

---

**文档版本:** 2026-02-03  
**状态:** ✅ 已部署  
**优先级:** 🔴 高
