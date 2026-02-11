"""
同义词管理服务层
提供数据库持久化 + 内存缓存的同义词 CRUD 操作，
以及查询反馈记录和候选同义词推荐功能。
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class SynonymManagerService:
    """同义词管理服务 - 支持数据库 + 静态配置双源"""

    def __init__(self):
        self._cache: Optional[Dict[str, str]] = None
        self._table_cache: Optional[Dict[str, List[str]]] = None

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _get_executor(self):
        """获取 PostgreSQL 执行器 (短连接)"""
        from app.services.postgresql_executor import PostgreSQLExecutor
        executor = PostgreSQLExecutor()
        if not executor.connect():
            raise ConnectionError("无法连接数据库")
        return executor

    def _invalidate_cache(self):
        """清空缓存，下次调用时重建"""
        self._cache = None
        self._table_cache = None
        # 同时清空原有静态模块缓存
        import app.config.table_synonyms as ts
        ts._SYNONYM_TO_TABLE_CACHE = None

    # ------------------------------------------------------------------
    # 查询 / 读取
    # ------------------------------------------------------------------
    def get_all_synonyms(self, table_name: Optional[str] = None,
                         source: Optional[str] = None,
                         is_active: Optional[bool] = True) -> List[Dict]:
        """
        获取同义词列表，支持按表名、来源、状态筛选。
        优先查数据库；数据库不可用时回退到静态配置。
        """
        try:
            executor = self._get_executor()
            conditions = []
            params = []

            if table_name:
                conditions.append("table_name = %s")
                params.append(table_name)
            if source:
                conditions.append("source = %s")
                params.append(source)
            if is_active is not None:
                conditions.append("is_active = %s")
                params.append(is_active)

            where = " WHERE " + " AND ".join(conditions) if conditions else ""
            rows = executor.execute_query(
                f"SELECT id, table_name, synonym, source, is_active, created_at, updated_at, created_by "
                f"FROM table_synonyms{where} ORDER BY table_name, synonym",
                tuple(params) if params else None
            )
            executor.close()

            return [
                {
                    "id": r[0], "table_name": r[1], "synonym": r[2],
                    "source": r[3], "is_active": r[4],
                    "created_at": r[5].isoformat() if r[5] else None,
                    "updated_at": r[6].isoformat() if r[6] else None,
                    "created_by": r[7],
                }
                for r in (rows or [])
            ]
        except Exception as e:
            logger.warning(f"数据库查询失败，回退到静态配置: {e}")
            return self._fallback_get_all(table_name)

    def _fallback_get_all(self, table_name: Optional[str] = None) -> List[Dict]:
        from app.config.table_synonyms import TABLE_SYNONYMS
        results = []
        for tbl, syns in TABLE_SYNONYMS.items():
            if table_name and tbl != table_name:
                continue
            for syn in syns:
                results.append({
                    "id": None, "table_name": tbl, "synonym": syn,
                    "source": "builtin", "is_active": True,
                    "created_at": None, "updated_at": None, "created_by": "system",
                })
        return results

    def get_synonym_map(self) -> Dict[str, str]:
        """获取 {同义词 -> 表名} 的完整映射 (带缓存)"""
        if self._cache is not None:
            return self._cache

        try:
            executor = self._get_executor()
            rows = executor.execute_query(
                "SELECT synonym, table_name FROM table_synonyms WHERE is_active = TRUE"
            )
            executor.close()
            self._cache = {r[0].lower(): r[1] for r in (rows or [])}
        except Exception:
            from app.config.table_synonyms import get_synonym_to_table_map
            self._cache = get_synonym_to_table_map()

        return self._cache

    def map_table_name(self, keyword: str) -> str:
        """将关键词映射到实际表名"""
        m = self.get_synonym_map()
        return m.get(keyword.lower().strip(), keyword)

    def get_tables_summary(self) -> List[Dict]:
        """获取每张表的同义词统计摘要"""
        try:
            executor = self._get_executor()
            rows = executor.execute_query(
                """SELECT table_name, 
                          COUNT(*) as total,
                          COUNT(*) FILTER (WHERE is_active) as active,
                          COUNT(*) FILTER (WHERE source = 'manual') as manual,
                          COUNT(*) FILTER (WHERE source = 'auto') as auto,
                          COUNT(*) FILTER (WHERE source = 'builtin') as builtin
                   FROM table_synonyms
                   GROUP BY table_name ORDER BY table_name"""
            )
            executor.close()
            return [
                {"table_name": r[0], "total": r[1], "active": r[2],
                 "manual": r[3], "auto": r[4], "builtin": r[5]}
                for r in (rows or [])
            ]
        except Exception as e:
            logger.error(f"获取摘要失败: {e}")
            return []

    # ------------------------------------------------------------------
    # 创建 / 更新 / 删除
    # ------------------------------------------------------------------
    def add_synonym(self, table_name: str, synonym: str,
                    source: str = 'manual', created_by: str = 'admin') -> Dict:
        """添加一条同义词映射"""
        executor = self._get_executor()
        try:
            executor.execute_query(
                """INSERT INTO table_synonyms (table_name, synonym, source, created_by)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (table_name, synonym) DO UPDATE
                   SET is_active = TRUE, updated_at = NOW(), source = EXCLUDED.source""",
                (table_name, synonym.lower().strip(), source, created_by)
            )
            self._log_audit(executor, 'add', table_name, synonym, created_by)
            self._invalidate_cache()
            executor.close()
            return {"success": True, "table_name": table_name, "synonym": synonym}
        except Exception as e:
            executor.close()
            raise e

    def add_synonyms_batch(self, table_name: str, synonyms: List[str],
                           source: str = 'manual', created_by: str = 'admin') -> Dict:
        """批量添加同义词"""
        added = []
        errors = []
        for syn in synonyms:
            try:
                self.add_synonym(table_name, syn, source, created_by)
                added.append(syn)
            except Exception as e:
                errors.append({"synonym": syn, "error": str(e)})
        return {"added": added, "errors": errors}

    def update_synonym(self, synonym_id: int, **kwargs) -> Dict:
        """更新同义词属性 (table_name / synonym / is_active)"""
        allowed = {'table_name', 'synonym', 'is_active'}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return {"success": False, "error": "无有效字段"}

        sets = ", ".join(f"{k} = %s" for k in updates)
        vals = list(updates.values()) + [synonym_id]

        executor = self._get_executor()
        executor.execute_query(
            f"UPDATE table_synonyms SET {sets}, updated_at = NOW() WHERE id = %s",
            tuple(vals)
        )
        self._log_audit(executor, 'update', kwargs.get('table_name', ''),
                        kwargs.get('synonym', ''), 'admin',
                        details={"id": synonym_id, "changes": updates})
        self._invalidate_cache()
        executor.close()
        return {"success": True, "id": synonym_id, "updates": updates}

    def delete_synonym(self, synonym_id: int) -> Dict:
        """删除同义词 (软删除 - 设为 inactive)"""
        executor = self._get_executor()
        # 先查询信息用于审计
        rows = executor.execute_query(
            "SELECT table_name, synonym FROM table_synonyms WHERE id = %s",
            (synonym_id,)
        )
        if not rows:
            executor.close()
            return {"success": False, "error": "未找到该同义词"}

        executor.execute_query(
            "UPDATE table_synonyms SET is_active = FALSE, updated_at = NOW() WHERE id = %s",
            (synonym_id,)
        )
        self._log_audit(executor, 'delete', rows[0][0], rows[0][1], 'admin')
        self._invalidate_cache()
        executor.close()
        return {"success": True, "id": synonym_id}

    def hard_delete_synonym(self, synonym_id: int) -> Dict:
        """物理删除同义词"""
        executor = self._get_executor()
        rows = executor.execute_query(
            "SELECT table_name, synonym FROM table_synonyms WHERE id = %s",
            (synonym_id,)
        )
        if not rows:
            executor.close()
            return {"success": False, "error": "未找到该同义词"}

        executor.execute_query("DELETE FROM table_synonyms WHERE id = %s", (synonym_id,))
        self._log_audit(executor, 'hard_delete', rows[0][0], rows[0][1], 'admin')
        self._invalidate_cache()
        executor.close()
        return {"success": True, "id": synonym_id}

    # ------------------------------------------------------------------
    # 反馈 / 未匹配词记录
    # ------------------------------------------------------------------
    def record_unmatched_term(self, term: str, original_query: str = '',
                              suggested_table: str = None):
        """记录一个未匹配的查询词 (用于自动学习)"""
        try:
            executor = self._get_executor()
            executor.execute_query(
                """INSERT INTO unmatched_query_terms (term, original_query, suggested_table)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (term) DO UPDATE
                   SET frequency = unmatched_query_terms.frequency + 1,
                       updated_at = NOW(),
                       original_query = COALESCE(EXCLUDED.original_query, unmatched_query_terms.original_query)""",
                (term.lower().strip(), original_query, suggested_table)
            )
            executor.close()
            logger.info(f"📝 记录未匹配词: '{term}'")
        except Exception as e:
            logger.warning(f"记录未匹配词失败: {e}")

    def get_unmatched_terms(self, status: str = 'pending',
                            min_frequency: int = 1,
                            limit: int = 50) -> List[Dict]:
        """获取未匹配查询词列表 (候选队列)"""
        try:
            executor = self._get_executor()
            rows = executor.execute_query(
                """SELECT id, term, original_query, frequency, suggested_table,
                          status, reviewed_by, reviewed_at, created_at
                   FROM unmatched_query_terms
                   WHERE status = %s AND frequency >= %s
                   ORDER BY frequency DESC, created_at DESC
                   LIMIT %s""",
                (status, min_frequency, limit)
            )
            executor.close()
            return [
                {
                    "id": r[0], "term": r[1], "original_query": r[2],
                    "frequency": r[3], "suggested_table": r[4],
                    "status": r[5], "reviewed_by": r[6],
                    "reviewed_at": r[7].isoformat() if r[7] else None,
                    "created_at": r[8].isoformat() if r[8] else None,
                }
                for r in (rows or [])
            ]
        except Exception as e:
            logger.error(f"获取未匹配词失败: {e}")
            return []

    def approve_unmatched_term(self, term_id: int, table_name: str,
                               reviewed_by: str = 'admin') -> Dict:
        """
        审批未匹配词 → 自动创建同义词映射
        """
        executor = self._get_executor()
        rows = executor.execute_query(
            "SELECT term FROM unmatched_query_terms WHERE id = %s",
            (term_id,)
        )
        if not rows:
            executor.close()
            return {"success": False, "error": "未找到该记录"}

        term = rows[0][0]

        # 更新状态
        executor.execute_query(
            """UPDATE unmatched_query_terms
               SET status = 'approved', reviewed_by = %s, reviewed_at = NOW(),
                   suggested_table = %s, updated_at = NOW()
               WHERE id = %s""",
            (reviewed_by, table_name, term_id)
        )
        executor.close()

        # 创建同义词映射
        self.add_synonym(table_name, term, source='auto', created_by=reviewed_by)

        return {"success": True, "term": term, "table_name": table_name}

    def reject_unmatched_term(self, term_id: int, reviewed_by: str = 'admin') -> Dict:
        """拒绝未匹配词"""
        executor = self._get_executor()
        executor.execute_query(
            """UPDATE unmatched_query_terms
               SET status = 'rejected', reviewed_by = %s, reviewed_at = NOW(), updated_at = NOW()
               WHERE id = %s""",
            (reviewed_by, term_id)
        )
        executor.close()
        return {"success": True, "id": term_id}

    def ignore_unmatched_term(self, term_id: int) -> Dict:
        """忽略未匹配词"""
        executor = self._get_executor()
        executor.execute_query(
            "UPDATE unmatched_query_terms SET status = 'ignored', updated_at = NOW() WHERE id = %s",
            (term_id,)
        )
        executor.close()
        return {"success": True, "id": term_id}

    # ------------------------------------------------------------------
    # 审计日志
    # ------------------------------------------------------------------
    def _log_audit(self, executor, action: str, table_name: str,
                   synonym: str, performed_by: str, details: dict = None):
        """写入审计日志"""
        import json
        try:
            executor.execute_query(
                """INSERT INTO synonym_audit_log (action, table_name, synonym, details, performed_by)
                   VALUES (%s, %s, %s, %s, %s)""",
                (action, table_name, synonym, json.dumps(details) if details else None, performed_by)
            )
        except Exception as e:
            logger.warning(f"审计日志写入失败: {e}")

    def get_audit_log(self, limit: int = 50) -> List[Dict]:
        """获取审计日志"""
        try:
            executor = self._get_executor()
            rows = executor.execute_query(
                """SELECT id, action, table_name, synonym, details, performed_by, created_at
                   FROM synonym_audit_log ORDER BY created_at DESC LIMIT %s""",
                (limit,)
            )
            executor.close()
            return [
                {
                    "id": r[0], "action": r[1], "table_name": r[2],
                    "synonym": r[3], "details": r[4], "performed_by": r[5],
                    "created_at": r[6].isoformat() if r[6] else None,
                }
                for r in (rows or [])
            ]
        except Exception as e:
            logger.error(f"获取审计日志失败: {e}")
            return []

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------
    def get_stats(self) -> Dict:
        """获取同义词系统总体统计"""
        try:
            executor = self._get_executor()
            syn_rows = executor.execute_query(
                """SELECT COUNT(*) as total,
                          COUNT(*) FILTER (WHERE is_active) as active,
                          COUNT(DISTINCT table_name) as tables,
                          COUNT(*) FILTER (WHERE source = 'manual') as manual,
                          COUNT(*) FILTER (WHERE source = 'auto') as auto,
                          COUNT(*) FILTER (WHERE source = 'builtin') as builtin
                   FROM table_synonyms"""
            )
            unmatched_rows = executor.execute_query(
                """SELECT COUNT(*) as total,
                          COUNT(*) FILTER (WHERE status = 'pending') as pending,
                          COUNT(*) FILTER (WHERE status = 'approved') as approved,
                          COUNT(*) FILTER (WHERE status = 'rejected') as rejected
                   FROM unmatched_query_terms"""
            )
            executor.close()

            sr = syn_rows[0] if syn_rows else (0,) * 6
            ur = unmatched_rows[0] if unmatched_rows else (0,) * 4

            return {
                "synonyms": {
                    "total": sr[0], "active": sr[1], "tables": sr[2],
                    "manual": sr[3], "auto": sr[4], "builtin": sr[5],
                },
                "unmatched": {
                    "total": ur[0], "pending": ur[1],
                    "approved": ur[2], "rejected": ur[3],
                }
            }
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            return {"synonyms": {}, "unmatched": {}}


# 全局单例
synonym_manager = SynonymManagerService()
