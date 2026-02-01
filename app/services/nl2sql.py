"""
NL2SQL 转换服务
将自然语言转换为SQL查询语句
"""
from typing import Optional, Dict, Any
import logging
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)

class NL2SQLConverter:
    """自然语言到SQL的转换器"""
    
    def __init__(self):
        """初始化转换器"""
        self.schema_info = {}
        self.llm_provider = get_llm_provider()
        
    def set_schema(self, schema: Dict[str, Any]) -> None:
        """
        设置数据库 schema 信息
        
        Args:
            schema: 包含表名、列名、数据类型等信息的字典
        """
        self.schema_info = schema
        logger.info(f"Schema set with tables: {list(schema.keys())}")
    
    def convert(self, natural_language: str) -> Optional[str]:
        """
        将自然语言转换为 SQL
        
        Args:
            natural_language: 用户输入的自然语言查询
            
        Returns:
            转换后的 SQL 语句，或失败时返回 None
        """
        try:
            # 准备 schema 信息
            schema_str = self._format_schema()
            
            # 使用 LLM 提供者转换
            sql = self.llm_provider.convert_nl_to_sql(natural_language, schema_str)
            
            if sql:
                logger.info(f"Converted NL to SQL: {sql}")
                return sql
            else:
                logger.warning("LLM provider returned None")
                return self._fallback_parse_nl_to_sql(natural_language)
                
        except Exception as e:
            logger.error(f"Error converting NL to SQL: {str(e)}")
            return self._fallback_parse_nl_to_sql(natural_language)
    
    def _format_schema(self) -> str:
        """
        格式化 schema 信息为字符串
        
        Returns:
            格式化后的 schema 信息
        """
        if not self.schema_info:
            return ""
        
        schema_str = ""
        for table_name, columns in self.schema_info.items():
            schema_str += f"\nTable: {table_name}\n"
            for col_name, col_type in columns.items():
                schema_str += f"  - {col_name} ({col_type})\n"
        
        return schema_str
    
    def _fallback_parse_nl_to_sql(self, nl: str) -> str:
        """
        备用的简单关键词匹配实现
        当 LLM 调用失败时使用
        
        Args:
            nl: 自然语言查询
            
        Returns:
            SQL 语句
        """
        logger.info("Using fallback NL to SQL parsing")
        nl_lower = nl.lower()
        
        # 简单的关键词匹配
        if '查询' in nl_lower or 'select' in nl_lower or '显示' in nl_lower:
            return "SELECT * FROM users LIMIT 10"
        elif '插入' in nl_lower or 'insert' in nl_lower or '添加' in nl_lower:
            return "INSERT INTO users (name, email) VALUES ('example', 'example@example.com')"
        elif '更新' in nl_lower or 'update' in nl_lower or '修改' in nl_lower:
            return "UPDATE users SET name = 'updated' WHERE id = 1"
        elif '删除' in nl_lower or 'delete' in nl_lower:
            return "DELETE FROM users WHERE id = 1"
        else:
            return "SELECT * FROM users"
