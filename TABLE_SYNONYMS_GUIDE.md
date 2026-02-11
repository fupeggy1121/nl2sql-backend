# 表名同义词映射系统 - 完整指南

## 🎯 概述

这是一个完整的表名同义词（别名）映射系统，用于处理用户用各种不同的表达方式（如"片篮"、"载具"等）查询特定表的情况。

## 📋 映射关系

### 当前支持的映射

| 实际表名 | 同义词示例 | 使用场景 |
|---------|----------|---------|
| **carriers** | 片篮、载具、载体、晶圆载体、装载容器 | 查询晶圆装载容器信息 |
| **wafers** | 晶圆、晶片、圆片、芯片 | 查询晶圆信息 |
| **wafer_inspection_results** | 检测结果、检测数据、检验结果、测试结果 | 查询晶圆检测数据 |
| **batches** | 批次、批、生产批次、lot | 查询生产批次信息 |
| **equipment** | 设备、机器、装置 | 查询设备信息 |
| **production_records** | 生产、产出、产量、生产数据、生产记录 | 查询生产记录 |
| **quality_metrics** | 质量、良品率、合格率、质量指标、yield | 查询质量指标 |
| **defects** | 缺陷、不良、瑕疵、不良品、failure | 查询缺陷信息 |
| **users** | 用户、人员、操作员、operator | 查询用户信息 |
| **logs** | 日志、记录、system_log | 查询系统日志 |

## 🚀 使用方式

### 1. 前端用户查询示例

用户可以用以下任何一种方式查询 carriers 表，都能被正确识别：

```
┌─────────────────────────────────────────┐
│ 用户输入                                 │
├─────────────────────────────────────────┤
│ 1. "查询片篮"                            │
│ 2. "查询载具"                            │
│ 3. "查询载体"                            │
│ 4. "查询晶圆载体"                        │
│ 5. "查询装载容器"                        │
│ 6. "返回 carriers 表的前10条数据"       │
│ 7. "显示 carrier 表"                     │
│ 8. "查询当前状态为可用的载具"            │
└─────────────────────────────────────────┘
          ⬇️ 意图识别和映射
┌─────────────────────────────────────────┐
│ 系统识别结果                             │
├─────────────────────────────────────────┤
│ table: "carriers"                        │
│ table_synonym: "片篮" / "载具" / ...    │
│ intent: "direct_query"                   │
│ confidence: 0.95+                        │
└─────────────────────────────────────────┘
```

### 2. 后端 API 调用

**请求**：
```bash
POST /api/query/recognize-intent
Content-Type: application/json

{
  "query": "查询片篮的信息"
}
```

**响应**：
```json
{
  "success": true,
  "type": "direct_table_query",
  "entities": {
    "tableName": "carriers",
    "raw_table_name": "片篮",
    "metric": "general",
    "timeRange": "",
    "equipment": [],
    "shift": [],
    "comparison": false
  },
  "confidence": 0.92,
  "clarifications": []
}
```

### 3. Python 代码集成

```python
from app.services.intent_recognizer import IntentRecognizer
from app.config.llm_provider import get_llm_provider

# 初始化意图识别器
llm_provider = get_llm_provider()
recognizer = IntentRecognizer(llm_provider=llm_provider)

# 识别用户意图
user_query = "查询片篮的信息"
result = recognizer.recognize(user_query)

print(f"识别结果：")
print(f"  表名: {result['entities'].get('table')}")
print(f"  用户输入关键词: {result['entities'].get('raw_table_name')}")
print(f"  意图: {result['intent']}")
print(f"  置信度: {result['confidence']:.2%}")
```

### 4. 直接使用映射函数

```python
from app.config.table_synonyms import (
    map_table_name, 
    is_valid_table_name,
    get_synonyms_for_table
)

# 单个表名映射
print(map_table_name('片篮'))           # 输出: carriers
print(map_table_name('晶圆'))           # 输出: wafers
print(map_table_name('unknown'))       # 输出: unknown (未找到映射)

# 检查是否是有效的表名
print(is_valid_table_name('片篮'))      # 输出: True
print(is_valid_table_name('carriers'))  # 输出: True
print(is_valid_table_name('xyz'))       # 输出: False

# 获取某个表的所有同义词
print(get_synonyms_for_table('carriers'))
# 输出: ['carrier', '载体', '载具', '片篮', '晶圆载体', ...]
```

## ✏️ 如何添加新的映射关系

### 步骤 1：编辑配置文件

打开 [app/config/table_synonyms.py](app/config/table_synonyms.py)

### 步骤 2：在 `TABLE_SYNONYMS` 字典中添加

```python
TABLE_SYNONYMS = {
    # 已有的映射...
    
    # 新增映射 - 例如要添加"设备状态"表的映射
    'equipment_status': [
        'equipment_status',
        '设备状态',
        '设备信息',
        'device_status',
        '状态表',
    ],
}
```

### 步骤 3：（可选）添加测试

编辑 [test_intent_recognizer.py](../../test_intent_recognizer.py)：

```python
TEST_CASES = [
    # 已有的测试...
    {
        'query': '查询设备状态',
        'expected_intent': 'direct_query',
        'expected_table': 'equipment_status'
    }
]
```

### 步骤 4：验证映射

重启应用后测试：

```bash
curl -X POST http://localhost:5000/api/query/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{"query":"查询设备状态"}'
```

应该返回：
```json
{
  "entities": {
    "tableName": "equipment_status"
  }
}
```

## 🔍 技术细节

### 映射过程

整个同义词映射流程如下：

```
用户输入
  ⬇️
意图识别 (IntentRecognizer)
  ⬇️
表名提取 (_extract_entities)
  ⬇️
同义词识别 (map_table_name)
  ⬇️
映射到实际表名
  ⬇️
返回结果 (UserIntent)
```

### 关键函数说明

#### `map_table_name(keyword: str) -> str`
- **功能**：将关键词映射到实际表名
- **示例**：`map_table_name('片篮')` → `'carriers'`
- **返回**：实际表名，如未找到则返回原始输入

#### `is_valid_table_name(keyword: str) -> bool`
- **功能**：检查关键词是否是有效的表名或同义词
- **示例**：`is_valid_table_name('片篮')` → `True`

#### `get_synonyms_for_table(table_name: str) -> list`
- **功能**：获取某个表的所有同义词
- **示例**：`get_synonyms_for_table('carriers')` → `['carrier', '载体', '片篮', ...]`

#### `get_synonym_to_table_map() -> dict`
- **功能**：获取完整的同义词映射字典（带缓存）
- **返回**：`{同义词: 实际表名, ...}`

### 缓存机制

为了提高性能，系统使用了缓存机制：

```python
_SYNONYM_TO_TABLE_CACHE = None  # 首次调用时初始化

def get_synonym_to_table_map():
    global _SYNONYM_TO_TABLE_CACHE
    if _SYNONYM_TO_TABLE_CACHE is None:
        # 构建缓存
        _SYNONYM_TO_TABLE_CACHE = {}
        for table_name, synonyms in TABLE_SYNONYMS.items():
            for synonym in synonyms:
                _SYNONYM_TO_TABLE_CACHE[synonym.lower()] = table_name
    return _SYNONYM_TO_TABLE_CACHE
```

这种设计保证了：
- ✅ 首次查找时有小的初始化开销
- ✅ 后续查找都是 O(1) 复杂度
- ✅ 同义词比较时不区分大小写

## 🧪 测试场景

### 场景 1：基本表名映射

```python
from app.config.table_synonyms import map_table_name

# 测试基本映射
assert map_table_name('片篮') == 'carriers'
assert map_table_name('Carriers') == 'carriers'
assert map_table_name('CARRIERS') == 'carriers'
assert map_table_name('晶圆') == 'wafers'
```

### 场景 2：完整意图识别流程

```python
from app.services.intent_recognizer import IntentRecognizer

recognizer = IntentRecognizer()
queries = [
    '查询片篮的信息',
    '显示载具',
    '返回当前状态为可用的载具',
    '查询晶圆的检测结果',
]

for query in queries:
    result = recognizer.recognize(query)
    print(f"查询: {query}")
    print(f"表名: {result['entities'].get('table')}")
    print(f"置信度: {result['confidence']:.2%}\n")
```

### 场景 3：API 端点测试

```bash
# 测试 1: 查询片篮
curl -X POST http://localhost:5000/api/query/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{"query":"查询片篮"}' | jq '.entities.tableName'

# 测试 2: 查询载具
curl -X POST http://localhost:5000/api/query/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{"query":"查询载具状态"}' | jq '.entities'

# 测试 3: 查询晶圆
curl -X POST http://localhost:5000/api/query/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{"query":"查询晶圆的信息"}' | jq '.entities.tableName'
```

## 📊 示例数据流

### 例子 1: "查询片篮"

```
输入: "查询片篮"
  ⬇️ 正则匹配 + 意图识别
识别为 direct_query 意图
  ⬇️ 实体提取
提取出表名关键词: "片篮"
  ⬇️ 同义词映射
map_table_name('片篮') → 'carriers'
  ⬇️ 返回结果
{
  "type": "direct_table_query",
  "entities": {
    "tableName": "carriers",
    "raw_table_name": "片篮"
  },
  "confidence": 0.92
}
```

### 例子 2: "查询当前状态为可用的载具"

```
输入: "查询当前状态为可用的载具"
  ⬇️ 正则匹配 + 意图识别
识别为 direct_query 意图
  ⬇️ 实体提取
提取出表名关键词: "载具"
  ⬇️ 同义词映射
map_table_name('载具') → 'carriers'
  ⬇️ 返回结果
{
  "type": "direct_table_query",
  "entities": {
    "tableName": "carriers",
    "raw_table_name": "载具",
    "filters": {
      "status": "available"
    }
  },
  "confidence": 0.92
}
```

## 🔗 相关文件

- **配置文件**: [app/config/table_synonyms.py](app/config/table_synonyms.py)
- **意图识别服务**: [app/services/intent_recognizer.py](app/services/intent_recognizer.py)
- **测试文件**: [test_intent_recognizer.py](../../test_intent_recognizer.py)
- **API 路由**: [app/routes/query_routes.py](../routes/query_routes.py)

## 🎓 最佳实践

1. **保持同义词的一致性**
   - 同义词应该在中文和英文之间保持逻辑关系
   - 避免过度的别名，这会增加维护成本

2. **定期审查和更新**
   - 根据真实用户的查询习惯更新同义词
   - 删除不常用的冗余同义词

3. **测试新映射**
   - 任何新映射都应该经过完整的测试
   - 使用 curl 或其他工具验证 API 响应

4. **文档化映射** 
   - 在这个指南中记录所有的映射关系
   - 保持文档与代码的同步

## ✅ 完整的映射列表

详见 [app/config/table_synonyms.py](app/config/table_synonyms.py) 中的 `TABLE_SYNONYMS` 字典。

## 📞 常见问题

### Q1: 同义词是否区分大小写？
A: 不区分。系统会自动转换为小写进行比较。

### Q2: 如何处理不在映射中的表名？
A: 系统会返回原始输入的表名，不会进行映射。

### Q3: 性能如何？
A: 使用了缓存机制，首次查找有初始化开销，之后都是 O(1) 查询。

### Q4: 可以动态添加映射吗？
A: 当前版本需要编辑配置文件。如需动态管理，可以考虑从数据库加载配置。

### Q5: 同义词顺序重要吗？
A: 不重要。系统会遍历所有同义词进行匹配。
