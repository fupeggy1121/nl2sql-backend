#!/usr/bin/env python3
"""
generate_relation_mappings.py
==============================
从 mapping_prod.json 的 key_columns + key_column_comments 中自动推断高置信度
ForeignKey 关系，可选地通过 LLM 辅助分析中低置信度候选，生成 relation_mappings 草稿。

用法:
  # 纯规则推断（不需要 LLM，速度快）
  python generate_relation_mappings.py

  # 开启 LLM 辅助分析中置信度候选（需要 DEEPSEEK_API_KEY）
  python generate_relation_mappings.py --llm

  # 指定置信度阈值（只输出 high + medium）
  python generate_relation_mappings.py --min-confidence medium

  # 直接将结果合并写入 mapping_prod.json（高置信度自动合并，其余标注 TODO）
  python generate_relation_mappings.py --merge

输出:
  relation_mappings_draft.json   — 完整草稿（含三档置信度条目）
  relation_mappings_high.json    — 仅高置信度条目，可直接审查后合并
"""

import json
import os
import re
import sys
import argparse
import logging
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("gen_relation")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

# ------------------------------------------------------------------
# 路径
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
MAPPING_FILE = BASE_DIR / "app/ontology/data/mapping_prod.json"
DRAFT_FILE   = BASE_DIR / "relation_mappings_draft.json"
HIGH_FILE    = BASE_DIR / "relation_mappings_high.json"

# ------------------------------------------------------------------
# FK 列名后缀规则（优先级从高到低）
# ------------------------------------------------------------------
FK_SUFFIXES = [
    ("_id",   "high"),    # equipment_id → 精确 FK
    ("_code", "medium"),  # equipment_code → 可能是软性关联
    ("_no",   "medium"),  # lot_no → 可能是软性关联
    ("_num",  "low"),
    ("_key",  "low"),
]

# 跳过这些通用列（非外键）
SKIP_COLUMNS = {
    "id", "created_at", "updated_at", "gmt_create", "gmt_update",
    "create_user_id", "update_user_id", "operator_id", "user_id",
    "create_by", "update_by", "deleted", "version", "trace_id",
    "sort", "remark", "remark_id", "sequence", "order_no",
}

# 正则：从注释中提取被引用对象（"设备id" → "设备"）
COMMENT_REF_PATTERNS = [
    re.compile(r"^(.{1,8})[Ii][Dd]$"),           # 设备id / lot_id
    re.compile(r"^(.{1,8})的?\s*[Ii][Dd]"),       # 批次的ID
    re.compile(r"关联(.{1,8})"),                   # 关联批次
    re.compile(r"(.{1,8})(编号|号码|代码|编码)"),   # 批次编号
]


# ------------------------------------------------------------------
# 数据加载
# ------------------------------------------------------------------

def load_mapping(path: Path) -> Tuple[List[Dict], Dict[str, Dict], Dict[str, List[Dict]]]:
    """
    加载 mapping_prod.json，返回：
      object_mappings_list   — 原始列表
      table_by_name          — physical_table → entry
      tables_by_prefix       — 表名前缀 → [entry]（用于模糊匹配）
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("object_mappings", [])
    table_by_name: Dict[str, Dict] = {}
    tables_by_prefix: Dict[str, List[Dict]] = defaultdict(list)

    for entry in entries:
        tname = entry.get("physical_table")
        if not tname:
            continue
        table_by_name[tname] = entry
        # 建立前缀索引：取下划线分隔的各前缀段
        parts = tname.split("_")
        for i in range(1, len(parts) + 1):
            prefix = "_".join(parts[:i])
            tables_by_prefix[prefix].append(entry)

    return entries, table_by_name, dict(tables_by_prefix)


# ------------------------------------------------------------------
# 候选 FK 推断
# ------------------------------------------------------------------

def strip_fk_suffix(col: str) -> Tuple[Optional[str], str]:
    """
    从列名中剥离 FK 后缀，返回 (推断的被引用表名段, 置信度)。
    例：equipment_id → ("equipment", "high")
         accy_life_model_id → ("accy_life_model", "high")
         equipment_code → ("equipment", "medium")
    """
    for suffix, confidence in FK_SUFFIXES:
        if col.endswith(suffix) and col != suffix:
            ref = col[:-len(suffix)]
            # 忽略太短的推断（如 'a_id' → 'a'）
            if len(ref) < 2:
                continue
            return ref, confidence
    return None, "none"


def find_referenced_table(
    ref_name: str,
    table_by_name: Dict[str, Dict],
    tables_by_prefix: Dict[str, List[Dict]],
    comment: str = "",
) -> Tuple[Optional[Dict], str]:
    """
    根据推断的引用表名找到目标 entry，返回 (entry, 细化置信度)。

    匹配策略（按优先级）:
      1. exact:            ref_name == physical_table
      2. exact_plural:     ref_name + 's' / ref_name[:-1]
      3. prefix_unique:    tables_by_prefix[ref_name] 恰好 1 条
      4. comment_hint:     注释中含中文 → 对照 label_cn 匹配
    """
    # 1. 精确匹配
    if ref_name in table_by_name:
        return table_by_name[ref_name], "high"

    # 2. 复数/单数变形
    for variant in [ref_name + "s", ref_name + "es",
                    ref_name[:-1] if ref_name.endswith("s") else None]:
        if variant and variant in table_by_name:
            return table_by_name[variant], "high"

    # 3. 前缀唯一匹配
    candidates = tables_by_prefix.get(ref_name, [])
    if len(candidates) == 1:
        return candidates[0], "medium"
    if len(candidates) > 1:
        # 优先找complete match的子集
        exact = [c for c in candidates if c["physical_table"] == ref_name or
                 c["physical_table"].startswith(ref_name + "_")]
        if len(exact) == 1:
            return exact[0], "medium"

    # 4. 注释中找中文关键词，对比 label_cn
    if comment:
        for pattern in COMMENT_REF_PATTERNS:
            m = pattern.search(comment)
            if m:
                keyword = m.group(1).strip()
                if len(keyword) >= 2:
                    # 在所有表的 label_cn 中搜索
                    for entry in table_by_name.values():
                        label = entry.get("label_cn", "")
                        if keyword in label or label in keyword:
                            return entry, "medium"

    return None, "none"


# ------------------------------------------------------------------
# 主推断逻辑
# ------------------------------------------------------------------

class RelationCandidate:
    __slots__ = ["source_table", "source_key", "target_table", "target_key",
                 "confidence", "logic_relation", "description", "comment",
                 "source_pk"]

    def __init__(self, source_table, source_key, target_table, target_key,
                 confidence, description="", comment="", source_pk="id"):
        self.source_table = source_table
        self.source_key = source_key
        self.target_table = target_table
        self.target_key = target_key
        self.confidence = confidence   # high / medium / low
        self.description = description
        self.comment = comment
        self.source_pk = source_pk
        # 自动生成 logic_relation
        src_short = source_table.replace("_", "").title()[:12]
        tgt_short = target_table.split("_")[0].title()
        col_short = source_key.replace("_id", "").replace("_code", "").title()[:10]
        self.logic_relation = f"semi:{src_short}RelatesTo{tgt_short}"

    def to_mapping_entry(self) -> Dict:
        note = f"[AUTO-GENERATED] confidence={self.confidence}"
        if self.comment:
            note += f" | col_comment: {self.comment}"
        if self.confidence != "high":
            note += " | ⚠ TODO: 请人工验证此关系是否正确"
        return {
            "logic_relation": self.logic_relation,
            "description": self.description or f"{self.source_table}.{self.source_key} → {self.target_table}",
            "strategy": "ForeignKey",
            "confidence": self.confidence,
            "join_logic": {
                "source_table": self.source_table,
                "source_key": self.source_key,
                "target_table": self.target_table,
                "target_key": "id",
                "note": note
            }
        }


def infer_relations(
    entries: List[Dict],
    table_by_name: Dict[str, Dict],
    tables_by_prefix: Dict[str, List[Dict]],
    min_confidence: str = "medium",
) -> List[RelationCandidate]:
    """
    遍历所有 object_mappings 的 key_columns，推断外键关系。
    """
    confidence_rank = {"high": 3, "medium": 2, "low": 1}
    min_rank = confidence_rank.get(min_confidence, 2)

    candidates: List[RelationCandidate] = []
    # 去重: (source_table, source_key) → 已处理
    seen: Set[Tuple[str, str]] = set()

    for entry in entries:
        source_table = entry.get("physical_table")
        if not source_table:
            continue
        source_pk = entry.get("primary_key", "id") or "id"
        cols = entry.get("key_columns", [])
        comments = entry.get("key_column_comments", {})

        for col in cols:
            if col in SKIP_COLUMNS or col == source_pk:
                continue
            if (source_table, col) in seen:
                continue

            ref_name, suffix_conf = strip_fk_suffix(col)
            if not ref_name or confidence_rank.get(suffix_conf, 0) < min_rank:
                continue

            # 不要自引用
            if ref_name == source_table or source_table.startswith(ref_name):
                continue

            comment = comments.get(col, "")
            target_entry, match_conf = find_referenced_table(
                ref_name, table_by_name, tables_by_prefix, comment
            )

            if not target_entry:
                continue  # 找不到目标表，跳过

            # 综合两段置信度取低
            final_conf = suffix_conf if confidence_rank.get(suffix_conf, 0) <= confidence_rank.get(match_conf, 0) else match_conf
            if confidence_rank.get(final_conf, 0) < min_rank:
                continue

            seen.add((source_table, col))
            target_table = target_entry["physical_table"]
            target_pk = target_entry.get("primary_key", "id") or "id"

            # 构建描述
            src_label = entry.get("label_cn", source_table)
            tgt_label = target_entry.get("label_cn", target_table)
            col_short = col.replace("_id", "").replace("_code", "")
            description = f"{src_label}（{source_table}）通过 {col} 关联 {tgt_label}（{target_table}）"

            cand = RelationCandidate(
                source_table=source_table,
                source_key=col,
                target_table=target_table,
                target_key=target_pk,
                confidence=final_conf,
                description=description,
                comment=comment,
                source_pk=source_pk,
            )
            candidates.append(cand)

    # 按置信度排序：high → medium → low
    candidates.sort(key=lambda c: (-confidence_rank.get(c.confidence, 0), c.source_table))
    logger.info(
        "推断完成: high=%d, medium=%d, low=%d",
        sum(1 for c in candidates if c.confidence == "high"),
        sum(1 for c in candidates if c.confidence == "medium"),
        sum(1 for c in candidates if c.confidence == "low"),
    )
    return candidates


# ------------------------------------------------------------------
# LLM 辅助分析（可选）
# ------------------------------------------------------------------

def llm_review_candidates(
    candidates: List[RelationCandidate],
    table_by_name: Dict[str, Dict],
) -> List[RelationCandidate]:
    """
    将中置信度候选批量发给 LLM，让其判断是否为真实外键关系并给出描述。
    需要 DEEPSEEK_API_KEY 环境变量。
    """
    try:
        import openai
    except ImportError:
        logger.warning("openai 库未安装，跳过 LLM 辅助分析")
        return candidates

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        logger.warning("DEEPSEEK_API_KEY 未设置，跳过 LLM 辅助分析")
        return candidates

    medium_candidates = [c for c in candidates if c.confidence == "medium"]
    if not medium_candidates:
        return candidates

    logger.info(f"发送 {len(medium_candidates)} 条中置信度候选给 LLM 分析...")

    # 批量化：每次发送最多 30 条
    from openai import OpenAI
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com/v1",
    )

    BATCH_SIZE = 30
    updated_map: Dict[Tuple[str, str], str] = {}  # (source_table, col) → "confirm" / "reject" / "unsure"

    for i in range(0, len(medium_candidates), BATCH_SIZE):
        batch = medium_candidates[i: i + BATCH_SIZE]
        items_str = "\n".join(
            f"{j+1}. 表 `{c.source_table}` 的列 `{c.source_key}`（注释: {c.comment or '无'}）"
            f" → 推断引用 `{c.target_table}`"
            for j, c in enumerate(batch)
        )
        prompt = f"""以下是从 MES（制造执行系统）数据库 cc_semi_mvp 中自动推断的外键关系候选，请逐条判断：

{items_str}

对每条给出：
- confirm：该列确实是引用目标表的外键
- reject：该列不是外键（如只是业务关联码、不强制约束）
- unsure：无法确定

直接返回 JSON 数组，格式：
[{{"index":1,"result":"confirm","note":"可选备注"}},...]
只输出 JSON，不要其他文字。"""

        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=1000,
            )
            raw = resp.choices[0].message.content.strip()
            # 提取 JSON
            json_match = re.search(r'\[.*\]', raw, re.DOTALL)
            if json_match:
                results = json.loads(json_match.group())
                for item in results:
                    idx = item.get("index", 0) - 1
                    if 0 <= idx < len(batch):
                        c = batch[idx]
                        updated_map[(c.source_table, c.source_key)] = item.get("result", "unsure")
        except Exception as e:
            logger.warning(f"LLM 分析批次 {i//BATCH_SIZE+1} 失败: {e}")

    # 更新置信度：confirm → high, reject → 从列表移除, unsure → 保持 medium
    new_candidates = []
    for c in candidates:
        key = (c.source_table, c.source_key)
        if c.confidence == "medium":
            verdict = updated_map.get(key, "unsure")
            if verdict == "confirm":
                c.confidence = "high"
                c.to_mapping_entry()  # 更新 note
                new_candidates.append(c)
            elif verdict == "reject":
                logger.info(f"LLM 拒绝: {c.source_table}.{c.source_key} → {c.target_table}")
                continue
            else:
                new_candidates.append(c)
        else:
            new_candidates.append(c)

    return new_candidates


# ------------------------------------------------------------------
# 合并写入 mapping_prod.json
# ------------------------------------------------------------------

def merge_into_mapping(
    mapping_path: Path,
    candidates: List[RelationCandidate],
    only_high: bool = False,
) -> None:
    """
    将高置信度（或全部）候选合并写入 mapping_prod.json 的 relation_mappings 字段。
    已存在的条目不替换。
    """
    with open(mapping_path, encoding="utf-8") as f:
        data = json.load(f)

    existing_relations = data.get("relation_mappings", [])
    existing_keys = {
        (r["join_logic"].get("source_table"), r["join_logic"].get("source_key"))
        for r in existing_relations
        if r.get("strategy") == "ForeignKey" and r.get("join_logic")
    }

    added = 0
    for c in candidates:
        if only_high and c.confidence != "high":
            entry = c.to_mapping_entry()
            entry["join_logic"]["note"] = "⚠ TODO: 中置信度，请人工确认后移除此标注"
            existing_relations.append(entry)
            added += 1
        elif (c.source_table, c.source_key) not in existing_keys:
            existing_relations.append(c.to_mapping_entry())
            added += 1

    data["relation_mappings"] = existing_relations

    # 原子写入
    tmp = mapping_path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(mapping_path)

    logger.info(f"已合并 {added} 条 relation_mappings 到 {mapping_path}")


# ------------------------------------------------------------------
# 主入口
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="自动推断 relation_mappings 草稿")
    parser.add_argument("--llm", action="store_true", help="启用 LLM 辅助分析中置信度候选")
    parser.add_argument(
        "--min-confidence", choices=["high", "medium", "low"],
        default="medium", help="最低置信度阈值（默认 medium）"
    )
    parser.add_argument(
        "--merge", action="store_true",
        help="将高置信度结果直接合并写入 mapping_prod.json，中置信度加 TODO 标注"
    )
    parser.add_argument(
        "--mapping-file", type=Path, default=MAPPING_FILE,
        help="mapping JSON 文件路径（默认 app/ontology/data/mapping_prod.json）"
    )
    args = parser.parse_args()

    # 加载数据
    logger.info(f"加载映射文件: {args.mapping_file}")
    entries, table_by_name, tables_by_prefix = load_mapping(args.mapping_file)
    logger.info(f"共 {len(entries)} 条 object_mappings，{len(table_by_name)} 个物理表")

    # 推断
    candidates = infer_relations(entries, table_by_name, tables_by_prefix, args.min_confidence)

    # LLM 辅助
    if args.llm:
        candidates = llm_review_candidates(candidates, table_by_name)

    if not candidates:
        logger.warning("未推断出任何候选关系，请检查 key_columns 数据质量。")
        return

    # 输出统计
    high   = [c for c in candidates if c.confidence == "high"]
    medium = [c for c in candidates if c.confidence == "medium"]
    low    = [c for c in candidates if c.confidence == "low"]

    print(f"\n{'='*60}")
    print(f"推断结果统计:")
    print(f"  🟢 高置信度 (high)   : {len(high):>4} 条  — 可直接审查后使用")
    print(f"  🟡 中置信度 (medium)  : {len(medium):>4} 条  — 需人工确认")
    print(f"  🔴 低置信度 (low)     : {len(low):>4}  条  — 仅供参考")
    print(f"{'='*60}\n")

    # 写入草稿文件
    all_entries = [c.to_mapping_entry() for c in candidates]
    high_entries = [c.to_mapping_entry() for c in high]

    with open(DRAFT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "description": "auto-generated relation_mappings draft — review before merging",
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "counts": {"high": len(high), "medium": len(medium), "low": len(low)},
            "relation_mappings": all_entries,
        }, f, ensure_ascii=False, indent=2)
    logger.info(f"完整草稿已写入: {DRAFT_FILE}")

    with open(HIGH_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "description": "HIGH confidence only — ready for review",
            "relation_mappings": high_entries,
        }, f, ensure_ascii=False, indent=2)
    logger.info(f"高置信度草稿已写入: {HIGH_FILE}")

    # 打印高置信度样本
    print("高置信度样例（前 20 条）:")
    for c in high[:20]:
        print(f"  {c.source_table}.{c.source_key:30s} → {c.target_table}")

    if len(high) > 20:
        print(f"  ... 及另外 {len(high)-20} 条，详见 {HIGH_FILE}")

    # 合并写入
    if args.merge:
        merge_into_mapping(args.mapping_file, candidates, only_high=False)
        logger.info("--merge 完成，请使用 git diff 查看变更")
    else:
        print(f"\n提示: 若确认草稿无误，运行以下命令合并写入:")
        print(f"  python generate_relation_mappings.py --merge")
        print(f"  python generate_relation_mappings.py --merge --llm  # 同时启用 LLM 辅助")


if __name__ == "__main__":
    main()
