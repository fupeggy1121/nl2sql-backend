# 🎯 后端 API 验证和测试指南

## ✅ 问题已修复

**问题**: 端口 8000 被占用，API 返回 500 和 404 错误  
**原因**: 统一查询路由使用了异步函数，但 Flask 不支持  
**修复**: 转换为同步函数，使用 `asyncio.run()` 调用异步服务

---

## 🚀 启动后端

```bash
cd /Users/fupeggy/NL2SQL
source .venv/bin/activate
python run.py
```

或使用 VS Code 任务:
```
Ctrl+Shift+P → Tasks: Run Task → 启动 NL2SQL 后端应用
```

---

## 🧪 API 端点测试

### 1️⃣ 健康检查

```bash
curl http://localhost:8000/api/schema/status
```

**预期响应**:
```json
{
  "success": true,
  "status": {
    "tables": {"approved": 2, "total": 2},
    "columns": {"approved": 5, "total": 5}
  }
}
```

### 2️⃣ 处理查询 (完整流程)

```bash
curl -X POST http://localhost:8000/api/query/unified/process \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "获取OEE数据", "execution_mode": "explain"}'
```

**预期响应**: 
```json
{
  "success": true,
  "query_plan": {
    "query_intent": {...},
    "generated_sql": "SELECT ...",
    "requires_clarification": false
  }
}
```

或如果需要澄清:
```json
{
  "success": true,
  "query_plan": {
    "query_intent": {...},
    "requires_clarification": true,
    "clarification_questions": [
      "您想查询哪个指标？(OEE, 良率, 效率, 停机时间等)",
      "您想查询哪个时间段？(今天, 本周, 本月等)"
    ]
  }
}
```

### 3️⃣ 仅解释 SQL (不执行)

```bash
curl -X POST http://localhost:8000/api/query/unified/explain \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "对比A和B设备的产量"}'
```

### 4️⃣ 执行 SQL

```bash
curl -X POST http://localhost:8000/api/query/unified/execute \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT * FROM production_orders LIMIT 10",
    "query_intent": {"query_type": "direct_table"}
  }'
```

### 5️⃣ 验证 SQL 语法

```bash
curl -X POST http://localhost:8000/api/query/unified/validate-sql \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM production_orders WHERE date > '\''2026-01-01'\''"}'
```

**预期响应**:
```json
{
  "success": true,
  "is_valid": true,
  "errors": [],
  "warnings": ["建议添加LIMIT子句以限制返回行数"]
}
```

### 6️⃣ 获取 SQL 变体

```bash
curl -X POST http://localhost:8000/api/query/unified/suggest-variants \
  -H "Content-Type: application/json" \
  -d '{
    "natural_language": "获取OEE数据",
    "base_sql": "SELECT * FROM equipment"
  }'
```

### 7️⃣ 获取推荐查询

```bash
curl -X GET http://localhost:8000/api/query/unified/query-recommendations
```

**预期响应**:
```json
{
  "success": true,
  "recommendations": [
    {
      "title": "查看今天的OEE",
      "natural_language": "查询今天各设备的OEE数据",
      "category": "metric",
      "icon": "chart"
    },
    ...
  ]
}
```

### 8️⃣ 获取执行历史

```bash
curl -X GET "http://localhost:8000/api/query/unified/execution-history?limit=10"
```

---

## 📊 完整工作流示例

### 场景: 查询今天的设备效率

**Step 1**: 用户输入自然语言查询
```bash
curl -X POST http://localhost:8000/api/query/unified/process \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "查看今天各设备的效率", "execution_mode": "explain"}'
```

**Step 2**: 后端返回可能需要澄清
```json
{
  "success": true,
  "query_plan": {
    "requires_clarification": true,
    "clarification_questions": [
      "您想按哪个时间粒度查看？(小时、班次、整天)",
      "是否包含停机时间分析？"
    ]
  }
}
```

**Step 3**: 用户回答澄清问题 (在新请求中)
```bash
curl -X POST http://localhost:8000/api/query/unified/process \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "查看今天各设备的效率，按小时粒度，包含停机时间", "execution_mode": "explain"}'
```

**Step 4**: 后端生成 SQL
```json
{
  "success": true,
  "query_plan": {
    "query_intent": {...},
    "generated_sql": "SELECT date_trunc('"'"'hour'"'"', timestamp) as hour, equipment_id, SUM(efficiency) / COUNT(*) as avg_efficiency, SUM(downtime) as total_downtime FROM production_records WHERE date = CURRENT_DATE GROUP BY 1, 2 ORDER BY 1, 2",
    "explanation": "此查询计算今天每个设备每小时的平均效率和停机时间",
    "requires_clarification": false
  }
}
```

**Step 5**: 用户审核 SQL (可编辑)

**Step 6**: 用户批准执行
```bash
curl -X POST http://localhost:8000/api/query/unified/execute \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT date_trunc('"'"'hour'"'"', timestamp) as hour, equipment_id, SUM(efficiency) / COUNT(*) as avg_efficiency FROM production_records WHERE date = CURRENT_DATE GROUP BY 1, 2 ORDER BY 1, 2",
    "query_intent": {"query_type": "metric", "metric": "efficiency"}
  }'
```

**Step 7**: 后端返回结果
```json
{
  "success": true,
  "query_result": {
    "success": true,
    "data": [
      {"hour": "2026-02-03T08:00:00", "equipment_id": "E001", "avg_efficiency": 0.92},
      {"hour": "2026-02-03T09:00:00", "equipment_id": "E001", "avg_efficiency": 0.88},
      ...
    ],
    "rows_count": 24,
    "summary": "查询返回今天24个小时的设备效率数据",
    "visualization_type": "line"
  }
}
```

---

## 🔧 常见问题排查

### Q1: API 返回 500 错误

**检查清单**:
1. 确认后端正在运行: `ps aux | grep "python.*run.py"`
2. 检查日志: `tail -50 /tmp/backend.log`
3. 验证 schema 已加载: `curl http://localhost:8000/api/schema/status`
4. 检查请求格式是否正确

### Q2: 澄清问题未显示

**原因**: 某些查询可能被识别为足够清晰  
**解决**: 尝试更模糊的查询或检查后端日志

### Q3: SQL 生成失败

**检查清单**:
1. 意图识别是否成功: 检查 `query_plan.query_intent`
2. Schema 是否正确加载: 检查 `/api/schema/status`
3. LLM 是否可用: 检查 DeepSeek API 配置

### Q4: 执行查询超时

**解决方案**:
1. 添加 LIMIT 限制行数
2. 检查 SQL 是否过于复杂
3. 查看数据库连接是否正常

---

## 📈 性能测试

### 响应时间基准

```bash
# 测试生成 SQL 的响应时间
time curl -s -X POST http://localhost:8000/api/query/unified/process \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "获取OEE数据", "execution_mode": "explain"}' > /dev/null
```

**预期**: < 3 秒

### 并发测试

```bash
# 发送 10 个并发请求
for i in {1..10}; do
  curl -s -X POST http://localhost:8000/api/query/unified/process \
    -H "Content-Type: application/json" \
    -d "{\"natural_language\": \"查询 $i\", \"execution_mode\": \"explain\"}" &
done
wait
```

---

## 🧪 自动化测试

### Python 测试脚本

```python
import requests
import json

BASE_URL = "http://localhost:8000/api/query/unified"

# 测试 1: 简单查询
response = requests.post(f"{BASE_URL}/process", json={
    "natural_language": "获取OEE数据",
    "execution_mode": "explain"
})
assert response.status_code == 200
assert response.json()["success"] == True
print("✅ Test 1 passed: Simple query")

# 测试 2: 获取推荐
response = requests.get(f"{BASE_URL}/query-recommendations")
assert response.status_code == 200
assert len(response.json()["recommendations"]) > 0
print("✅ Test 2 passed: Get recommendations")

# 测试 3: 验证 SQL
response = requests.post(f"{BASE_URL}/validate-sql", json={
    "sql": "SELECT * FROM production_orders LIMIT 10"
})
assert response.status_code == 200
assert response.json()["is_valid"] == True
print("✅ Test 3 passed: Validate SQL")

print("\n✅ All tests passed!")
```

### Bash 测试脚本

```bash
#!/bin/bash

BASE_URL="http://localhost:8000/api/query/unified"

echo "🧪 Testing Backend API..."

# 测试 1: 健康检查
echo -n "1️⃣  Health check... "
if curl -s http://localhost:8000/api/schema/status | grep -q '"success":true'; then
  echo "✅"
else
  echo "❌"
  exit 1
fi

# 测试 2: 处理查询
echo -n "2️⃣  Process query... "
if curl -s -X POST $BASE_URL/process \
  -H "Content-Type: application/json" \
  -d '{"natural_language":"获取数据","execution_mode":"explain"}' | grep -q '"success":true'; then
  echo "✅"
else
  echo "❌"
  exit 1
fi

# 测试 3: 获取推荐
echo -n "3️⃣  Get recommendations... "
if curl -s -X GET $BASE_URL/query-recommendations | grep -q '"success":true'; then
  echo "✅"
else
  echo "❌"
  exit 1
fi

echo -e "\n✅ All tests passed!"
```

---

## 📚 文档链接

- [BACKEND_SERVICE_ARCHITECTURE.md](./BACKEND_SERVICE_ARCHITECTURE.md) - 完整架构
- [FRONTEND_INTEGRATION_ADJUSTMENTS.md](./FRONTEND_INTEGRATION_ADJUSTMENTS.md) - 前端集成指南
- [QUICK_START_BACKEND_SERVICE.md](./QUICK_START_BACKEND_SERVICE.md) - 快速启动

---

## ✅ 验收清单

集成完成后应满足:

- [ ] ✅ 后端正常启动，无错误
- [ ] ✅ `/api/schema/status` 返回 200
- [ ] ✅ `/api/query/unified/process` 返回 200 和有效 JSON
- [ ] ✅ `/api/query/unified/query-recommendations` 返回推荐列表
- [ ] ✅ 简单查询可以生成 SQL
- [ ] ✅ 澄清查询返回问题列表
- [ ] ✅ SQL 执行返回结果
- [ ] ✅ 所有 API 响应时间 < 3 秒

---

**更新时间**: 2026-02-03  
**状态**: ✅ 后端 API 已修复并可用  
**下一步**: 按照 [FRONTEND_INTEGRATION_ADJUSTMENTS.md](./FRONTEND_INTEGRATION_ADJUSTMENTS.md) 继续前端集成

