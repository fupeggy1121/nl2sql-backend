"""
多数据源注册表 (DataSourceRegistry)

支持系统同时访问多个 MySQL 数据库实例，每个实例由 source_id 唯一标识。

环境变量命名规范:
  MYSQL_HOST_<SOURCE_ID_UPPER>
  MYSQL_PORT_<SOURCE_ID_UPPER>
  MYSQL_DB_<SOURCE_ID_UPPER>
  MYSQL_USER_<SOURCE_ID_UPPER>
  MYSQL_PASSWORD_<SOURCE_ID_UPPER>

示例（source_id="mes_prod"):
  MYSQL_HOST_MES_PROD=10.60.120.33
  MYSQL_PORT_MES_PROD=3336
  MYSQL_DB_MES_PROD=cc_semi_mvp
  MYSQL_USER_MES_PROD=root
  MYSQL_PASSWORD_MES_PROD=xxxx

示例（source_id="equip_mgmt"):
  MYSQL_HOST_EQUIP_MGMT=10.60.120.34
  MYSQL_PORT_EQUIP_MGMT=3306
  MYSQL_DB_EQUIP_MGMT=equipment_mgmt
  MYSQL_USER_EQUIP_MGMT=readonly
  MYSQL_PASSWORD_EQUIP_MGMT=xxxx

fallback: 若未配置 source_id 专属变量，则回退到 legacy 全局变量（MYSQL_HOST / MYSQL_SOURCE 等）。

持久化存储: app/config/data_sources_store.json
  用户通过 API 管理的数据源存储在此文件中，优先级高于环境变量。
"""

from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# JSON 持久化文件路径
_STORE_PATH = Path(__file__).parent / "data_sources_store.json"

# ── 内置已知数据源 ID ──────────────────────────────────────────────────────
MES_PROD    = "mes_prod"
EQUIP_MGMT  = "equip_mgmt"

# 默认数据源（未指定 source_id 的 PhysicalTable 使用此数据源）
DEFAULT_SOURCE_ID = MES_PROD


@dataclass
class DataSourceConfig:
    """单个数据源连接配置。"""
    source_id: str
    host: str
    port: int
    db: str
    user: str
    password: str
    connect_timeout: int = 3
    read_timeout: int = 45
    charset: str = "utf8mb4"
    description: str = ""
    display_name: str = ""
    is_default: bool = False

    def to_pymysql_kwargs(self) -> dict:
        """转换为 pymysql.connect() 可接受的关键字参数。"""
        return dict(
            host=self.host,
            port=self.port,
            db=self.db,
            user=self.user,
            password=self.password,
            connect_timeout=self.connect_timeout,
            read_timeout=self.read_timeout,
            charset=self.charset,
        )

    def to_dict(self, mask_password: bool = True) -> dict:
        """序列化为字典，可选脱敏密码。"""
        return {
            "source_id": self.source_id,
            "display_name": self.display_name or self.source_id,
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "user": self.user,
            "password": "••••" if mask_password else self.password,
            "description": self.description,
            "is_default": self.is_default,
        }


def _load_source_config(source_id: str) -> Optional[DataSourceConfig]:
    """从环境变量加载指定 source_id 的连接配置。

    优先读取 MYSQL_*_<SOURCE_ID_UPPER> 格式，若全部缺失则回退到
    legacy MYSQL_SOURCE 体系（仅对 DEFAULT_SOURCE_ID 有效）。
    返回 None 表示该数据源未配置。
    """
    suffix = source_id.upper().replace("-", "_")

    def _env(key: str, fallback: str = "") -> str:
        return os.getenv(f"MYSQL_{key}_{suffix}", "").strip() or fallback

    host = _env("HOST")
    port_str = _env("PORT")
    db = _env("DB")
    user = _env("USER")

    # 如果专属变量为空，对默认数据源回退到 legacy 变量体系
    if not host and source_id == DEFAULT_SOURCE_ID:
        legacy_source = os.getenv("MYSQL_SOURCE", "test").lower()
        legacy_suffix = legacy_source.upper()

        def _legacy(key: str, fallback: str) -> str:
            return (os.getenv(f"MYSQL_{key}_{legacy_suffix}")
                    or os.getenv(f"MYSQL_{key}")
                    or os.getenv(f"PROD_DB_{key}", fallback))

        host     = _legacy("HOST",     "10.60.120.33")
        port_str = _legacy("PORT",     "3336")
        db       = _legacy("DB",       "cc_semi_mvp")
        user     = _legacy("USER",     "root")
        password = _legacy("PASSWORD", "")
    else:
        if not host:
            return None  # 该数据源未配置，跳过
        password = _env("PASSWORD")

    try:
        port = int(port_str) if port_str else 3306
    except ValueError:
        logger.warning("[DataSourceRegistry] 无效 port='%s' for source_id='%s'，使用默认 3306", port_str, source_id)
        port = 3306

    read_timeout = int(os.getenv("MYSQL_QUERY_TIMEOUT", "45"))

    return DataSourceConfig(
        source_id=source_id,
        host=host,
        port=port,
        db=db,
        user=user,
        password=password,
        read_timeout=read_timeout,
    )


class DataSourceRegistry:
    """数据源注册表 — 管理所有已知数据源的连接配置。

    数据源优先级:
      1. JSON 持久化文件 (data_sources_store.json) — 用户通过 API 管理的配置
      2. 环境变量 MYSQL_*_<SOURCE_ID_UPPER> — 系统级配置
      3. Legacy 环境变量 MYSQL_SOURCE — 向后兼容

    使用方法:
        registry = DataSourceRegistry.get_instance()
        cfg = registry.get(MES_PROD)
        kwargs = cfg.to_pymysql_kwargs()
    """

    _instance: Optional["DataSourceRegistry"] = None

    def __init__(self):
        self._configs: Dict[str, DataSourceConfig] = {}
        self._default_id: str = DEFAULT_SOURCE_ID
        self._load_all()

    @classmethod
    def get_instance(cls) -> "DataSourceRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """清除缓存实例（测试 / 配置重载时使用）。"""
        cls._instance = None

    # ── 加载 ──────────────────────────────────────────────────────────────

    def _load_all(self) -> None:
        """加载所有数据源：若 JSON store 存在则以其为权威列表，否则从环境变量发现。"""
        # 1. 若 JSON 持久化文件存在，直接以其为权威（避免 env fallback 重新注入已删除的数据源）
        if _STORE_PATH.exists():
            self._load_from_store()
        else:
            # JSON 不存在时，从环境变量自动发现（首次启动 / 迁移场景）
            known_sources: list = []
            extra = os.getenv("DATA_SOURCE_IDS", "")
            if extra:
                for sid in extra.split(","):
                    sid = sid.strip()
                    if sid and sid not in known_sources:
                        known_sources.append(sid)

            # 自动发现所有 MYSQL_HOST_<X> 环境变量对应的数据源
            for key, val in os.environ.items():
                if key.startswith("MYSQL_HOST_") and val.strip():
                    sid = key[len("MYSQL_HOST_"):].lower()
                    if sid and sid not in known_sources:
                        known_sources.append(sid)

            for sid in known_sources:
                cfg = _load_source_config(sid)
                if cfg is not None:
                    if not cfg.display_name:
                        cfg.display_name = sid.replace("_", " ").title()
                    self._configs[sid] = cfg
                    logger.debug("[DataSourceRegistry] 已注册数据源(env): %s → %s:%s/%s",
                                 sid, cfg.host, cfg.port, cfg.db)

        # 2. 同步 is_default 标记
        self._sync_default_flag()

        logger.info("[DataSourceRegistry] 已加载数据源: %s (默认: %s)",
                    list(self._configs.keys()), self._default_id)

    def _load_from_store(self) -> None:
        """从 JSON 持久化文件加载数据源配置（完整替换，JSON 即权威列表）。"""
        if not _STORE_PATH.exists():
            return
        try:
            data = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
            self._default_id = data.get("default_source_id", DEFAULT_SOURCE_ID)
            self._configs.clear()  # JSON 为权威，清除 env 阶段加载的条目
            for item in data.get("sources", []):
                sid = item.get("source_id", "").strip()
                if not sid:
                    continue
                cfg = DataSourceConfig(
                    source_id=sid,
                    display_name=item.get("display_name", sid),
                    host=item.get("host", ""),
                    port=int(item.get("port", 3306)),
                    db=item.get("db", ""),
                    user=item.get("user", ""),
                    password=item.get("password", ""),
                    description=item.get("description", ""),
                    read_timeout=int(item.get("read_timeout", 45)),
                )
                self._configs[sid] = cfg
                logger.debug("[DataSourceRegistry] 已注册数据源(json): %s → %s:%s/%s",
                             sid, cfg.host, cfg.port, cfg.db)
        except Exception as e:
            logger.warning("[DataSourceRegistry] JSON 加载失败: %s", e)

    def _save_to_store(self) -> None:
        """将当前配置持久化到 JSON 文件。"""
        data = {
            "default_source_id": self._default_id,
            "sources": [],
        }
        for cfg in self._configs.values():
            data["sources"].append({
                "source_id": cfg.source_id,
                "display_name": cfg.display_name or cfg.source_id,
                "host": cfg.host,
                "port": cfg.port,
                "db": cfg.db,
                "user": cfg.user,
                "password": cfg.password,
                "description": cfg.description,
                "read_timeout": cfg.read_timeout,
            })
        try:
            _STORE_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("[DataSourceRegistry] JSON 保存失败: %s", e)

    def _sync_default_flag(self) -> None:
        """同步每个 config 的 is_default 标记。"""
        for sid, cfg in self._configs.items():
            cfg.is_default = (sid == self._default_id)

    # ── 查询 ──────────────────────────────────────────────────────────────

    def get(self, source_id: str) -> DataSourceConfig:
        """获取数据源配置，不存在时抛出 KeyError。"""
        if source_id not in self._configs:
            raise KeyError(
                f"数据源 '{source_id}' 未配置。已知数据源: {list(self._configs.keys())}"
            )
        return self._configs[source_id]

    def get_or_default(self, source_id: Optional[str]) -> DataSourceConfig:
        """若 source_id 为 None 或未配置，返回默认数据源配置。"""
        if source_id and source_id in self._configs:
            return self._configs[source_id]
        return self._configs[self._default_id]

    def has(self, source_id: str) -> bool:
        return source_id in self._configs

    def all_ids(self) -> List[str]:
        return list(self._configs.keys())

    def list_all(self, mask_password: bool = True) -> List[dict]:
        """返回所有数据源配置列表（用于 API 响应）。"""
        return [cfg.to_dict(mask_password=mask_password)
                for cfg in self._configs.values()]

    @property
    def default_id(self) -> str:
        return self._default_id

    # ── 变更 ──────────────────────────────────────────────────────────────

    def add_or_update(self, source_id: str, **kwargs) -> DataSourceConfig:
        """新增或更新数据源配置并持久化。"""
        if source_id in self._configs:
            cfg = self._configs[source_id]
            for k, v in kwargs.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
        else:
            cfg = DataSourceConfig(
                source_id=source_id,
                display_name=kwargs.get("display_name", source_id),
                host=kwargs.get("host", ""),
                port=int(kwargs.get("port", 3306)),
                db=kwargs.get("db", ""),
                user=kwargs.get("user", ""),
                password=kwargs.get("password", ""),
                description=kwargs.get("description", ""),
                read_timeout=int(kwargs.get("read_timeout", 45)),
            )
            self._configs[source_id] = cfg
        self._save_to_store()
        self._sync_default_flag()
        return cfg

    def remove(self, source_id: str) -> None:
        """删除数据源配置并持久化。"""
        if source_id == self._default_id:
            raise ValueError(f"不能删除默认数据源 '{source_id}'，请先更改默认数据源")
        if source_id not in self._configs:
            raise KeyError(f"数据源 '{source_id}' 不存在")
        del self._configs[source_id]
        self._save_to_store()

    def set_default(self, source_id: str) -> None:
        """设置默认数据源并持久化。"""
        if source_id not in self._configs:
            raise KeyError(f"数据源 '{source_id}' 不存在")
        self._default_id = source_id
        self._sync_default_flag()
        self._save_to_store()
