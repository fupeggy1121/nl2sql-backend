"""
Pipeline Cache — 两级内存 TTL 缓存

Level 1: 意图缓存 (intent_cache)
  - Key: normalize(user_input)
  - Value: (intent, intent_data)
  - TTL: 300 秒 (5 分钟)
  - 目的: 相同问题重复提问时跳过 LLM 意图识别 (省 ~1 次 LLM 调用)

Level 2: 语义上下文缓存 (semantic_cache)
  - Key: normalize(user_input)
  - Value: semantic_context dict
  - TTL: 300 秒
  - 目的: 跳过本体引擎重建 (本体引擎是纯规则不调 LLM，但可节省 1-5ms)

Level 3: 查询结果缓存 (result_cache)
  - Key: sql_text (stripped + lowercased)
  - Value: query_result dict
  - TTL: 60 秒 (短 TTL，防止缓存过期数据)
  - 目的: 完全相同的 SQL 不重复执行数据库查询

线程安全: 使用 threading.Lock，安全用于 FastAPI 多工作线程场景。
"""

import hashlib
import logging
import re
import threading
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _normalize_key(text: str) -> str:
    """规范化缓存 Key：去除多余空白、转小写、去除标点"""
    text = text.strip().lower()
    # 合并连续空白
    text = re.sub(r'\s+', ' ', text)
    # 去除句尾标点
    text = re.sub(r'[？?！!。\.,$]+$', '', text).strip()
    return text


def _make_hash(key: str) -> str:
    """生成 SHA256 短 hash 用于快速比较（原始 key 也保留）"""
    return hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]


# ─────────────────────────────────────────────── #
# TTLCache                                        #
# ─────────────────────────────────────────────── #

class TTLCache:
    """
    简单线程安全 TTL 字典缓存。

    用法:
        cache = TTLCache(ttl_seconds=300, maxsize=500, name="intent")
        cache.set("你好", value={"intent": "chat"})
        result = cache.get("你好")   # None if expired or missing
        stats = cache.stats()
    """

    def __init__(self, ttl_seconds: float = 300, maxsize: int = 1000, name: str = ""):
        self._ttl = ttl_seconds
        self._maxsize = maxsize
        self._name = name or "unnamed"
        # {normalized_key: (value, expire_timestamp)}
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def _is_expired(self, expire_ts: float) -> bool:
        return time.monotonic() > expire_ts

    def get(self, raw_key: str) -> Optional[Any]:
        """获取缓存值，未命中或已过期返回 None"""
        nk = _normalize_key(raw_key)
        with self._lock:
            entry = self._store.get(nk)
            if entry is None:
                self._misses += 1
                return None
            value, expire_ts = entry
            if self._is_expired(expire_ts):
                del self._store[nk]
                self._misses += 1
                return None
            self._hits += 1
            return value

    def set(self, raw_key: str, value: Any) -> None:
        """写入缓存，超过 maxsize 时随机淘汰 10% 最旧条目"""
        nk = _normalize_key(raw_key)
        expire_ts = time.monotonic() + self._ttl
        with self._lock:
            if len(self._store) >= self._maxsize and nk not in self._store:
                self._evict()
            self._store[nk] = (value, expire_ts)

    def invalidate(self, raw_key: str) -> None:
        """手动删除某条缓存"""
        nk = _normalize_key(raw_key)
        with self._lock:
            self._store.pop(nk, None)

    def clear(self) -> None:
        """清空全部缓存"""
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            return {
                "name": self._name,
                "size": len(self._store),
                "maxsize": self._maxsize,
                "ttl_seconds": self._ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 3),
            }

    def _evict(self) -> None:
        """淘汰已过期条目；若无过期，则淘汰最旧的 10%"""
        now = time.monotonic()
        expired = [k for k, (_, ts) in self._store.items() if ts < now]
        if expired:
            for k in expired:
                del self._store[k]
            return
        # 无过期条目：按过期时间排序，删最旧 10%
        sorted_keys = sorted(self._store.keys(), key=lambda k: self._store[k][1])
        to_remove = max(1, len(sorted_keys) // 10)
        for k in sorted_keys[:to_remove]:
            del self._store[k]


# ─────────────────────────────────────────────── #
# 全局缓存单例                                    #
# ─────────────────────────────────────────────── #

#: 意图识别结果缓存 (intent + intent_data)，TTL 5 分钟
intent_cache = TTLCache(ttl_seconds=300, maxsize=500, name="intent")

#: 语义上下文缓存 (semantic_context dict)，TTL 5 分钟
semantic_cache = TTLCache(ttl_seconds=300, maxsize=500, name="semantic")

#: SQL 执行结果缓存，TTL 60 秒（短 TTL 防数据过时）
result_cache = TTLCache(ttl_seconds=60, maxsize=200, name="result")


def get_cache_stats() -> Dict[str, Any]:
    """返回所有缓存的命中率统计，可挂到监控 API"""
    return {
        "intent": intent_cache.stats(),
        "semantic": semantic_cache.stats(),
        "result": result_cache.stats(),
    }
