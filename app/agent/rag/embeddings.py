"""
Embeddings — 文本向量化服务 (Phase D)

支持:
1. OpenAI 兼容 API（OpenAI text-embedding-3-small）
2. 批量向量化
3. 缓存避免重复计算
4. 本地哈希 fallback（当 API 不可用时，生成确定性伪向量）

优先级: OpenAI API → 本地哈希 fallback
"""

import hashlib
import logging
import math
import os
import struct
from functools import lru_cache
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── 配置 ──
EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 维
EMBEDDING_DIM = 1536
MAX_BATCH_SIZE = 100                        # OpenAI 批量限制


# ── 本地哈希 embedding fallback ──
def _hash_embed(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """
    基于 SHA-256 的确定性伪嵌入。

    原理: 对文本做多轮 SHA-256 哈希，将每 4 字节解析为 float32，
    然后 L2 归一化。相同文本 → 相同向量，语义理解有限但可跑通流程。
    """
    # 对文本做中文分词级别的 n-gram 增强
    # 简单处理：使用 2-gram 字符组合 + 原始文本
    text_lower = text.strip().lower()

    # 用多轮哈希填充向量
    raw_floats = []
    seed = text_lower.encode("utf-8")
    i = 0
    while len(raw_floats) < dim:
        h = hashlib.sha256(seed + i.to_bytes(4, "big")).digest()
        # 每个 sha256 产出 32 字节 = 8 个 float32
        for offset in range(0, 32, 4):
            if len(raw_floats) >= dim:
                break
            # 解析为 float 并归一化到 [-1, 1]
            val = struct.unpack("!I", h[offset:offset + 4])[0]
            raw_floats.append((val / 2147483648.0) - 1.0)
        i += 1

    # L2 归一化
    norm = math.sqrt(sum(x * x for x in raw_floats))
    if norm > 0:
        raw_floats = [x / norm for x in raw_floats]

    return raw_floats


class EmbeddingService:
    """
    文本向量化服务

    优先使用 OpenAI embedding API，
    如果不可用则 fallback 到本地哈希伪嵌入（可跑通流程，语义有限）。
    """

    def __init__(self):
        self._client = None
        self._api_available: Optional[bool] = None  # API 是否可用
        self._use_fallback = False                   # 是否已降级到 hash
        self._cache: dict = {}  # 简单内存缓存

    @property
    def is_available(self) -> bool:
        """embedding 服务始终可用（有 API 用 API，否则用 hash fallback）"""

    @property
    def has_real_embeddings(self) -> bool:
        """
        仅当真正的 OpenAI embedding API 可用时返回 True。
        hash fallback 不具备语义，不应用于相似度匹配（会产生误命中）。
        """
        if self._use_fallback:
            return False
        if self._api_available is False:
            return False
        if self._api_available is None:
            # 尚未尝试 — 触发一次初始化
            client = self._get_client()
            return client is not None
        return True
        return True

    @property
    def using_fallback(self) -> bool:
        return self._use_fallback

        return self._use_fallback

    def _get_client(self):
        """延迟初始化 OpenAI client，如无可用 API key 则返回 None"""
        if self._client is not None:
            return self._client
        if self._use_fallback:
            return None

        try:
            from openai import OpenAI

            api_key = os.getenv("OPENAI_API_KEY", "")

            # 仅使用真正的 OpenAI key（DeepSeek 不支持 /embeddings）
            if not api_key or api_key == "your_openai_api_key":
                logger.warning(
                    "[embeddings] OPENAI_API_KEY not set or placeholder — "
                    "using local hash fallback"
                )
                self._use_fallback = True
                return None

            self._client = OpenAI(api_key=api_key)
            logger.info("[embeddings] OpenAI client initialized")
            return self._client

        except Exception as e:
            logger.error(f"[embeddings] Failed to init client: {e}")
            self._use_fallback = True
            return None

    def embed_text(self, text: str) -> Optional[List[float]]:
        """
        将单个文本向量化。

        Args:
            text: 要向量化的文本

        Returns:
            1536 维浮点向量，失败返回 None
        """
        # 缓存检查
        cache_key = hashlib.md5(text.encode("utf-8")).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        client = self._get_client()
        if not client:
            # 使用本地 hash fallback
            vector = _hash_embed(text)
            self._cache[cache_key] = vector
            return vector

        try:
            # 文本预处理：截断过长文本
            truncated = text[:8000]  # ~2000 tokens

            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=truncated,
            )
            vector = response.data[0].embedding

            # 缓存
            self._cache[cache_key] = vector
            return vector

        except Exception as e:
            logger.warning(f"[embeddings] API failed, using hash fallback: {e}")
            self._use_fallback = True
            vector = _hash_embed(text)
            self._cache[cache_key] = vector
            return vector

    def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        批量向量化。

        Args:
            texts: 文本列表

        Returns:
            向量列表（与输入等长），失败的位置为 None
        """
        if not texts:
            return []

        results: List[Optional[List[float]]] = [None] * len(texts)

        # 先从缓存中获取已有的
        uncached_indices = []
        uncached_texts = []
        for i, text in enumerate(texts):
            cache_key = hashlib.md5(text.encode("utf-8")).hexdigest()
            if cache_key in self._cache:
                results[i] = self._cache[cache_key]
            else:
                uncached_indices.append(i)
                uncached_texts.append(text[:8000])

        if not uncached_texts:
            return results

        client = self._get_client()

        # ── fallback 模式: 全部使用 hash embedding ──
        if not client:
            logger.info(
                f"[embeddings] Using hash fallback for {len(uncached_texts)} texts"
            )
            for j, text in enumerate(uncached_texts):
                idx = uncached_indices[j]
                vector = _hash_embed(text)
                results[idx] = vector
                cache_key = hashlib.md5(
                    texts[idx].encode("utf-8")
                ).hexdigest()
                self._cache[cache_key] = vector
            return results

        # ── API 模式: 分批调用 OpenAI ──
        for batch_start in range(0, len(uncached_texts), MAX_BATCH_SIZE):
            batch_end = min(batch_start + MAX_BATCH_SIZE, len(uncached_texts))
            batch = uncached_texts[batch_start:batch_end]
            batch_indices = uncached_indices[batch_start:batch_end]

            try:
                response = client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=batch,
                )
                for j, emb_data in enumerate(response.data):
                    idx = batch_indices[j]
                    vector = emb_data.embedding
                    results[idx] = vector
                    cache_key = hashlib.md5(
                        texts[idx].encode("utf-8")
                    ).hexdigest()
                    self._cache[cache_key] = vector

                logger.info(
                    f"[embeddings] Batch {batch_start}-{batch_end}: "
                    f"{len(batch)} texts embedded via API"
                )

            except Exception as e:
                logger.warning(
                    f"[embeddings] API batch {batch_start}-{batch_end} failed, "
                    f"falling back to hash: {e}"
                )
                self._use_fallback = True
                # Fallback 当前批次
                for j, text in enumerate(batch):
                    idx = batch_indices[j]
                    if results[idx] is None:
                        vector = _hash_embed(text)
                        results[idx] = vector
                        cache_key = hashlib.md5(
                            texts[idx].encode("utf-8")
                        ).hexdigest()
                        self._cache[cache_key] = vector

        return results

    @property
    def dimension(self) -> int:
        return EMBEDDING_DIM

    def clear_cache(self):
        self._cache.clear()


# ── 全局单例 ──
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """获取全局 EmbeddingService 实例"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
