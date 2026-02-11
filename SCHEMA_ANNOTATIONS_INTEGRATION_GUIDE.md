# NL2SQL Schema 注释数据库集成指南

## 📋 概述

所有提取的数据库 Schema 语义信息已成功导入到 Supabase 的以下三个表中：

| 表名 | 记录数 | 用途 | 状态 |
|------|--------|------|------|
| `schema_table_annotations` | 15 | 表级别的业务含义和用途 | ✅ 已导入 |
| `schema_column_annotations` | 261 | 列级别的类型、说明、示例 | ✅ 已导入 |
| `schema_relation_annotations` | 0 | 表间的关系映射 | ⚠️ 待配置 |

## 🔍 按用途查询

### 1. 查询所有表的业务定义

```sql
SELECT 
  table_name,
  table_name_cn,
  description_cn,
  business_meaning,
  use_case
FROM schema_table_annotations
WHERE status = 'approved'
ORDER BY table_name;
```

**Python 示例:**
```python
from app.services.supabase_client import SupabaseClient

client = SupabaseClient()
result = client.client.table('schema_table_annotations').select('*').eq('status', 'approved').execute()

for annotation in result.data:
    print(f"{annotation['table_name']}: {annotation['description_cn']}")
```

### 2. 查询某个表的所有列定义

```sql
SELECT 
  column_name,
  column_name_cn,
  data_type,
  description_cn,
  example_value,
  business_meaning
FROM schema_column_annotations
WHERE table_name = 'quality_records'
  AND status = 'approved'
ORDER BY column_name;
```

**Python 示例:**
```python
result = client.client.table('schema_column_annotations').select('*').eq('table_name', 'quality_records').execute()

for col in result.data:
    print(f"{col['column_name']} ({col['data_type']}): {col['description_cn']}")
```

### 3. 按列名查询

```sql
SELECT 
  table_name,
  column_name_cn,
  description_cn,
  data_type
FROM schema_column_annotations
WHERE column_name = 'created_at'
  AND status = 'approved';
```

## 🎯 NL2SQL 集成建议

### 方案 1：在查询处理前加载 Schema 元数据

```python
from app.services.supabase_client import SupabaseClient

class SchemaContext:
    def __init__(self):
        self.client = SupabaseClient()
        self.table_annotations = None
        self.column_annotations = None
    
    def load_schema_context(self):
        """加载所有 schema 注释"""
        # 加载表注释
        tables = self.client.client.table('schema_table_annotations').select('*').eq('status', 'approved').execute()
        self.table_annotations = {t['table_name']: t for t in tables.data}
        
        # 加载列注释
        columns = self.client.client.table('schema_column_annotations').select('*').eq('status', 'approved').execute()
        self.column_annotations = {(c['table_name'], c['column_name']): c for c in columns.data}
    
    def get_table_description(self, table_name):
        """获取表的中文描述"""
        if table_name in self.table_annotations:
            return self.table_annotations[table_name]['description_cn']
        return None
    
    def get_column_info(self, table_name, column_name):
        """获取列的详细信息"""
        key = (table_name, column_name)
        if key in self.column_annotations:
            col_info = self.column_annotations[key]
            return {
                'chinese_name': col_info.get('column_name_cn'),
                'data_type': col_info.get('data_type'),
                'description': col_info.get('description_cn'),
                'example': col_info.get('example_value'),
                'business_meaning': col_info.get('business_meaning')
            }
        return None
```

### 方案 2：在 LLM Prompt 中使用 Schema 信息

```python
def build_enhanced_prompt(query, schema_context):
    """构建包含 Schema 信息的增强 prompt"""
    
    schema_context.load_schema_context()
    
    # 获取所有表的完整定义
    tables_info = []
    for table_name, annotation in schema_context.table_annotations.items():
        tables_info.append(f"""
        表: {table_name}
        中文名: {annotation.get('table_name_cn')}
        用途: {annotation.get('description_cn')}
        业务含义: {annotation.get('business_meaning')}
        使用场景: {annotation.get('use_case')}
        """)
    
    # 构建增强 prompt
    enhanced_prompt = f"""
    用户查询: {query}
    
    可用的数据库表:
    {''.join(tables_info)}
    
    请根据上述表定义理解用户的意图，生成准确的 SQL 查询。
    """
    
    return enhanced_prompt
```

### 方案 3：动态生成 Query Guide

```python
def generate_query_suggestions(user_intent, schema_context):
    """根据用户意图和 schema 生成查询建议"""
    
    schema_context.load_schema_context()
    
    suggestions = []
    
    # 例：如果用户问质量相关的问题
    if '质量' in user_intent or 'quality' in user_intent.lower():
        quality_table = schema_context.table_annotations.get('quality_records')
        if quality_table:
            cols = [c for c in schema_context.column_annotations.values() 
                   if c.get('table_name') == 'quality_records']
            
            suggestion = {
                'table': 'quality_records',
                'description': quality_table['description_cn'],
                'relevant_columns': [c['column_name'] for c in cols[:5]]
            }
            suggestions.append(suggestion)
    
    return suggestions
```

## 📊 Schema 数据结构

### schema_table_annotations 字段说明

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| id | UUID | 记录唯一ID | `{uuid}` |
| table_name | text | 表英文名 | `quality_records` |
| table_name_cn | text | 表中文名 | `质量记录` |
| description_cn | text | 中文描述 | `存储产品质量测量和检验数据` |
| description_en | text | 英文描述 | `Product quality measurements` |
| business_meaning | text | 业务含义 | `质量数据管理` |
| use_case | text | 使用场景 | `质量统计、管制图` |
| status | text | 审批状态 | `approved` / `pending` / `rejected` |
| created_by | text | 创建者 | `system` / `admin` |
| reviewed_by | text | 审核者 | `system` / `admin` |
| created_at | timestamp | 创建时间 | `2026-02-11T10:00:00` |
| updated_at | timestamp | 更新时间 | `2026-02-11T10:00:00` |

### schema_column_annotations 字段说明

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| id | UUID | 记录唯一ID | `{uuid}` |
| table_name | text | 所属表名 | `quality_records` |
| column_name | text | 列英文名 | `measurement_value` |
| column_name_cn | text | 列中文名 | `测量值` |
| data_type | text | 数据类型 | `numeric` / `text` / `timestamp` |
| description_cn | text | 中文描述 | `产品测量的实际值` |
| description_en | text | 英文描述 | `Actual measurement value` |
| business_meaning | text | 业务含义 | `质量数据关键指标` |
| example_value | text | 示例值 | `98.5` / `PASS` |
| value_range | text | 值范围 | `0-100` / `PASS/FAIL` |
| status | text | 审批状态 | `approved` / `pending` |
| created_by | text | 创建者 | `system` |
| reviewed_by | text | 审核者 | `system` / `admin` |
| created_at | timestamp | 创建时间 | `2026-02-11T10:00:00` |
| updated_at | timestamp | 更新时间 | `2026-02-11T10:00:00` |

## 🔄 工作流程

### 1. 系统初始化时

```python
# 在应用启动时，加载所有 schema 上下文
class AppInitializer:
    @staticmethod
    def initialize():
        schema_context = SchemaContext()
        schema_context.load_schema_context()
        return schema_context
```

### 2. 处理用户查询时

```python
def process_nl_query(query, schema_context):
    # 1. 加载 schema 元数据
    schema_context.load_schema_context()
    
    # 2. 构建增强 prompt，包含 schema 信息
    enhanced_prompt = build_enhanced_prompt(query, schema_context)
    
    # 3. 调用 LLM 生成 SQL
    sql = call_llm(enhanced_prompt)
    
    # 4. 执行 SQL 和返回结果
    return execute_sql(sql)
```

### 3. 维护阶段

```python
# 当更新或添加表时
def register_new_table(table_name, table_name_cn, description):
    """注册新表的 schema 注释"""
    annotation = {
        'table_name': table_name,
        'table_name_cn': table_name_cn,
        'description_cn': description,
        'status': 'pending',
        'created_by': 'admin',
        'created_at': datetime.now().isoformat()
    }
    
    client.client.table('schema_table_annotations').insert(annotation).execute()
```

## 📈 性能优化建议

1. **缓存 Schema 元数据**
   - 在应用启动时加载一次
   - 定期刷新（每小时或每天）
   - 使用 Redis 缓存

2. **预编译查询**
   - 使用常见查询的预定义模板
   - 基于列功能分类的查询模板

3. **异步加载**
   - 背景任务加载 schema 元数据
   - 不阻塞用户查询

## ⚠️ 注意事项

1. **权限控制**
   - schema_table_annotations 和 schema_column_annotations 应该 PUBLIC 可读
   - 修改权限只给 admin 用户

2. **数据一致性**
   - 确保表和列注释与实际数据库结构同步
   - 定期验证注释信息的准确性

3. **状态管理**
   - 未审批的注释使用 `status = 'pending'`
   - 只在生成 SQL 时使用 `status = 'approved'` 的注释

## 🚀 下一步

- [ ] 完成 schema_relation_annotations 表的数据导入
- [ ] 在 NL2SQL 模型中集成 schema 元数据加载
- [ ] 创建列和表的审核审批工作流
- [ ] 建立 schema 变更追踪和版本控制
- [ ] 实现 schema 信息的前端编辑界面
