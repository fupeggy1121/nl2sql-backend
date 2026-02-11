"""
查询结果缓存服务
基于 SQL 指纹的内存缓存，避免重复查询
支持 TTL 过期和 LRU 淘汰
"""
import hashlib
import logging
import time
import threading
from typing import Dict, Any, Optional
from collections import OrderedDict

logger = logging.getLogger(__name__)


class QueryCache:
    """
    SQL 查询结果缓存
    
    特性:
    - 基于 SQL 指纹（去除空白/大小写差异）做 key
    - TTL 过期自动失效
    - LRU 淘汰策略，防止内存溢出
    - 线程安全
    """
    
    def __init__(self, max_size: int = 200, default_ttl: int = 300):
        """
        Args:
            max_size: 最大缓存条目数
            default_ttl: 默认过期时间（秒），默认 5 分钟
        """
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._stats = {'hits': 0, 'misses': 0, 'evictions': 0}
    
    @staticmethod
    def _normalize_sql(sql: str) -> str:
        """标准化 SQL 用于指纹计算 — 去除多余空白和分号，转小写"""
        import re
        normalized = re.sub(r'\s+', ' ', sql.strip().rstrip(';')).lower()
        return normalized
    
    @staticmethod
    def _sql_fingerprint(sql: str) -> str:
        """计算 SQL 指纹"""
        normalized = QueryCache._normalize_sql(sql)
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    
    def get(self, sql: str) -> Optional[Dict[str, Any]]:
        """
        从缓存获取查询结果
        
        Args:
            sql: SQL 查询语句
            
        Returns:
            缓存的查询结果或 None（未命中/过期）
        """
        key = self._sql_fingerprint(sql)
        
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats['misses'] += 1
                return None
            
            # 检查 TTL
            if time.time() > entry['expires_at']:
                del self._cache[key]
                self._stats['misses'] += 1
                logger.debug(f"Cache expired for SQL: {sql[:60]}...")
                return None
            
            # LRU: 移到末尾（最近使用）
            self._cache.move_to_end(key)
            self._stats['hits'] += 1
            
            elapsed = time.time() - entry['cached_at']
            logger.info(f"✅ Cache HIT (age={elapsed:.1f}s): {sql[:60]}...")
            return entry['result']
    
    def set(self, sql: str, result: Dict[str, Any], ttl: Optional[int] = None):
        """
        缓存查询结果
        
        Args:
            sql: SQL 查询语句
            result: 查询结果字典
            ttl: 自定义过期时间（秒），None 使用默认值
        """
        # 不缓存失败结果
        if not result.get('success', False):
            return
        
        key = self._sql_fingerprint(sql)
        ttl = ttl if ttl is not None else self._determine_ttl(sql, result)
        
        with self._lock:
            # LRU 淘汰
            while len(self._cache) >= self.max_size:
                evicted_key, _ = self._cache.popitem(last=False)
                self._stats['evictions'] += 1
                logger.debug(f"Cache evicted entry (LRU)")
            
            self._cache[key] = {
                'result': result,
                'cached_at': time.time(),
                'expires_at': time.time() + ttl,
                'sql': sql[:200]  # 保存截断的 SQL 用于调试
            }
            logger.info(f"📦 Cached (TTL={ttl}s, size={len(self._cache)}): {sql[:60]}...")
    
    def _determine_ttl(self, sql: str, result: Dict[str, Any]) -> int:
        """
        根据查询类型自动决定 TTL
        
        - 聚合查询 (COUNT/SUM/AVG) → 较长 TTL (10 分钟)
        - 大结果集 (>100 rows) → 较长 TTL (5 分钟)
        - 小结果集简单查询 → 较短 TTL (2 分钟)
        - 写操作相关 → 不缓存 (返回0)
        """
        import re
        sql_upper = sql.upper().strip()
        
        # 写操作不缓存
        if any(sql_upper.startswith(kw) for kw in ['INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP']):
            return 0
        
        # 聚合查询 — 计算成本高，缓存更久
        if re.search(r'\b(COUNT|SUM|AVG|MIN|MAX|GROUP\s+BY)\b', sql_upper):
            return 600  # 10 分钟
        
        # 大结果集
        row_count = result.get('count', 0)
        if row_count > 100:
            return 300  # 5 分钟
        
        # 默认
        return 120  # 2 分钟
    
    def invalidate(self, sql: Optional[str] = None, table_name: Optional[str] = None):
        """
        使缓存失效
        
        Args:
            sql: 精确 SQL 失效
            table_name: 使涉及该表的所有缓存失效
        """
        with self._lock:
            if sql:
                key = self._sql_fingerprint(sql)
                if key in self._cache:
                    del self._cache[key]
                    logger.info(f"Cache invalidated for SQL: {sql[:60]}...")
            elif table_name:
                keys_to_remove = [
                    k for k, v in self._cache.items()
                    if table_name.lower() in v.get('sql', '').lower()
                ]
                for k in keys_to_remove:
                    del self._cache[k]
                logger.info(f"Cache invalidated {len(keys_to_remove)} entries for table: {table_name}")
    
    def clear(self):
        """清空所有缓存"""
        with self._lock:
            size = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared ({size} entries)")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self._lock:
            total = self._stats['hits'] + self._stats['misses']
            hit_rate = (self._stats['hits'] / total * 100) if total > 0 else 0
            return {
                **self._stats,
                'size': len(self._cache),
                'max_size': self.max_size,
                'hit_rate': round(hit_rate, 1),
                'total_requests': total
            }


# 全局单例
_query_cache: Optional[QueryCache] = None


def get_query_cache() -> QueryCache:
    """获取全局查询缓存实例"""
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache(max_size=200, default_ttl=300)
    return _query_cache
