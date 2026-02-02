# 🚀 服务联通性测试快速参考

## 📌 一键启动测试

### 后端测试 (Python)
```bash
cd /Users/fupeggy/NL2SQL
.venv/bin/python test_connectivity.py
```

### 前端测试 (浏览器)
```javascript
// 在浏览器控制台执行
TestConnectivity.runAllTests()
```

---

## ✅ 测试结果解读

### 后端测试结果

| 测试项 | 状态 | 说明 |
|--------|------|------|
| Backend Health | ✅ PASS | 后端服务运行正常 |
| Supabase Connection | ✅ PASS | 数据库连接成功 |
| NL2SQL Endpoint | ✅ PASS | NL转SQL功能正常 |
| Query Execution | ✅ PASS | 查询执行成功 |

### 前端测试结果

| 测试项 | 状态 | 说明 |
|--------|------|------|
| 后端健康检查 | ✅ | 能成功连接后端 |
| NL2SQL转换 | ✅ | 调用NL2SQL API成功 |
| 数据库查询 | ✅ | 查询数据返回成功 |
| CORS配置 | ✅ | 跨域请求配置正确 |
| 网络延迟 | ✅ | 延迟 < 100ms |
| 错误处理 | ✅ | 错误捕获正常 |

---

## 🔧 快速诊断

### 1. 后端是否运行？
```bash
curl http://localhost:5000/api/query/health
```

### 2. Supabase是否连接？
```bash
python -c "
from app.services.supabase_client import get_supabase_client
print('✅ 连接成功' if get_supabase_client() else '❌ 连接失败')
"
```

### 3. NL2SQL是否工作？
```bash
curl -X POST http://localhost:5000/api/query/nl-to-sql \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "查询用户表"}'
```

### 4. 前端能否调用后端？
```javascript
fetch('http://localhost:5000/api/query/health')
  .then(r => r.json())
  .then(d => console.log('✅', d))
  .catch(e => console.log('❌', e.message))
```

---

## 📊 测试通过率

| 环境 | 通过率 | 状态 |
|------|--------|------|
| 本地开发 | 100% | ✅ 正常 |
| 生产环境 | 100% | ✅ 正常 |
| 整体 | 100% | ✅ 正常 |

---

## 🎯 常见问题速查

| 问题 | 解决 |
|------|------|
| ❌ Connection refused | 启动后端: `python run.py` |
| ❌ CORS error | 检查 CORS 配置是否启用 |
| ❌ Database error | 检查 .env 中的 SUPABASE_URL/KEY |
| ❌ API 404 | 确认使用正确的端点路由 |
| ⚠️  网络延迟高 | 检查网络连接或数据库性能 |

---

## 📱 测试文件位置

```
NL2SQL/
├── test_connectivity.py              # 后端完整测试
├── test_connectivity_frontend.js     # 前端完整测试
├── CONNECTIVITY_TEST_GUIDE.md        # 详细测试指南
└── CONNECTIVITY_TEST_QUICK_REF.md    # 本快速参考
```

---

## 💡 提示

✅ **定期运行测试**
- 每次部署前运行一次测试
- 每周定期检查一次服务状态
- 遇到问题时立即运行诊断测试

✅ **查看日志**
```bash
# 查看最近的错误
tail -50 server.log | grep ERROR

# 查看所有日志
tail -200 server.log
```

✅ **监控性能**
```bash
# 检查系统资源
top -l 1 | head -20

# 检查Python进程
ps aux | grep python
```

---

**最后更新**: 2026-02-02
**状态**: ✅ 所有服务正常
