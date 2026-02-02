# 🔍 服务联通性测试指南

## 📋 测试覆盖范围

本指南提供完整的服务联通性测试方案，包括：
- ✅ 后端服务健康检查
- ✅ 前后端通信测试
- ✅ Supabase数据库连接
- ✅ NL2SQL功能测试
- ✅ 网络性能测试
- ✅ CORS跨域配置

---

## 🚀 快速开始

### 1️⃣ 后端服务联通性测试

#### 方案A: Python脚本测试（推荐）

```bash
# 进入项目目录
cd /Users/fupeggy/NL2SQL

# 激活虚拟环境
source .venv/bin/activate

# 运行完整测试套件
python test_connectivity.py
```

**预期输出：**
```
╔══════════════════════════════════════════════════════╗
║        NL2SQL 服务联通性测试套件                      ║
║        2026-02-02 10:30:00                           ║
╚══════════════════════════════════════════════════════╝

🔍 后端服务健康检查
✅ 应用导入成功
✅ 后端服务正常运行: {'status': 'ok', 'version': '1.0'}

🔍 Supabase数据库连接检查
✅ Supabase客户端初始化成功
✅ Supabase数据库连接正常
ℹ️  查询示例: 1 条记录

...

🔍 测试总结
✅ PASS - Backend Health
✅ PASS - Supabase Connection
✅ PASS - NL2SQL Endpoint
✅ PASS - Query Execution

总体通过率: 4/4 (100%)
✅ 所有测试通过！系统运行正常 🎉
```

#### 方案B: curl命令测试

```bash
# 测试1: 后端健康检查
curl http://localhost:5000/api/query/health

# 测试2: NL2SQL转换
curl -X POST http://localhost:5000/api/query/nl-to-sql \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "查询所有用户"}'

# 测试3: 数据库查询
curl -X POST http://localhost:5000/api/query/execute \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM wafers LIMIT 5"}'
```

#### 方案C: Python交互式测试

```python
# 在Python REPL中运行

# 1. 导入必要模块
from app import create_app
from app.services.supabase_client import get_supabase_client
from app.services.query_executor import QueryExecutor

# 2. 创建应用实例
app = create_app()
print("✅ 应用创建成功")

# 3. 测试数据库连接
sb = get_supabase_client()
print(f"✅ Supabase客户端: {sb}")

# 4. 测试查询执行
executor = QueryExecutor(sb)
result = executor.execute_query("SELECT * FROM wafers LIMIT 2")
print(f"✅ 查询结果: {len(result)} 条记录")
print(f"✅ 样本数据: {result[0] if result else 'No data'}")

# 5. 测试NL2SQL端点
with app.test_client() as client:
    response = client.post(
        '/api/query/nl-to-sql',
        json={'natural_language': '显示wafers表前10条数据'}
    )
    print(f"✅ NL2SQL响应: {response.get_json()}")
```

---

### 2️⃣ 前端服务联通性测试

#### 方案A: 浏览器控制台测试

```javascript
// 1. 在浏览器中打开网站

// 2. 打开开发者工具 (F12 或 Cmd+Option+I)

// 3. 进入 Console 标签

// 4. 运行完整测试
TestConnectivity.runAllTests();

// 5. 或运行单个测试
TestConnectivity.testBackendHealth();
TestConnectivity.testNL2SQLConversion();
TestConnectivity.testDatabaseQuery();
TestConnectivity.testCORS();
TestConnectivity.testNetworkLatency();
```

**预期输出：**
```
╔════════════════════════════════════════════════════════╗
║      NL2SQL 前端服务联通性测试套件                     ║
║      API地址: http://localhost:5000                   ║
╚════════════════════════════════════════════════════════╝

✅ 后端服务正常
✅ NL2SQL转换: 返回 SQL: SELECT * FROM wafers LIMIT 100
✅ 查询成功: 返回 100 条记录
✅ CORS配置正确
✅ 网络延迟: 45.23ms (优秀)

总体通过率: 5/5 (100%)
✅ 所有测试通过！系统运行正常 🎉
```

#### 方案B: HTML测试页面

```html
<!DOCTYPE html>
<html>
<head>
    <title>服务联通性测试</title>
</head>
<body>
    <h1>NL2SQL 服务联通性测试</h1>
    <button onclick="TestConnectivity.runAllTests()">运行所有测试</button>
    
    <!-- 引入测试脚本 -->
    <script src="test_connectivity_frontend.js"></script>
</body>
</html>
```

---

### 3️⃣ 分步测试指南

#### 步骤1: 启动后端服务

```bash
cd /Users/fupeggy/NL2SQL
source .venv/bin/activate
python run.py
```

**成功标志：**
```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

#### 步骤2: 验证后端健康状态

```bash
# 方式1: curl
curl http://localhost:5000/api/query/health

# 方式2: Python
python -c "
import requests
r = requests.get('http://localhost:5000/api/query/health')
print(r.json())
"
```

**成功响应：**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": "2026-02-02T10:30:00"
}
```

#### 步骤3: 测试Supabase连接

```bash
# 运行Python脚本
python -c "
from app.services.supabase_client import get_supabase_client
sb = get_supabase_client()
result = sb.client.table('wafers').select('id').limit(1).execute()
print(f'✅ Supabase连接成功，查询到 {len(result.data)} 条记录')
"
```

**成功标志：**
```
✅ Supabase连接成功，查询到 1 条记录
```

#### 步骤4: 测试NL2SQL转换

```bash
curl -X POST http://localhost:5000/api/query/nl-to-sql \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "返回 wafers 表的前300条数据"}'
```

**成功响应：**
```json
{
  "success": true,
  "sql": "SELECT * FROM wafers LIMIT 300",
  "confidence": 0.95
}
```

#### 步骤5: 测试数据库查询

```bash
curl -X POST http://localhost:5000/api/query/execute \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM wafers LIMIT 5"}'
```

**成功响应：**
```json
{
  "success": true,
  "data": [
    { "id": 1, "name": "wafer_001", ... },
    { "id": 2, "name": "wafer_002", ... }
  ],
  "count": 2
}
```

#### 步骤6: 测试CORS配置

```bash
# 从不同源发起请求（模拟跨域）
curl -X OPTIONS http://localhost:5000/api/query/health \
  -H "Origin: http://bolt.new" \
  -H "Access-Control-Request-Method: POST" \
  -v
```

**成功标志：** 响应头包含 `Access-Control-Allow-Origin`

---

## 🔧 常见问题排查

### ❌ 问题1: 后端连接失败

**症状：** `Connection refused` 或 `Failed to connect`

**解决方案：**
```bash
# 1. 检查后端是否运行
lsof -i :5000

# 2. 如果未运行，启动后端
python run.py

# 3. 检查端口是否被占用
kill $(lsof -t -i:5000)  # 杀死占用5000端口的进程
python run.py            # 重新启动
```

### ❌ 问题2: Supabase连接失败

**症状：** `Supabase client initialization failed` 或 `Auth error`

**解决方案：**
```bash
# 1. 检查环境变量
echo $SUPABASE_URL
echo $SUPABASE_KEY

# 2. 如果缺少环境变量，编辑 .env 文件
cp .env.example .env
# 填充 SUPABASE_URL 和 SUPABASE_KEY

# 3. 验证凭证
python -c "
import os
print(f'Supabase URL: {os.getenv(\"SUPABASE_URL\")}')
print(f'Supabase Key: {os.getenv(\"SUPABASE_KEY\", \"Not set\")[:20]}...')
"
```

### ❌ 问题3: CORS错误

**症状：** `Access to XMLHttpRequest blocked by CORS policy`

**解决方案：**
```bash
# 1. 检查 Flask app 的 CORS 配置
grep -n "CORS\|cors" app/__init__.py

# 2. 确保 CORS 已正确配置
# 在 app/__init__.py 中应该有：
# CORS(app, resources={
#     r"/api/*": {
#         "origins": ["*"],
#         "methods": ["GET", "POST", "OPTIONS"],
#         "allow_headers": ["Content-Type"]
#     }
# })

# 3. 重启后端
python run.py
```

### ❌ 问题4: 网络延迟高

**症状：** 测试显示延迟 > 1000ms

**解决方案：**
```bash
# 1. 检查网络连接
ping 8.8.8.8

# 2. 检查后端性能
python -m cProfile -s cumtime run.py

# 3. 检查数据库连接
python -c "
import time
from app.services.supabase_client import get_supabase_client

start = time.time()
sb = get_supabase_client()
end = time.time()
print(f'Supabase连接耗时: {(end-start)*1000:.2f}ms')
"
```

---

## 📊 测试报告示例

```
╔════════════════════════════════════════════════════════╗
║           NL2SQL 服务联通性测试报告                     ║
║           生成时间: 2026-02-02 10:30:00               ║
╚════════════════════════════════════════════════════════╝

【测试环境】
- 系统: macOS 14.2
- Python: 3.13.0
- 后端地址: http://localhost:5000
- 数据库: Supabase (PostgreSQL)
- 前端框架: React + TypeScript

【测试结果】
✅ 后端服务健康检查      PASS
✅ Supabase连接测试      PASS
✅ NL2SQL端点测试        PASS
✅ 数据库查询执行        PASS
✅ CORS跨域配置          PASS
✅ 网络延迟测试          PASS (平均 45ms)
✅ 错误处理测试          PASS
✅ 页面性能测试          PASS (首屏加载 1.2s)

【总体评分】
总通过率: 8/8 (100%) ⭐⭐⭐⭐⭐

【性能指标】
- 平均响应时间: 45ms
- 数据库查询: 120ms
- 页面加载: 1.2s
- 网络带宽: 良好

【建议】
✓ 系统运行正常，无需调整
✓ 性能指标优秀
✓ 可继续进行功能测试
```

---

## 🎯 完整测试清单

- [ ] 后端服务启动成功
- [ ] 后端健康检查通过
- [ ] Supabase连接成功
- [ ] 数据库查询正常
- [ ] NL2SQL转换功能
- [ ] CORS配置正确
- [ ] 网络延迟可接受
- [ ] 前后端通信正常
- [ ] 错误处理正确
- [ ] 页面加载性能良好

---

## 📞 需要帮助？

如果测试失败，请收集以下信息：

1. **测试环境**
   ```bash
   python --version
   pip list | grep -E "flask|supabase|requests"
   env | grep -E "SUPABASE|DB_"
   ```

2. **错误日志**
   ```bash
   # 查看最后100行日志
   tail -100 server.log
   ```

3. **网络连接**
   ```bash
   curl -v http://localhost:5000/api/query/health
   ```

4. **数据库连接**
   ```bash
   psql -h [SUPABASE_HOST] -U [DB_USER] -d [DB_NAME] -c "SELECT 1"
   ```

然后提供这些信息给支持团队。

---

**祝测试顺利！🚀**
