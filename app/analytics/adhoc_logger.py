"""
即席查询日志记录器

功能：每次即席路径（route_decision="adhoc"）执行成功后，
      将查询关键字段追加到 JSONL 日志文件中。

用途：积累一段时间的日志后，通过频次统计识别"高频查询 → skill 升级候选"。

日志格式（每行一条 JSON）::

    {
      "ts":            "2026-04-03T14:25:00.123",  # ISO 时间戳
      "user_input":    "查各工站可用载具",
      "route_decision": "adhoc",
      "generated_sql": "SELECT ...",
      "tables_used":   ["matrix_carrier_info"],
      "rows_returned": 42,
      "latency_ms":    230                          # data_loader 执行阶段耗时
    }

日志路径：<workspace>/logs/adhoc_queries.jsonl
          可通过环境变量 ADHOC_LOG_PATH 覆盖。

LLM SQL 非确定性备注：
  LLM 生成 SQL 存在非确定性——同一 prompt 偶尔产出有语法问题的 SQL。
  当前有 deterministic SQL fallback 兜底，不影响可用性。
  若未来要移除 deterministic SQL（标记 deprecated），需先统计
  一段时间内 LLM SQL 的 L1 失败率，确认 < 1% 再做决定。
  失败次数可通过此日志的 "llm_gen_failed": true 字段统计。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── 日志文件路径 ──────────────────────────────────────────────────────────────
_DEFAULT_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
_LOG_PATH: Optional[Path] = None


def _get_log_path() -> Path:
    global _LOG_PATH
    if _LOG_PATH is None:
        env_path = os.getenv("ADHOC_LOG_PATH")
        if env_path:
            _LOG_PATH = Path(env_path)
        else:
            _LOG_PATH = _DEFAULT_LOG_DIR / "adhoc_queries.jsonl"
    return _LOG_PATH


def log_adhoc_query(
    *,
    user_input: str,
    route_decision: str,
    generated_sql: str,
    tables_used: List[str],
    rows_returned: int,
    latency_ms: float,
    llm_gen_failed: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    将即席查询结果追加到 JSONL 日志文件。

    线程安全：每次写入独立 open/close，兼容多进程（append mode atomic on POSIX）。

    参数说明：
      llm_gen_failed: True 表示 LLM SQL 生成失败（已 fallback 到 deterministic SQL）。
                      用于统计 LLM L1 失败率。
    """
    entry: Dict[str, Any] = {
        "ts": datetime.now().isoformat(timespec="milliseconds"),
        "user_input": user_input,
        "route_decision": route_decision,
        "generated_sql": generated_sql,
        "tables_used": tables_used,
        "rows_returned": rows_returned,
        "latency_ms": round(latency_ms, 1),
    }
    if llm_gen_failed:
        entry["llm_gen_failed"] = True
    if extra:
        entry.update(extra)

    log_path = _get_log_path()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.debug(f"[adhoc_logger] logged: tables={tables_used}, rows={rows_returned}")
    except OSError as e:
        # 日志写入失败不应影响正常业务响应
        logger.warning(f"[adhoc_logger] write failed ({log_path}): {e}")
