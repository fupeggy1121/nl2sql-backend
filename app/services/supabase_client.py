"""
Supabase 数据库客户端
支持通过 PostgreSQL 连接查询 Supabase
"""
import os
import logging
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class SupabaseClient:
    """Supabase PostgreSQL 数据库客户端"""
    
    def __init__(self):
        """初始化 Supabase 连接"""
        self.host = os.getenv('DB_HOST')
        self.port = int(os.getenv('DB_PORT', 5432))
        self.user = os.getenv('DB_USER')
        self.password = os.getenv('DB_PASSWORD')
        self.database = os.getenv('DB_NAME')
        self.connection = None
        self._connect()
    
    def _connect(self):
        """建立数据库连接"""
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                connect_timeout=10
            )
            logger.info(f"✅ Supabase connected successfully")
        except psycopg2.Error as e:
            logger.error(f"❌ Failed to connect to Supabase: {str(e)}")
            self.connection = None
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        if self.connection is None:
            return False
        try:
            cursor = self.connection.cursor()
            cursor.execute('SELECT 1')
            cursor.close()
            return True
        except:
            return False
    
    def execute_query(self, sql: str) -> Dict[str, Any]:
        """
        执行 SELECT 查询
        
        Args:
            sql: SQL 查询语句
            
        Returns:
            查询结果和元数据
        """
        try:
            if not self.is_connected():
                self._connect()
            
            if not self.connection:
                return {
                    'success': False,
                    'error': 'Database connection failed',
                    'data': []
                }
            
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(sql)
            rows = cursor.fetchall()
            cursor.close()
            
            # Convert psycopg2 RealDictRow to regular dict
            data = [dict(row) for row in rows]
            
            logger.info(f"✅ Query executed: {len(data)} rows returned")
            
            return {
                'success': True,
                'data': data,
                'count': len(data),
                'message': f'成功返回 {len(data)} 条记录'
            }
            
        except psycopg2.Error as e:
            error_msg = str(e)
            logger.error(f"❌ Query execution failed: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'data': []
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Unexpected error: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'data': []
            }
    
    def execute_write(self, sql: str) -> Dict[str, Any]:
        """
        执行写操作（INSERT, UPDATE, DELETE）
        
        Args:
            sql: SQL 写入语句
            
        Returns:
            操作结果
        """
        try:
            if not self.is_connected():
                self._connect()
            
            if not self.connection:
                return {
                    'success': False,
                    'error': 'Database connection failed'
                }
            
            cursor = self.connection.cursor()
            cursor.execute(sql)
            affected_rows = cursor.rowcount
            self.connection.commit()
            cursor.close()
            
            logger.info(f"✅ Write operation successful: {affected_rows} rows affected")
            
            return {
                'success': True,
                'affected_rows': affected_rows,
                'message': f'成功影响 {affected_rows} 条记录'
            }
            
        except psycopg2.Error as e:
            error_msg = str(e)
            logger.error(f"❌ Write operation failed: {error_msg}")
            self.connection.rollback() if self.connection else None
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_schema_info(self, table_name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取数据库表的 schema 信息
        
        Args:
            table_name: 表名（可选，不指定则返回所有表）
            
        Returns:
            表信息
        """
        try:
            if not self.is_connected():
                self._connect()
            
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            
            if table_name:
                # 获取特定表的列信息
                sql = f"""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                """
                cursor.execute(sql, (table_name,))
            else:
                # 获取所有用户表
                sql = """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """
                cursor.execute(sql)
            
            rows = cursor.fetchall()
            cursor.close()
            
            return {
                'success': True,
                'data': [dict(row) for row in rows]
            }
            
        except Exception as e:
            logger.error(f"Failed to get schema info: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
    
    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")


# 全局 Supabase 客户端实例
_supabase_client = None


def get_supabase_client() -> SupabaseClient:
    """获取 Supabase 客户端单例"""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient()
    return _supabase_client
