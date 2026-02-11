"""
数据库查询服务
执行 SQL 查询并返回结果
支持 PostgreSQL 直接连接和 Supabase 客户端
"""
from typing import List, Dict, Any, Optional
import logging
import re

logger = logging.getLogger(__name__)

class QueryExecutor:
    """SQL 查询执行器 - 支持 PostgreSQL 直接连接和 Supabase"""
    
    def __init__(self, supabase_client=None):
        """
        初始化查询执行器
        
        Args:
            supabase_client: Supabase 客户端对象（可选）
        """
        self.supabase_client = supabase_client
        self.pg_executor = None  # 延迟初始化PostgreSQL执行器
    
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
        执行 SQL 查询 - 使用 PostgreSQL 直接连接
        
        优点：支持完整的 SQL 语法，包括 WHERE、GROUP BY、ORDER BY 等所有条件
        
        Args:
            sql: SQL 查询语句（完整的SQL，包括WHERE条件）
            params: 查询参数（可选，Supabase 不支持）
            
        Returns:
            包含查询结果和元数据的字典
        """
        try:
            # 首先尝试使用 PostgreSQL 直接连接执行 SQL
            if self.pg_executor is None:
                try:
                    # 延迟导入 PostgreSQLExecutor，这样如果 psycopg2 不可用也不会导致应用启动失败
                    from app.services.postgresql_executor import PostgreSQLExecutor
                    self.pg_executor = PostgreSQLExecutor()
                except ImportError as e:
                    logger.warning(f"Cannot import PostgreSQLExecutor: {str(e)}, falling back to Supabase")
                    self.pg_executor = False  # 标记为不可用
            
            # 如果 PostgreSQL 可用，尝试使用它
            if self.pg_executor and self.pg_executor is not False:
                # 连接到数据库
                if not self.pg_executor.conn:
                    if not self.pg_executor.connect():
                        logger.warning("PostgreSQL direct connection failed, falling back to Supabase")
                        return self._execute_via_supabase(sql)
                
                # 执行 SQL 查询
                logger.info(f"Executing SQL via PostgreSQL: {sql}")
                
                try:
                    self.pg_executor.cursor.execute(sql)
                    
                    # 获取所有结果
                    rows = self.pg_executor.cursor.fetchall()
                    
                    # 获取列名
                    column_names = [desc[0] for desc in self.pg_executor.cursor.description]
                    
                    # 将结果转换为字典列表
                    data = []
                    for row in rows:
                        row_dict = {}
                        for i, col_name in enumerate(column_names):
                            row_dict[col_name] = row[i]
                        data.append(row_dict)
                    
                    logger.info(f"✅ Query executed successfully: {len(data)} rows returned")
                    
                    return {
                        'success': True,
                        'data': data,
                        'count': len(data),
                        'message': f'成功返回 {len(data)} 条记录'
                    }
                    
                except Exception as query_error:
                    logger.error(f"PostgreSQL query execution failed: {str(query_error)}")
                    # 查询执行失败，尝试回退到Supabase
                    return self._execute_via_supabase(sql)
            else:
                # PostgreSQL 不可用，直接使用 Supabase
                logger.info("PostgreSQL executor not available, using Supabase")
                return self._execute_via_supabase(sql)
            
        except Exception as e:
            logger.error(f"Error in execute_query: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
    
    def _execute_via_supabase(self, sql: str) -> Dict[str, Any]:
        """
        通过 Supabase 客户端执行查询（回退方案）
        
        注意：这种方式可能不支持复杂的 WHERE 条件，
        建议也用PostgreSQL直接连接
        
        Args:
            sql: SQL 查询语句
            
        Returns:
            查询结果
        """
        try:
            if not self.supabase_client:
                return {
                    'success': False,
                    'error': 'No database connection available (neither PostgreSQL nor Supabase)',
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
            
            logger.info(f"Falling back to Supabase for query on table: {table_name}")
            logger.warning(f"⚠️ Supabase PostgREST may not support WHERE conditions in this query")
            
            # 调用 Supabase 客户端的 execute_query 方法
            result = self.supabase_client.execute_query(sql, table_name)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in _execute_via_supabase: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
