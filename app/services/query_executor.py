"""
数据库查询服务
执行 SQL 查询并返回结果
支持 Supabase 客户端
"""
from typing import List, Dict, Any, Optional
import logging
import re

logger = logging.getLogger(__name__)

class QueryExecutor:
    """SQL 查询执行器 - 支持 Supabase"""
    
    def __init__(self, supabase_client=None):
        """
        初始化查询执行器
        
        Args:
            supabase_client: Supabase 客户端对象
        """
        self.supabase_client = supabase_client
    
    def _extract_table_from_sql(self, sql: str) -> Optional[str]:
        """
        从 SQL 语句中提取表名
        支持: SELECT ... FROM table_name, DELETE FROM table_name, UPDATE table_name, INSERT INTO table_name
        
        Args:
            sql: SQL 语句
            
        Returns:
            表名或 None
        """
        try:
            # 移除注释和多余空格
            sql_clean = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
            sql_clean = re.sub(r'/\*.*?\*/', '', sql_clean, flags=re.DOTALL)
            sql_clean = re.sub(r'\s+', ' ', sql_clean).strip()
            
            # 提取表名 - 优先匹配 schema.table，然后再匹配 table
            patterns = [
                (r'FROM\s+public\.(\w+)', True),           # SELECT ... FROM public.table
                (r'DELETE\s+FROM\s+public\.(\w+)', True),  # DELETE FROM public.table
                (r'UPDATE\s+public\.(\w+)', True),         # UPDATE public.table
                (r'INSERT\s+INTO\s+public\.(\w+)', True),  # INSERT INTO public.table
                (r'FROM\s+(\w+)', False),                  # SELECT ... FROM table
                (r'DELETE\s+FROM\s+(\w+)', False),         # DELETE FROM table
                (r'UPDATE\s+(\w+)', False),                # UPDATE table
                (r'INSERT\s+INTO\s+(\w+)', False),         # INSERT INTO table
            ]
            
            for pattern, has_schema in patterns:
                match = re.search(pattern, sql_clean, re.IGNORECASE)
                if match:
                    table_name = match.group(1)
                    logger.info(f"Extracted table name from SQL: {table_name} (has_schema: {has_schema})")
                    return table_name
            
            logger.warning(f"Could not extract table name from SQL: {sql[:100]}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting table name: {str(e)}")
            return None
    
    def execute_query(self, sql: str, params: Optional[List] = None) -> Dict[str, Any]:
        """
        执行 SQL 查询
        
        Args:
            sql: SQL 查询语句
            params: 查询参数（可选，Supabase 不支持）
            
        Returns:
            包含查询结果和元数据的字典
        """
        try:
            if not self.supabase_client:
                logger.error("Database connection not initialized")
                return {
                    'success': False,
                    'error': 'Database connection not initialized',
                    'data': []
                }
            
            # 检查 Supabase 客户端是否连接
            if not self.supabase_client.client:
                logger.error("Supabase client not connected")
                return {
                    'success': False,
                    'error': 'Supabase client not connected',
                    'data': []
                }
            
            # 从 SQL 中提取表名
            table_name = self._extract_table_from_sql(sql)
            
            if not table_name:
                logger.warning(f"Cannot determine table from SQL: {sql}")
                return {
                    'success': False,
                    'error': 'Cannot determine table from SQL statement',
                    'data': [],
                    'sql': sql
                }
            
            # 使用 Supabase 执行查询
            logger.info(f"Executing query on table: {table_name}")
            logger.info(f"SQL: {sql}")
            
            # 调用 Supabase 客户端的 execute_query 方法
            result = self.supabase_client.execute_query(sql, table_name)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
