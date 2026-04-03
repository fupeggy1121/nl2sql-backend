"""
MySQL 直接 SQL 执行服务
DB_BACKEND=mysql 时用于替代 PostgreSQLExecutor
接口与 PostgreSQLExecutor 保持一致，QueryExecutor 无需感知差异
"""

import os
import logging
from typing import List, Tuple, Optional
from dotenv import load_dotenv

try:
    import pymysql
    import pymysql.cursors
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False
    pymysql = None

load_dotenv()
logger = logging.getLogger(__name__)


def _build_mysql_connect_kwargs() -> dict:
    """从环境变量构建 pymysql.connect 关键字参数。

    优先级:
      1. MYSQL_SOURCE=test|dev → 对应 MYSQL_*_TEST / MYSQL_*_DEV 系列变量
      2. MYSQL_HOST/PORT/DB/USER/PASSWORD 直接变量（兼容回退）
      3. 内置默认值
    """
    source = os.getenv("MYSQL_SOURCE", "test").lower()
    suffix = source.upper()  # "TEST" or "DEV"

    def _get(key: str, fallback: str) -> str:
        return (os.getenv(f"MYSQL_{key}_{suffix}")
                or os.getenv(f"MYSQL_{key}")
                or os.getenv(f"PROD_DB_{key}", fallback))

    host     = _get("HOST",     "10.60.120.33")
    port     = int(_get("PORT", "3336"))
    db       = _get("DB",       "cc_semi_mvp")
    user     = _get("USER",     "root")
    password = _get("PASSWORD", "")
    return dict(host=host, port=port, db=db, user=user, password=password,
                connect_timeout=3, charset="utf8mb4")


class MySQLExecutor:
    """直接连接 MySQL 执行 SQL，接口对齐 PostgreSQLExecutor。"""

    def __init__(self):
        if not PYMYSQL_AVAILABLE:
            logger.warning("⚠️ pymysql not available – MySQL executor unavailable")
        self.conn    = None
        self.cursor  = None
        self._kwargs = _build_mysql_connect_kwargs()

    # ── 连接 ─────────────────────────────────────────────────────────────────
    def connect(self) -> bool:
        if not PYMYSQL_AVAILABLE:
            logger.error("❌ pymysql not installed")
            return False
        try:
            self.conn   = pymysql.connect(**self._kwargs,
                                          cursorclass=pymysql.cursors.DictCursor)
            self.cursor = self.conn.cursor()
            self.cursor.execute("SELECT 1")
            self.cursor.fetchall()  # 消耗测试查询结果，避免 cursor buffer 残留
            logger.info("✅ MySQL 连接成功 (%s:%s/%s)",
                        self._kwargs["host"], self._kwargs["port"], self._kwargs["db"])
            return True
        except Exception as e:
            logger.error("❌ MySQL 连接失败: %s", e)
            self.conn = self.cursor = None
            return False

    # ── 重连 ──────────────────────────────────────────────────────────────────
    def _reconnect(self) -> bool:
        """检测到断连后尝试重新建立连接，成功返回 True。"""
        logger.warning("⚠️ MySQL 连接已断开，尝试重连…")
        try:
            if self.conn:
                try:
                    self.conn.close()
                except Exception:
                    pass
        finally:
            self.conn = self.cursor = None
        return self.connect()

    # ── 核心查询（供 QueryExecutor 调用）────────────────────────────────────
    def execute_query(self, query: str, params: tuple = None) -> Optional[List]:
        """执行 SELECT/DML，返回 List[dict]（SELECT）或 None（DML）。

        断连时自动重连一次后重试；重连失败返回 None。
        """
        for attempt in range(2):
            if not self.cursor:
                if attempt == 0:
                    if not self._reconnect():
                        logger.error("❌ 数据库未连接且重连失败")
                        return None
                else:
                    logger.error("❌ 数据库未连接")
                    return None
            try:
                if params:
                    self.cursor.execute(query, params)
                else:
                    self.cursor.execute(query)

                if query.strip().upper().startswith("SELECT"):
                    return list(self.cursor.fetchall())   # DictCursor → List[dict]
                else:
                    self.conn.commit()
                    return None
            except (pymysql.err.OperationalError, pymysql.err.InterfaceError) as e:
                # errno 属于连接丢失范围时才重连；否则视为普通 SQL 错误
                _CONN_ERRNOS = {0, 2003, 2006, 2013, 2026, 2055}
                err_no = e.args[0] if e.args else -1
                if err_no not in _CONN_ERRNOS:
                    logger.error("❌ 查询执行失败: %s", e)
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                    return None
                logger.error("❌ 查询执行失败（连接异常）: %s", e)
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                self.conn = self.cursor = None
                if attempt == 0:
                    logger.warning("⚠️ 尝试重连后重试…")
                    if not self._reconnect():
                        return None
                    continue
                return None
            except Exception as e:
                logger.error("❌ 查询执行失败: %s", e)
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return None
        return None

    # ── 描述符（QueryExecutor 需要 .description） ────────────────────────────
    @property
    def description(self):
        return self.cursor.description if self.cursor else None

    def fetchall(self):
        return list(self.cursor.fetchall()) if self.cursor else []

    # ── 兼容 PostgreSQLExecutor 的其他方法 ────────────────────────────────────
    def execute_batch(self, queries: List[str]) -> bool:
        if not self.cursor:
            return False
        try:
            for q in queries:
                self.cursor.execute(q)
            self.conn.commit()
            return True
        except Exception as e:
            logger.error("❌ 批量执行失败: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass
            return False

    def table_exists(self, table_name: str) -> bool:
        if not self.cursor:
            return False
        self.cursor.execute(
            "SELECT COUNT(*) as cnt FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
            (self._kwargs["db"], table_name)
        )
        row = self.cursor.fetchone()
        return (row["cnt"] if row else 0) > 0

    def get_table_columns(self, table_name: str) -> List[Tuple]:
        if not self.cursor:
            return []
        self.cursor.execute(
            "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY "
            "FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION",
            (self._kwargs["db"], table_name)
        )
        return self.cursor.fetchall()

    def close(self):
        try:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
        except Exception:
            pass
        finally:
            self.cursor = self.conn = None
