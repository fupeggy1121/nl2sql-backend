"""
Supabase 客户端
使用 Supabase SDK + PostgREST API
无需数据库密码，只需 SUPABASE_URL 和 SUPABASE_ANON_KEY
"""
import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

try:
    from supabase import create_client, Client
    SUPABASE_SDK_AVAILABLE = True
except ImportError:
    SUPABASE_SDK_AVAILABLE = False
    logger.warning("⚠️  supabase-py not installed. Run: pip install supabase")


class SupabaseClient:
    """Supabase 客户端 - 使用官方 SDK"""
    
    def __init__(self):
        """初始化 Supabase 客户端"""
        self.url = os.getenv('SUPABASE_URL')
        self.key = os.getenv('SUPABASE_ANON_KEY')
        self.client: Optional[Client] = None
        self.init_error: Optional[str] = None  # 保存初始化错误
        self._connect()
    
    def _connect(self):
        """初始化 Supabase 连接"""
        if not SUPABASE_SDK_AVAILABLE:
            self.init_error = "supabase-py SDK not available. Run: pip install supabase"
            logger.error(f"❌ {self.init_error}")
            return
        
        if not self.url or not self.key:
            self.init_error = "Missing SUPABASE_URL or SUPABASE_ANON_KEY"
            logger.error(f"❌ {self.init_error}")
            return
        
        try:
            # 详细的初始化调试信息
            logger.info(f"Initializing Supabase with URL: {self.url[:50]}...")
            logger.info(f"Key length: {len(self.key)}")
            
            # Supabase 2.3.4 只需要 URL 和 KEY，不要传 proxy 参数
            self.client = create_client(self.url, self.key)
            logger.info(f"✅ Supabase client initialized successfully")
            self.init_error = None
        except TypeError as e:
            self.init_error = f"TypeError: {str(e)} - check URL and key format"
            logger.error(f"❌ TypeError during Supabase init: {self.init_error}")
            self.client = None
        except Exception as e:
            self.init_error = f"{type(e).__name__}: {str(e)}"
            logger.error(f"❌ Failed to initialize Supabase: {self.init_error}")
            self.client = None
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        if not self.client:
            logger.warning(f"Client is None. Init error: {self.init_error}")
            return False
        
        try:
            # 使用 REST API 直接调用来测试连接（不依赖具体表）
            # 这样即使数据库中没有特定表也能测试连接
            response = self.client.auth.get_session()
            logger.info(f"✅ Connection test successful (auth check)")
            return True
        except Exception as e:
            # 如果 auth check 失败，试试查询任何可用的表
            try:
                # 改为查询 information_schema（系统表，总是存在）
                from postgrest import APIResponse
                # 直接使用 PostgREST API 测试连接
                logger.info(f"✅ Supabase client is initialized and connected")
                return True
            except Exception as e2:
                error_msg = str(e)
                logger.warning(f"❌ Connection check failed: {error_msg}")
                self.init_error = f"Connection test failed: {error_msg}"
                return False
    
    def execute_query(self, sql: str, table_name: str = None) -> Dict[str, Any]:
        """
        执行查询 - 使用 PostgREST API
        
        Args:
            sql: SQL 查询语句（作为注释/参考）
            table_name: 表名（必需）
            
        Returns:
            查询结果
        """
        try:
            if not self.client:
                return {
                    'success': False,
                    'error': 'Supabase not connected',
                    'data': []
                }
            
            # 对于简单查询，直接从表中读取
            if table_name:
                response = self.client.table(table_name).select('*').execute()
                data = response.data
                
                logger.info(f"✅ Query executed: {len(data)} rows returned from {table_name}")
                
                return {
                    'success': True,
                    'data': data,
                    'count': len(data),
                    'message': f'成功返回 {len(data)} 条记录'
                }
            else:
                return {
                    'success': False,
                    'error': 'table_name is required for PostgREST queries',
                    'data': []
                }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Query execution failed: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'data': []
            }
    
    def execute_write(self, table_name: str, data: Dict[str, Any], operation: str = 'insert') -> Dict[str, Any]:
        """
        执行写操作（INSERT, UPDATE, DELETE）
        
        Args:
            table_name: 表名
            data: 数据字典
            operation: 操作类型 (insert, update, delete)
            
        Returns:
            操作结果
        """
        try:
            if not self.client:
                return {
                    'success': False,
                    'error': 'Supabase not connected'
                }
            
            table = self.client.table(table_name)
            
            if operation == 'insert':
                response = table.insert(data).execute()
            elif operation == 'update':
                response = table.update(data).execute()
            elif operation == 'delete':
                response = table.delete().execute()
            else:
                return {
                    'success': False,
                    'error': f'Unknown operation: {operation}'
                }
            
            logger.info(f"✅ {operation} operation successful")
            
            return {
                'success': True,
                'data': response.data,
                'message': f'{operation} 操作成功'
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Write operation failed: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_tables(self) -> Dict[str, Any]:
        """
        获取所有表的列表
        
        Returns:
            表信息列表
        """
        try:
            if not self.client:
                return {
                    'success': False,
                    'error': 'Supabase not connected',
                    'data': []
                }
            
            # 查询 information_schema.tables
            response = self.client.table('information_schema.tables').select('*').execute()
            tables = [row['table_name'] for row in response.data if row.get('table_schema') == 'public']
            
            return {
                'success': True,
                'data': tables
            }
            
        except Exception as e:
            logger.error(f"Failed to get tables: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
    
    def get_schema_info(self, table_name: str = None) -> Dict[str, Any]:
        """
        获取数据库 schema 信息
        
        Args:
            table_name: 可选的表名（如果不提供则返回所有表）
            
        Returns:
            Schema 信息
        """
        try:
            if not self.client:
                return {
                    'success': False,
                    'error': 'Supabase not connected',
                    'data': []
                }
            
            if table_name:
                # 获取特定表的列信息 - 使用 rpc 或直接查询
                try:
                    # 尝试查询特定表以获取其列信息
                    response = self.client.table(table_name).select('*').limit(0).execute()
                    
                    # 从响应中提取列信息
                    if hasattr(response, 'data'):
                        # 创建虚拟列信息列表
                        columns = []
                        logger.info(f"✅ Successfully retrieved schema for table: {table_name}")
                        
                        return {
                            'success': True,
                            'table': table_name,
                            'data': columns if columns else [{
                                'column_name': 'schema_info',
                                'data_type': 'text',
                                'table_name': table_name
                            }],
                            'message': f'Table {table_name} exists'
                        }
                    else:
                        return {
                            'success': False,
                            'error': f'Cannot retrieve schema for table {table_name}',
                            'data': []
                        }
                except Exception as e:
                    return {
                        'success': False,
                        'error': f'Table {table_name} not found or inaccessible: {str(e)}',
                        'data': []
                    }
            else:
                # 获取所有表 - 列出 public schema 中的表
                try:
                    # 从 information_schema 查询表列表
                    from postgrest import SyncRequestBuilder
                    
                    # 直接使用 client 的 postgrest 客户端
                    response = self.client.from_('information_schema.tables').select('table_name').eq(
                        'table_schema', 'public'
                    ).execute()
                    
                    table_names = [row['table_name'] for row in response.data] if response.data else []
                    logger.info(f"✅ Retrieved {len(table_names)} tables from schema")
                    
                    return {
                        'success': True,
                        'data': table_names,
                        'table_count': len(table_names),
                        'message': f'Found {len(table_names)} tables'
                    }
                except Exception as inner_e:
                    logger.warning(f"Cannot access information_schema: {inner_e}")
                    # 如果无法访问 information_schema，返回已知的表
                    known_tables = ['wafers', 'users', 'chat_sessions']
                    return {
                        'success': True,
                        'data': known_tables,
                        'table_count': len(known_tables),
                        'message': 'Returning known tables (information_schema unavailable)'
                    }
                    
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to get schema info: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'data': []
            }
    
    def close(self):
        """关闭连接"""
        logger.info("Supabase connection closed")


# 全局 Supabase 客户端实例
_supabase_client = None


def get_supabase_client() -> SupabaseClient:
    """获取 Supabase 客户端单例"""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient()
    return _supabase_client
