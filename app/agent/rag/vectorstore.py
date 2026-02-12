"""
VectorStore — pgvector 向量存储与检索 (Phase D)

封装 Supabase pgvector 的 CRUD 操作:
- upsert_documents: 批量插入/更新文档向量
- search: 向量相似度搜索
- delete_by_type: 按 doc_type 删除
- get_stats: 统计信息
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VectorDocument:
    """待入库的文档"""

    def __init__(
        self,
        content: str,
        doc_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
    ):
        self.content = content
        self.doc_type = doc_type
        self.metadata = metadata or {}
        self.embedding = embedding


class SearchResult:
    """检索结果"""

    def __init__(
        self,
        content: str,
        doc_type: str,
        metadata: Dict[str, Any],
        similarity: float,
    ):
        self.content = content
        self.doc_type = doc_type
        self.metadata = metadata
        self.similarity = similarity

    def __repr__(self):
        return (
            f"SearchResult(type={self.doc_type}, "
            f"sim={self.similarity:.3f}, "
            f"content={self.content[:60]}...)"
        )


class VectorStore:
    """
    pgvector 向量存储

    使用 Supabase client 操作 knowledge_embeddings 表。
    支持 RPC 函数 match_knowledge 进行向量搜索。
    """

    TABLE = "knowledge_embeddings"

    def __init__(self):
        self._client = None
        self._available: Optional[bool] = None

    def _get_client(self):
        """获取 Supabase client（优先使用 service_role key 绕过 RLS）"""
        if self._client is not None:
            return self._client

        try:
            import os

            # 优先使用 service_role key（绕过 RLS）
            service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
            supabase_url = os.getenv("SUPABASE_URL", "")
            if service_key and supabase_url:
                from supabase import create_client
                self._client = create_client(supabase_url, service_key)
                self._available = True
                logger.info("[vectorstore] Using service_role key (RLS bypassed)")
                return self._client

            # 降级到 anon key client
            from app.services.supabase_client import get_supabase_client

            supabase = get_supabase_client()
            if supabase and supabase.client:
                self._client = supabase.client
                self._available = True
                logger.info("[vectorstore] Supabase client ready (anon key)")
            else:
                self._available = False
                logger.warning("[vectorstore] Supabase client not available")
        except Exception as e:
            self._available = False
            logger.error(f"[vectorstore] Init failed: {e}")

        return self._client

    @property
    def is_available(self) -> bool:
        if self._available is None:
            self._get_client()
        return bool(self._available)

    # ── 写入 ──

    def upsert_documents(self, documents: List[VectorDocument]) -> int:
        """
        批量插入文档向量。

        Args:
            documents: VectorDocument 列表，需含 embedding

        Returns:
            成功插入数量
        """
        client = self._get_client()
        if not client:
            logger.warning("[vectorstore] Client not available, skip upsert")
            return 0

        rows = []
        for doc in documents:
            if doc.embedding is None:
                logger.warning(
                    f"[vectorstore] Skip doc without embedding: "
                    f"{doc.content[:40]}..."
                )
                continue
            rows.append({
                "content": doc.content,
                "doc_type": doc.doc_type,
                "metadata": json.dumps(doc.metadata, ensure_ascii=False),
                "embedding": doc.embedding,
                "token_count": len(doc.content) // 2,  # 粗略估算
            })

        if not rows:
            return 0

        try:
            # 分批插入（每批 50 条）
            inserted = 0
            batch_size = 50
            for i in range(0, len(rows), batch_size):
                batch = rows[i: i + batch_size]
                result = (
                    client.table(self.TABLE)
                    .insert(batch)
                    .execute()
                )
                inserted += len(result.data) if result.data else 0

            logger.info(f"[vectorstore] Upserted {inserted}/{len(rows)} documents")
            return inserted

        except Exception as e:
            logger.error(f"[vectorstore] Upsert failed: {e}")
            return 0

    # ── 搜索 ──

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        threshold: float = 0.5,
        doc_type: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        向量相似度搜索。

        Args:
            query_embedding: 查询向量
            top_k: 返回前 K 个结果
            threshold: 最低相似度阈值
            doc_type: 过滤文档类型

        Returns:
            SearchResult 列表，按相似度降序
        """
        client = self._get_client()
        if not client:
            return []

        try:
            # 使用 RPC 函数 match_knowledge
            params = {
                "query_embedding": query_embedding,
                "match_threshold": threshold,
                "match_count": top_k,
            }
            if doc_type:
                params["filter_doc_type"] = doc_type

            result = client.rpc("match_knowledge", params).execute()

            if not result.data:
                return []

            results = []
            for row in result.data:
                metadata = row.get("metadata", {})
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except json.JSONDecodeError:
                        metadata = {}
                results.append(SearchResult(
                    content=row["content"],
                    doc_type=row["doc_type"],
                    metadata=metadata,
                    similarity=row["similarity"],
                ))

            logger.info(
                f"[vectorstore] Search returned {len(results)} results "
                f"(type={doc_type}, threshold={threshold})"
            )
            return results

        except Exception as e:
            logger.error(f"[vectorstore] Search failed: {e}")
            return []

    # ── 删除 ──

    def delete_by_type(self, doc_type: str) -> int:
        """按文档类型删除（用于重新入库前清理）"""
        client = self._get_client()
        if not client:
            return 0

        try:
            result = (
                client.table(self.TABLE)
                .delete()
                .eq("doc_type", doc_type)
                .execute()
            )
            count = len(result.data) if result.data else 0
            logger.info(f"[vectorstore] Deleted {count} docs of type '{doc_type}'")
            return count
        except Exception as e:
            logger.error(f"[vectorstore] Delete failed: {e}")
            return 0

    # ── 统计 ──

    def get_stats(self) -> Dict[str, Any]:
        """获取向量库统计信息"""
        client = self._get_client()
        if not client:
            return {"available": False}

        try:
            # 按 doc_type 统计
            result = (
                client.table(self.TABLE)
                .select("doc_type", count="exact")
                .execute()
            )
            total = result.count if hasattr(result, "count") else 0

            # 分类统计
            type_counts = {}
            if result.data:
                for row in result.data:
                    dt = row.get("doc_type", "unknown")
                    type_counts[dt] = type_counts.get(dt, 0) + 1

            return {
                "available": True,
                "total_documents": total or sum(type_counts.values()),
                "by_type": type_counts,
            }
        except Exception as e:
            logger.error(f"[vectorstore] Stats failed: {e}")
            return {"available": False, "error": str(e)}


# ── 全局单例 ──
_vectorstore: Optional[VectorStore] = None


def get_vectorstore() -> VectorStore:
    """获取全局 VectorStore 实例"""
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = VectorStore()
    return _vectorstore
