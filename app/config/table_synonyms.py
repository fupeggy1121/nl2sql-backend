"""
Table / Ontology Class Synonym Mapping — Compatibility Shim
============================================================
旧版本直接维护物理表名 → 同义词的静态字典。
现已迁移至本体类 URI 架构（semi:Equipment 等），
真正的同义词数据由 ontology_synonyms.py 统一维护，
并持久化到 Supabase class_synonyms 表。

本文件保留原有公开 API（TABLE_SYNONYMS / map_table_name /
is_valid_table_name 等），将各函数代理到 ontology_synonyms，
以保证 ingest.py 等历史调用方无需修改。

架构变化:
  旧: physical_table  → synonyms   (如 'carriers' → ['载具', ...])
  新: semi:URI        → synonyms   (如 'semi:Carrier' → ['载具', ...])
"""
from __future__ import annotations

from app.config.ontology_synonyms import (
    CLASS_SYNONYMS,
    RELATION_SYNONYMS,
    get_synonym_to_uri_map,
    get_label_cn,
)

# ─── TABLE_SYNONYMS ───────────────────────────────────────────────────────────
# 格式与旧版保持兼容: {key: [synonyms]}
# key 已变为本体类 URI（semi:Equipment 等），而非物理表名。
# ingest.py 等使用方只需 for tn, syns in TABLE_SYNONYMS.items()，无感知变更。
TABLE_SYNONYMS: dict[str, list[str]] = {
    uri: list(info["synonyms"])
    for uri, info in {**CLASS_SYNONYMS, **RELATION_SYNONYMS}.items()
}

_SYNONYM_TO_TABLE_CACHE: dict[str, str] | None = None


def get_synonym_to_table_map() -> dict[str, str]:
    """同义词 → 本体类 URI 映射缓存（旧版返回物理表名，现返回 semi:URI）。"""
    global _SYNONYM_TO_TABLE_CACHE
    if _SYNONYM_TO_TABLE_CACHE is None:
        _SYNONYM_TO_TABLE_CACHE = {
            syn.lower(): uri
            for uri, info in {**CLASS_SYNONYMS, **RELATION_SYNONYMS}.items()
            for syn in info["synonyms"]
        }
    return _SYNONYM_TO_TABLE_CACHE


def map_table_name(keyword: str) -> str:
    """将关键词映射到本体类 URI（旧版返回物理表名）。

    Example:
        >>> map_table_name('片篮')
        'semi:Carrier'
        >>> map_table_name('unknown_table')
        'unknown_table'
    """
    return get_synonym_to_table_map().get(keyword.lower().strip(), keyword)


def is_valid_table_name(keyword: str) -> bool:
    """检查关键词是否可映射到某个本体 URI。

    Example:
        >>> is_valid_table_name('片篮')
        True
        >>> is_valid_table_name('semi:Carrier')
        True
        >>> is_valid_table_name('invalid_table')
        False
    """
    m = get_synonym_to_table_map()
    return keyword.lower().strip() in m or keyword in TABLE_SYNONYMS


def get_all_table_names() -> list[str]:
    """返回所有已定义的本体类 URI 列表（旧版返回物理表名）。"""
    return list(TABLE_SYNONYMS.keys())


def get_synonyms_for_table(table_name: str) -> list[str]:
    """获取某个 URI/表名的同义词列表。

    Example:
        >>> get_synonyms_for_table('semi:Carrier')
        ['载具', '载体', '片篮', ...]
    """
    return TABLE_SYNONYMS.get(table_name, [])
