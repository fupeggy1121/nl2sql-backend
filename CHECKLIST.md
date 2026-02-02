# ✅ 行动清单 - 从报错到正常工作

## 📋 问题状态
- ❌ 前端报错：`Failed to fetch`
- ❌ 后端报告：`supabase: disconnected`

---

## 🎯 3 分钟快速修复（推荐）

### ① 获取 Supabase 凭证（1 分钟）

- [ ] 访问 https://app.supabase.com
- [ ] 选择你的项目
- [ ] 进入 Settings → API
- [ ] **复制这两个值：**
  - [ ] Project URL: `https://...supabase.co`
  - [ ] Service Role Secret: `eyJ...` (长字符串)

**⚠️ 重要：** 复制的是 **Service Role Secret** 不是 Anon 密钥！

### ② 在 Render 中配置（1 分钟）

- [ ] 访问 https://dashboard.render.com
- [ ] 找到 `nl2sql-backend-amok` 服务
- [ ] 进入 **Environment** 标签页
- [ ] 点击 **+ Add Environment Variable**
- [ ] 添加第一个变量：
  - Key: `SUPABASE_URL`
  - Value: `https://...supabase.co`
  - [ ] 点击 Save
- [ ] 再次点击 **+ Add Environment Variable**
- [ ] 添加第二个变量：
  - Key: `SUPABASE_SERVICE_KEY`
  - Value: `eyJ...` (完整的长密钥)
  - [ ] 点击 Save
- [ ] ⏳ 等待服务自动重新部署（1-2 分钟）

### ③ 验证连接（1 分钟）

在浏览器地址栏中访问：
```
https://nl2sql-backend-amok.onrender.com/api/query/health
```

- [ ] 看到 `"supabase": "connected"` ✅ **成功！**
- [ ] 看到 `"supabase": "disconnected"` ❌ 检查凭证是否正确

**或者** 在浏览器 Console 中运行：
```javascript
fetch('https://nl2sql-backend-amok.onrender.com/api/query/health')
  .then(r => r.json())
  .then(console.log)
```

---

## 🔧 如果上面不行，继续这些步骤

### ④ 确认前端 API 配置

在你的 Bolt 项目中：

- [ ] 打开或创建 `src/services/nl2sqlApi.js`
- [ ] 确认 API URL 是否正确：
  ```javascript
  const API_BASE_URL = 'https://nl2sql-backend-amok.onrender.com/api/query';
  ```
- [ ] 确认导出了 `nl2sqlApi` 对象
- [ ] 在统一聊天组件中正确导入

### ⑤ 清理浏览器缓存并重新加载

- [ ] 在 Bolt 项目中按 `Ctrl+Shift+Delete` (Windows) 或 `Cmd+Shift+Delete` (Mac)
- [ ] 清除缓存后重新加载页面
- [ ] 再次测试

### ⑥ 检查 Render 日志（如果还是不行）

- [ ] 登录 https://dashboard.render.com
- [ ] 选择 `nl2sql-backend-amok` 服务
- [ ] 点击 **Logs** 标签页
- [ ] 搜索 "supabase" 或 "error"
- [ ] 查看是否有错误提示

---

## 📚 对应的文档参考

| 步骤 | 文档 | 用途 |
|-----|------|------|
| 快速修复 | `QUICK_FIX_GUIDE.md` | 5 分钟解决方案 |
| Supabase 配置 | `RENDER_ENV_SETUP.md` | 详细配置步骤（含截图位置） |
| 深度排查 | `TROUBLESHOOTING_GUIDE.md` | 完整的故障排查 |
| API 代码 | `nl2sqlApi-template.js` | 前端 API 客户端代码 |
| 自动诊断 | `check-connection.sh` | 运行诊断脚本 |

---

## ✅ 成功的标志

当问题解决时，你会看到：

### ✅ 后端响应
```json
{
  "service": "NL2SQL Report Backend",
  "status": "healthy",
  "supabase": "connected"
}
```

### ✅ 前端 UI
顶部显示：`✅ 已连接`

### ✅ 功能测试
1. 输入自然语言问题
2. AI 生成 SQL 建议
3. 点击"执行查询"
4. 显示查询结果

---

## 🔴 如果还是有错误

### 收集诊断信息

在浏览器 Console 中运行：
```javascript
console.log('=== 诊断 ===');
fetch('https://nl2sql-backend-amok.onrender.com/api/query/health')
  .then(r => {
    console.log('HTTP Status:', r.status);
    return r.json();
  })
  .then(data => {
    console.log('Response:', JSON.stringify(data, null, 2));
    console.log('Supabase Status:', data.supabase);
  })
  .catch(err => console.error('Error:', err.message));
```

### 可能的错误和解决方案

| 错误 | 原因 | 解决方案 |
|-----|-----|---------|
| `Failed to fetch` | 网络/后端问题 | 检查 Render 是否在运行，URL 是否正确 |
| `HTTP 404` | 端点不存在 | 检查 URL 是否正确 |
| `HTTP 500` | 服务器错误 | 检查 Render 日志中的错误 |
| `supabase: disconnected` | 环境变量缺少/错误 | 重新检查 Render 环境变量 |
| CORS 错误 | 跨域问题 | 后端已配置 CORS，检查前端 URL |

---

## 🎁 完成后的下一步

### ① 提交代码更新
```bash
git add .
git commit -m "Fix: Configure Supabase environment variables"
git push origin main
```

### ② 测试完整功能流程
- [ ] 在统一聊天中输入自然语言查询
- [ ] 验证 SQL 建议生成
- [ ] 执行查询并验证结果
- [ ] 测试导出功能
- [ ] 测试反馈功能

### ③ 监控后续
- [ ] 定期检查 Render 日志
- [ ] 监控错误率
- [ ] 收集用户反馈

---

## 📞 仍需帮助？

### 快速参考
```bash
# 快速诊断
bash check-connection.sh

# 查看 Render 实时日志
curl -s https://nl2sql-backend-amok.onrender.com/api/query/health | python -m json.tool
```

### 相关文档
- 🚀 快速开始：`QUICK_FIX_GUIDE.md`
- 🔧 详细配置：`RENDER_ENV_SETUP.md`
- 🐛 问题排查：`TROUBLESHOOTING_GUIDE.md`
- 📋 完整总结：`SOLUTION_SUMMARY.md`

---

## ✨ 记住

**这是一个临时问题，3-5 分钟可以完全解决！**

一旦配置好 Supabase 环境变量，你的整个系统就会正常工作：

✅ 前端可以调用后端 API
✅ 后端可以连接数据库
✅ 用户可以执行 NL2SQL 查询
✅ 结果可以正确显示

---

**开始行动吧！** 祝你一切顺利 🎉

---

import os
from supabase import create_client, Client

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')

client = create_client(supabase_url, supabase_key)
