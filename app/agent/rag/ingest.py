"""
Knowledge Ingest — 知识库入库脚本 (Phase D)

从现有数据源构建 RAG 知识库:
1. schema_table_annotations → 表描述文档
2. schema_column_annotations → 列描述文档
3. synonym_mappings / table_synonyms → 业务术语文档
4. SQL 示例 → SQL 案例文档（可选，从 agent_interactions 提取）

支持:
- 全量重建（--rebuild）
- 增量更新（默认）
- 干跑模式（--dry-run）

用法:
    python -m app.agent.rag.ingest [--rebuild] [--dry-run]
"""

import argparse
import logging
import sys
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# 文档类型常量
DOC_TYPE_SCHEMA = "schema"          # 表+列描述
DOC_TYPE_SYNONYM = "synonym"        # 同义词/业务术语
DOC_TYPE_SQL_EXAMPLE = "sql_example"  # 历史 SQL 案例
DOC_TYPE_BUSINESS = "business_rule"   # 业务规则


class KnowledgeIngestor:
    """知识入库引擎"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._embedding_service = None
        self._vectorstore = None
        self._stats = {
            "schema_docs": 0,
            "synonym_docs": 0,
            "sql_example_docs": 0,
            "total_embedded": 0,
            "errors": 0,
        }

    @property
    def embedding_service(self):
        if self._embedding_service is None:
            from app.agent.rag.embeddings import get_embedding_service
            self._embedding_service = get_embedding_service()
        return self._embedding_service

    @property
    def vectorstore(self):
        if self._vectorstore is None:
            from app.agent.rag.vectorstore import get_vectorstore
            self._vectorstore = get_vectorstore()
        return self._vectorstore

    # ── 入口 ──

    def run(self, rebuild: bool = False):
        """执行知识入库"""
        logger.info("=" * 60)
        logger.info("Knowledge Ingest — Phase D")
        logger.info(f"  rebuild={rebuild}, dry_run={self.dry_run}")
        logger.info("=" * 60)

        start = time.time()

        # 检查服务可用性
        if not self.dry_run:
            if not self.embedding_service.is_available:
                logger.error("Embedding service not available. Check API keys.")
                return
            if not self.vectorstore.is_available:
                logger.error("VectorStore not available. Check Supabase connection.")
                return

        # 如果 rebuild，先清理
        if rebuild and not self.dry_run:
            logger.info("Rebuilding: clearing existing documents...")
            self.vectorstore.delete_by_type(DOC_TYPE_SCHEMA)
            self.vectorstore.delete_by_type(DOC_TYPE_SYNONYM)
            self.vectorstore.delete_by_type(DOC_TYPE_SQL_EXAMPLE)

        # 1. Schema annotations
        self._ingest_schema_annotations()

        # 2. Synonyms
        self._ingest_synonyms()

        # 3. SQL examples (from agent_interactions if available)
        self._ingest_sql_examples()

        elapsed = time.time() - start
        logger.info("=" * 60)
        logger.info(f"Ingest complete in {elapsed:.1f}s")
        logger.info(f"  Schema docs:      {self._stats['schema_docs']}")
        logger.info(f"  Synonym docs:     {self._stats['synonym_docs']}")
        logger.info(f"  SQL example docs: {self._stats['sql_example_docs']}")
        logger.info(f"  Total embedded:   {self._stats['total_embedded']}")
        logger.info(f"  Errors:           {self._stats['errors']}")
        logger.info("=" * 60)

    # ── Schema 入库 ──

    def _ingest_schema_annotations(self):
        """从 Supabase 加载 schema annotations 并入库"""
        logger.info("[ingest] Loading schema annotations...")

        try:
            from app.services.nl2sql_enhanced import get_enhanced_nl2sql_converter
            converter = get_enhanced_nl2sql_converter()
            metadata = converter.annotation_metadata

            tables = metadata.get("tables", {})
            columns = metadata.get("columns", {})

            if not tables:
                logger.warning("[ingest] No table annotations found")
                return

            # 为每个表生成一个文档（包含表描述 + 所有列信息）
            documents = []
            for table_name, tinfo in tables.items():
                doc_text = self._build_table_document(
                    table_name, tinfo, columns
                )
                documents.append({
                    "content": doc_text,
                    "doc_type": DOC_TYPE_SCHEMA,
                    "metadata": {
                        "table_name": table_name,
                        "name_cn": tinfo.get("name_cn", ""),
                        "source": "schema_annotations",
                    },
                })

            logger.info(f"[ingest] Built {len(documents)} schema documents")
            self._embed_and_store(documents)
            self._stats["schema_docs"] = len(documents)

        except Exception as e:
            logger.error(f"[ingest] Schema ingest failed: {e}")
            self._stats["errors"] += 1

    def _build_table_document(
        self,
        table_name: str,
        tinfo: Dict[str, Any],
        columns: Dict[str, Any],
    ) -> str:
        """构建单个表的文档文本"""
        cn_name = tinfo.get("name_cn", "")
        desc = tinfo.get("description_cn", "")
        biz = tinfo.get("business_meaning", "")
        use_case = tinfo.get("use_case", "")

        parts = [f"表名: {table_name}"]
        if cn_name:
            parts.append(f"中文名: {cn_name}")
        if desc:
            parts.append(f"描述: {desc}")
        if biz:
            parts.append(f"业务含义: {biz}")
        if use_case:
            parts.append(f"使用场景: {use_case}")

        # 列信息
        table_cols = [
            col for col in columns.values()
            if col.get("table_name") == table_name
        ]
        if table_cols:
            parts.append(f"\n列 ({len(table_cols)} 个):")
            for col in table_cols:
                col_name = col.get("column_name", "")
                col_cn = col.get("column_name_cn", "")
                col_type = col.get("data_type", "")
                col_desc = col.get("description_cn", "")
                example = col.get("example_value", "")

                line = f"  - {col_name}"
                if col_cn:
                    line += f" ({col_cn})"
                if col_type:
                    line += f": {col_type}"
                if col_desc:
                    line += f" — {col_desc}"
                if example:
                    line += f" [示例: {example}]"
                parts.append(line)

        return "\n".join(parts)

    # ── 同义词入库 ──

    def _ingest_synonyms(self):
        """从 Supabase 和静态配置加载同义词"""
        logger.info("[ingest] Loading synonyms...")

        documents = []

        # 1. 从 Supabase table_synonyms 加载
        try:
            from app.services.supabase_client import get_supabase_client
            supabase = get_supabase_client()
            if supabase and supabase.client:
                result = (
                    supabase.client.table("table_synonyms")
                    .select("table_name, synonym")
                    .eq("is_active", True)
                    .execute()
                )
                if result.data:
                    # 按表名分组
                    groups: Dict[str, List[str]] = {}
                    for row in result.data:
                        tn = row.get("table_name", "")
                        syn = row.get("synonym", "")
                        if tn and syn:
                            groups.setdefault(tn, []).append(syn)

                    for tn, syns in groups.items():
                        doc_text = (
                            f"表名: {tn}\n"
                            f"同义词/别名: {', '.join(syns)}\n"
                            f"当用户提到 {' 或 '.join(syns)} 时，"
                            f"指的是数据库表 {tn}"
                        )
                        documents.append({
                            "content": doc_text,
                            "doc_type": DOC_TYPE_SYNONYM,
                            "metadata": {
                                "table_name": tn,
                                "synonyms": syns,
                                "source": "supabase",
                            },
                        })
                    logger.info(
                        f"[ingest] Loaded {len(documents)} synonym groups from Supabase"
                    )
        except Exception as e:
            logger.warning(f"[ingest] Supabase synonyms load failed: {e}")

        # 2. 从静态配置补充
        try:
            from app.config.table_synonyms import TABLE_SYNONYMS
            for tn, syns in TABLE_SYNONYMS.items():
                # 避免重复
                existing_tables = {
                    d["metadata"]["table_name"] for d in documents
                }
                if tn not in existing_tables:
                    doc_text = (
                        f"表名: {tn}\n"
                        f"同义词/别名: {', '.join(syns)}\n"
                        f"当用户提到 {' 或 '.join(syns)} 时，"
                        f"指的是数据库表 {tn}"
                    )
                    documents.append({
                        "content": doc_text,
                        "doc_type": DOC_TYPE_SYNONYM,
                        "metadata": {
                            "table_name": tn,
                            "synonyms": list(syns),
                            "source": "static_config",
                        },
                    })
        except Exception as e:
            logger.warning(f"[ingest] Static synonyms load failed: {e}")

        if documents:
            self._embed_and_store(documents)
        self._stats["synonym_docs"] = len(documents)

    # ── SQL 案例入库 ──

    def _ingest_sql_examples(self):
        """从 agent_interactions 表提取成功的 SQL 案例"""
        logger.info("[ingest] Loading SQL examples...")

        documents = []
        try:
            from app.services.supabase_client import get_supabase_client
            supabase = get_supabase_client()
            if supabase and supabase.client:
                result = (
                    supabase.client.table("agent_interactions")
                    .select("user_input, generated_sql, intent, result_summary")
                    .eq("success", True)
                    .not_.is_("generated_sql", "null")
                    .order("created_at", desc=True)
                    .limit(100)  # 最近 100 条成功案例
                    .execute()
                )
                if result.data:
                    for row in result.data:
                        user_input = row.get("user_input", "")
                        sql = row.get("generated_sql", "")
                        if not user_input or not sql:
                            continue
                        doc_text = (
                            f"用户问题: {user_input}\n"
                            f"生成 SQL: {sql}\n"
                            f"意图: {row.get('intent', '')}\n"
                            f"结果: {row.get('result_summary', '')}"
                        )
                        documents.append({
                            "content": doc_text,
                            "doc_type": DOC_TYPE_SQL_EXAMPLE,
                            "metadata": {
                                "user_input": user_input[:200],
                                "intent": row.get("intent", ""),
                                "source": "agent_interactions",
                            },
                        })
                    logger.info(
                        f"[ingest] Loaded {len(documents)} SQL examples"
                    )
        except Exception as e:
            # agent_interactions 表可能还不存在
            logger.info(f"[ingest] SQL examples not available: {e}")

        if documents:
            self._embed_and_store(documents)
        self._stats["sql_example_docs"] = len(documents)

    # ── 向量化 & 存储 ──

    def _embed_and_store(self, documents: List[Dict[str, Any]]):
        """批量向量化并存储"""
        if self.dry_run:
            logger.info(f"[ingest] [DRY RUN] Would embed & store {len(documents)} docs")
            return

        from app.agent.rag.vectorstore import VectorDocument

        # 批量 embedding
        texts = [d["content"] for d in documents]
        embeddings = self.embedding_service.embed_batch(texts)

        # 构建 VectorDocument
        vec_docs = []
        for doc, emb in zip(documents, embeddings):
            if emb is None:
                logger.warning(
                    f"[ingest] Embedding failed: {doc['content'][:40]}..."
                )
                self._stats["errors"] += 1
                continue
            vec_docs.append(VectorDocument(
                content=doc["content"],
                doc_type=doc["doc_type"],
                metadata=doc["metadata"],
                embedding=emb,
            ))

        if vec_docs:
            count = self.vectorstore.upsert_documents(vec_docs)
            self._stats["total_embedded"] += count
            logger.info(f"[ingest] Stored {count} documents")


# ── CLI 入口 ──

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="RAG Knowledge Ingest (Phase D)")
    parser.add_argument(
        "--rebuild", action="store_true",
        help="Clear existing documents and rebuild from scratch",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview what would be ingested without actually writing",
    )
    args = parser.parse_args()

    ingestor = KnowledgeIngestor(dry_run=args.dry_run)
    ingestor.run(rebuild=args.rebuild)


if __name__ == "__main__":
    main()
