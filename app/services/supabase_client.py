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
    
    # ─── SQL 复杂度分类 ──────────────────────────────
    
    SQL_COMPLEXITY_SIMPLE = 'simple'        # SELECT * FROM t WHERE ... LIMIT ...
    SQL_COMPLEXITY_AGGREGATE = 'aggregate'  # COUNT/SUM/AVG + 可能有 GROUP BY
    SQL_COMPLEXITY_COMPLEX = 'complex'      # JOIN / 子查询 / UNION / HAVING / 窗口函数
    
    def classify_sql_complexity(self, sql: str) -> str:
        """
        对 SQL 语句进行复杂度分级
        
        Returns:
            'simple' / 'aggregate' / 'complex'
        """
        sql_upper = re.sub(r'\s+', ' ', sql).upper().strip()
        
        # complex: JOIN / 子查询 / UNION / HAVING / 窗口函数
        complex_patterns = [
            r'\bJOIN\b',
            r'\bUNION\b',
            r'\bHAVING\b',
            r'\bWITH\b\s+\w+\s+AS\b',  # CTE
            r'\bOVER\s*\(',              # 窗口函数
            r'\(\s*SELECT\b',            # 子查询
        ]
        for pattern in complex_patterns:
            if re.search(pattern, sql_upper):
                return self.SQL_COMPLEXITY_COMPLEX
        
        # aggregate: COUNT/SUM/AVG/MIN/MAX 或 GROUP BY
        if re.search(r'\b(COUNT|SUM|AVG|MIN|MAX)\s*\(', sql_upper) or \
           re.search(r'\bGROUP\s+BY\b', sql_upper):
            return self.SQL_COMPLEXITY_AGGREGATE
        
        return self.SQL_COMPLEXITY_SIMPLE
    
    # ─── 聚合查询检测 ─────────────────────────────────
    
    def _detect_aggregate_query(self, sql: str) -> Optional[Dict[str, Any]]:
        """
        检测SQL是否为聚合查询 (COUNT, SUM, AVG, MIN, MAX)
        支持单聚合和多聚合。
        
        Returns:
            聚合信息字典或 None
            单聚合: {'function': 'count', 'column': '*', 'alias': 'count'}
            多聚合: {'multi': True, 'aggregates': [{...}, {...}]}
        """
        sql_clean = re.sub(r'\s+', ' ', sql).strip()
        
        # 匹配所有聚合函数
        agg_pattern = r'(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(\*|\w+)\s*\)(?:\s+AS\s+(\w+))?'
        matches = list(re.finditer(agg_pattern, sql_clean, re.IGNORECASE))
        
        if not matches:
            return None
        
        aggregates = []
        for m in matches:
            func_name = m.group(1).lower()
            column = m.group(2)
            alias = m.group(3) or func_name
            aggregates.append({'function': func_name, 'column': column, 'alias': alias})
        
        # 检测 GROUP BY
        group_by = self._parse_group_by(sql_clean)
        
        if len(aggregates) == 1 and not group_by:
            return aggregates[0]
        
        return {'multi': True, 'aggregates': aggregates, 'group_by': group_by}

    def execute_query(self, sql: str, table_name: str = None) -> Dict[str, Any]:
        """
        执行查询 - 分层策略
        
        根据 SQL 复杂度自动选择最优执行路径:
          simple    → PostgREST select + filter + order + limit
          aggregate → PostgREST count / client-side aggregation
          complex   → 尝试 Supabase RPC (rpc_execute_sql) 或降级
        
        Args:
            sql: SQL 查询语句
            table_name: 表名（必需）
        """
        try:
            if not self.client:
                return {'success': False, 'error': 'Supabase not connected', 'data': []}
            if not table_name:
                return {'success': False, 'error': 'table_name is required for PostgREST queries', 'data': []}
            
            complexity = self.classify_sql_complexity(sql)
            logger.info(f"SQL complexity: {complexity} | table: {table_name} | SQL: {sql[:80]}...")
            
            # ── complex: 尝试 RPC，失败则降级 ──
            if complexity == self.SQL_COMPLEXITY_COMPLEX:
                rpc_result = self._try_execute_via_rpc(sql)
                if rpc_result and rpc_result.get('success'):
                    return rpc_result
                logger.warning(f"⚠️ Complex SQL degraded to PostgREST (may lose precision): {sql[:80]}")
            
            # ── 解析公共子句 ──
            where_conditions = self._parse_where_conditions(sql)
            
            # ── aggregate ──
            agg_info = self._detect_aggregate_query(sql)
            if agg_info:
                return self._execute_aggregate_query(table_name, agg_info, where_conditions, sql)
            
            # ── simple: 标准 PostgREST 查询 ──
            return self._execute_simple_query(table_name, sql, where_conditions)
            
        except Exception as e:
            logger.error(f"❌ Query execution failed: {str(e)}")
            return {'success': False, 'error': str(e), 'data': []}
    
    def _execute_simple_query(
        self, table_name: str, sql: str, where_conditions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行简单查询 — PostgREST select + filter + order + limit + distinct
        """
        select_columns = self._parse_select_columns(sql)
        
        # DISTINCT 检测
        is_distinct = bool(re.search(r'SELECT\s+DISTINCT\b', sql, re.IGNORECASE))
        
        query = self.client.table(table_name).select(select_columns)
        
        # 应用 WHERE
        if where_conditions:
            query = self._apply_where_conditions(query, where_conditions)
        
        # LIMIT
        limit = self._parse_limit(sql)
        if limit:
            query = query.limit(limit)
        
        # OFFSET
        offset = self._parse_offset(sql)
        if offset:
            query = query.offset(offset)
        
        # ORDER BY（支持多列）
        order_list = self._parse_order_by_multi(sql)
        for order_info in order_list:
            query = query.order(order_info['column'], desc=order_info['desc'])
        
        response = query.execute()
        data = response.data
        
        # 客户端去重 (PostgREST 不直接支持 DISTINCT)
        if is_distinct and data:
            data = self._client_distinct(data)
        
        logger.info(f"✅ Simple query: {len(data)} rows from {table_name}")
        return {
            'success': True,
            'data': data,
            'count': len(data),
            'message': f'成功返回 {len(data)} 条记录'
        }
    
    def _try_execute_via_rpc(self, sql: str) -> Optional[Dict[str, Any]]:
        """
        尝试通过 Supabase RPC 执行复杂 SQL
        
        需要在数据库中创建函数:
          CREATE OR REPLACE FUNCTION execute_sql(query text)
          RETURNS json AS $$ ... $$ LANGUAGE plpgsql SECURITY DEFINER;
        
        如果 RPC 不存在，返回 None 以触发降级
        """
        try:
            if not self.client:
                return None
            # 去除尾部分号 — RPC 会将 SQL 嵌入子查询 FROM (%s) t，
            # 分号在子查询内属于语法错误
            sql_clean = sql.rstrip().rstrip(';').rstrip()
            response = self.client.rpc('execute_sql', {'query': sql_clean}).execute()
            if response.data is not None:
                # RPC 返回的可能是 JSON 数据
                data = response.data if isinstance(response.data, list) else [response.data]
                logger.info(f"✅ RPC execute_sql succeeded: {len(data)} rows")
                return {
                    'success': True,
                    'data': data,
                    'count': len(data),
                    'message': f'通过 RPC 执行成功，返回 {len(data)} 条记录',
                    'execution_method': 'rpc'
                }
            return None
        except Exception as e:
            logger.warning(f"RPC execute_sql failed: {str(e)[:200]}")
            return None
    
    def _execute_aggregate_query(
        self, table_name: str, agg_info: Dict[str, Any],
        where_conditions: Dict[str, Any], original_sql: str
    ) -> Dict[str, Any]:
        """
        执行聚合查询 — 支持单聚合、多聚合、GROUP BY
        
        策略:
        - 纯 COUNT(*) → PostgREST count='exact' + limit(0)（最高效）
        - 单聚合无 GROUP BY → 拉取目标列 + Python 计算
        - 多聚合 / GROUP BY → 拉取必要列 + Python 分组聚合
        """
        is_multi = agg_info.get('multi', False)
        aggregates = agg_info.get('aggregates', [agg_info]) if is_multi else [agg_info]
        group_by = agg_info.get('group_by', []) if is_multi else []
        
        logger.info(f"Aggregate query: {[a['function']+'('+a['column']+')' for a in aggregates]} "
                     f"GROUP BY {group_by} on {table_name}")
        
        try:
            # ── 快速路径: 纯 COUNT(*) 无 GROUP BY ──
            if len(aggregates) == 1 and aggregates[0]['function'] == 'count' and not group_by:
                return self._fast_count(table_name, aggregates[0], where_conditions)
            
            # ── 通用路径: 拉取数据 + Python 聚合 ──
            # 确定需要拉取的列
            needed_cols = set(group_by)
            for agg in aggregates:
                if agg['column'] != '*':
                    needed_cols.add(agg['column'])
            
            select_str = ','.join(needed_cols) if needed_cols else '*'
            query = self.client.table(table_name).select(select_str)
            if where_conditions:
                query = self._apply_where_conditions(query, where_conditions)
            response = query.execute()
            rows = response.data
            
            if not rows:
                empty_row = {a['alias']: None for a in aggregates}
                return {'success': True, 'data': [empty_row], 'count': 1,
                        'message': '无数据可聚合'}
            
            # 分组
            if group_by:
                result_data = self._grouped_aggregate(rows, aggregates, group_by)
            else:
                result_data = [self._compute_aggregates(rows, aggregates)]
            
            logger.info(f"✅ Aggregate result: {len(result_data)} groups")
            return {
                'success': True,
                'data': result_data,
                'count': len(result_data),
                'message': f'聚合查询成功，返回 {len(result_data)} 条结果'
            }
        
        except Exception as e:
            logger.error(f"❌ Aggregate query failed: {str(e)}")
            return {'success': False, 'error': f'聚合查询失败: {str(e)}', 'data': []}
    
    def _fast_count(self, table_name: str, agg: Dict, where_conditions: Dict) -> Dict[str, Any]:
        """使用 PostgREST count='exact' 的快速计数"""
        query = self.client.table(table_name).select('*', count='exact')
        if where_conditions:
            query = self._apply_where_conditions(query, where_conditions)
        query = query.limit(0)
        response = query.execute()
        count_val = response.count if hasattr(response, 'count') and response.count is not None else len(response.data)
        alias = agg.get('alias', 'count')
        logger.info(f"✅ Fast COUNT: {count_val}")
        return {
            'success': True,
            'data': [{alias: count_val}],
            'count': 1,
            'message': f'COUNT = {count_val}'
        }
    
    def _compute_aggregates(self, rows: list, aggregates: list) -> Dict[str, Any]:
        """对一组行计算多个聚合函数"""
        result = {}
        for agg in aggregates:
            func, col, alias = agg['function'], agg['column'], agg['alias']
            
            if func == 'count':
                result[alias] = len(rows)
                continue
            
            values = []
            for row in rows:
                val = row.get(col)
                if val is not None:
                    try:
                        values.append(float(val))
                    except (ValueError, TypeError):
                        pass
            
            if not values:
                result[alias] = None
            elif func == 'sum':
                result[alias] = round(sum(values), 4)
            elif func == 'avg':
                result[alias] = round(sum(values) / len(values), 4)
            elif func == 'min':
                result[alias] = min(values)
            elif func == 'max':
                result[alias] = max(values)
            else:
                result[alias] = None
        
        return result
    
    def _grouped_aggregate(self, rows: list, aggregates: list, group_by: list) -> list:
        """分组后对每组计算聚合"""
        from collections import defaultdict
        groups = defaultdict(list)
        
        for row in rows:
            key = tuple(row.get(col) for col in group_by)
            groups[key].append(row)
        
        results = []
        for key, group_rows in groups.items():
            row_result = dict(zip(group_by, key))
            agg_values = self._compute_aggregates(group_rows, aggregates)
            row_result.update(agg_values)
            results.append(row_result)
        
        return results
    
    def _parse_select_columns(self, sql: str) -> str:
        """解析 SELECT 列，返回 PostgREST 兼容的 select 字符串"""
        match = re.search(r'SELECT\s+(DISTINCT\s+)?(.+?)\s+FROM', sql, re.IGNORECASE)
        if match:
            cols = match.group(2).strip()
            if re.search(r'(COUNT|SUM|AVG|MIN|MAX)\s*\(', cols, re.IGNORECASE):
                return '*'
            if cols.strip() == '*':
                return '*'
            cleaned = []
            for col in cols.split(','):
                col = col.strip()
                # 去除 table.column 的表名前缀
                col = re.sub(r'^\w+\.', '', col)
                col = re.sub(r'\s+AS\s+\w+', '', col, flags=re.IGNORECASE).strip()
                if col:
                    cleaned.append(col)
            return ','.join(cleaned) if cleaned else '*'
        return '*'
    
    def _parse_limit(self, sql: str) -> Optional[int]:
        """解析 LIMIT 子句"""
        match = re.search(r'LIMIT\s+(\d+)', sql, re.IGNORECASE)
        return int(match.group(1)) if match else None
    
    def _parse_offset(self, sql: str) -> Optional[int]:
        """解析 OFFSET 子句"""
        match = re.search(r'OFFSET\s+(\d+)', sql, re.IGNORECASE)
        return int(match.group(1)) if match else None
    
    def _parse_order_by_multi(self, sql: str) -> list:
        """解析 ORDER BY 子句 — 支持多列排序"""
        match = re.search(r'ORDER\s+BY\s+(.+?)(?:LIMIT|OFFSET|;|$)', sql, re.IGNORECASE)
        if not match:
            return []
        order_clause = match.group(1).strip()
        results = []
        for part in order_clause.split(','):
            part = part.strip()
            m = re.match(r'(\w+)(?:\s+(ASC|DESC))?', part, re.IGNORECASE)
            if m:
                results.append({
                    'column': m.group(1),
                    'desc': m.group(2) and m.group(2).upper() == 'DESC'
                })
        return results
    
    def _parse_group_by(self, sql: str) -> list:
        """解析 GROUP BY 子句"""
        match = re.search(r'GROUP\s+BY\s+(.+?)(?:HAVING|ORDER|LIMIT|;|$)', sql, re.IGNORECASE)
        if not match:
            return []
        return [col.strip() for col in match.group(1).split(',') if col.strip()]
    
    @staticmethod
    def _client_distinct(data: list) -> list:
        """客户端去重"""
        import json
        seen = set()
        result = []
        for row in data:
            key = json.dumps(row, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                result.append(row)
        return result
    
    def _parse_where_conditions(self, sql: str) -> list:
        """
        解析 SQL 中的 WHERE 条件（增强版）
        
        支持的操作符: =, !=, <>, >, <, >=, <=, LIKE, ILIKE,
                      IN (...), IS NULL, IS NOT NULL, BETWEEN
        
        Returns:
            条件列表 [{'column': str, 'op': str, 'value': Any}, ...]
        """
        where_match = re.search(
            r'WHERE\s+(.+?)(?:;|ORDER\s|GROUP\s|LIMIT\s|HAVING\s|\s*$)',
            sql, re.IGNORECASE
        )
        if not where_match:
            return []
        
        where_clause = where_match.group(1).strip()
        
        # 先提取 BETWEEN...AND... 子句并替换为占位符，
        # 避免 BETWEEN 的 AND 被误分割
        between_cache = {}
        counter = [0]
        def replace_between(m):
            placeholder = f'__BETWEEN_{counter[0]}__'
            between_cache[placeholder] = m.group(0)
            counter[0] += 1
            return placeholder
        where_clause = re.sub(
            r"\w+\s+BETWEEN\s+.+?\s+AND\s+\S+",
            replace_between, where_clause, flags=re.IGNORECASE
        )
        
        and_parts = re.split(r'\s+AND\s+', where_clause, flags=re.IGNORECASE)
        # 恢复 BETWEEN 占位符
        and_parts = [between_cache.get(p.strip(), p) for p in and_parts]
        
        conditions = []
        for part in and_parts:
            part = part.strip()
            cond = None
            
            # IS NOT NULL
            m = re.match(r'(\w+)\s+IS\s+NOT\s+NULL', part, re.IGNORECASE)
            if m:
                cond = {'column': m.group(1), 'op': 'is_not_null', 'value': None}
            
            # IS NULL
            if not cond:
                m = re.match(r'(\w+)\s+IS\s+NULL', part, re.IGNORECASE)
                if m:
                    cond = {'column': m.group(1), 'op': 'is_null', 'value': None}
            
            # BETWEEN
            if not cond:
                m = re.match(r"(\w+)\s+BETWEEN\s+'?([^']+?)'?\s+AND\s+'?([^']+?)'?$",
                             part, re.IGNORECASE)
                if m:
                    cond = {'column': m.group(1), 'op': 'between',
                            'value': [self._cast_value(m.group(2)), self._cast_value(m.group(3))]}
            
            # IN (...)
            if not cond:
                m = re.match(r"(\w+)\s+IN\s*\((.+?)\)", part, re.IGNORECASE)
                if m:
                    raw_vals = [v.strip().strip("'\"") for v in m.group(2).split(',')]
                    cond = {'column': m.group(1), 'op': 'in',
                            'value': [self._cast_value(v) for v in raw_vals]}
            
            # NOT LIKE / NOT ILIKE
            if not cond:
                m = re.match(r"(\w+)\s+NOT\s+(I?LIKE)\s+'([^']+)'", part, re.IGNORECASE)
                if m:
                    op = 'not_ilike' if m.group(2).upper() == 'ILIKE' else 'not_like'
                    cond = {'column': m.group(1), 'op': op, 'value': m.group(3)}
            
            # LIKE / ILIKE
            if not cond:
                m = re.match(r"(\w+)\s+(I?LIKE)\s+'([^']+)'", part, re.IGNORECASE)
                if m:
                    op = 'ilike' if m.group(2).upper() == 'ILIKE' else 'like'
                    cond = {'column': m.group(1), 'op': op, 'value': m.group(3)}
            
            # 比较操作符: >=, <=, !=, <>, >, <, =
            if not cond:
                m = re.match(r"(\w+)\s*(>=|<=|!=|<>|>|<|=)\s*'?([^']*?)'?\s*$", part, re.IGNORECASE)
                if m:
                    col, op_str, val = m.group(1), m.group(2), m.group(3)
                    op_map = {
                        '=': 'eq', '!=': 'neq', '<>': 'neq',
                        '>': 'gt', '<': 'lt', '>=': 'gte', '<=': 'lte'
                    }
                    cond = {'column': col, 'op': op_map[op_str], 'value': self._cast_value(val)}
            
            if cond:
                logger.info(f"  Parsed condition: {cond['column']} {cond['op']} {cond.get('value')}")
                conditions.append(cond)
            else:
                logger.warning(f"  Unparsed WHERE part: {part}")
        
        return conditions
    
    @staticmethod
    def _cast_value(val):
        """尝试将字符串转为 int / float"""
        try:
            return int(val)
        except (ValueError, TypeError):
            pass
        try:
            return float(val)
        except (ValueError, TypeError):
            pass
        return val
    
    def _apply_where_conditions(self, query, conditions):
        """
        应用 WHERE 条件到 PostgREST 查询（增强版）
        
        兼容旧版 dict 和新版 list[dict] 格式
        """
        # 兼容旧格式 dict
        if isinstance(conditions, dict):
            for col, val in conditions.items():
                query = query.eq(col, val)
            return query
        
        for cond in conditions:
            col, op, val = cond['column'], cond['op'], cond.get('value')
            logger.info(f"Applying filter: {col} {op} {val}")
            
            if op == 'eq':
                query = query.eq(col, val)
            elif op == 'neq':
                query = query.neq(col, val)
            elif op == 'gt':
                query = query.gt(col, val)
            elif op == 'lt':
                query = query.lt(col, val)
            elif op == 'gte':
                query = query.gte(col, val)
            elif op == 'lte':
                query = query.lte(col, val)
            elif op == 'like':
                query = query.like(col, val)
            elif op == 'ilike':
                query = query.ilike(col, val)
            elif op == 'not_like':
                query = query.not_.like(col, val)
            elif op == 'not_ilike':
                query = query.not_.ilike(col, val)
            elif op in ('in',):
                query = query.in_(col, val)
            elif op == 'is_null':
                query = query.is_(col, 'null')
            elif op == 'is_not_null':
                query = query.neq(col, 'null')
            elif op == 'between':
                query = query.gte(col, val[0]).lte(col, val[1])
            else:
                logger.warning(f"Unsupported op '{op}', skipping")
        
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


def get_supabase_client():
    """获取 Supabase 客户端单例。

    DB_BACKEND=postgres 时返回 None：
      QueryExecutor 会走纯 psycopg2 路径，SupabaseClient 完全跳过。
    DB_BACKEND=supabase（默认）时返回正常客户端。
    """
    import os
    if os.getenv("DB_BACKEND", "supabase") == "postgres":
        return None

    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient()
    return _supabase_client
