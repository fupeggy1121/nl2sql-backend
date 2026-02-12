"""
RAG Tools — 向量检索工具 (Phase D)

提供 LangChain @tool 封装:
- rag_search: 向量相似度搜索，返回最相关的文档片段
- rag_search_schema: 专门搜索 schema 文档
- rag_search_sql_examples: 搜索历史 SQL 案例（few-shot）

这些 Tool 被 query_planner 和 sql_generator 节点调用，
替代原来全量加载 schema 的方式，改为按需 RAG 检索。
"""

import logging
from typing import List, Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# 延迟初始化
_embedding_service = None
_vectorstore = None


def _get_services():
    """延迟初始化 embedding + vectorstore"""
    global _embedding_service, _vectorstore
    if _embedding_service is None:
        from app.agent.rag.embeddings import get_embedding_service
        _embedding_service = get_embedding_service()
    if _vectorstore is None:
        from app.agent.rag.vectorstore import get_vectorstore
        _vectorstore = get_vectorstore()
    return _embedding_service, _vectorstore


def _rag_available() -> bool:
    """检查 RAG 服务是否可用"""
    emb, vs = _get_services()
    return emb.is_available and vs.is_available


@tool
def rag_search(query: str, doc_type: str = "", top_k: int = 5) -> str:
    """Search the knowledge base for relevant documents using vector similarity.
    Use this to find schema info, synonyms, SQL examples, or business rules.
    Args:
        query: The search query in natural language
        doc_type: Optional filter: 'schema', 'synonym', 'sql_example', 'business_rule'
        top_k: Maximum number of results to return (default 5)
    Returns:
        Concatenated relevant document texts, or fallback message if RAG unavailable.
    """
    if not _rag_available():
        logger.info("[rag_tools] RAG not available, falling back to schema_tools")
        return _fallback_search(query)

    emb_service, vectorstore = _get_services()

    # 向量化查询
    query_vec = emb_service.embed_text(query)
    if query_vec is None:
        logger.warning("[rag_tools] Failed to embed query, using fallback")
        return _fallback_search(query)

    # 搜索
    doc_type_filter = doc_type if doc_type else None
    results = vectorstore.search(
        query_embedding=query_vec,
        top_k=top_k,
        threshold=0.4,
        doc_type=doc_type_filter,
    )

    if not results:
        logger.info(f"[rag_tools] No results for: {query[:60]}...")
        return _fallback_search(query)

    # 格式化结果
    parts = []
    for r in results:
        parts.append(
            f"[{r.doc_type}] (相似度: {r.similarity:.2f})\n{r.content}"
        )

    context = "\n\n---\n\n".join(parts)
    logger.info(
        f"[rag_tools] Found {len(results)} results "
        f"(query: {query[:40]}..., type={doc_type_filter})"
    )
    return context


@tool
def rag_search_schema(query: str, top_k: int = 3) -> str:
    """Search specifically for database schema information.
    Returns table definitions, column descriptions, and data types
    relevant to the user's query. Use this to understand what tables
    and columns are available for SQL generation.
    """
    return rag_search.invoke({
        "query": query,
        "doc_type": "schema",
        "top_k": top_k,
    })


@tool
def rag_search_sql_examples(query: str, top_k: int = 3) -> str:
    """Search for similar historical SQL queries as few-shot examples.
    Returns past user questions and the SQL that was successfully generated.
    Use this to find reference SQL patterns for similar queries.
    """
    return rag_search.invoke({
        "query": query,
        "doc_type": "sql_example",
        "top_k": top_k,
    })


def _fallback_search(query: str) -> str:
    """
    RAG 不可用时的降级方案：
    使用现有的 schema_tools.get_schema_context 做关键词匹配。
    """
    try:
        from app.agent.tools.schema_tools import get_schema_context
        return get_schema_context.invoke({"user_input": query})
    except Exception as e:
        logger.error(f"[rag_tools] Fallback search failed: {e}")
        return "Schema context not available."
