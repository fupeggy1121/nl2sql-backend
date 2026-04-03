"""
Skill 文件加载器

扫描 skills/metrics/*.md (YAML frontmatter + Markdown body)，
支持客户覆盖: skills/overrides/{customer_id}/*.md
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).parent
_METRICS_DIR = _SKILLS_DIR / "metrics"
_OVERRIDES_DIR = _SKILLS_DIR / "overrides"

# frontmatter 分隔符
_FM_DELIMITER = "---"


@dataclass
class SkillDefinition:
    """解析后的 Skill 定义 — 仅包含计算方法论，不含物理数据源信息。

    物理表名、JOIN 路径、过滤条件等属于 Mapping 层 (MetricDefinition)。
    Skill 层只关注"如何计算"，不关注"数据从哪来"。
    """
    skill_name: str
    zh_names: List[str] = field(default_factory=list)
    compute_mode: str = "python_compute"
    standard_definition: str = ""
    formula: str = ""
    granularity: List[str] = field(default_factory=list)
    required_columns: List[str] = field(default_factory=list)  # Python Computer 必需列
    rn_order: str = ""                                          # ROW_NUMBER 排序方向（ASC/DESC）
    body: str = ""          # Markdown body（供 LLM 阅读）
    source_file: str = ""   # 来源文件路径
    is_override: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)  # 其余 frontmatter 字段


def _parse_yaml_value(value: str) -> Any:
    """简易 YAML 值解析（不依赖 PyYAML）"""
    value = value.strip()
    if value == "":
        return ""
    # 布尔
    if value.lower() in ("true", "yes"):
        return True
    if value.lower() in ("false", "no"):
        return False
    # 数值
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        pass
    # 去除外层引号
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def _parse_frontmatter(text: str) -> tuple[Dict[str, Any], str]:
    """
    解析 YAML frontmatter + Markdown body。
    不依赖 python-frontmatter / PyYAML，手动解析简单 YAML。

    Returns: (metadata_dict, markdown_body)
    """
    lines = text.split("\n")

    # 寻找 frontmatter 边界
    if not lines or lines[0].strip() != _FM_DELIMITER:
        return {}, text

    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == _FM_DELIMITER:
            end_idx = i
            break

    if end_idx == -1:
        return {}, text

    fm_lines = lines[1:end_idx]
    body = "\n".join(lines[end_idx + 1:]).strip()

    # 解析简单 YAML（支持标量、列表、多行字符串）
    meta: Dict[str, Any] = {}
    current_key: Optional[str] = None
    current_list: Optional[List[str]] = None
    current_block: Optional[List[str]] = None
    block_mode = False  # | 多行字符串模式

    for line in fm_lines:
        stripped = line.strip()

        # 空行
        if not stripped:
            if block_mode and current_block is not None:
                current_block.append("")
            continue

        # 列表项
        if stripped.startswith("- ") and current_key is not None:
            if current_list is None:
                current_list = []
            val = stripped[2:].strip()
            # 去引号
            if (val.startswith('"') and val.endswith('"')) or \
               (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            current_list.append(val)
            continue

        # 多行块继续
        if block_mode and current_block is not None and (line.startswith("  ") or line.startswith("\t")):
            current_block.append(line.rstrip())
            continue

        # 保存前一个 key 的值
        if current_key is not None:
            if current_list is not None:
                meta[current_key] = current_list
            elif block_mode and current_block is not None:
                meta[current_key] = "\n".join(current_block).strip()
            current_list = None
            current_block = None
            block_mode = False

        # 新的 key: value
        match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.*)', stripped)
        if match:
            current_key = match.group(1)
            raw_value = match.group(2).strip()

            if raw_value == "|":
                # 多行字符串
                block_mode = True
                current_block = []
            elif raw_value == "" or raw_value is None:
                # 值在后续行（列表或块）
                pass
            else:
                meta[current_key] = _parse_yaml_value(raw_value)
                current_key = None  # 已赋值，重置
        else:
            # 无法解析的行，跳过
            if block_mode and current_block is not None:
                current_block.append(line.rstrip())

    # 处理最后一个 key
    if current_key is not None:
        if current_list is not None:
            meta[current_key] = current_list
        elif block_mode and current_block is not None:
            meta[current_key] = "\n".join(current_block).strip()

    return meta, body


class SkillLoader:
    """
    Skill 加载器 — 启动时扫描 skills/metrics/*.md,
    支持客户覆盖 (skills/overrides/{customer_id}/*.md)
    """

    def __init__(self):
        self._skills: Dict[str, SkillDefinition] = {}
        self._loaded = False

    def load_all(self) -> Dict[str, SkillDefinition]:
        """扫描并加载所有标准 skill 文件"""
        self._skills.clear()

        if not _METRICS_DIR.exists():
            logger.warning(f"[SkillLoader] metrics dir not found: {_METRICS_DIR}")
            return self._skills

        for md_file in sorted(_METRICS_DIR.glob("*.md")):
            try:
                skill = self._load_file(md_file, is_override=False)
                if skill:
                    self._skills[skill.skill_name] = skill
                    logger.info(f"[SkillLoader] loaded skill: {skill.skill_name} ({len(skill.zh_names)} zh_names)")
            except Exception as e:
                logger.error(f"[SkillLoader] failed to load {md_file.name}: {e}")

        self._loaded = True
        logger.info(f"[SkillLoader] loaded {len(self._skills)} standard skills")
        return self._skills

    def get_skill(self, name: str, customer_id: Optional[str] = None) -> Optional[SkillDefinition]:
        """
        获取指标 skill。优先查找客户覆盖，其次标准 skill。

        :param name: skill_name (如 "first_pass_yield")
        :param customer_id: 客户 ID（None=使用标准 skill）
        """
        if not self._loaded:
            self.load_all()

        # 1) 客户覆盖
        if customer_id:
            override_dir = _OVERRIDES_DIR / customer_id
            override_file = override_dir / f"{name}.md"
            if override_file.exists():
                try:
                    skill = self._load_file(override_file, is_override=True)
                    if skill:
                        logger.info(f"[SkillLoader] using override: {customer_id}/{name}")
                        return skill
                except Exception as e:
                    logger.warning(f"[SkillLoader] override load failed {override_file}: {e}")

        # 2) 标准 skill
        return self._skills.get(name)

    def find_by_zh_name(self, zh_name: str) -> Optional[SkillDefinition]:
        """通过中文名称查找 skill"""
        if not self._loaded:
            self.load_all()

        best_match: Optional[SkillDefinition] = None
        best_len = 0

        for skill in self._skills.values():
            for name in skill.zh_names:
                if name in zh_name and len(name) > best_len:
                    best_match = skill
                    best_len = len(name)

        return best_match

    def list_skills(self) -> List[SkillDefinition]:
        """列出所有已加载的标准 skill"""
        if not self._loaded:
            self.load_all()
        return list(self._skills.values())

    def _load_file(self, path: Path, is_override: bool) -> Optional[SkillDefinition]:
        """解析单个 skill markdown 文件"""
        content = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(content)

        skill_name = meta.get("skill_name", "")
        if not skill_name:
            logger.warning(f"[SkillLoader] missing skill_name in {path.name}")
            return None

        # 已知字段（仅方法论相关，不含物理数据源字段）
        known_keys = {
            "skill_name", "zh_names", "compute_mode", "standard_definition",
            "formula", "granularity", "required_columns", "rn_order",
        }
        extra = {k: v for k, v in meta.items() if k not in known_keys}

        return SkillDefinition(
            skill_name=skill_name,
            zh_names=meta.get("zh_names", []),
            compute_mode=meta.get("compute_mode", "python_compute"),
            standard_definition=meta.get("standard_definition", ""),
            formula=meta.get("formula", ""),
            granularity=meta.get("granularity", []),
            required_columns=meta.get("required_columns", []),
            rn_order=meta.get("rn_order", ""),
            body=body,
            source_file=str(path),
            is_override=is_override,
            extra=extra,
        )


# ── 模块级便捷实例 ──
_default_loader: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    """获取全局 SkillLoader 单例"""
    global _default_loader
    if _default_loader is None:
        _default_loader = SkillLoader()
        _default_loader.load_all()
    return _default_loader
