
# Schema 语义标注系统 - 完整指南

## 📋 系统概述

Schema 语义标注系统是一个用于改进 NL2SQL 理解能力的工具，通过为数据库的表和列添加中英文描述、业务含义等元数据，帮助 AI 更准确地理解用户的查询意图。

**核心流程:**
```
扫描 Schema → LLM 生成标注 → 手动审核 → 批准 → 用于 NL2SQL
```

---

## 🚀 快速开始

### 前提条件

1. **环境变量已配置**
   ```bash
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_ANON_KEY=your-anon-key
   DEEPSEEK_API_KEY=your-deepseek-key
   ```

2. **依赖已安装**
   ```bash
   pip install -r requirements.txt
   ```

### 第一步: 创建标注表

在 Supabase 控制台执行 SQL 脚本：

```bash
python supabase/create_annotation_tables.py
```

或手动在 Supabase SQL Editor 执行脚本输出的 SQL。

**创建的表:**
- `schema_table_annotations` - 表级标注
- `schema_column_annotations` - 列级标注  
- `schema_relation_annotations` - 关系标注
- `annotation_audit_log` - 审计日志

### 第二步: 扫描数据库

```bash
python app/tools/scan_schema.py
```

此命令将：
- 连接到 Supabase 数据库
- 扫描所有表和列
- 导出 Schema 信息到 `schema_discovery.json`

### 第三步: 使用 LLM 自动生成标注

```bash
python app/tools/auto_annotate_schema.py
```

此命令将：
- 读取扫描的 Schema
- 调用 DeepSeek LLM 为每个表生成标注
- 包括中英文名称、描述、业务含义等
- 将标注保存到 Supabase (状态: pending)

### 第四步: 审核和批准标注

**获取待审核的标注:**
```bash
curl http://localhost:5000/api/schema/tables/pending
curl http://localhost:5000/api/schema/columns/pending
```

**批准标注:**
```bash
curl -X POST http://localhost:5000/api/schema/tables/<id>/approve \
  -H "Content-Type: application/json" \
  -d '{"reviewer": "admin"}'
```

**拒绝标注（需要修改）:**
```bash
curl -X POST http://localhost:5000/api/schema/tables/<id>/reject \
  -H "Content-Type: application/json" \
  -d '{"reason": "描述不够准确", "reviewer": "admin"}'
```

**编辑标注:**
```bash
curl -X PUT http://localhost:5000/api/schema/tables/<id> \
  -H "Content-Type: application/json" \
  -d '{
    "table_name_cn": "新的中文名",
    "description_cn": "新的描述"
  }'
```

### 第五步: 获取已批准的元数据用于 NL2SQL

```bash
curl http://localhost:5000/api/schema/metadata
```

返回所有已批准的标注元数据，可被 NL2SQL 系统用于：
- 更好地理解表名和列名
- 识别相关字段
- 生成更准确的 SQL

---

## 📊 标注数据结构

### 表标注 (schema_table_annotations)

```json
{
  "id": "uuid",
  "table_name": "production_orders",
  "table_name_cn": "生产订单",
  "description_cn": "存储生产订单的基本信息，包括订单编号、产品ID、数量等",
  "description_en": "Stores basic information of production orders including order number, product ID, quantity, etc.",
  "business_meaning": "用于跟踪和管理制造过程中的生产订单",
  "use_case": "生产计划、订单跟踪、产量分析",
  "status": "approved",  // pending, approved, rejected
  "created_at": "2024-02-03T...",
  "reviewed_by": "admin"
}
```

### 列标注 (schema_column_annotations)

```json
{
  "id": "uuid",
  "table_name": "production_orders",
  "column_name": "order_number",
  "column_name_cn": "订单号",
  "data_type": "varchar(50)",
  "description_cn": "唯一的生产订单编号，如 PO-2024-001",
  "description_en": "Unique production order number, e.g., PO-2024-001",
  "example_value": "PO-2024-001",
  "business_meaning": "用于唯一标识和追踪生产订单",
  "value_range": "格式: PO-YYYY-NNN (年份-序号)",
  "status": "approved"
}
```

---

## 🔧 API 端点详细说明

### 自动标注

**POST** `/api/schema/tables/auto-annotate`

为所有（或指定的）表自动生成 LLM 标注。

```bash
curl -X POST http://localhost:5000/api/schema/tables/auto-annotate \
  -H "Content-Type: application/json" \
  -d '{
    "table_names": ["production_orders", "equipment"]
  }'
```

响应:
```json
{
  "success": true,
  "message": "Auto-annotation job started",
  "tables_to_annotate": ["production_orders", "equipment"]
}
```

### 获取待审核标注

**GET** `/api/schema/tables/pending`

```bash
curl http://localhost:5000/api/schema/tables/pending
```

响应:
```json
{
  "success": true,
  "count": 3,
  "annotations": [
    {
      "id": "...",
      "table_name": "production_orders",
      "table_name_cn": "生产订单",
      "status": "pending",
      ...
    }
  ]
}
```

**GET** `/api/schema/columns/pending`

获取待审核的列标注。

### 审核操作

**POST** `/api/schema/tables/<id>/approve`

批准表标注。

```bash
curl -X POST http://localhost:5000/api/schema/tables/<id>/approve \
  -H "Content-Type: application/json" \
  -d '{"reviewer": "admin"}'
```

**POST** `/api/schema/tables/<id>/reject`

拒绝表标注并说明原因。

```bash
curl -X POST http://localhost:5000/api/schema/tables/<id>/reject \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "描述不够准确，需要修改",
    "reviewer": "admin"
  }'
```

**PUT** `/api/schema/tables/<id>`

编辑和更新标注内容。

```bash
curl -X PUT http://localhost:5000/api/schema/tables/<id> \
  -H "Content-Type: application/json" \
  -d '{
    "table_name_cn": "修改后的中文名",
    "description_cn": "修改后的描述",
    "business_meaning": "修改后的业务含义"
  }'
```

### 获取已批准的元数据

**GET** `/api/schema/metadata`

获取所有已批准的 schema 元数据，用于 NL2SQL 系统。

```bash
curl http://localhost:5000/api/schema/metadata
```

响应:
```json
{
  "success": true,
  "metadata": {
    "tables": {
      "production_orders": {
        "name_cn": "生产订单",
        "description_cn": "...",
        "business_meaning": "..."
      }
    },
    "columns": {
      "production_orders": {
        "order_number": {
          "name_cn": "订单号",
          "data_type": "varchar(50)",
          "description_cn": "..."
        }
      }
    },
    "last_updated": "2024-02-03T..."
  }
}
```

### 查看标注进度

**GET** `/api/schema/status`

获取标注完成情况统计。

```bash
curl http://localhost:5000/api/schema/status
```

---

## 🧠 LLM 标注提示词

系统使用以下提示词指导 LLM 生成高质量标注：

```
请为以下数据库表生成中英文语义标注。

表名: {table_name}
列信息:
- {column_name} ({data_type})
...

请生成以下信息（JSON 格式）：
{
    "table_name_cn": "中文表名",
    "table_name_en": "{table_name}",
    "description_cn": "表的中文描述",
    "description_en": "Table description in English",
    "business_meaning": "业务含义说明",
    "use_case": "使用场景",
    "columns": [
        {
            "column_name": "列名",
            "column_name_cn": "中文列名",
            "data_type": "数据类型",
            "description_cn": "中文描述",
            "description_en": "English description",
            "example_value": "示例值",
            "business_meaning": "业务含义",
            "range": "取值范围（如适用）"
        }
    ]
}
```

---

## 🔄 标注生命周期

```
┌─────────────────────────────────────────────┐
│  LLM 自动生成标注 (pending)                  │
└────────────────┬────────────────────────────┘
                 │
                 ▼
        ┌────────────────────┐
        │  人员审核标注       │
        └────────┬───────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
    通过          需要修改/拒绝
    (approved)    (rejected)
        │                 │
        │                 ▼
        │         ┌─────────────────┐
        │         │ 编辑并重新提交    │
        │         └────────┬────────┘
        │                  │
        │                  ▼
        │         └────────→ 审核
        │
        ▼
   ┌──────────────────────────────┐
   │  用于改进 NL2SQL 理解          │
   │ (integrated into query engine) │
   └──────────────────────────────┘
```

---

## 💡 最佳实践

### 1. 标注质量

- **准确性**: 确保中文名称和描述准确反映表/列的用途
- **完整性**: 为每个字段提供示例值和取值范围
- **一致性**: 使用统一的术语和命名规范

### 2. 审核流程

- **第一遍**: 检查 LLM 生成的标注是否准确
- **第二遍**: 验证中文翻译是否恰当
- **第三遍**: 确认业务含义是否全面

### 3. 集成到 NL2SQL

批准标注后，可以：

1. 更新 NL2SQL 的 schema 理解
2. 改进意图识别的准确度
3. 增强查询生成的质量

---

## 📈 改进 NL2SQL 的方式

### 方法 1: 在 LLM 提示词中使用元数据

```python
# 在生成 SQL 时，包含已批准的 schema 元数据
metadata = get_approved_schema_metadata()

prompt = f"""
已知的数据库结构:
{format_metadata_for_prompt(metadata)}

用户查询: {user_query}

请生成相应的 SQL...
"""
```

### 方法 2: 在意图识别中使用元数据

```python
# 在识别意图时，参考 schema 元数据
intent = recognize_intent(
    user_query,
    schema_context=metadata['tables'],
    column_context=metadata['columns']
)
```

### 方法 3: 创建向量化的 schema 知识库

```python
# 对已批准的标注进行向量化存储
from langchain.embeddings import OpenAIEmbeddings

embeddings = OpenAIEmbeddings()
# 为每个表和列创建向量表示
table_vectors = [embeddings.embed_query(
    f"{t['name_cn']} {t['description_cn']}"
) for t in metadata['tables'].values()]
```

---

## 🐛 故障排除

### 问题 1: "Connection to Supabase failed"

**原因**: 环境变量未正确配置或 Supabase 连接异常

**解决方案**:
```bash
# 检查环境变量
echo $SUPABASE_URL
echo $SUPABASE_ANON_KEY

# 测试连接
python -c "from app.services.supabase_client import supabase; print(supabase.is_connected())"
```

### 问题 2: "No tables found"

**原因**: 数据库中没有任何表或连接异常

**解决方案**:
- 确认数据库中确实存在表
- 检查表是否在 `public` schema 中
- 尝试直接在 Supabase SQL Editor 执行查询

### 问题 3: "LLM response parsing failed"

**原因**: LLM 返回的不是有效的 JSON

**解决方案**:
- 检查 DEEPSEEK_API_KEY 是否正确
- 查看日志中的原始 LLM 响应
- 修改提示词以确保 JSON 格式

---

## 📚 相关文档

- [Supabase 文档](https://supabase.com/docs)
- [PostgreSQL Information Schema](https://www.postgresql.org/docs/current/information_schema.html)
- [DeepSeek API 文档](https://docs.deepseek.com)

---

## 🎯 下一步

1. ✅ 创建数据库表
2. ✅ 扫描并发现 schema
3. ✅ 生成 LLM 标注
4. ✅ 审核和批准
5. ⏳ 集成到 NL2SQL 查询引擎
6. ⏳ 测试和验证改进

---

**创建时间**: 2024-02-03  
**版本**: 1.0
