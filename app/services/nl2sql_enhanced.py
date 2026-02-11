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
            logger.info("Using fallback metadata loading...")
    
    def refresh_metadata(self) -> None:
        """刷新元数据（手动调用）"""
        self._load_annotation_metadata()
    
    def set_schema(self, schema: Dict[str, Any]) -> None:
        """设置基础数据库 schema 信息"""
        self.schema_info = schema
        logger.info(f"Schema set with tables: {list(schema.keys())}")
    
    def _build_enhanced_schema_prompt(self) -> str:
        """构建增强的 schema 提示词，包含中文名称和业务含义"""
        schema_lines = ["【数据库 Schema 信息】\n"]
        
        tables = self.annotation_metadata.get('tables', {})
        columns = self.annotation_metadata.get('columns', {})
        
        # 添加表信息
        for table_name, table_info in tables.items():
            schema_lines.append(f"表名: {table_name}")
            
            # 添加中文名称
            if 'name_cn' in table_info:
                schema_lines.append(f"  中文名: {table_info['name_cn']}")
            
            # 添加描述
            if 'description_cn' in table_info:
                schema_lines.append(f"  描述: {table_info['description_cn']}")
            if 'description_en' in table_info:
                schema_lines.append(f"  Description: {table_info['description_en']}")
            
            # 添加业务含义
            if 'business_meaning' in table_info:
                schema_lines.append(f"  业务含义: {table_info['business_meaning']}")
            
            # 添加使用场景
            if 'use_case' in table_info:
                schema_lines.append(f"  使用场景: {table_info['use_case']}")
            
            # 添加该表的列信息
            table_columns = [col for col in columns.values() 
                           if col.get('table_name') == table_name]
            if table_columns:
                schema_lines.append("  列:")
                for col in table_columns:
                    col_name = col.get('column_name', '')
                    col_name_cn = col.get('column_name_cn', '')
                    data_type = col.get('data_type', '')
                    desc = col.get('description_cn', '')
                    example = col.get('example_value', '')
                    
                    if col_name_cn:
                        schema_lines.append(f"    - {col_name} ({col_name_cn}): {data_type}")
                    else:
                        schema_lines.append(f"    - {col_name}: {data_type}")
                    
                    if desc:
                        schema_lines.append(f"      描述: {desc}")
                    if example:
                        schema_lines.append(f"      示例: {example}")
            
            schema_lines.append("")
        
        # 如果没有元数据，使用基础 schema
        if not tables and self.schema_info:
            schema_lines.append("【基础 Schema 信息】\n")
            for table_name, columns_info in self.schema_info.items():
                schema_lines.append(f"表: {table_name}")
                for col_name, col_type in columns_info.items():
                    schema_lines.append(f"  - {col_name} ({col_type})")
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

【用户查询】
{natural_language}

【转换规则】
1. 使用正确的表名和列名
2. 如果用户提及中文名称，请根据【中文表名映射】自动映射到对应的英文表名
3. 例外：如果用户说"载具"，应该映射到"carriers"表；"生产订单"映射到"production_orders"表
4. 考虑业务含义和使用场景来构建正确的逻辑
5. 优先使用表中存在的列名
6. 生成的 SQL 应该是可执行的，使用数据库中实际存在的表名

【输出要求】
- 仅输出 SQL 语句，不要包含其他文本或解释
- 如果无法理解查询，返回一个安全的 SELECT 语句
- 确保 SQL 语法正确
- 确保表名是从【中文表名映射】中选择的"""
        
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
                    return corrected_sql.strip()
                
                return sql.strip()
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
        
        检查SQL中使用的表是否存在，如果不存在则尝试修正
        """
        import re
        
        tables = self.annotation_metadata.get('tables', {})
        valid_table_names = set(tables.keys())
        
        if not valid_table_names:
            return sql
        
        # 提取SQL中的表名
        from_pattern = r'FROM\s+([\w_]+)(?:\s|$|;)'
        join_pattern = r'JOIN\s+([\w_]+)(?:\s|$|;)'
        
        corrected_sql = sql
        
        # 检查FROM子句中的表名
        for match in re.finditer(from_pattern, sql, re.IGNORECASE):
            table_name = match.group(1)
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
            'stations': 'stations',
            'station': 'stations',
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
