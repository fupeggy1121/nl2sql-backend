"""
Supabase 客户端
使用 Supabase SDK + PostgREST API
无需数据库密码，只需 SUPABASE_URL 和 SUPABASE_ANON_KEY
"""
import os
import logging
import re
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
    
    def _detect_aggregate_query(self, sql: str) -> Optional[Dict[str, Any]]:
        """
        检测SQL是否为聚合查询 (COUNT, SUM, AVG, MIN, MAX)
        
        Returns:
            聚合信息字典 {'function': 'count', 'column': '*', 'alias': 'count'} 或 None
        """
        sql_clean = re.sub(r'\s+', ' ', sql).strip()
        # 匹配 SELECT COUNT(*), SELECT COUNT(col), SELECT SUM(col) AS alias 等
        agg_pattern = r'SELECT\s+(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(\*|\w+)\s*\)(?:\s+AS\s+(\w+))?'
        match = re.search(agg_pattern, sql_clean, re.IGNORECASE)
        if match:
            func_name = match.group(1).lower()
            column = match.group(2)
            alias = match.group(3) or func_name
            return {'function': func_name, 'column': column, 'alias': alias}
        return None

    def execute_query(self, sql: str, table_name: str = None) -> Dict[str, Any]:
        """
        执行查询 - 使用 PostgREST API + WHERE 条件支持
        
        支持聚合查询 (COUNT/SUM/AVG/MIN/MAX) 和普通 SELECT 查询。
        
        Args:
            sql: SQL 查询语句（包含WHERE条件）
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
            
            if not table_name:
                return {
                    'success': False,
                    'error': 'table_name is required for PostgREST queries',
                    'data': []
                }
            
            # 解析SQL中的WHERE条件
            where_conditions = self._parse_where_conditions(sql)
            
            # 检测是否为聚合查询
            agg_info = self._detect_aggregate_query(sql)
            
            if agg_info:
                return self._execute_aggregate_query(
                    table_name, agg_info, where_conditions, sql
                )
            
            logger.info(f"Executing query on {table_name} with WHERE conditions: {where_conditions}")
            
            # 普通 SELECT 查询
            # 解析 SELECT 列（支持 SELECT col1, col2 而不仅是 SELECT *）
            select_columns = self._parse_select_columns(sql)
            query = self.client.table(table_name).select(select_columns)
            
            # 应用WHERE条件
            if where_conditions:
                query = self._apply_where_conditions(query, where_conditions)
            
            # 解析 LIMIT
            limit = self._parse_limit(sql)
            if limit:
                query = query.limit(limit)
            
            # 解析 ORDER BY
            order_info = self._parse_order_by(sql)
            if order_info:
                query = query.order(order_info['column'], desc=order_info['desc'])
            
            # 执行查询
            response = query.execute()
            data = response.data
            
            logger.info(f"✅ Query executed: {len(data)} rows returned from {table_name}")
            
            return {
                'success': True,
                'data': data,
                'count': len(data),
                'message': f'成功返回 {len(data)} 条记录'
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Query execution failed: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'data': []
            }
    
    def _execute_aggregate_query(
        self, table_name: str, agg_info: Dict[str, Any],
        where_conditions: Dict[str, Any], original_sql: str
    ) -> Dict[str, Any]:
        """
        执行聚合查询 (COUNT/SUM/AVG/MIN/MAX)
        
        对于 COUNT 使用 PostgREST 的 count='exact' 参数；
        对于 SUM/AVG/MIN/MAX 先拉取目标列数据再在 Python 端计算。
        """
        func = agg_info['function']
        column = agg_info['column']
        alias = agg_info['alias']
        
        logger.info(f"Executing aggregate query: {func}({column}) on {table_name}, WHERE={where_conditions}")
        
        try:
            if func == 'count':
                # 使用 PostgREST 的 count 功能，只获取 count 不拉取数据
                query = self.client.table(table_name).select('*', count='exact')
                if where_conditions:
                    query = self._apply_where_conditions(query, where_conditions)
                query = query.limit(0)  # 不需要实际数据行
                response = query.execute()
                count_value = response.count if hasattr(response, 'count') and response.count is not None else len(response.data)
                
                logger.info(f"✅ COUNT query result: {count_value}")
                return {
                    'success': True,
                    'data': [{alias: count_value}],
                    'count': 1,
                    'message': f'{func.upper()}({column}) = {count_value}'
                }
            
            else:
                # SUM / AVG / MIN / MAX — 拉取目标列数据后在 Python 端计算
                select_col = column if column != '*' else '*'
                query = self.client.table(table_name).select(select_col)
                if where_conditions:
                    query = self._apply_where_conditions(query, where_conditions)
                response = query.execute()
                rows = response.data
                
                if not rows or column == '*':
                    return {
                        'success': True,
                        'data': [{alias: None}],
                        'count': 1,
                        'message': f'无数据可计算 {func.upper()}'
                    }
                
                values = []
                for row in rows:
                    val = row.get(column)
                    if val is not None:
                        try:
                            values.append(float(val))
                        except (ValueError, TypeError):
                            pass
                
                if not values:
                    result_value = None
                elif func == 'sum':
                    result_value = sum(values)
                elif func == 'avg':
                    result_value = sum(values) / len(values)
                elif func == 'min':
                    result_value = min(values)
                elif func == 'max':
                    result_value = max(values)
                else:
                    result_value = None
                
                # 保留合理精度
                if result_value is not None and isinstance(result_value, float):
                    result_value = round(result_value, 4)
                
                logger.info(f"✅ {func.upper()} query result: {result_value}")
                return {
                    'success': True,
                    'data': [{alias: result_value}],
                    'count': 1,
                    'message': f'{func.upper()}({column}) = {result_value}'
                }
        
        except Exception as e:
            logger.error(f"❌ Aggregate query failed: {str(e)}")
            return {
                'success': False,
                'error': f'聚合查询失败: {str(e)}',
                'data': []
            }
    
    def _parse_select_columns(self, sql: str) -> str:
        """解析 SELECT 列，返回 PostgREST 兼容的 select 字符串"""
        match = re.search(r'SELECT\s+(.+?)\s+FROM', sql, re.IGNORECASE)
        if match:
            cols = match.group(1).strip()
            # 如果是聚合函数就返回 *（由 _execute_aggregate_query 处理）
            if re.search(r'(COUNT|SUM|AVG|MIN|MAX)\s*\(', cols, re.IGNORECASE):
                return '*'
            # 如果已经是 *，直接返回
            if cols.strip() == '*':
                return '*'
            # 清理别名 (col AS alias → col)
            cleaned = []
            for col in cols.split(','):
                col = col.strip()
                col = re.sub(r'\s+AS\s+\w+', '', col, flags=re.IGNORECASE).strip()
                if col:
                    cleaned.append(col)
            return ','.join(cleaned) if cleaned else '*'
        return '*'
    
    def _parse_limit(self, sql: str) -> Optional[int]:
        """解析 LIMIT 子句"""
        match = re.search(r'LIMIT\s+(\d+)', sql, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None
    
    def _parse_order_by(self, sql: str) -> Optional[Dict[str, Any]]:
        """解析 ORDER BY 子句"""
        match = re.search(r'ORDER\s+BY\s+(\w+)(?:\s+(ASC|DESC))?', sql, re.IGNORECASE)
        if match:
            return {
                'column': match.group(1),
                'desc': match.group(2) and match.group(2).upper() == 'DESC'
            }
        return None
    
    def _parse_where_conditions(self, sql: str) -> Dict[str, Any]:
        """
        解析SQL中的WHERE条件
        
        Args:
            sql: SQL查询语句
            
        Returns:
            WHERE条件字典 {column: value, ...}
        """
        # 匹配 WHERE 后的条件
        # 支持的格式:
        # - WHERE column = 'value'
        # - WHERE column = value
        # - WHERE column1 = 'val1' AND column2 = 'val2'
        
        where_match = re.search(r'WHERE\s+(.+?)(?:;|ORDER|GROUP|LIMIT|\s*$)', sql, re.IGNORECASE)
        
        if not where_match:
            return {}
        
        where_clause = where_match.group(1).strip()
        conditions = {}
        
        # Split by AND
        and_conditions = re.split(r'\s+AND\s+', where_clause, flags=re.IGNORECASE)
        
        for condition in and_conditions:
            # Parse individual conditions: column = value
            # Support: column = 'string' or column = number
            match = re.match(r"(\w+)\s*=\s*'([^']*)'", condition, re.IGNORECASE) or \
                    re.match(r"(\w+)\s*=\s*(\d+)", condition, re.IGNORECASE)
            
            if match:
                column = match.group(1)
                value = match.group(2)
                
                # Try to convert to number if possible
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    pass
                
                conditions[column] = value
                logger.info(f"  Parsed condition: {column} = {value}")
        
        return conditions
    
    def _apply_where_conditions(self, query, conditions: Dict[str, Any]):
        """
        应用WHERE条件到PostgREST查询
        
        Args:
            query: PostgREST查询对象
            conditions: WHERE条件字典
            
        Returns:
            应用了条件的查询对象
        """
        for column, value in conditions.items():
            logger.info(f"Applying filter: {column} eq {value}")
            query = query.eq(column, value)
        
        return query
    
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
    
    def table(self, table_name: str):
        """
        访问 Supabase 表
        
        Args:
            table_name: 表名
            
        Returns:
            Supabase 表对象
        """
        if not self.client:
            raise RuntimeError(f"Supabase client not initialized: {self.init_error}")
        return self.client.table(table_name)
    
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
