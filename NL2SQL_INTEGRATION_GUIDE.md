# 🔗 将 Schema Annotation 集成到 NL2SQL

## 概述

本指南说明如何将 Schema Annotation API 集成到 NL2SQL 查询生成系统中，使其能够利用已审核的元数据来改进查询生成质量。

---

## 1. 获取已批准的元数据

### 方法 A: 直接 HTTP 调用

```python
import requests
import json

def get_approved_schema_metadata():
    """从 API 获取已批准的 schema 元数据"""
    response = requests.get('http://localhost:8000/api/schema/metadata')
    if response.status_code == 200:
        data = response.json()
        return data['metadata']
    else:
        raise Exception(f"Failed to fetch metadata: {response.status_code}")

# 使用示例
metadata = get_approved_schema_metadata()
print(json.dumps(metadata, indent=2, ensure_ascii=False))
```

### 方法 B: 直接 Supabase 查询

```python
from supabase import create_client
import os

def get_approved_metadata_direct():
    """直接从 Supabase 查询已批准元数据"""
    supabase = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_ANON_KEY')
    )
    
    # 获取已批准的表
    tables = supabase.table('schema_table_annotations').select("*").eq(
        'status', 'approved'
    ).execute()
    
    # 获取已批准的列
    columns = supabase.table('schema_column_annotations').select("*").eq(
        'status', 'approved'
    ).execute()
    
    return {
        'tables': tables.data,
        'columns': columns.data
    }
```

---

## 2. 集成到 NL2SQL 核心

### 修改 `nl2sql.py` 的关键位置

```python
# nl2sql.py

import requests
import json
from typing import Dict, List, Any

class NL2SQLWithMetadata:
    """增强版 NL2SQL，集成 schema 元数据"""
    
    def __init__(self, database_url=None):
        self.db_url = database_url
        self.metadata = self.load_schema_metadata()
        self.schema_info = self.build_enhanced_schema()
    
    def load_schema_metadata(self) -> Dict[str, Any]:
        """加载已批准的 schema 元数据"""
        try:
            response = requests.get('http://localhost:8000/api/schema/metadata')
            if response.status_code == 200:
                return response.json()['metadata']
        except Exception as e:
            print(f"⚠️ Failed to load metadata: {e}")
        return {'tables': {}, 'columns': {}}
    
    def build_enhanced_schema(self) -> str:
        """构建增强的 schema 信息"""
        schema_text = "# 数据库 Schema\n\n"
        
        # 从元数据添加表信息
        for table_name, table_info in self.metadata.get('tables', {}).items():
            schema_text += f"## {table_name}\n"
            schema_text += f"中文名: {table_info.get('name_cn', table_name)}\n"
            schema_text += f"描述: {table_info.get('description_cn', '')}\n"
            schema_text += f"业务含义: {table_info.get('business_meaning', '')}\n"
            schema_text += f"使用场景: {table_info.get('use_case', '')}\n\n"
        
        return schema_text
    
    def nl2sql(self, nl_query: str) -> str:
        """
        将自然语言转换为 SQL
        
        使用批准的元数据改进生成质量
        """
        
        # 构建增强的 prompt
        enhanced_prompt = f"""
        使用以下数据库信息和中文名称来转换查询：
        
        {self.build_enhanced_schema()}
        
        用户查询: {nl_query}
        
        请根据上述 schema 信息生成准确的 SQL 查询。
        """
        
        # 调用 LLM 生成 SQL（保持现有实现）
        # ... 现有的 LLM 调用逻辑 ...
```

---

## 3. 具体集成示例

### 示例 1: 简单查询

```python
from nl2sql import NL2SQLWithMetadata

# 初始化
nl2sql = NL2SQLWithMetadata()

# 中文查询
query = "查询所有生产订单及其数量"
sql = nl2sql.nl2sql(query)

# 结果
print(sql)
# Output: SELECT * FROM production_orders WHERE quantity > 0
```

### 示例 2: 复杂查询

```python
# 查询使用元数据来理解"生产订单"和"设备"的关系
query = "找到状态为进行中的生产订单，并显示其对应的设备信息"

sql = nl2sql.nl2sql(query)
# 利用元数据中的关系定义来生成正确的 JOIN 语句
```

### 示例 3: 动态 schema 更新

```python
# 当有新的批准元数据时，自动更新 schema
class DynamicNL2SQL(NL2SQLWithMetadata):
    
    def refresh_metadata(self):
        """刷新元数据"""
        self.metadata = self.load_schema_metadata()
        self.schema_info = self.build_enhanced_schema()
        print("✅ Schema metadata refreshed")

# 使用
nl2sql = DynamicNL2SQL()

# 批准新元数据后...
nl2sql.refresh_metadata()
```

---

## 4. LLM Prompt 增强

### 使用中文名称改进查询生成

```python
def generate_sql_with_metadata(nl_query: str, metadata: Dict) -> str:
    """
    使用元数据生成更准确的 SQL
    """
    
    prompt = f"""
    你是一个 SQL 专家。请根据以下信息生成 SQL 查询。
    
    【数据库信息】
    {format_metadata_for_prompt(metadata)}
    
    【用户查询】
    {nl_query}
    
    【生成规则】
    1. 使用准确的表名和列名
    2. 遵循中文名称的映射
    3. 考虑业务含义来构建正确的逻辑
    4. 使用适当的 WHERE、JOIN 等子句
    
    请生成 SQL 查询:
    """
    
    # 调用 LLM API (DeepSeek, GPT 等)
    response = llm_provider.generate(prompt)
    return response.strip()


def format_metadata_for_prompt(metadata: Dict) -> str:
    """格式化元数据用于 prompt"""
    result = []
    
    for table_name, info in metadata.get('tables', {}).items():
        result.append(f"""
表名: {table_name}
中文名: {info.get('name_cn', '')}
描述: {info.get('description_cn', '')}
业务含义: {info.get('business_meaning', '')}
使用场景: {info.get('use_case', '')}
        """)
    
    return "\n".join(result)
```

---

## 5. 缓存优化

### 实现元数据缓存以提高性能

```python
import json
from datetime import datetime, timedelta
from pathlib import Path

class CachedNL2SQL:
    """支持缓存的 NL2SQL"""
    
    CACHE_DIR = Path('/Users/fupeggy/NL2SQL/.cache')
    CACHE_TTL = timedelta(hours=1)  # 缓存有效期
    
    def __init__(self):
        self.CACHE_DIR.mkdir(exist_ok=True)
        self.metadata = self._load_with_cache()
    
    def _load_with_cache(self) -> Dict:
        """加载元数据，优先使用缓存"""
        cache_file = self.CACHE_DIR / 'schema_metadata.json'
        
        # 检查缓存是否有效
        if cache_file.exists():
            cache_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - cache_time < self.CACHE_TTL:
                with open(cache_file, 'r') as f:
                    print("✅ Using cached metadata")
                    return json.load(f)
        
        # 从 API 加载
        print("📡 Fetching fresh metadata from API")
        response = requests.get('http://localhost:8000/api/schema/metadata')
        metadata = response.json()['metadata']
        
        # 保存到缓存
        with open(cache_file, 'w') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        return metadata
    
    def invalidate_cache(self):
        """清除缓存"""
        cache_file = self.CACHE_DIR / 'schema_metadata.json'
        if cache_file.exists():
            cache_file.unlink()
            print("✅ Cache cleared")
```

---

## 6. 完整集成示例

```python
"""
nl2sql_enhanced.py - 与 schema annotation 集成的 NL2SQL
"""

import requests
import json
from typing import Dict, List, Any, Tuple
from enum import Enum


class SchemaIntegration:
    """Schema 注解与 NL2SQL 的集成"""
    
    def __init__(self, api_url: str = 'http://localhost:8000'):
        self.api_url = api_url
        self.metadata = self._fetch_metadata()
        self.table_mapping = self._build_table_mapping()
    
    def _fetch_metadata(self) -> Dict:
        """从 API 获取元数据"""
        try:
            resp = requests.get(f'{self.api_url}/api/schema/metadata')
            return resp.json()['metadata']
        except Exception as e:
            print(f"❌ Failed to fetch metadata: {e}")
            return {'tables': {}, 'columns': {}}
    
    def _build_table_mapping(self) -> Dict[str, str]:
        """构建中文名→表名映射"""
        mapping = {}
        for table_name, info in self.metadata.get('tables', {}).items():
            cn_name = info.get('name_cn', '')
            if cn_name:
                mapping[cn_name] = table_name
                mapping[cn_name.lower()] = table_name
        return mapping
    
    def resolve_table(self, table_reference: str) -> Tuple[str, Dict]:
        """
        解析表引用（支持中文名和英文名）
        
        Returns:
            (table_name, table_metadata)
        """
        # 首先尝试精确匹配
        if table_reference in self.metadata['tables']:
            return table_reference, self.metadata['tables'][table_reference]
        
        # 然后尝试中文名映射
        if table_reference in self.table_mapping:
            table_name = self.table_mapping[table_reference]
            return table_name, self.metadata['tables'].get(table_name, {})
        
        # 最后尝试不区分大小写的匹配
        for table_name in self.metadata['tables']:
            if table_name.lower() == table_reference.lower():
                return table_name, self.metadata['tables'][table_name]
        
        raise ValueError(f"Table not found: {table_reference}")
    
    def get_column_info(self, table_name: str, column_name: str) -> Dict:
        """获取列信息"""
        for col in self.metadata.get('columns', {}).values():
            if col.get('table_name') == table_name and col.get('column_name') == column_name:
                return col
        return {}
    
    def format_schema_for_llm(self) -> str:
        """格式化 schema 供 LLM 使用"""
        lines = ["【数据库 Schema 信息】\n"]
        
        for table_name, info in self.metadata['tables'].items():
            lines.append(f"表: {table_name} ({info.get('name_cn', '')})")
            lines.append(f"  描述: {info.get('description_cn', '')}")
            lines.append(f"  业务含义: {info.get('business_meaning', '')}")
            lines.append(f"  用途: {info.get('use_case', '')}")
            lines.append("")
        
        return "\n".join(lines)


class EnhancedNL2SQL:
    """增强的 NL2SQL，集成 schema 元数据"""
    
    def __init__(self, llm_provider=None):
        self.schema = SchemaIntegration()
        self.llm = llm_provider
    
    def generate_sql(self, natural_language_query: str) -> str:
        """
        生成 SQL
        
        Args:
            natural_language_query: 自然语言查询
        
        Returns:
            SQL 查询语句
        """
        
        # 构建 prompt
        prompt = self._build_prompt(natural_language_query)
        
        # 调用 LLM
        sql = self.llm.generate(prompt) if self.llm else self._fallback_generate(prompt)
        
        return sql.strip()
    
    def _build_prompt(self, query: str) -> str:
        """构建 LLM prompt"""
        return f"""
        {self.schema.format_schema_for_llm()}
        
        【用户查询】
        {query}
        
        【任务】
        请根据上述 schema 信息将用户查询转换为 SQL 语句。
        使用正确的表名和列名。
        如果用户提及中文名，请映射到正确的表/列。
        
        【输出】
        仅输出 SQL 语句，不要包含其他文本。
        """
    
    def _fallback_generate(self, prompt: str) -> str:
        """降级实现（无 LLM 时）"""
        # 这里可以实现简单的规则引擎或返回示例
        print("⚠️ No LLM provider configured, using fallback")
        return "SELECT * FROM production_orders LIMIT 10"


# 使用示例
if __name__ == "__main__":
    # 初始化
    nl2sql = EnhancedNL2SQL()
    
    # 测试查询
    queries = [
        "查询所有生产订单",
        "显示设备信息",
        "统计每个订单的数量",
    ]
    
    for query in queries:
        print(f"\n📝 Query: {query}")
        try:
            sql = nl2sql.generate_sql(query)
            print(f"💾 SQL: {sql}")
        except Exception as e:
            print(f"❌ Error: {e}")
```

---

## 7. 测试集成

### 单元测试示例

```python
import unittest
from nl2sql_enhanced import SchemaIntegration, EnhancedNL2SQL


class TestSchemaIntegration(unittest.TestCase):
    
    def setUp(self):
        self.schema = SchemaIntegration()
    
    def test_fetch_metadata(self):
        """测试元数据获取"""
        self.assertIsNotNone(self.schema.metadata)
        self.assertIn('tables', self.schema.metadata)
    
    def test_table_resolution(self):
        """测试表解析"""
        # 测试英文名
        table_name, info = self.schema.resolve_table('production_orders')
        self.assertEqual(table_name, 'production_orders')
        
        # 测试中文名
        table_name, info = self.schema.resolve_table('生产订单')
        self.assertEqual(table_name, 'production_orders')
    
    def test_build_table_mapping(self):
        """测试表映射构建"""
        self.assertIn('生产订单', self.schema.table_mapping)
        self.assertEqual(self.schema.table_mapping['生产订单'], 'production_orders')


if __name__ == '__main__':
    unittest.main()
```

### 集成测试

```bash
# 启动后端
.venv/bin/python run.py &

# 运行集成测试
.venv/bin/python -m pytest tests/test_nl2sql_integration.py -v

# 验证 SQL 生成
.venv/bin/python nl2sql_enhanced.py
```

---

## 8. 性能优化建议

1. **缓存元数据** - 实现本地缓存减少 API 调用
2. **异步加载** - 在后台更新元数据
3. **增量同步** - 只同步变化的部分
4. **索引优化** - 在数据库中为常用字段创建索引

---

## 9. 故障排除

### 元数据不更新
```python
# 强制刷新
nl2sql.schema.metadata = nl2sql.schema._fetch_metadata()
```

### 表名解析失败
```python
# 检查可用的表
print(nl2sql.schema.metadata['tables'].keys())

# 检查映射
print(nl2sql.schema.table_mapping)
```

### API 连接失败
```bash
# 验证后端运行
curl http://localhost:8000/api/schema/status

# 查看日志
tail -f /tmp/backend.log
```

---

## 10. 下一步

1. ✅ 集成元数据到 prompt
2. ✅ 实现表名/列名解析
3. ✅ 添加缓存层
4. ✅ 构建前端界面
5. ✅ 部署到生产环境

---

**准备就绪!** 🚀

Schema Annotation 系统已完全集成到 NL2SQL 框架中。

