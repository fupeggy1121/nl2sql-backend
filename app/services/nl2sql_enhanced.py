"""
增强的 NL2SQL 服务 - 集成 Schema Annotation 元数据
使用已批准的表名和列名改进查询生成质量
"""
from typing import Optional, Dict, Any, List
import logging
import requests
import json
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)


class EnhancedNL2SQLConverter:
    """集成 Schema Annotation 的 NL2SQL 转换器"""
    
    def __init__(self, schema_api_url: str = "http://localhost:8000/api/schema"):
        """初始化转换器
        
        Args:
            schema_api_url: Schema Annotation API 地址
        """
        self.schema_api_url = schema_api_url
        self.schema_info = {}
        self.annotation_metadata = {}
        self.llm_provider = get_llm_provider()
        self._load_annotation_metadata()
    
    def _load_annotation_metadata(self) -> None:
        """从 Supabase 直接加载表注释元数据"""
        try:
            from app.services.supabase_client import SupabaseClient
            supabase = SupabaseClient()
            
            # 从 schema_table_annotations 表加载表注释
            tables_response = supabase.client.table('schema_table_annotations').select('*').execute()
            tables_data = {}
            for row in tables_response.data:
                table_name = row.get('table_name')
                tables_data[table_name] = {
                    'name_cn': row.get('table_name_cn', ''),
                    'description_cn': row.get('description_cn', ''),
                    'description_en': row.get('description_en', ''),
                    'business_meaning': row.get('business_meaning', ''),
                    'use_case': row.get('use_case', '')
                }
            
            # 从 schema_column_annotations 表加载列注释
            columns_response = supabase.client.table('schema_column_annotations').select('*').execute()
            columns_data = {}
            for row in columns_response.data:
                col_key = f"{row.get('table_name')}.{row.get('column_name')}"
                columns_data[col_key] = {
                    'table_name': row.get('table_name'),
                    'column_name': row.get('column_name'),
                    'column_name_cn': row.get('column_name_cn', ''),
                    'data_type': row.get('data_type', ''),
                    'description_cn': row.get('description_cn', ''),
                    'example_value': row.get('example_value', '')
                }
            
            self.annotation_metadata = {
                'tables': tables_data,
                'columns': columns_data
            }
            
            logger.info(f"✅ Loaded schema annotation metadata from Supabase")
            logger.info(f"   Tables: {len(tables_data)}")
            logger.info(f"   Columns: {len(columns_data)}")
            
        except Exception as e:
            logger.warning(f"Error loading annotation metadata from Supabase: {e}")
            logger.info("Falling back to MySQL schema_tools for annotation metadata...")
            self._load_annotation_metadata_from_mysql()

    def _load_annotation_metadata_from_mysql(self) -> None:
        """从 MySQL information_schema 加载表/列元数据（DB_BACKEND=mysql 时的备用路径）"""
        try:
            from app.agent.tools.schema_tools import _get_schema_metadata
            mysql_schema = _get_schema_metadata()
            raw_tables = mysql_schema.get('tables', {})
            tables_data = {}
            columns_data = {}
            for table_name, table_info in raw_tables.items():
                desc = (table_info.get('description') or
                        table_info.get('comment', '') or
                        table_info.get('table_comment', ''))
                tables_data[table_name] = {
                    'name_cn': desc,
                    'description_cn': desc,
                }
                for col_name, col_info in table_info.get('columns', {}).items():
                    col_desc = (col_info.get('description') or
                                col_info.get('comment', '') or
                                col_info.get('column_comment', ''))
                    col_key = f"{table_name}.{col_name}"
                    columns_data[col_key] = {
                        'table_name': table_name,
                        'column_name': col_name,
                        'data_type': col_info.get('type', col_info.get('column_type', '')),
                        'description_cn': col_desc,
                    }
            self.annotation_metadata = {'tables': tables_data, 'columns': columns_data}
            logger.info(
                f"✅ Loaded MySQL schema metadata: {len(tables_data)} tables, "
                f"{len(columns_data)} columns"
            )
        except Exception as ex:
            logger.warning(f"MySQL schema fallback also failed: {ex}")
    
    def refresh_metadata(self) -> None:
        """刷新元数据（手动调用）"""
        self._load_annotation_metadata()
    
    def set_schema(self, schema: Dict[str, Any]) -> None:
        """设置基础数据库 schema 信息"""
        self.schema_info = schema
        logger.info(f"Schema set with tables: {list(schema.keys())}")
    
    def _build_enhanced_schema_prompt(self) -> str:
        """构建增强的 schema 提示词。
        当表数量较少（Supabase 注解）时输出完整列信息；
        当表数量很多（MySQL 全量）时只输出表名目录，避免超出 LLM 上下文限制。
        """
        tables = self.annotation_metadata.get('tables', {})
        columns = self.annotation_metadata.get('columns', {})

        if not tables:
            # 没有元数据也没有 schema_info，返回空
            if self.schema_info:
                lines = ["【数据库 Schema 信息】\n"]
                for table_name, columns_info in self.schema_info.items():
                    lines.append(f"表: {table_name}")
                    for col_name, col_type in columns_info.items():
                        lines.append(f"  - {col_name} ({col_type})")
                    lines.append("")
                return "\n".join(lines)
            return ""

        # 表数量 > 100 时只列出表名目录（详细 schema 由 RAG 在 nl_query 中提供）
        if len(tables) > 100:
            lines = ["【可用数据库表目录（仅用于表名合法性校验）】"]
            for table_name, table_info in tables.items():
                desc = table_info.get('description_cn') or table_info.get('name_cn', '')
                if desc:
                    lines.append(f"  {table_name}  ({desc})")
                else:
                    lines.append(f"  {table_name}")
            lines.append("")
            return "\n".join(lines)

        # 表数量较少时输出完整列信息（与原逻辑一致）
        schema_lines = ["【数据库 Schema 信息】\n"]
        for table_name, table_info in tables.items():
            schema_lines.append(f"表名: {table_name}")
            if table_info.get('name_cn'):
                schema_lines.append(f"  中文名: {table_info['name_cn']}")
            if table_info.get('description_cn'):
                schema_lines.append(f"  描述: {table_info['description_cn']}")
            if table_info.get('business_meaning'):
                schema_lines.append(f"  业务含义: {table_info['business_meaning']}")
            table_columns = [col for col in columns.values()
                             if col.get('table_name') == table_name]
            if table_columns:
                schema_lines.append("  列:")
                for col in table_columns:
                    col_name = col.get('column_name', '')
                    col_name_cn = col.get('column_name_cn', '')
                    data_type = col.get('data_type', '')
                    desc = col.get('description_cn', '')
                    if col_name_cn:
                        schema_lines.append(f"    - {col_name} ({col_name_cn}): {data_type}")
                    else:
                        schema_lines.append(f"    - {col_name}: {data_type}")
                    if desc:
                        schema_lines.append(f"      描述: {desc}")
            schema_lines.append("")
        return "\n".join(schema_lines)
    
    def _build_enhanced_prompt(self, natural_language: str) -> str:
        """构建增强的 LLM 提示词，包含显式的中文-英文表名映射"""
        schema_prompt = self._build_enhanced_schema_prompt()
        
        # 构建中文-英文表名映射表
        tables = self.annotation_metadata.get('tables', {})
        table_mappings = []
        for table_name, table_info in tables.items():
            cn_name = table_info.get('name_cn', '')
            if cn_name:
                table_mappings.append(f"  • '{cn_name}' → {table_name}")
        
        mapping_section = ""
        if table_mappings:
            mapping_section = "\n【中文表名映射】\n" + "\n".join(table_mappings)
        
        prompt = f"""{schema_prompt}{mapping_section}

【用户查询与上下文（包含相关 Schema 片段）】
{natural_language}

【转换规则（严格遵守）】
1. **只能使用上方【数据库 Schema 信息】或【用户查询与上下文】中明确列出的表名和列名。**
   禁止使用任何未在 Schema 中出现的表名（如 stations、wafers、sub_batches、users 等）。
2. 如果用户提及中文名称，根据【中文表名映射】映射到对应的英文表名。
3. 考虑表的业务含义构建正确逻辑，优先使用表中实际存在的列。
4. **SQL 格式限制**：
   - 禁止使用 WITH (CTE) 语法
   - 禁止 SELECT 子句中的关联子查询
   - 多表查询使用 JOIN + GROUP BY 的标准写法
5. **MySQL 语法规范**（目标数据库是 MySQL 8.0，禁止 PostgreSQL 语法）：
   - 时间间隔写法：`INTERVAL 1 DAY`（不加引号），不是 `INTERVAL '1 day'`
   - 最近N天：`gmt_create >= NOW() - INTERVAL 7 DAY`
   - 最近N月：`gmt_create >= NOW() - INTERVAL 1 MONTH`（不是 INTERVAL '1 month'）
   - 字符串拼接：使用 `CONCAT()`，不用 `||`
   - 禁止 `FILTER (WHERE ...)` 语法
   - 禁止 `::` 类型转换，用 `CAST(x AS TYPE)` 代替
   - **JSON数组遍历**：当需要展开 JSON 列中的数组并 JOIN 时，必须使用 MySQL 内置函数 `JSON_TABLE()`（注意：JSON_TABLE 是函数名，不是表名），并用 `FOR ORDINALITY` 保留数组原始顺序，标准写法：
     `CROSS JOIN JSON_TABLE(<json列>, '$[*]' COLUMNS (seq FOR ORDINALITY, id INT PATH '$.id')) AS jt`
     `INNER JOIN <目标表> t ON t.id = jt.id`
     `ORDER BY jt.seq`
     关键键字段名从语义注释获取（`$.id` 或 `$.process_id` 等）；
     禁止用 `JSON_CONTAINS()` / `JSON_EXTRACT()` 与整体数组做比较；
     禁止把物理表名当作函数名（如 `CROSS JOIN matrix_routerx_config_route(...)` 是错误写法）
6. SQL 末尾不要添加分号 (;)
7. WHERE 条件用 name/description 列做中文匹配，不猜测 code 列的英文值
8. **语义引擎优先原则**（当用户查询包含[语义引擎分析结果]时必须严格遵守）：
   - 【指标定义】中的公式是计算逻辑的唯一权威来源，必须使用其 formula、anchor_table 和 auto_filter
   - 【涉及实体】中列出的所有维度类都是 GROUP BY 的依据，所有维度必须同时出现在 SELECT 和 GROUP BY 中
   - 【业务规则约束】中的路径示例仅为 JOIN 路径参考片段，禁止直接照搬，必须按当前查询的实际维度和指标重新组合
   - 如查询同时包含多个指标（如"在制品数量"+"良率"），为每个指标分别使用其定义的公式和路径，合并到同一 SELECT

【输出要求】
- 仅输出 SQL 语句，不含任何解释或 markdown 代码块（禁止 ```sql 标记）
- 只使用 Schema 中实际存在的表名
- 不在 SQL 末尾添加分号"""
        
        return prompt
    
    def convert(self, natural_language: str) -> Optional[str]:
        """将自然语言转换为 SQL
        
        Args:
            natural_language: 用户输入的自然语言查询
            
        Returns:
            转换后的 SQL 语句
        """
        try:
            # 使用增强的 schema 构建提示词
            enhanced_prompt = self._build_enhanced_prompt(natural_language)
            
            # 调用 LLM 直接转换（使用完整的 prompt）
            sql = self.llm_provider.generate(enhanced_prompt) if hasattr(
                self.llm_provider, 'generate'
            ) else self._call_llm_with_prompt(enhanced_prompt)
            
            if sql:
                logger.info(f"✅ Converted NL to SQL (before validation): {sql[:100]}...")
                
                # 验证和纠正表名
                corrected_sql = self._validate_and_fix_table_names(sql)
                
                if corrected_sql != sql:
                    logger.info(f"✅ SQL corrected: {corrected_sql[:100]}...")
                    return corrected_sql.strip().rstrip(';').strip()
                
                return sql.strip().rstrip(';').strip()
            else:
                logger.warning("LLM provider returned None")
                return self._fallback_parse_nl_to_sql(natural_language)
                
        except Exception as e:
            logger.error(f"Error converting NL to SQL: {str(e)}")
            return self._fallback_parse_nl_to_sql(natural_language)
    
    def _call_llm_with_prompt(self, prompt: str) -> Optional[str]:
        """直接调用 LLM 的通用方法"""
        try:
            # 尝试使用 convert_nl_to_sql 方法（带完整 prompt）
            if hasattr(self.llm_provider, 'convert_nl_to_sql'):
                # 将完整 prompt 作为 natural_language 参数传递
                return self.llm_provider.convert_nl_to_sql(prompt)
            
            # 备选：直接调用 API
            return self._fallback_parse_nl_to_sql(prompt)
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return None
    
    def _fallback_parse_nl_to_sql(self, nl: str) -> str:
        """备用的简单关键词匹配实现"""
        logger.info("Using fallback NL to SQL parsing")
        nl_lower = nl.lower()
        
        # 从注解元数据中获取真实的表名（如果可用）
        tables = self.annotation_metadata.get('tables', {})
        
        # 简单的关键词匹配
        if '查询' in nl_lower or 'select' in nl_lower or '显示' in nl_lower:
            if tables:
                first_table = list(tables.keys())[0]
                return f"SELECT * FROM {first_table} LIMIT 10"
            return "SELECT * FROM users LIMIT 10"
        elif '插入' in nl_lower or 'insert' in nl_lower or '添加' in nl_lower:
            return "INSERT INTO users (name, email) VALUES ('example', 'example@example.com')"
        elif '更新' in nl_lower or 'update' in nl_lower or '修改' in nl_lower:
            return "UPDATE users SET name = 'updated' WHERE id = 1"
        elif '删除' in nl_lower or 'delete' in nl_lower:
            return "DELETE FROM users WHERE id = 1"
        else:
            if tables:
                first_table = list(tables.keys())[0]
                return f"SELECT * FROM {first_table}"
            return "SELECT * FROM users"
    
    def get_table_name_from_cn(self, cn_name: str) -> Optional[str]:
        """从中文名称获取表名
        
        Args:
            cn_name: 中文表名
            
        Returns:
            英文表名，或 None 如果未找到
        """
        tables = self.annotation_metadata.get('tables', {})
        for table_name, table_info in tables.items():
            if table_info.get('name_cn') == cn_name:
                return table_name
        return None
    
    def get_column_name_from_cn(self, table_name: str, cn_col_name: str) -> Optional[str]:
        """从中文列名获取列名
        
        Args:
            table_name: 英文表名
            cn_col_name: 中文列名
            
        Returns:
            英文列名，或 None 如果未找到
        """
        columns = self.annotation_metadata.get('columns', {})
        for col in columns.values():
            if (col.get('table_name') == table_name and 
                col.get('column_name_cn') == cn_col_name):
                return col.get('column_name')
        return None
    
    def _validate_and_fix_table_names(self, sql: str) -> str:
        """验证和修正SQL中的表名
        
        检查SQL中使用的表是否存在，如果不存在则尝试修正。
        跳过 CTE（WITH）定义的别名，不将其"修正"为真实表名。
        """
        import re
        
        tables = self.annotation_metadata.get('tables', {})
        valid_table_names = set(tables.keys())
        
        if not valid_table_names:
            return sql

        # 补充加载本体映射文件中的物理表名，避免将生产库表名误改为测试库表名
        try:
            from app.ontology.mapping import get_mapping
            _ont_tables = get_mapping().list_physical_tables()
            for _pt in _ont_tables:
                if _pt.table_name:
                    valid_table_names.add(_pt.table_name)
        except Exception:
            pass

        # 提取 CTE 别名（WITH name AS ...），避免将其误修正为真实表名
        cte_aliases = set()
        cte_pattern = r'\bWITH\b\s+([\w_]+)\s+AS\b'
        for m in re.finditer(cte_pattern, sql, re.IGNORECASE):
            cte_aliases.add(m.group(1).lower())
        # 也匹配逗号分隔的后续 CTE: ), name AS (
        subsequent_cte = r'\)\s*,\s*([\w_]+)\s+AS\s*\('
        for m in re.finditer(subsequent_cte, sql, re.IGNORECASE):
            cte_aliases.add(m.group(1).lower())
        
        if cte_aliases:
            logger.info(f"CTE aliases detected (skipping validation): {cte_aliases}")

        # MySQL 内置表函数 / 关键字，出现在 JOIN 后面但不是真实表名，跳过验证
        builtin_table_functions = {
            'json_table', 'lateral', 'dual',
        }

        # 提取SQL中的表名
        from_pattern = r'FROM\s+([\w_]+)(?:\s|$|;)'
        join_pattern = r'JOIN\s+([\w_]+)(?:\s|$|;)'
        
        corrected_sql = sql
        
        # 检查FROM子句中的表名
        for match in re.finditer(from_pattern, sql, re.IGNORECASE):
            table_name = match.group(1)
            # 跳过 CTE 别名 和 MySQL 内置表函数
            if table_name.lower() in cte_aliases or table_name.lower() in builtin_table_functions:
                continue
            if table_name.lower() not in [t.lower() for t in valid_table_names]:
                # 表名不存在，这是一个可能的错误
                logger.warning(f"Table '{table_name}' not found in schema, attempting to correct...")
                
                # 尝试通过中文名称反向查找
                corrected_name = self._find_best_matching_table(table_name)
                if corrected_name:
                    logger.info(f"Corrected table name: {table_name} → {corrected_name}")
                    corrected_sql = re.sub(
                        rf'\b{re.escape(table_name)}\b',
                        corrected_name,
                        corrected_sql,
                        flags=re.IGNORECASE
                    )
        
        # 检查JOIN子句中的表名
        for match in re.finditer(join_pattern, sql, re.IGNORECASE):
            table_name = match.group(1)
            # 跳过 CTE 别名 和 MySQL 内置表函数
            if table_name.lower() in cte_aliases or table_name.lower() in builtin_table_functions:
                continue
            if table_name.lower() not in [t.lower() for t in valid_table_names]:
                logger.warning(f"Table '{table_name}' in JOIN not found in schema")
                corrected_name = self._find_best_matching_table(table_name)
                if corrected_name:
                    logger.info(f"Corrected JOIN table: {table_name} → {corrected_name}")
                    corrected_sql = re.sub(
                        rf'\b{re.escape(table_name)}\b',
                        corrected_name,
                        corrected_sql,
                        flags=re.IGNORECASE
                    )
        
        return corrected_sql
    
    def _find_best_matching_table(self, incorrect_table: str) -> Optional[str]:
        """通过相似度或中文映射查找最匹配的表名"""
        tables = self.annotation_metadata.get('tables', {})
        
        # 明确的映射规则（常见错误）
        # 注意：不要在此处硬编码 stations/station，因为不同DB环境的真实表名不同
        # 物理表名映射应由语义引擎(semantic_resolver)通过ontology动态确定
        specific_mappings = {
            'vehicles': 'carriers',
            'vehicle': 'carriers',
            'equipment': 'equipment',
            'orders': 'production_orders',
            'order': 'production_orders',
            'products': 'products',
            'product': 'products',
            'batches': 'batches',
            'batch': 'batches',
            'wafers': 'wafers',
            'wafer': 'wafers',
            'carriers': 'carriers',
            'carrier': 'carriers',
        }
        
        # 精确匹配（忽略大小写）
        incorrect_lower = incorrect_table.lower()
        if incorrect_lower in specific_mappings:
            mapped = specific_mappings[incorrect_lower]
            if mapped in tables:
                return mapped
        
        # 模糊匹配：寻找最相似的表名
        from difflib import SequenceMatcher
        best_match = None
        best_ratio = 0.6  # 至少 60% 相似度
        
        for table_name in tables.keys():
            ratio = SequenceMatcher(None, incorrect_lower, table_name.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = table_name
        
        if best_match:
            logger.info(f"Found similar table: {best_match} (similarity: {best_ratio:.2%})")
            return best_match
        
        return None
    
    def get_metadata_summary(self) -> Dict[str, Any]:
        """获取当前元数据摘要"""
        return {
            'tables': len(self.annotation_metadata.get('tables', {})),
            'columns': len(self.annotation_metadata.get('columns', {})),
            'table_names': list(self.annotation_metadata.get('tables', {}).keys()),
            'column_count_by_table': {
                table: len([c for c in self.annotation_metadata.get('columns', {}).values()
                           if c.get('table_name') == table])
                for table in self.annotation_metadata.get('tables', {}).keys()
            }
        }


# 全局实例
_enhanced_converter = None


def get_enhanced_nl2sql_converter() -> EnhancedNL2SQLConverter:
    """获取增强的 NL2SQL 转换器单例"""
    global _enhanced_converter
    if _enhanced_converter is None:
        _enhanced_converter = EnhancedNL2SQLConverter()
    return _enhanced_converter
