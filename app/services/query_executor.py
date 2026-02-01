"""
数据库查询服务
执行 SQL 查询并返回结果
"""
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class QueryExecutor:
    """SQL 查询执行器"""
    
    def __init__(self, db_connection=None):
        """
        初始化查询执行器
        
        Args:
            db_connection: 数据库连接对象
        """
        self.db_connection = db_connection
    
    def execute_query(self, sql: str, params: Optional[List] = None) -> Dict[str, Any]:
        """
        执行 SQL 查询
        
        Args:
            sql: SQL 查询语句
            params: 查询参数（可选）
            
        Returns:
            包含查询结果和元数据的字典
        """
        try:
            if not self.db_connection:
                logger.error("Database connection not initialized")
                return {
                    'success': False,
                    'error': 'Database connection not initialized',
                    'data': []
                }
            
            # 执行查询
            cursor = self.db_connection.cursor()
            cursor.execute(sql, params or ())
            
            # 获取结果
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            
            # 将结果转换为字典列表
            result_data = [dict(zip(columns, row)) for row in rows]
            
            cursor.close()
            
            logger.info(f"Query executed successfully, returned {len(result_data)} rows")
            
            return {
                'success': True,
                'data': result_data,
                'count': len(result_data),
                'columns': columns
            }
            
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
    
    def execute_insert(self, sql: str, params: Optional[List] = None) -> Dict[str, Any]:
        """
        执行插入操作
        
        Args:
            sql: INSERT SQL 语句
            params: 查询参数（可选）
            
        Returns:
            包含操作结果的字典
        """
        try:
            cursor = self.db_connection.cursor()
            cursor.execute(sql, params or ())
            self.db_connection.commit()
            
            logger.info(f"Insert operation successful, affected rows: {cursor.rowcount}")
            
            return {
                'success': True,
                'affected_rows': cursor.rowcount,
                'last_insert_id': cursor.lastrowid
            }
            
        except Exception as e:
            logger.error(f"Error executing insert: {str(e)}")
            self.db_connection.rollback()
            return {
                'success': False,
                'error': str(e)
            }
