"""
baseline_service — 业务预警基线管理服务

提供 Supabase PostgreSQL CRUD + 内存缓存，供:
  - baseline_manager 节点在 NL 设定/更新/删除基线时调用
  - response_builder 节点在查询时匹配并注入 thresholds
  - baselines API 端点调用

数据库表: alert_baselines (见 migrations/create_alert_baselines.sql)

缓存策略: 启动时惰性加载全量 enabled baselines，CUD 后自动刷新
"""
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BaselineService:
    """业务预警基线服务 — Supabase PostgREST CRUD + 内存缓存"""

    TABLE = "alert_baselines"

    def __init__(self):
        self._cache: Optional[List[Dict[str, Any]]] = None  # None = 未初始化

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _get_client(self):
        """获取 Supabase 客户端，使用 service_role key 跳过 RLS（admin 写操作需要）"""
        import os
        from app.services.supabase_client import SupabaseClient
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        sc = SupabaseClient(key=service_key) if service_key else SupabaseClient()
        if not sc.client:
            raise ConnectionError(f"Supabase 不可用: {sc.init_error}")
        return sc.client

    def _invalidate_cache(self):
        self._cache = None

    def _load_cache(self):
        """从 DB 加载全量 enabled baselines 到内存缓存"""
        try:
            client = self._get_client()
            res = (
                client.table(self.TABLE)
                .select("*")
                .eq("enabled", True)
                .execute()
            )
            self._cache = res.data or []
            logger.debug(f"[baseline_service] Cache loaded: {len(self._cache)} enabled baselines")
        except Exception as e:
            logger.warning(f"[baseline_service] Cache load failed, using empty: {e}")
            self._cache = []

    @property
    def _enabled_cache(self) -> List[Dict[str, Any]]:
        """惰性加载缓存"""
        if self._cache is None:
            self._load_cache()
        return self._cache or []

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def list_baselines(self, q: str = "", enabled_only: bool = False) -> List[Dict[str, Any]]:
        """列出所有基线，可按关键词搜索"""
        try:
            client = self._get_client()
            query = client.table(self.TABLE).select("*").order("created_at", desc=True)
            if enabled_only:
                query = query.eq("enabled", True)
            res = query.execute()
            rows = res.data or []
            if q:
                q_lower = q.lower()
                rows = [
                    r for r in rows
                    if q_lower in (r.get("label") or "").lower()
                    or q_lower in (r.get("field") or "").lower()
                    or q_lower in (r.get("metric_id") or "").lower()
                    or any(q_lower in kw.lower() for kw in (r.get("keywords") or []))
                ]
            return rows
        except Exception as e:
            logger.error(f"[baseline_service] list_baselines error: {e}")
            return []

    def get_baseline(self, baseline_id: str) -> Optional[Dict[str, Any]]:
        """按 ID 获取单条基线"""
        try:
            client = self._get_client()
            res = client.table(self.TABLE).select("*").eq("id", baseline_id).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error(f"[baseline_service] get_baseline error: {e}")
            return None

    # ------------------------------------------------------------------
    # 写操作
    # ------------------------------------------------------------------
    def create_baseline(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建基线，返回创建后的记录"""
        if not data.get("id"):
            data["id"] = f"BL-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc).isoformat()
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)
        data.setdefault("enabled", True)
        data.setdefault("direction", "below")
        data.setdefault("scope", {})
        data.setdefault("keywords", [])
        data.setdefault("created_by", "system")

        try:
            client = self._get_client()
            res = client.table(self.TABLE).insert(data).execute()
            self._invalidate_cache()
            return res.data[0] if res.data else data
        except Exception as e:
            logger.error(f"[baseline_service] create_baseline error: {e}")
            raise

    def update_baseline(self, baseline_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """部分更新基线"""
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        # 过滤掉 None 值（不覆盖已有字段）
        updates = {k: v for k, v in updates.items() if v is not None}
        try:
            client = self._get_client()
            res = (
                client.table(self.TABLE)
                .update(updates)
                .eq("id", baseline_id)
                .execute()
            )
            self._invalidate_cache()
            return res.data[0] if res.data else {}
        except Exception as e:
            logger.error(f"[baseline_service] update_baseline error: {e}")
            raise

    def delete_baseline(self, baseline_id: str) -> bool:
        """删除基线"""
        try:
            client = self._get_client()
            client.table(self.TABLE).delete().eq("id", baseline_id).execute()
            self._invalidate_cache()
            return True
        except Exception as e:
            logger.error(f"[baseline_service] delete_baseline error: {e}")
            return False

    def toggle_baseline(self, baseline_id: str) -> Dict[str, Any]:
        """切换基线启用/禁用状态"""
        existing = self.get_baseline(baseline_id)
        if not existing:
            raise ValueError(f"基线 {baseline_id} 不存在")
        new_enabled = not existing.get("enabled", True)
        return self.update_baseline(baseline_id, {"enabled": new_enabled})

    # ------------------------------------------------------------------
    # 匹配（供 response_builder 使用）
    # ------------------------------------------------------------------
    def match_baselines(
        self,
        y_axis_field: str = "",
        query_text: str = "",
        scope_filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        根据 yAxisField 和查询文本关键词匹配命中的 enabled baselines。

        规则（任一满足即命中）:
          1. baseline.field == y_axis_field（精确字段名匹配）
          2. baseline.keywords 中有任何一个词出现在 query_text 中

        scope 过滤（可选，当 baseline.scope 非空时）:
          若 scope_filters 提供，则两者的公共 key 必须值相同
        """
        results = []
        query_lower = query_text.lower()
        for bl in self._enabled_cache:
            # 字段名精确匹配
            field_match = y_axis_field and bl.get("field") == y_axis_field
            # 关键词模糊匹配
            keywords = bl.get("keywords") or []
            kw_match = any(kw.lower() in query_lower for kw in keywords if kw)

            if not (field_match or kw_match):
                continue

            # scope 过滤
            bl_scope: Dict = bl.get("scope") or {}
            if bl_scope and scope_filters:
                scope_ok = all(
                    str(scope_filters.get(k, "")) == str(v)
                    for k, v in bl_scope.items()
                )
                if not scope_ok:
                    continue

            results.append(bl)

        return results


# 全局单例
baseline_service = BaselineService()
