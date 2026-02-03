"""
Supabase 直接 SQL 执行服务
用于数据库迁移、表创建等管理操作
"""

import psycopg2
from psycopg2 import sql
import os
import logging
from typing import List, Tuple, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class PostgreSQLExecutor:
    """直接连接 Supabase PostgreSQL 执行 SQL
    
    使用场景：
    - 数据库迁移 (创建表)
    - 初始数据加载
    - 数据库维护操作
    """
    
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.connection_string = self._build_connection_string()
    
    def _build_connection_string(self) -> str:
        """构建 PostgreSQL 连接字符串"""
        return (
            f"postgresql://"
            f"{os.getenv('SUPABASE_DB_USER', 'postgres')}:"
            f"{os.getenv('SUPABASE_DB_PASSWORD')}@"
            f"{os.getenv('SUPABASE_DB_HOST')}:"
            f"{os.getenv('SUPABASE_DB_PORT', 5432)}/"
            f"{os.getenv('SUPABASE_DB_NAME', 'postgres')}"
        )
    
    def connect(self) -> bool:
        """建立数据库连接"""
        try:
            # 从连接字符串连接
            self.conn = psycopg2.connect(self.connection_string)
            self.cursor = self.conn.cursor()
            
            # 测试连接
            self.cursor.execute("SELECT 1")
            self.conn.commit()
            
            logger.info("✅ PostgreSQL 连接成功")
            return True
        except psycopg2.Error as e:
            logger.error(f"❌ 数据库连接失败: {str(e)}")
            self.conn = None
            self.cursor = None
            return False
    
    def execute_query(self, query: str, params: tuple = None) -> Optional[List]:
        """执行单个查询"""
        if not self.cursor:
            logger.error("❌ 数据库未连接")
            return None
        
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            
            # 如果是 SELECT 查询，返回结果
            if query.strip().upper().startswith('SELECT'):
                return self.cursor.fetchall()
            else:
                self.conn.commit()
                return None
        except psycopg2.Error as e:
            logger.error(f"❌ 查询执行失败: {str(e)}")
            self.conn.rollback()
            return None
    
    def execute_sql_file(self, file_path: str) -> bool:
        """执行 SQL 文件（用于迁移）
        
        Args:
            file_path: SQL 文件路径
            
        Returns:
            是否成功
        """
        if not self.cursor:
            logger.error("❌ 数据库未连接")
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # 分割成单个语句（按 ; 分割）
            statements = [
                stmt.strip() 
                for stmt in sql_content.split(';') 
                if stmt.strip() and not stmt.strip().startswith('--')
            ]
            
            logger.info(f"开始执行 {len(statements)} 个 SQL 语句...")
            
            successful = 0
            failed = 0
            
            for i, stmt in enumerate(statements, 1):
                try:
                    logger.debug(f"[{i}/{len(statements)}] 执行: {stmt[:60]}...")
                    self.cursor.execute(stmt)
                    self.conn.commit()
                    successful += 1
                    logger.info(f"✅ [{i}/{len(statements)}] 成功")
                except psycopg2.Error as e:
                    error_msg = str(e)
                    # 某些错误可以忽略（如对象已存在）
                    if 'already exists' in error_msg.lower() or \
                       'duplicate' in error_msg.lower() or \
                       'relation' in error_msg.lower():
                        logger.warning(f"⚠️  [{i}/{len(statements)}] 对象已存在（正常）")
                        successful += 1
                    else:
                        logger.error(f"❌ [{i}/{len(statements)}] 失败: {error_msg[:80]}")
                        failed += 1
            
            logger.info(f"执行完成: {successful} 成功, {failed} 失败")
            return failed == 0
            
        except Exception as e:
            logger.error(f"❌ 文件读取或执行失败: {str(e)}")
            return False
        finally:
            self.close()
    
    def execute_batch(self, queries: List[str]) -> bool:
        """批量执行查询
        
        Args:
            queries: SQL 查询列表
            
        Returns:
            是否全部成功
        """
        if not self.cursor:
            logger.error("❌ 数据库未连接")
            return False
        
        try:
            for i, query in enumerate(queries, 1):
                logger.debug(f"[{i}/{len(queries)}] 执行查询...")
                self.cursor.execute(query)
            
            self.conn.commit()
            logger.info(f"✅ 批量执行成功: {len(queries)} 个查询")
            return True
            
        except psycopg2.Error as e:
            logger.error(f"❌ 批量执行失败: {str(e)}")
            self.conn.rollback()
            return False
    
    def table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        try:
            query = """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = %s
            )
            """
            self.cursor.execute(query, (table_name,))
            result = self.cursor.fetchone()
            return result[0] if result else False
        except Exception as e:
            logger.error(f"❌ 检查表失败: {str(e)}")
            return False
    
    def get_table_columns(self, table_name: str) -> List[Tuple]:
        """获取表的列信息"""
        try:
            query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
            """
            self.cursor.execute(query, (table_name,))
            return self.cursor.fetchall()
        except Exception as e:
            logger.error(f"❌ 获取列信息失败: {str(e)}")
            return []
    
    def close(self):
        """关闭连接"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("数据库连接已关闭")


# 使用示例
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 执行迁移
    executor = PostgreSQLExecutor()
    if executor.connect():
        # 执行 SQL 文件
        success = executor.execute_sql_file('migration.sql')
        
        if success:
            # 验证表是否创建
            tables = [
                'schema_table_annotations',
                'schema_column_annotations',
                'schema_relation_annotations',
                'annotation_audit_log'
            ]
            
            print("\n验证创建的表:")
            for table in tables:
                exists = executor.table_exists(table)
                status = "✅" if exists else "❌"
                print(f"  {status} {table}")
        
        executor.close()
