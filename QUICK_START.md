# ✅ Schema Annotation 系统 - 快速开始指南

## 🎯 当前状态

系统已完全部署并验证。所有 API 端点工作正常，演示数据已插入数据库。

---

## 📋 快速操作清单

### ✅ 第一步：验证后端运行

```bash
# 检查后端是否运行
curl http://localhost:8000/api/schema/status

# 预期输出
# {"status":{"pending_table_annotations":1,"pending_column_annotations":5},"success":true}
```

### ✅ 第二步：批准所有待审核的列注解

```bash
# 获取所有待审核的列
curl http://localhost:8000/api/schema/columns/pending

# 对每个列执行批准（或写脚本批量批准）
curl -X POST http://localhost:8000/api/schema/columns/{column_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"reviewer": "admin"}'
```

### ✅ 第三步：验证元数据已准备好

```bash
# 获取所有已批准的元数据
curl http://localhost:8000/api/schema/metadata

# 应该包含所有表和列的信息
```

### ✅ 第四步：集成到 NL2SQL

```python
# 在你的 nl2sql.py 中添加
import requests

def get_schema_metadata():
    response = requests.get('http://localhost:8000/api/schema/metadata')
    return response.json()['metadata']

# 在查询生成时使用元数据
metadata = get_schema_metadata()
# 使用 metadata['tables'] 和 metadata['columns'] 来改进 SQL 生成
```

---

## 🔌 关键 API 端点

| 端点 | 方法 | 用途 | 状态 |
|------|------|------|------|
| `/api/schema/status` | GET | 系统状态 | ✅ 工作 |
| `/api/schema/tables/pending` | GET | 待审核表 | ✅ 工作 |
| `/api/schema/columns/pending` | GET | 待审核列 | ✅ 工作 |
| `/api/schema/metadata` | GET | 已批准元数据 | ✅ 工作 |
| `/api/schema/tables/{id}/approve` | POST | 批准表 | ✅ 工作 |
| `/api/schema/columns/{id}/approve` | POST | 批准列 | ✅ 工作 |
| `/api/schema/tables/{id}/reject` | POST | 拒绝表 | ✅ 工作 |
| `/api/schema/tables/{id}` | PUT | 编辑表 | ✅ 工作 |

---

## 📊 当前数据状态

**已批准:**
- ✅ production_orders (生产订单) - 表

**待批准:**
- ⏳ equipment (设备信息) - 表  
- ⏳ production_orders.order_number (订单编号) - 列
- ⏳ production_orders.quantity (生产数量) - 列
- ⏳ production_orders.status (订单状态) - 列
- ⏳ equipment.equipment_code (设备编码) - 列
- ⏳ equipment.equipment_type (设备类型) - 列

---

## 🚀 后端启动命令

```bash
# 进入项目目录
cd /Users/fupeggy/NL2SQL

# 启动后端（前台）
.venv/bin/python run.py

# 或后台运行
.venv/bin/python run.py > /tmp/backend.log 2>&1 &
```

**运行地址:** `http://localhost:8000`

---

## 🧪 测试命令

```bash
# 1. 检查演示数据
python check_demo_data.py

# 2. 完整 API 测试
python test_api_complete.py

# 3. 查看后端日志
tail -f /tmp/backend.log
```

---

## 📝 批量批准注解脚本

```python
#!/usr/bin/env python3
"""批量批准所有待审核注解"""

import requests
import json

BASE_URL = "http://localhost:8000/api/schema"

def approve_all():
    # 批准所有待审核的表
    tables_resp = requests.get(f"{BASE_URL}/tables/pending")
    tables = tables_resp.json()['annotations']
    
    for table in tables:
        resp = requests.post(
            f"{BASE_URL}/tables/{table['id']}/approve",
            json={"reviewer": "admin", "notes": "Approved"}
        )
        print(f"✅ Approved table: {table['table_name']}")
    
    # 批准所有待审核的列
    columns_resp = requests.get(f"{BASE_URL}/columns/pending")
    columns = columns_resp.json()['annotations']
    
    for column in columns:
        resp = requests.post(
            f"{BASE_URL}/columns/{column['id']}/approve",
            json={"reviewer": "admin"}
        )
        print(f"✅ Approved column: {column['table_name']}.{column['column_name']}")
    
    print("\n✅ All annotations approved!")
    
    # 显示最终状态
    status_resp = requests.get(f"{BASE_URL}/status")
    status = status_resp.json()['status']
    print(f"\nFinal status:")
    print(f"  Pending tables: {status['pending_table_annotations']}")
    print(f"  Pending columns: {status['pending_column_annotations']}")

if __name__ == "__main__":
    approve_all()
```

**运行:**
```bash
python batch_approve.py
```

---

## 🔍 故障排除

### 问题 1: 后端无法连接

```bash
# 检查端口是否在使用
lsof -i :8000

# 查看错误日志
cat /tmp/backend.log | tail -50
```

### 问题 2: 数据库连接失败

```bash
# 检查环境变量
echo "URL: $SUPABASE_URL"
echo "Key: ${SUPABASE_ANON_KEY:0:20}..."

# 验证连接
python check_demo_data.py
```

### 问题 3: API 返回空结果

```bash
# 确保演示数据已插入
python insert_demo_annotations.py

# 验证数据存在
curl http://localhost:8000/api/schema/tables/pending
```

---

## 📚 详细文档

查看以下文件获取完整信息：

1. **[DEPLOYMENT_COMPLETE_FINAL.md](DEPLOYMENT_COMPLETE_FINAL.md)**
   - 完整的部署报告
   - API 参考
   - 故障排除指南

2. **[NL2SQL_INTEGRATION_GUIDE.md](NL2SQL_INTEGRATION_GUIDE.md)**
   - 如何集成到 NL2SQL
   - 代码示例
   - 优化建议

3. **[README.md](README.md)**
   - 项目概览
   - 项目结构

---

## 💡 下一步建议

### 立即可做（5 分钟）
1. ✅ 验证后端运行：`curl http://localhost:8000/api/schema/status`
2. ✅ 批准所有待审核注解（使用上面的脚本）
3. ✅ 验证元数据可用：`curl http://localhost:8000/api/schema/metadata`

### 短期任务（30 分钟）
1. 📝 在 NL2SQL 中集成元数据
2. 🧪 测试查询生成质量改进
3. 📊 验证中文名称正确映射

### 中期任务（2-4 小时）
1. 🎨 构建前端审核界面（可选）
2. 🔄 自动刷新元数据
3. 📈 添加更多 schema 信息

### 长期任务
1. 🚀 部署到生产环境
2. 📊 监控系统性能
3. 🔄 定期更新元数据

---

## 🎓 关键概念

### Schema Annotation (模式注解)
为数据库表和列添加可读的描述和元数据：
- 中文名称
- 业务含义
- 使用场景
- 示例值

### 批准工作流
1. 系统自动生成注解（或手动输入）
2. 管理员审核并批准
3. 批准后的注解可供应用使用

### 元数据
包含所有已批准的表和列信息的结构化数据，可被 LLM 或应用直接使用。

---

## ⚙️ 配置文件

关键配置位置：
- `.env` - 环境变量（SUPABASE_URL, SUPABASE_ANON_KEY 等）
- `run.py` - 应用启动点
- `app/routes/schema_routes.py` - API 端点定义
- `app/services/schema_annotator.py` - 核心标注服务

---

## 📞 支持

如有问题或需要帮助：

1. 查看详细文档：[DEPLOYMENT_COMPLETE_FINAL.md](DEPLOYMENT_COMPLETE_FINAL.md)
2. 查看集成指南：[NL2SQL_INTEGRATION_GUIDE.md](NL2SQL_INTEGRATION_GUIDE.md)
3. 运行诊断脚本：`python check_demo_data.py`
4. 查看后端日志：`tail -f /tmp/backend.log`

---

## ✨ 系统特性

✅ **完全部署** - 所有组件就绪
✅ **已验证** - 所有 API 端点测试通过
✅ **包含演示** - 示例数据已插入
✅ **文档完整** - 详细指南可用
✅ **可扩展** - 易于集成和定制

---

**准备就绪!** 🚀

系统已完全配置。开始批准注解，然后集成到 NL2SQL！

*最后更新: 2026-02-03*

