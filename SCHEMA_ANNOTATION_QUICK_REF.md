# Schema 语义标注系统 - 快速参考

## ⚡ 一句话总结
通过 LLM 自动生成数据库表和列的中英文标注，然后手动审核批准，最后用来改进 NL2SQL 的理解能力。

---

## 🚀 3 分钟快速开始

### 步骤 1: 创建数据库表
```bash
# 在 Supabase SQL Editor 中执行此脚本的输出
python supabase/create_annotation_tables.py
```

### 步骤 2: 扫描数据库
```bash
python app/tools/scan_schema.py
# 输出: schema_discovery.json
```

### 步骤 3: 生成标注
```bash
python app/tools/auto_annotate_schema.py
# LLM 自动为每个表生成标注，保存为 pending 状态
```

### 步骤 4: 审核和批准
```bash
# 获取待审核的标注
curl http://localhost:5000/api/schema/tables/pending

# 批准标注
curl -X POST http://localhost:5000/api/schema/tables/<id>/approve \
  -d '{"reviewer": "admin"}'
```

### 步骤 5: 使用标注
```bash
# 获取已批准的元数据
curl http://localhost:5000/api/schema/metadata
# 用于改进 NL2SQL 的理解
```

---

## 📚 关键文件位置

| 文件 | 用途 |
|------|------|
| `app/services/schema_annotator.py` | 核心标注服务 |
| `app/routes/schema_routes.py` | API 路由 |
| `supabase/create_annotation_tables.py` | 数据库迁移脚本 |
| `app/tools/scan_schema.py` | Schema 扫描工具 |
| `app/tools/auto_annotate_schema.py` | LLM 标注工具 |
| `SCHEMA_ANNOTATION_GUIDE.md` | 完整指南 |

---

## 🔌 主要 API 端点

```
GET  /api/schema/tables/pending          # 获取待审核表标注
GET  /api/schema/columns/pending         # 获取待审核列标注
POST /api/schema/tables/<id>/approve     # 批准标注
POST /api/schema/tables/<id>/reject      # 拒绝标注
PUT  /api/schema/tables/<id>             # 编辑标注
GET  /api/schema/metadata                # 获取已批准元数据
GET  /api/schema/status                  # 查看进度
```

---

## 📊 数据库表结构

### schema_table_annotations
```sql
id UUID PRIMARY KEY
table_name VARCHAR UNIQUE
table_name_cn VARCHAR              -- 中文表名
description_cn TEXT                -- 中文描述
description_en TEXT                -- 英文描述
business_meaning TEXT              -- 业务含义
use_case TEXT                      -- 使用场景
status VARCHAR (pending/approved/rejected)
created_at TIMESTAMP
reviewed_by VARCHAR
```

### schema_column_annotations
```sql
id UUID PRIMARY KEY
table_name VARCHAR
column_name VARCHAR
column_name_cn VARCHAR             -- 中文列名
data_type VARCHAR
description_cn TEXT                -- 中文描述
description_en TEXT                -- 英文描述
example_value TEXT                 -- 示例值
business_meaning TEXT              -- 业务含义
value_range TEXT                   -- 取值范围
status VARCHAR (pending/approved/rejected)
created_at TIMESTAMP
reviewed_by VARCHAR
```

---

## 🔄 标注生命周期

```
LLM 自动生成 (pending)
       ↓
   人员审核
       ↓
   ┌──┴──┐
   ↓     ↓
 批准  修改/拒绝
   ↓     ↓
   ↓   编辑重新提交
   └──┬──┘
      ↓
  用于 NL2SQL
```

---

## 💡 使用场景

### 场景 1: 改进 NL2SQL 的表理解
```python
# 在生成 SQL 前，获取 schema 元数据
metadata = schema_annotator.get_approved_schema_metadata()
# metadata['tables']['production_orders']['description_cn']
# = "生产订单表，存储订单信息..."
```

### 场景 2: 改进意图识别
```python
# 在识别意图时，参考表的业务含义
tables_info = metadata['tables']
# 当用户问"查询生产"时，可以自动识别是 production_orders 表
```

### 场景 3: 改进查询解析
```python
# 在构建 WHERE 子句时，使用列的取值范围
column_range = metadata['columns']['production_orders']['status']['range']
# "pending, in_progress, completed" 
# 防止生成无效的 WHERE status = 'unknown'
```

---

## ⚠️ 常见问题

**Q: 为什么有些标注被自动拒绝？**
A: 检查 Supabase 连接和 DeepSeek API 状态。

**Q: 如何修改已批准的标注？**
A: 先 reject，修改后重新提交和批准。或直接编辑（但不会更新 reviewed_by 时间戳）。

**Q: 标注的元数据如何影响 NL2SQL？**
A: 需要在 `nl2sql.py` 和 `intent_recognizer.py` 中集成元数据。

**Q: 可以删除已批准的标注吗？**
A: 目前不支持，可以拒绝后重新提交。

---

## 🔐 权限管理

目前 RLS 策略:
- 所有用户可以读取 **已批准** (approved) 的标注
- 标注创建、编辑、审核需要应用级别的访问控制（在 API 层实现）

---

## 📈 优化建议

1. **加速标注生成**: 使用异步任务队列（Celery）
2. **改进质量**: 集成人工反馈循环改进 LLM 提示词
3. **版本控制**: 记录标注修改历史
4. **可视化**: 创建前端仪表板显示进度
5. **验证**: 自动验证标注完整性

---

## 🎯 集成清单

- [ ] 创建数据库表
- [ ] 扫描现有 schema
- [ ] 生成 LLM 标注
- [ ] 审核和批准标注
- [ ] 测试 API 端点
- [ ] 在 `nl2sql.py` 中集成元数据
- [ ] 在 `intent_recognizer.py` 中使用元数据
- [ ] 部署到生产环境
- [ ] 监控标注使用情况
- [ ] 收集用户反馈改进标注

---

## 📞 获取帮助

1. 查看完整指南: `SCHEMA_ANNOTATION_GUIDE.md`
2. 检查实现细节: `SCHEMA_ANNOTATION_IMPLEMENTATION.md`
3. 查看日志: `app/logs/`
4. 检查 Supabase 控制台

---

**最后更新**: 2024-02-03  
**版本**: 1.0
