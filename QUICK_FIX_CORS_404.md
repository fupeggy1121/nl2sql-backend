# 404/CORS 问题快速修复指南

## 🎯 问题症状

前端调用 API 时看到：
- ❌ `404 Not Found` 错误
- ❌ `Failed to fetch` 错误
- ❌ OPTIONS 请求失败

## 🔧 已实施的修复

### 修复 1: 创建环境变量文件

**文件**: `.env.frontend`

```env
# 开发环境
VITE_API_BASE_URL=http://localhost:8000/api/query/unified

# 生产环境（可选，部署时替换）
# VITE_API_BASE_URL=https://nl2sql-backend-amok.onrender.com/api/query/unified
```

### 修复 2: 更新前端 API 服务

**文件**: `src/services/nl2sqlApi_v2.js`

现在支持动态 API 基础 URL，自动使用环境变量。

### 修复 3: 后端 CORS 配置

**已验证**: 后端 `app/__init__.py` 中的 CORS 配置正确
- ✅ 支持 OPTIONS 方法
- ✅ 支持所有源 (`*`)
- ✅ 自动处理预检请求

## 📋 立即可做

### 本地开发

```bash
# 1. 确保后端运行
python run.py

# 2. 启动前端
npm run dev

# 3. 检查网络请求
# 打开浏览器开发者工具 → Network → 查找 /api/query/unified 请求
```

### Render 生产环境部署

```bash
# 1. 更新环境变量
VITE_API_BASE_URL=https://nl2sql-backend-amok.onrender.com/api/query/unified

# 2. 重新部署前端
git push origin main
```

## ✅ 验证修复

### 测试 OPTIONS 请求

```bash
curl -X OPTIONS http://localhost:8000/api/query/unified/process \
  -H "Origin: http://localhost:3000"
```

**预期结果**:
```
HTTP/1.1 200 OK
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS, HEAD
Access-Control-Allow-Headers: *
```

### 测试 API 请求

```bash
curl -X POST http://localhost:8000/api/query/unified/process \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "查询数据"}'
```

**预期结果**:
```json
{
  "success": true,
  "query_plan": {...}
}
```

## 📚 详细文档

- [FRONTEND_API_CONFIGURATION.md](./FRONTEND_API_CONFIGURATION.md) - 完整配置指南
- [BACKEND_API_VERIFICATION_GUIDE.md](./BACKEND_API_VERIFICATION_GUIDE.md) - API 测试指南
- [FRONTEND_INTEGRATION_ADJUSTMENTS.md](./FRONTEND_INTEGRATION_ADJUSTMENTS.md) - 集成指南

## 🚀 下一步

1. ✅ 确认 `.env.frontend` 文件已创建
2. ✅ 启动后端和前端
3. ✅ 测试 API 调用
4. ✅ 检查网络请求是否成功
5. ✅ 如果有其他问题，参考详细配置指南

## 💡 常见问题

**Q: 仍然看到 404 错误？**
A: 检查 `.env.frontend` 中的 `VITE_API_BASE_URL` 是否包含完整路径 `/api/query/unified`

**Q: 部署到 Render 后仍然失败？**
A: 确保在 Render 仪表板中设置了正确的环境变量

**Q: 如何验证 API 地址是否正确？**
A: 在浏览器开发者工具中查看 Network 标签，确认请求 URL 为 `http://localhost:8000/api/query/unified/process`

---

**修复提交**: a442fcf  
**修复时间**: 2026-02-03  
**状态**: ✅ 完成

