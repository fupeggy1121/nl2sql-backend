# 前端 API 配置指南

## 问题描述

前端在调用后端 API 时遇到 404 Not Found 错误，原因是 API 基础 URL 配置不正确。

## 根本原因

后端 API 的统一查询路由使用前缀 `/api/query/unified`，但如果前端配置的基础 URL 不包含这个路径，就会导致请求失败。

### 例如：
- ❌ **错误**: `REACT_APP_API_URL=https://nl2sql-backend.onrender.com/api` → 请求 `/api/explain-query` 
- ✅ **正确**: `VITE_API_BASE_URL=https://nl2sql-backend.onrender.com/api/query/unified` → 请求 `/api/query/unified/process`

## 解决方案

### 1. 创建前端环境变量文件

在项目根目录创建 `.env.frontend` 文件：

```bash
# 开发环境
VITE_API_BASE_URL=http://localhost:8000/api/query/unified

# 或生产环境（Render）
VITE_API_BASE_URL=https://nl2sql-backend-amok.onrender.com/api/query/unified
```

### 2. 配置说明

#### 本地开发

```env
# .env.frontend
VITE_API_BASE_URL=http://localhost:8000/api/query/unified
REACT_APP_API_URL=http://localhost:8000
VITE_DEBUG=true
```

运行前端：
```bash
npm run dev  # Vite 会自动读取 .env.frontend
```

#### Render 生产环境

```env
# .env.frontend
VITE_API_BASE_URL=https://nl2sql-backend-amok.onrender.com/api/query/unified
REACT_APP_API_URL=https://nl2sql-backend-amok.onrender.com
VITE_DEBUG=false
```

### 3. 环境变量优先级

前端 API 服务现在支持多种环境变量方式，优先级如下：

1. **Vite 环境变量**（推荐）
   - `import.meta.env.VITE_API_BASE_URL`
   - 需要在 `.env.frontend` 中配置

2. **React 环境变量**（备选）
   - `process.env.REACT_APP_API_URL`
   - 会自动拼接 `/api/query/unified`

3. **本地默认值**
   - `http://localhost:8000/api/query/unified`

## 后端 API 路由说明

后端所有统一查询 API 都在 `/api/query/unified` 路径下：

| 端点 | 方法 | 功能 |
|-----|------|------|
| `/api/query/unified/process` | POST | 处理自然语言查询 |
| `/api/query/unified/explain` | POST | 仅获取 SQL 解释 |
| `/api/query/unified/execute` | POST | 执行 SQL 查询 |
| `/api/query/unified/suggest-variants` | POST | 获取 SQL 变体 |
| `/api/query/unified/validate-sql` | POST | 验证 SQL |
| `/api/query/unified/query-recommendations` | GET | 获取推荐查询 |
| `/api/query/unified/execution-history` | GET | 获取执行历史 |

## CORS 配置

后端已配置 CORS 中间件，支持：

```python
CORS(app, 
     origins="*",  # 允许所有源
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
     allow_headers=["*"],  # 允许所有请求头
     expose_headers=["*"],  # 暴露所有响应头
     max_age=3600)  # 预检结果缓存 1 小时
```

因此前端的 OPTIONS 预检请求会被自动处理，无需额外配置。

## 前端代码更新

已更新 `src/services/nl2sqlApi_v2.js`，现在支持动态 API 基础 URL：

```javascript
// 支持 Vite 和 React 环境变量
const getApiBaseUrl = () => {
  if (typeof import !== 'undefined' && import.meta?.env?.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  if (typeof process !== 'undefined' && process.env?.REACT_APP_API_URL) {
    return `${process.env.REACT_APP_API_URL}/api/query/unified`;
  }
  return 'http://localhost:8000/api/query/unified';
};

const UNIFIED_API_URL = getApiBaseUrl();
```

## 测试步骤

### 1. 验证本地后端

```bash
# 启动后端
python run.py

# 测试 API
curl -X GET http://localhost:8000/api/query/unified/query-recommendations
```

### 2. 前端开发环境测试

```bash
# 确保 .env.frontend 中配置了正确的 API URL
VITE_API_BASE_URL=http://localhost:8000/api/query/unified

# 启动前端
npm run dev

# 在浏览器开发者工具中检查网络请求
# 应该看到对 http://localhost:8000/api/query/unified/process 的请求
```

### 3. 完整工作流测试

```bash
# 1. 启动后端
python run.py

# 2. 启动前端
npm run dev

# 3. 在前端界面输入查询
# 应该看到：
# - ✅ OPTIONS 请求返回 200
# - ✅ POST 请求返回 200 和 JSON 响应
# - ✅ 查询意图识别结果显示
# - ✅ 澄清问题（如需要）显示
```

## 常见问题排查

### 问题 1: 仍然看到 404 Not Found

**原因**: API 基础 URL 配置不正确

**解决**:
1. 检查 `.env.frontend` 文件中的 `VITE_API_BASE_URL`
2. 确保包含完整的 `/api/query/unified` 路径
3. 清除 npm 缓存并重启开发服务器
   ```bash
   rm -rf node_modules/.vite
   npm run dev
   ```

### 问题 2: CORS 错误

**原因**: 后端 CORS 配置问题

**解决**:
1. 确保后端已启动
2. 检查后端 `app/__init__.py` 中的 CORS 配置
3. 确保 `methods` 包含 `OPTIONS`

### 问题 3: OPTIONS 请求返回 404

**原因**: 后端某些路由没有正确处理 OPTIONS 请求

**解决**:
1. 确保使用统一查询路由（`/api/query/unified/*`）
2. 检查 Flask-CORS 中间件是否正确注册在蓝图之前
3. 查看后端日志确认 OPTIONS 请求是否到达

## 生产环境部署

### Render 环境变量配置

1. 登录 Render 仪表板
2. 选择前端服务
3. 进入 "Environment" 设置
4. 添加环境变量：

```
VITE_API_BASE_URL=https://nl2sql-backend-amok.onrender.com/api/query/unified
REACT_APP_API_URL=https://nl2sql-backend-amok.onrender.com
```

5. 重新部署前端

### 验证生产环境

```bash
# 从生产环境测试
curl -X OPTIONS https://your-frontend-url/api \
  -H "Origin: https://your-frontend-url"

# 应该返回 CORS 头和 200 状态
```

## 参考链接

- [FRONTEND_INTEGRATION_ADJUSTMENTS.md](./FRONTEND_INTEGRATION_ADJUSTMENTS.md) - 前端集成调整指南
- [BACKEND_API_VERIFICATION_GUIDE.md](./BACKEND_API_VERIFICATION_GUIDE.md) - 后端 API 验证指南
- [app/__init__.py](./app/__init__.py#L30-L50) - 后端 CORS 配置

