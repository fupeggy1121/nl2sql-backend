"""
本体 TTL 版本管理器

功能：
- 上传新 TTL 文件时自动备份当前版本
- 维护版本历史（JSON 元数据 + TTL 快照）
- 支持回滚到任意历史版本
- 上传后自动触发热重载
"""

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.ontology.config import DEFAULT_TTL_PATH, ONTOLOGY_DATA_DIR

logger = logging.getLogger(__name__)

# 版本存储目录
VERSIONS_DIR = ONTOLOGY_DATA_DIR / "versions"
VERSION_INDEX_FILE = VERSIONS_DIR / "index.json"


def _ensure_dirs():
    """确保版本目录存在"""
    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _load_index() -> List[Dict[str, Any]]:
    """加载版本索引"""
    _ensure_dirs()
    if VERSION_INDEX_FILE.exists():
        return json.loads(VERSION_INDEX_FILE.read_text(encoding="utf-8"))
    return []


def _save_index(index: List[Dict[str, Any]]):
    """保存版本索引"""
    _ensure_dirs()
    VERSION_INDEX_FILE.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _next_version(index: List[Dict[str, Any]]) -> int:
    """下一个版本号"""
    if not index:
        return 1
    return max(v["version"] for v in index) + 1


def _snapshot_filename(version: int) -> str:
    return f"v{version:04d}.ttl"


def get_current_ttl() -> str:
    """读取当前 TTL 文件内容"""
    if not DEFAULT_TTL_PATH.exists():
        raise FileNotFoundError(f"TTL file not found: {DEFAULT_TTL_PATH}")
    return DEFAULT_TTL_PATH.read_text(encoding="utf-8")


def list_versions() -> List[Dict[str, Any]]:
    """列出所有历史版本（最新在前）"""
    index = _load_index()
    return sorted(index, key=lambda v: v["version"], reverse=True)


def get_version_detail(version: int) -> Optional[Dict[str, Any]]:
    """获取指定版本详情"""
    index = _load_index()
    for v in index:
        if v["version"] == version:
            return v
    return None


def get_version_content(version: int) -> Optional[str]:
    """读取指定版本的 TTL 内容"""
    detail = get_version_detail(version)
    if detail is None:
        return None
    snapshot_path = VERSIONS_DIR / detail["filename"]
    if not snapshot_path.exists():
        return None
    return snapshot_path.read_text(encoding="utf-8")


def save_new_version(
    ttl_content: str,
    message: str = "",
    author: str = "system",
) -> Dict[str, Any]:
    """
    保存新版本。

    1. 备份当前 TTL 为历史快照
    2. 写入新 TTL
    3. 更新版本索引
    4. 触发热重载

    Returns: 新版本的元数据
    """
    _ensure_dirs()
    index = _load_index()
    version = _next_version(index)

    # ── Step 1: 备份当前文件（如果存在且版本历史为空或内容有变化）──
    if DEFAULT_TTL_PATH.exists() and not index:
        # 首次上传：先把原始文件存为 v1
        old_content = DEFAULT_TTL_PATH.read_text(encoding="utf-8")
        init_version = 1
        init_snapshot = _snapshot_filename(init_version)
        (VERSIONS_DIR / init_snapshot).write_text(old_content, encoding="utf-8")
        index.append({
            "version": init_version,
            "filename": init_snapshot,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Initial version (auto-snapshot before first upload)",
            "author": "system",
            "size_bytes": len(old_content.encode("utf-8")),
        })
        version = init_version + 1

    # ── Step 2: 保存新 TTL 到版本目录 ──
    snapshot = _snapshot_filename(version)
    (VERSIONS_DIR / snapshot).write_text(ttl_content, encoding="utf-8")

    # ── Step 3: 覆盖当前文件 ──
    DEFAULT_TTL_PATH.write_text(ttl_content, encoding="utf-8")

    # ── Step 4: 更新索引 ──
    entry = {
        "version": version,
        "filename": snapshot,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message or f"Version {version}",
        "author": author,
        "size_bytes": len(ttl_content.encode("utf-8")),
    }
    index.append(entry)
    _save_index(index)

    # ── Step 5: 热重载 ──
    try:
        from app.ontology.loader import load_ontology
        from app.ontology.mapping import load_mapping
        load_ontology(force_reload=True)
        load_mapping(force_reload=True)
        logger.info("Hot-reload after version %d upload", version)
    except Exception as e:
        logger.warning("Hot-reload failed after upload: %s", e)

    logger.info("Saved ontology version %d (%d bytes)", version, entry["size_bytes"])
    return entry


def rollback_to_version(version: int) -> Dict[str, Any]:
    """
    回滚到指定版本。

    从版本快照恢复到当前 TTL，并创建新版本记录。
    """
    content = get_version_content(version)
    if content is None:
        raise ValueError(f"Version {version} not found or snapshot missing")

    entry = save_new_version(
        ttl_content=content,
        message=f"Rollback to version {version}",
        author="system",
    )
    logger.info("Rolled back to version %d → new version %d", version, entry["version"])
    return entry


def diff_versions(v1: int, v2: int) -> Dict[str, Any]:
    """简易diff: 行数变化统计"""
    c1 = get_version_content(v1)
    c2 = get_version_content(v2)
    if c1 is None or c2 is None:
        raise ValueError(f"Version {v1} or {v2} not found")

    lines1 = c1.splitlines()
    lines2 = c2.splitlines()

    set1 = set(lines1)
    set2 = set(lines2)

    return {
        "v1": v1,
        "v2": v2,
        "v1_lines": len(lines1),
        "v2_lines": len(lines2),
        "added": len(set2 - set1),
        "removed": len(set1 - set2),
        "unchanged": len(set1 & set2),
    }
