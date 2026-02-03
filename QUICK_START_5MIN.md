# 🚀 5 分钟快速开始指南

## 现在就开始！

### 1️⃣ 启动后端 (30 秒)

```bash
cd /Users/fupeggy/NL2SQL
python run.py
```

**预期输出**:
```
 * Running on http://127.0.0.1:8000
 * Debug mode: off
```

### 2️⃣ 启动前端 (30 秒)

打开新终端：

```bash
cd /Users/fupeggy/NL2SQL
npm run dev
```

**预期输出**:
```
Local:   http://localhost:5173/
```

### 3️⃣ 打开浏览器 (10 秒)

访问: **http://localhost:5173/**

### 4️⃣ 测试工作流 (3 分钟)

#### 步骤 A: 输入查询
在前端输入一个自然语言查询：
```
查询今天的OEE数据
```

#### 步骤 B: 查看澄清
系统会要求澄清：
```
• 您想查询哪个指标？(OEE, 良率, 效率, 停机时间等)
• 您想查询哪个时间段？(今天, 本周, 本月等)
```

#### 步骤 C: 回答澄清
选择或输入：
```
指标: OEE
时间段: 今天
```

#### 步骤 D: 查看 SQL
系统会生成 SQL 供审核

#### 步骤 E: 执行查询
点击"执行"按钮查看结果

---

## ✅ 验证清单

- [ ] 后端启动成功
- [ ] 前端启动成功
- [ ] 可以访问 http://localhost:5173/
- [ ] 可以输入查询
- [ ] 可以看到澄清问题
- [ ] 可以查看生成的 SQL
- [ ] 可以执行查询

## 🔍 调试提示

### 查看网络请求
1. 打开浏览器开发者工具 (F12)
2. 切换到 Network 标签
3. 输入查询
4. 查看网络请求
5. 应该看到 POST 请求到 `http://localhost:8000/api/query/unified/process`

### 查看后端日志
```bash
# 在后端运行的终端中可以看到日志
2026-02-03 15:10:00 - app.routes.unified_query_routes - INFO - Processing query...
```

### 查看前端日志
```bash
# 在前端运行的终端中可以看到日志
[vite] hmr update
```

## 📞 常见问题

### Q: 后端启动时说"Port 8000 already in use"
```bash
# A: 杀死占用端口的进程
pkill -f "python.*run.py"
python run.py
```

### Q: 前端显示 404 错误
```bash
# A: 检查 .env.frontend 文件
VITE_API_BASE_URL=http://localhost:8000/api/query/unified
```

### Q: 看不到澄清问题
```bash
# A: 确保输入了足够短的查询，比如：
"查询OEE"  # 会要求澄清
"查询今天上午OEE数据"  # 可能不需要澄清
```

## 🎯 后续步骤

### 深入了解
1. 阅读 [FRONTEND_INTEGRATION_ADJUSTMENTS.md](./FRONTEND_INTEGRATION_ADJUSTMENTS.md)
2. 查看代码示例 [FRONTEND_MIGRATION_EXAMPLES.tsx](./FRONTEND_MIGRATION_EXAMPLES.tsx)
3. 完成集成检查清单 [FRONTEND_INTEGRATION_CHECKLIST.md](./FRONTEND_INTEGRATION_CHECKLIST.md)

### 生产部署
1. 在 Render 仪表板设置环境变量
2. 提交代码到 Git
3. Render 会自动部署

### 更多功能
1. 添加自定义澄清问题
2. 实现结果可视化
3. 添加查询历史功能
4. 支持多个数据库

## 📊 系统架构

```
前端 (React/Vite)
    ↓ (HTTP POST/GET)
前端 API 客户端 (nl2sqlApi_v2.js)
    ↓
后端 API (Flask)
    ↓
统一查询服务
    ├─ 意图识别 (LLM + 规则)
    ├─ SQL 生成
    ├─ SQL 执行
    └─ 结果格式化
    ↓
数据库 (Supabase PostgreSQL)
```

## 💾 重要文件

| 文件 | 用途 |
|-----|------|
| `run.py` | 后端入口 |
| `.env` | 后端配置 |
| `.env.frontend` | 前端配置 |
| `src/services/nl2sqlApi_v2.js` | 前端 API 客户端 |
| `app/routes/unified_query_routes.py` | 后端 API 路由 |
| `app/services/unified_query_service.py` | 统一查询服务 |

## 🆘 需要帮助？

### 立即查看
- [QUICK_FIX_CORS_404.md](./QUICK_FIX_CORS_404.md) - 404/CORS 问题
- [FRONTEND_API_CONFIGURATION.md](./FRONTEND_API_CONFIGURATION.md) - API 配置
- [BACKEND_API_VERIFICATION_GUIDE.md](./BACKEND_API_VERIFICATION_GUIDE.md) - API 测试

### 完整文档
- [PROJECT_STATUS_COMPLETE.md](./PROJECT_STATUS_COMPLETE.md) - 项目完整状态
- [PROBLEM_RESOLUTION_SUMMARY.md](./PROBLEM_RESOLUTION_SUMMARY.md) - 问题解决总结
- [BACKEND_STARTUP_COMPLETE.md](./BACKEND_STARTUP_COMPLETE.md) - 启动状态

---

**祝您使用愉快！** 🎉

在 5 分钟内您可以看到一个完整的 NL2SQL 查询工作流程。

如有任何问题，参考上面的常见问题或查看详细文档。

