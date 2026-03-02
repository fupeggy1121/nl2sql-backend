"""
同义词管理服务层
提供数据库持久化 + 内存缓存的同义词 CRUD 操作，
以及查询反馈记录和候选同义词推荐功能。

数据库优先级:
  1. PostgreSQL 直连 (SUPABASE_DB_HOST)
  2. Supabase PostgREST (SUPABASE_URL + SUPABASE_ANON_KEY)
  3. 静态配置回退 (table_synonyms.py)
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class SynonymManagerService:
    """同义词管理服务 - 支持 PostgreSQL / Supabase REST / 静态配置三层回退"""

    def __init__(self):
        self._cache: Optional[Dict[str, str]] = None
        self._table_cache: Optional[Dict[str, List[str]]] = None
        self._supabase_client = None
        self._pg_available: Optional[bool] = None  # None=未检测, True/False=已知

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _get_executor(self):
        """获取 PostgreSQL 执行器 (短连接), 失败则抛异常"""
        import os
        # 快速失败: 如果 DB_HOST 就是 None，跳过 PG 尝试
        if not os.getenv('SUPABASE_DB_HOST'):
            self._pg_available = False
            raise ConnectionError("SUPABASE_DB_HOST 未配置")
        from app.services.postgresql_executor import PostgreSQLExecutor
        executor = PostgreSQLExecutor()
        if not executor.connect():
            self._pg_available = False
            raise ConnectionError("无法连接数据库")
        self._pg_available = True
        return executor

    def _get_supabase(self):
        """获取 Supabase 客户端 (单例)"""
        if self._supabase_client is None:
            from app.services.supabase_client import get_supabase_client
            self._supabase_client = get_supabase_client()
        if not self._supabase_client or not self._supabase_client.client:
            raise ConnectionError("Supabase 客户端不可用")
        return self._supabase_client.client

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
    def get_all_synonyms(self, target_uri: Optional[str] = None,
                         table_name: Optional[str] = None,
                         source: Optional[str] = None,
                         is_active: Optional[bool] = True) -> List[Dict]:
        """
        获取同义词列表。target_uri 和 table_name 参数均可用于过滤（target_uri 优先）。
        优先 class_synonyms PG → class_synonyms Supabase REST → table_synonyms (legacy) → 静态配置。
        """
        uri_filter = target_uri or table_name
        # ── 1. 尝试 PostgreSQL 直连 (class_synonyms) ──
        try:
            executor = self._get_executor()
            conditions = []
            params = []

            if uri_filter:
                conditions.append("target_uri = %s")
                params.append(uri_filter)
            if source:
                conditions.append("source = %s")
                params.append(source)
            if is_active is not None:
                conditions.append("is_active = %s")
                params.append(is_active)

            where = " WHERE " + " AND ".join(conditions) if conditions else ""
            rows = executor.execute_query(
                f"SELECT id, target_uri, target_label_cn, target_type, synonym, "
                f"source, is_active, created_at, updated_at, created_by "
                f"FROM class_synonyms{where} ORDER BY target_uri, synonym",
                tuple(params) if params else None
            )
            executor.close()
            if rows is not None:  # table exists
                return [
                    {
                        "id": r[0], "target_uri": r[1], "target_label_cn": r[2],
                        "target_type": r[3], "synonym": r[4], "source": r[5],
                        "is_active": r[6],
                        "created_at": r[7].isoformat() if r[7] else None,
                        "updated_at": r[8].isoformat() if r[8] else None,
                        "created_by": r[9],
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.debug(f"PG class_synonyms 查询失败: {e}")

        # ── 2. 尝试 Supabase REST (class_synonyms) ──
        try:
            client = self._get_supabase()
            query = client.table('class_synonyms').select(
                'id,target_uri,target_label_cn,target_type,synonym,source,is_active,created_at,updated_at,created_by'
            )
            if uri_filter:
                query = query.eq('target_uri', uri_filter)
            if source:
                query = query.eq('source', source)
            if is_active is not None:
                query = query.eq('is_active', is_active)
            query = query.order('target_uri').order('synonym')
            response = query.execute()
            if response.data:  # non-empty list — class_synonyms table is populated
                logger.info(f"✅ Supabase REST class_synonyms: {len(response.data)} 条")
                return response.data
        except Exception as e:
            logger.warning(f"Supabase REST class_synonyms 查询失败: {e}")

        # ── 3. 尝试 PG table_synonyms (旧表) ──
        try:
            executor = self._get_executor()
            conditions = []
            params = []
            if uri_filter:
                conditions.append("table_name = %s")
                params.append(uri_filter)
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
                    "id": r[0], "target_uri": r[1], "target_label_cn": r[1],
                    "target_type": "class", "synonym": r[2],
                    "source": r[3], "is_active": r[4],
                    "created_at": r[5].isoformat() if r[5] else None,
                    "updated_at": r[6].isoformat() if r[6] else None,
                    "created_by": r[7],
                }
                for r in (rows or [])
            ]
        except Exception as e:
            logger.debug(f"PG table_synonyms 查询失败: {e}")

        # ── 4. 尝试 Supabase REST (table_synonyms) ──
        try:
            client = self._get_supabase()
            query = client.table('table_synonyms').select(
                'id,table_name,synonym,source,is_active,created_at,updated_at,created_by'
            )
            if uri_filter:
                query = query.eq('table_name', uri_filter)
            if source:
                query = query.eq('source', source)
            if is_active is not None:
                query = query.eq('is_active', is_active)
            query = query.order('table_name').order('synonym')
            response = query.execute()
            logger.info(f"✅ Supabase REST table_synonyms: {len(response.data)} 条")
            # Remap field names for compatibility
            return [
                {"id": r.get('id'), "target_uri": r.get('table_name'), "target_label_cn": r.get('table_name'),
                 "target_type": "class", "synonym": r.get('synonym'), "source": r.get('source'),
                 "is_active": r.get('is_active'), "created_at": r.get('created_at'),
                 "updated_at": r.get('updated_at'), "created_by": r.get('created_by')}
                for r in (response.data or [])
            ]
        except Exception as e:
            logger.warning(f"Supabase REST table_synonyms 查询失败: {e}")

        # ── 5. 静态配置回退 ──
        return self._fallback_get_all(uri_filter)

    def _fallback_get_all(self, target_uri: Optional[str] = None) -> List[Dict]:
        """Use ontology_synonyms.py as static fallback, return target_uri fields."""
        from app.config.ontology_synonyms import get_all_synonyms_flat
        results = get_all_synonyms_flat()
        if target_uri:
            results = [r for r in results if r.get('target_uri') == target_uri]
        return results

    def get_synonym_map(self) -> Dict[str, str]:
        """获取 {同义词 -> 表名} 的完整映射 (带缓存)"""
        if self._cache is not None:
            return self._cache

        # 尝试 PG — class_synonyms 优先
        try:
            executor = self._get_executor()
            try:
                rows = executor.execute_query(
                    "SELECT synonym, target_uri FROM class_synonyms WHERE is_active = TRUE"
                )
                self._cache = {r[0].lower(): r[1] for r in (rows or [])}
            except Exception:
                rows = executor.execute_query(
                    "SELECT synonym, table_name FROM table_synonyms WHERE is_active = TRUE"
                )
                self._cache = {r[0].lower(): r[1] for r in (rows or [])}
            executor.close()
            return self._cache
        except Exception:
            pass

        # 尝试 Supabase REST
        try:
            client = self._get_supabase()
            try:
                response = client.table('class_synonyms').select('synonym,target_uri').eq('is_active', True).execute()
                self._cache = {r['synonym'].lower(): r['target_uri'] for r in (response.data or [])}
            except Exception:
                pass
            if not self._cache:
                # class_synonyms empty or missing — try table_synonyms
                try:
                    response = client.table('table_synonyms').select('synonym,table_name').eq('is_active', True).execute()
                    self._cache = {r['synonym'].lower(): r['table_name'] for r in (response.data or [])}
                except Exception:
                    pass
            if self._cache:
                logger.info(f"✅ Supabase REST 加载同义词映射: {len(self._cache)} 条")
                return self._cache
        except Exception:
            pass

        # 静态配置 — 使用 ontology_synonyms.py
        from app.config.ontology_synonyms import get_synonym_to_uri_map
        self._cache = get_synonym_to_uri_map()
        return self._cache

    def map_table_name(self, keyword: str) -> str:
        """将关键词映射到实际表名（先解析到本体URI，再查映射字典得到物理表名）"""
        uri = self.map_keyword_to_class(keyword)
        if uri:
            tables = self.resolve_to_tables(uri)
            if tables:
                return tables[0]
        # 最终回退：用synonym_map直接返回（可能是旧式物理表名）
        m = self.get_synonym_map()
        return m.get(keyword.lower().strip(), keyword)

    def map_keyword_to_class(self, keyword: str) -> Optional[str]:
        """关键词 → 本体类 URI（未命中返回 None）"""
        return self.get_synonym_map().get(keyword.lower().strip())

    def resolve_to_tables(self, target_uri: str) -> List[str]:
        """本体类 URI → 当前环境物理表名列表"""
        try:
            from app.ontology.mapping import load_mapping
            mapping = load_mapping()
            return mapping.list_table_names_for_class(target_uri)
        except Exception as e:
            logger.warning(f"resolve_to_tables({target_uri}) 失败: {e}")
            return []

    def lookup(self, keyword: str) -> Dict:
        """关键词详细解析结果"""
        uri = self.map_keyword_to_class(keyword)
        if not uri:
            return {"keyword": keyword, "matched": False, "target_uri": None, "tables": []}
        from app.config.ontology_synonyms import get_label_cn
        return {
            "keyword": keyword, "matched": True,
            "target_uri": uri, "target_label_cn": get_label_cn(uri),
            "tables": self.resolve_to_tables(uri),
        }

    def get_synonyms_by_class(self) -> List[Dict]:
        """按本体类分组的同义词摘要"""
        return self.get_synonyms_by_table()

    def get_synonyms_by_table(self) -> List[Dict]:
        """获取每个本体类/表的同义词统计摘要（返回 target_uri 字段）"""
        # 尝试 PG — class_synonyms 优先
        try:
            executor = self._get_executor()
            try:
                rows = executor.execute_query(
                    """SELECT target_uri, target_label_cn, target_type,
                              COUNT(*) as total,
                              COUNT(*) FILTER (WHERE is_active) as active,
                              COUNT(*) FILTER (WHERE source = 'manual') as manual,
                              COUNT(*) FILTER (WHERE source = 'auto') as auto,
                              COUNT(*) FILTER (WHERE source = 'builtin') as builtin
                       FROM class_synonyms
                       GROUP BY target_uri, target_label_cn, target_type ORDER BY target_uri"""
                )
                executor.close()
                return [
                    {"target_uri": r[0], "target_label_cn": r[1], "target_type": r[2],
                     "total": r[3], "active": r[4], "manual": r[5], "auto": r[6], "builtin": r[7]}
                    for r in (rows or [])
                ]
            except Exception:
                rows = executor.execute_query(
                    """SELECT table_name, COUNT(*) as total,
                              COUNT(*) FILTER (WHERE is_active) as active,
                              COUNT(*) FILTER (WHERE source = 'manual') as manual,
                              COUNT(*) FILTER (WHERE source = 'auto') as auto,
                              COUNT(*) FILTER (WHERE source = 'builtin') as builtin
                       FROM table_synonyms
                       GROUP BY table_name ORDER BY table_name"""
                )
                executor.close()
                return [
                    {"target_uri": r[0], "target_label_cn": r[0], "target_type": "class",
                     "total": r[1], "active": r[2], "manual": r[3], "auto": r[4], "builtin": r[5]}
                    for r in (rows or [])
                ]
        except Exception:
            pass

        # 尝试 Supabase REST
        try:
            client = self._get_supabase()
            from collections import defaultdict
            # Try class_synonyms
            try:
                response = client.table('class_synonyms').select(
                    'target_uri,target_label_cn,target_type,source,is_active'
                ).execute()
                stats: dict = defaultdict(lambda: {"target_label_cn": "", "target_type": "class",
                                                    "total": 0, "active": 0, "manual": 0, "auto": 0, "builtin": 0})
                for r in (response.data or []):
                    k = r['target_uri']
                    stats[k]["target_label_cn"] = r.get('target_label_cn', '')
                    stats[k]["target_type"] = r.get('target_type', 'class')
                    stats[k]["total"] += 1
                    if r.get('is_active'): stats[k]["active"] += 1
                    src = r.get('source', '')
                    if src in ('manual', 'auto', 'builtin'): stats[k][src] += 1
                if stats:
                    return [{"target_uri": k, **v} for k, v in sorted(stats.items())]
            except Exception:
                pass
            # Fall back to table_synonyms
            response = client.table('table_synonyms').select('table_name,source,is_active').execute()
            stats2: dict = defaultdict(lambda: {"total": 0, "active": 0, "manual": 0, "auto": 0, "builtin": 0})
            for r in (response.data or []):
                t = r['table_name']
                stats2[t]["total"] += 1
                if r.get('is_active'): stats2[t]["active"] += 1
                src = r.get('source', '')
                if src in ('manual', 'auto', 'builtin'): stats2[t][src] += 1
            return [{"target_uri": k, "target_label_cn": k, "target_type": "class", **v}
                    for k, v in sorted(stats2.items())]
        except Exception as e:
            logger.error(f"获取摘要失败: {e}")
            return []

    # ------------------------------------------------------------------
    # 创建 / 更新 / 删除
    # ------------------------------------------------------------------
    def add_synonym(self, target_uri: str = None, synonym: str = None,
                    table_name: str = None,  # backward compat
                    source: str = 'manual', created_by: str = 'admin') -> Dict:
        """添加同义词 (target_uri/synonym 为新接口；table_name 向后兼容)"""
        uri = target_uri or table_name
        syn = synonym
        if not uri or not syn:
            return {"success": False, "error": "target_uri and synonym are required"}
        syn_lower = syn.lower().strip()
        from app.config.ontology_synonyms import get_label_cn, get_target_type
        label_cn = get_label_cn(uri)
        ttype = get_target_type(uri)

        # 尝试 PG
        try:
            executor = self._get_executor()
            try:
                # 先尝试写入 class_synonymsⱬ回退 table_synonyms
                try:
                    executor.execute_query(
                        """INSERT INTO class_synonyms
                               (target_uri, target_label_cn, target_type, synonym, source, created_by)
                           VALUES (%s, %s, %s, %s, %s, %s)
                           ON CONFLICT (target_uri, synonym) DO UPDATE
                           SET is_active = TRUE, updated_at = NOW(), source = EXCLUDED.source""",
                        (uri, label_cn, ttype, syn_lower, source, created_by)
                    )
                except Exception:
                    executor.execute_query(
                        """INSERT INTO table_synonyms (table_name, synonym, source, created_by)
                           VALUES (%s, %s, %s, %s)
                           ON CONFLICT (table_name, synonym) DO UPDATE
                           SET is_active = TRUE, updated_at = NOW(), source = EXCLUDED.source""",
                        (uri, syn_lower, source, created_by)
                    )
                self._log_audit(executor, 'add', uri, syn, created_by)
                self._invalidate_cache()
                executor.close()
                return {"success": True, "target_uri": uri, "synonym": syn}
            except Exception as e:
                executor.close()
                raise e
        except ConnectionError:
            pass

        # Supabase REST fallback
        client = self._get_supabase()
        try:
            client.table('class_synonyms').upsert({
                'target_uri': uri, 'target_label_cn': label_cn,
                'target_type': ttype, 'synonym': syn_lower,
                'source': source, 'created_by': created_by, 'is_active': True,
            }, on_conflict='target_uri,synonym').execute()
        except Exception:
            client.table('table_synonyms').upsert({
                'table_name': uri, 'synonym': syn_lower,
                'source': source, 'created_by': created_by, 'is_active': True,
            }, on_conflict='table_name,synonym').execute()
        self._log_audit_via_supabase(client, 'add', uri, syn, created_by)
        self._invalidate_cache()
        return {"success": True, "target_uri": uri, "synonym": syn}

    def add_synonyms_batch(self, target_uri: str = None, synonyms: List[str] = None,
                           table_name: str = None,  # backward compat
                           source: str = 'manual', created_by: str = 'admin') -> Dict:
        """批量添加同义词"""
        uri = target_uri or table_name
        added = []
        errors = []
        for syn in (synonyms or []):
            try:
                self.add_synonym(target_uri=uri, synonym=syn, source=source, created_by=created_by)
                added.append(syn)
            except Exception as e:
                errors.append({"synonym": syn, "error": str(e)})
        return {"added": added, "errors": errors}

    def update_synonym(self, synonym_id, *args, **kwargs) -> Dict:
        """更新同义词属性 (target_uri / synonym / is_active)"""
        # Support both update_synonym(id, dict) and update_synonym(id, field=val)
        if args and isinstance(args[0], dict):
            kwargs.update(args[0])
        allowed = {'target_uri', 'table_name', 'synonym', 'is_active'}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        # normalize: use 'target_uri' key if only 'table_name' passed
        if 'table_name' in updates and 'target_uri' not in updates:
            updates['target_uri'] = updates.pop('table_name')
        if not updates:
            return {"success": False, "error": "无有效字段"}

        # 尝试 PG
        try:
            sets_cs = ", ".join(f"{k} = %s" for k in updates)
            vals = list(updates.values()) + [synonym_id]
            executor = self._get_executor()
            try:
                executor.execute_query(
                    f"UPDATE class_synonyms SET {sets_cs}, updated_at = NOW() WHERE id = %s",
                    tuple(vals)
                )
            except Exception:
                # Fall back to table_synonyms with old field name
                sets_ts = ", ".join(f"{'table_name' if k == 'target_uri' else k} = %s" for k in updates)
                executor.execute_query(
                    f"UPDATE table_synonyms SET {sets_ts}, updated_at = NOW() WHERE id = %s",
                    tuple(vals)
                )
            self._log_audit(executor, 'update', kwargs.get('target_uri', ''),
                            kwargs.get('synonym', ''), 'admin',
                            details={"id": synonym_id, "changes": updates})
            self._invalidate_cache()
            executor.close()
            return {"success": True, "id": synonym_id, "updates": updates}
        except ConnectionError:
            pass

        # Supabase REST fallback
        client = self._get_supabase()
        try:
            client.table('class_synonyms').update(updates).eq('id', synonym_id).execute()
        except Exception:
            ts_updates = dict(updates)
            if 'target_uri' in ts_updates:
                ts_updates['table_name'] = ts_updates.pop('target_uri')
            client.table('table_synonyms').update(ts_updates).eq('id', synonym_id).execute()
        self._log_audit_via_supabase(client, 'update', kwargs.get('target_uri', ''),
                                     kwargs.get('synonym', ''), 'admin',
                                     details={"id": synonym_id, "changes": updates})
        self._invalidate_cache()
        return {"success": True, "id": synonym_id, "updates": updates}
    def delete_synonym(self, synonym_id: int) -> Dict:
        """删除同义词 (软删除 - 设为 inactive)"""
        # 尝试 PG
        try:
            executor = self._get_executor()
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
        except ConnectionError:
            pass

        # Supabase REST fallback
        client = self._get_supabase()
        resp = client.table('table_synonyms').select('table_name,synonym').eq('id', synonym_id).execute()
        if not resp.data:
            return {"success": False, "error": "未找到该同义词"}
        client.table('table_synonyms').update({'is_active': False}).eq('id', synonym_id).execute()
        self._log_audit_via_supabase(client, 'delete', resp.data[0]['table_name'], resp.data[0]['synonym'], 'admin')
        self._invalidate_cache()
        return {"success": True, "id": synonym_id}

    def hard_delete_synonym(self, synonym_id: int) -> Dict:
        """物理删除同义词"""
        # 尝试 PG
        try:
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
        except ConnectionError:
            pass

        # Supabase REST fallback
        client = self._get_supabase()
        resp = client.table('table_synonyms').select('table_name,synonym').eq('id', synonym_id).execute()
        if not resp.data:
            return {"success": False, "error": "未找到该同义词"}
        client.table('table_synonyms').delete().eq('id', synonym_id).execute()
        self._log_audit_via_supabase(client, 'hard_delete', resp.data[0]['table_name'], resp.data[0]['synonym'], 'admin')
        self._invalidate_cache()
        return {"success": True, "id": synonym_id}

    # ------------------------------------------------------------------
    # 反馈 / 未匹配词记录
    # ------------------------------------------------------------------
    def record_unmatched_term(self, term: str, original_query: str = '',
                              suggested_table: str = None):
        """记录一个未匹配的查询词 (用于自动学习)"""
        term_lower = term.lower().strip()
        # 尝试 PG
        try:
            executor = self._get_executor()
            executor.execute_query(
                """INSERT INTO unmatched_query_terms (term, original_query, suggested_table)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (term) DO UPDATE
                   SET frequency = unmatched_query_terms.frequency + 1,
                       updated_at = NOW(),
                       original_query = COALESCE(EXCLUDED.original_query, unmatched_query_terms.original_query)""",
                (term_lower, original_query, suggested_table)
            )
            executor.close()
            logger.info(f"📝 记录未匹配词: '{term}'")
            return
        except ConnectionError:
            pass
        except Exception as e:
            logger.warning(f"PG 记录未匹配词失败: {e}")

        # Supabase REST fallback
        try:
            client = self._get_supabase()
            client.table('unmatched_query_terms').upsert({
                'term': term_lower,
                'original_query': original_query,
                'suggested_table': suggested_table,
            }, on_conflict='term').execute()
            logger.info(f"📝 [Supabase] 记录未匹配词: '{term}'")
        except Exception as e:
            logger.warning(f"记录未匹配词失败: {e}")

    def get_unmatched_terms(self, status: str = 'pending',
                            min_frequency: int = 1,
                            limit: int = 50) -> List[Dict]:
        """获取未匹配查询词列表 (候选队列)"""
        # 尝试 PG
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
        except ConnectionError:
            pass
        except Exception as e:
            logger.error(f"PG 获取未匹配词失败: {e}")

        # Supabase REST fallback
        try:
            client = self._get_supabase()
            response = client.table('unmatched_query_terms').select('*').eq(
                'status', status
            ).gte('frequency', min_frequency).order(
                'frequency', desc=True
            ).order('created_at', desc=True).limit(limit).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"获取未匹配词失败: {e}")
            return []

    def approve_unmatched_term(self, term_id: int, table_name: str,
                               reviewed_by: str = 'admin') -> Dict:
        """审批未匹配词 → 自动创建同义词映射"""
        # 尝试 PG
        try:
            executor = self._get_executor()
            rows = executor.execute_query(
                "SELECT term FROM unmatched_query_terms WHERE id = %s",
                (term_id,)
            )
            if not rows:
                executor.close()
                return {"success": False, "error": "未找到该记录"}
            term = rows[0][0]
            executor.execute_query(
                """UPDATE unmatched_query_terms
                   SET status = 'approved', reviewed_by = %s, reviewed_at = NOW(),
                       suggested_table = %s, updated_at = NOW()
                   WHERE id = %s""",
                (reviewed_by, table_name, term_id)
            )
            executor.close()
            self.add_synonym(table_name, term, source='auto', created_by=reviewed_by)
            return {"success": True, "term": term, "table_name": table_name}
        except ConnectionError:
            pass

        # Supabase REST fallback
        client = self._get_supabase()
        resp = client.table('unmatched_query_terms').select('term').eq('id', term_id).execute()
        if not resp.data:
            return {"success": False, "error": "未找到该记录"}
        term = resp.data[0]['term']
        client.table('unmatched_query_terms').update({
            'status': 'approved', 'reviewed_by': reviewed_by, 'suggested_table': table_name
        }).eq('id', term_id).execute()
        self.add_synonym(table_name, term, source='auto', created_by=reviewed_by)
        return {"success": True, "term": term, "table_name": table_name}

    def reject_unmatched_term(self, term_id: int, reviewed_by: str = 'admin') -> Dict:
        """拒绝未匹配词"""
        try:
            executor = self._get_executor()
            executor.execute_query(
                """UPDATE unmatched_query_terms
                   SET status = 'rejected', reviewed_by = %s, reviewed_at = NOW(), updated_at = NOW()
                   WHERE id = %s""",
                (reviewed_by, term_id)
            )
            executor.close()
            return {"success": True, "id": term_id}
        except ConnectionError:
            pass

        client = self._get_supabase()
        client.table('unmatched_query_terms').update({
            'status': 'rejected', 'reviewed_by': reviewed_by
        }).eq('id', term_id).execute()
        return {"success": True, "id": term_id}

    def ignore_unmatched_term(self, term_id: int) -> Dict:
        """忽略未匹配词"""
        try:
            executor = self._get_executor()
            executor.execute_query(
                "UPDATE unmatched_query_terms SET status = 'ignored', updated_at = NOW() WHERE id = %s",
                (term_id,)
            )
            executor.close()
            return {"success": True, "id": term_id}
        except ConnectionError:
            pass

        client = self._get_supabase()
        client.table('unmatched_query_terms').update({
            'status': 'ignored'
        }).eq('id', term_id).execute()
        return {"success": True, "id": term_id}

    # ------------------------------------------------------------------
    # 审计日志
    # ------------------------------------------------------------------
    def _log_audit(self, executor, action: str, table_name: str,
                   synonym: str, performed_by: str, details: dict = None):
        """写入审计日志 (PG)"""
        import json
        try:
            executor.execute_query(
                """INSERT INTO synonym_audit_log (action, table_name, synonym, details, performed_by)
                   VALUES (%s, %s, %s, %s, %s)""",
                (action, table_name, synonym, json.dumps(details) if details else None, performed_by)
            )
        except Exception as e:
            logger.warning(f"审计日志写入失败: {e}")

    def _log_audit_via_supabase(self, client, action: str, table_name: str,
                                 synonym: str, performed_by: str, details: dict = None):
        """写入审计日志 (Supabase REST)"""
        import json
        try:
            client.table('synonym_audit_log').insert({
                'action': action,
                'table_name': table_name,
                'synonym': synonym,
                'details': json.dumps(details) if details else None,
                'performed_by': performed_by,
            }).execute()
        except Exception as e:
            logger.warning(f"[Supabase] 审计日志写入失败: {e}")

    def get_audit_log(self, limit: int = 50) -> List[Dict]:
        """获取审计日志"""
        # 尝试 PG
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
        except ConnectionError:
            pass
        except Exception as e:
            logger.error(f"PG 获取审计日志失败: {e}")

        # Supabase REST fallback
        try:
            client = self._get_supabase()
            response = client.table('synonym_audit_log').select('*').order(
                'created_at', desc=True
            ).limit(limit).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"获取审计日志失败: {e}")
            return []

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------
    def get_stats(self) -> Dict:
        """获取同义词系统总体统计"""
        # 尝试 PG
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
        except ConnectionError:
            pass
        except Exception as e:
            logger.error(f"PG 获取统计失败: {e}")

        # Supabase REST fallback — 拉数据后 Python 端聚合
        try:
            client = self._get_supabase()
            syn_resp = client.table('table_synonyms').select('is_active,source,table_name').execute()
            syn_data = syn_resp.data or []
            tables_set = set()
            s = {"total": 0, "active": 0, "manual": 0, "auto": 0, "builtin": 0}
            for r in syn_data:
                s["total"] += 1
                tables_set.add(r.get('table_name'))
                if r.get('is_active'):
                    s["active"] += 1
                src = r.get('source', '')
                if src in s:
                    s[src] += 1
            s["tables"] = len(tables_set)

            um_resp = client.table('unmatched_query_terms').select('status').execute()
            um_data = um_resp.data or []
            u = {"total": 0, "pending": 0, "approved": 0, "rejected": 0}
            for r in um_data:
                u["total"] += 1
                st = r.get('status', '')
                if st in u:
                    u[st] += 1

            return {"synonyms": s, "unmatched": u}
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            return {"synonyms": {}, "unmatched": {}}


# 全局单例
synonym_manager = SynonymManagerService()
