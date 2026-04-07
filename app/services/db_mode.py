"""
运行时数据库连接模式切换
支持在 prod / demo 数据库之间切换，无需重启服务

环境变量约定:
  prod:  SUPABASE_URL_PROD  / SUPABASE_ANON_KEY_PROD  / DATABASE_URL_PROD
  demo:  SUPABASE_URL_DEMO  / SUPABASE_ANON_KEY_DEMO  / DATABASE_URL_DEMO
  auto:  SUPABASE_URL       / SUPABASE_ANON_KEY        / DATABASE_URL  (默认)

优先级: runtime_override > DB_MODE env var > env defaults
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── 运行时模式 ─────────────────────────────────────────────────────
_RUNTIME_DB_MODE: Optional[str] = None   # "prod" | "demo" | None (= auto)


def get_db_credentials(mode: Optional[str] = None) -> dict:
    """
    根据当前模式返回数据库连接凭证字典。
    mode 为 None 时使用 _RUNTIME_DB_MODE；都为 None 则 auto。
    """
    effective = mode or _RUNTIME_DB_MODE or os.getenv("DB_MODE")

    if effective == "demo":
        return {
            "supabase_url": os.getenv("SUPABASE_URL_DEMO") or os.getenv("SUPABASE_URL"),
            "supabase_key": os.getenv("SUPABASE_ANON_KEY_DEMO") or os.getenv("SUPABASE_ANON_KEY"),
            "database_url": os.getenv("DATABASE_URL_DEMO") or os.getenv("DATABASE_URL"),
            "source": "demo",
        }
    elif effective == "prod":
        return {
            "supabase_url": os.getenv("SUPABASE_URL_PROD") or os.getenv("SUPABASE_URL"),
            "supabase_key": os.getenv("SUPABASE_ANON_KEY_PROD") or os.getenv("SUPABASE_ANON_KEY"),
            "database_url": os.getenv("DATABASE_URL_PROD") or os.getenv("DATABASE_URL"),
            "source": "prod",
        }
    else:
        return {
            "supabase_url": os.getenv("SUPABASE_URL"),
            "supabase_key": os.getenv("SUPABASE_ANON_KEY"),
            "database_url": os.getenv("DATABASE_URL"),
            "source": "auto",
        }


def set_db_mode(mode: str) -> dict:
    """
    切换运行时数据库模式，并立即清除所有缓存的连接对象。

    Args:
        mode: "test" | "dev" | "epi" | "mysql" | "supabase" | "prod" | "demo" | "auto"
              - test:     MySQL 测试环境 (10.60.120.33:3336)
              - dev:      MySQL 开发环境 (172.16.57.29:3306)
              - epi:      MySQL 外延测试环境 (10.60.120.33:40306)
              - mysql:    等同 test（向后兼容）
              - supabase: 切换到 Supabase（已停用，保留兼容）
              - prod/demo/auto: 切换 Supabase 环境（历史模式）

    Returns:
        当前模式信息 dict
    """
    global _RUNTIME_DB_MODE

    if mode in ("test", "mysql"):
        os.environ["DB_BACKEND"] = "mysql"
        os.environ["MYSQL_SOURCE"] = "test"
        logger.info("[db_mode] DB_BACKEND=mysql, MYSQL_SOURCE=test (测试环境)")
    elif mode == "dev":
        os.environ["DB_BACKEND"] = "mysql"
        os.environ["MYSQL_SOURCE"] = "dev"
        logger.info("[db_mode] DB_BACKEND=mysql, MYSQL_SOURCE=dev (开发环境)")
    elif mode == "epi":
        os.environ["DB_BACKEND"] = "mysql"
        os.environ["MYSQL_SOURCE"] = "epi"
        logger.info("[db_mode] DB_BACKEND=mysql, MYSQL_SOURCE=epi (外延测试环境)")
    elif mode == "supabase":
        os.environ["DB_BACKEND"] = "supabase"
        logger.info("[db_mode] DB_BACKEND switched to: supabase")
    elif mode == "auto":
        _RUNTIME_DB_MODE = None
    elif mode in ("prod", "demo"):
        _RUNTIME_DB_MODE = mode
    else:
        raise ValueError(f"Invalid db mode: {mode!r}. Must be 'test', 'dev', 'epi', 'mysql', 'supabase', 'prod', 'demo', or 'auto'")

    _reset_cached_connections()

    logger.info(f"[db_mode] Database mode switched to: runtime={_RUNTIME_DB_MODE!r}, backend={os.getenv('DB_BACKEND', 'mysql')}, source={os.getenv('MYSQL_SOURCE', 'test')}")
    return get_current_db_mode()


def get_current_db_mode() -> dict:
    """返回当前数据库模式的完整信息（不含敏感凭证）"""
    creds = get_db_credentials()
    url    = creds.get("supabase_url") or ""
    db_url = creds.get("database_url") or ""
    db_backend   = os.getenv("DB_BACKEND",    "mysql")
    mysql_source = os.getenv("MYSQL_SOURCE",  "test")

    suffix      = mysql_source.upper()
    mysql_host  = (os.getenv(f"MYSQL_HOST_{suffix}") or os.getenv("MYSQL_HOST") or "10.60.120.33")
    mysql_port  = (os.getenv(f"MYSQL_PORT_{suffix}") or os.getenv("MYSQL_PORT") or "3336")

    return {
        "mode":               _RUNTIME_DB_MODE or "auto",
        "source":             creds["source"],
        "supabase_url_hint":  (url[:40]    + "...") if len(url)    > 40 else url,
        "database_url_hint":  (db_url[:40] + "...") if len(db_url) > 40 else db_url,
        "runtime_db_mode":    _RUNTIME_DB_MODE,
        "db_backend":         db_backend,
        "mysql_source":       mysql_source,
        "mysql_host_hint":    f"{mysql_host}:{mysql_port}",
    }


def _reset_cached_connections():
    """清除所有模块级别的连接/客户端缓存，使下次访问时以新凭证重建。"""
    # 1. Supabase 客户端单例
    try:
        import app.services.supabase_client as _sc
        _sc._supabase_client = None
        logger.info("[db_mode] ✅ Supabase client singleton invalidated")
    except Exception as e:
        logger.warning(f"[db_mode] Could not reset Supabase client: {e}")

    # 2. database_tools 全局执行器（Agent 使用）
    try:
        import app.agent.tools.database_tools as _dt
        _dt._executor = None
        logger.info("[db_mode] ✅ database_tools executor invalidated")
    except Exception as e:
        logger.warning(f"[db_mode] Could not reset database_tools executor: {e}")

    # 3. UnifiedQueryService 单例（NL2SQL 查询主路径）
    try:
        import app.services.unified_query_service as _uqs
        _uqs._unified_query_service = None
        logger.info("[db_mode] ✅ UnifiedQueryService singleton invalidated")
    except Exception as e:
        logger.warning(f"[db_mode] Could not reset UnifiedQueryService: {e}")

    # 4. 查询结果缓存（切换 DB 后缓存数据无效，必须清空）
    try:
        import app.services.query_cache as _qc
        if _qc._query_cache is not None:
            _qc._query_cache.clear()
        logger.info("[db_mode] ✅ QueryCache cleared")
    except Exception as e:
        logger.warning(f"[db_mode] Could not clear QueryCache: {e}")
