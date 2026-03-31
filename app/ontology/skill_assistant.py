"""
本体建模自然语言助手 (Ontology NL Assistant)

职责：
  1. 接收用户的自然语言描述（如"添加一个机械臂类，继承自设备类"）
  2. 加载当前本体上下文（类列表、关系列表、值域列表）作为 LLM 背景知识
  3. 调用 LLM 将自然语言转换为结构化 OntologySpec JSON
  4. 自动执行 preview → commit → diagnose 全流程
  5. 返回结构化结果（含变更详情、校验问题、诊断报告）

这是让 Copilot/用户 用一句话就能修改本体模型的核心桥梁。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── System Prompt ────────────────────────────────────────────────────

_SYSTEM_PROMPT = """你是一个半导体MES系统的本体建模专家，专门负责维护基于OWL的语义本体（SEMI CIM Ontology）及其与MySQL物理表的映射字典。

你的任务是：根据用户的自然语言描述，将其转换为结构化的 OntologySpec JSON，用于更新本体模型。

## OntologySpec JSON 格式

```json
{
  "message": "本次变更的简要说明",
  "author": "nlp_assistant",
  "classes": [
    {
      "uri": "semi:ClassName",
      "label": "中文名(EnglishName)",
      "comment": "类的业务语义描述",
      "parent_uri": "semi:ParentClass",
      "physical_table": "physical_table_name",
      "primary_key": "id",
      "label_cn": "中文名",
      "display_column": "code_column",
      "key_columns": ["id", "code", "status"],
      "properties": {
        "semi:hasCode": "code_column"
      },
      "virtual": false,
      "note": "备注"
    }
  ],
  "relations": [
    {
      "uri": "semi:relationName",
      "label": "关系中文名",
      "comment": "关系语义描述",
      "domain_uri": "semi:SourceClass",
      "range_uri": "semi:TargetClass",
      "strategy": "ForeignKey",
      "description": "物理实现描述",
      "join_logic": {
        "source_table": "source_table",
        "source_key": "foreign_key_column",
        "target_table": "target_table",
        "target_key": "id"
      }
    }
  ],
  "data_properties": [
    {
      "uri": "semi:hasPropertyName",
      "label": "属性中文名",
      "comment": "属性描述",
      "domain_uris": ["semi:ClassName"],
      "range_type": "xsd:string"
    }
  ],
  "value_mappings": [
    {
      "domain": "semi:StatusDomainName",
      "semantic_value": "StatusValue",
      "description": "状态描述",
      "physical_condition": "status_column = 1",
      "applies_to_table": "table_name",
      "applies_to_column": "status_column"
    }
  ]
}
```

## 关系策略（strategy）说明

- `ForeignKey`: 标准外键，join_logic 需要 source_table/source_key/target_table/target_key
- `JoinTable`: 多对多中间表，join_logic 需要额外 bridge_table 字段
- `Indirect`: 多跳间接关联，join_logic 包含 path 数组
- `Recursive`: 自关联（树形），join_logic 包含 table/self_key/parent_key
- `Virtual`: 纯语义抽象，无物理 JOIN，join_logic 为空对象
- `Denormalized`: 非规范化存储（如 JSON 字段内嵌）

## 规则

1. URI 格式必须是 `semi:CamelCaseName`，不能有空格
2. label 格式：`中文名(EnglishName)` 或只有中文
3. label_cn 只包含中文部分
4. 如果用户只描述语义（没有提到物理表），设置 virtual=true
5. 如果用户描述了物理表结构，填写 physical_table 和 key_columns
6. 只输出 JSON，不要有任何其他文字说明
7. 如果用户的描述不涉及某个类型（如没提到数据属性），该数组留空 []
8. 值映射（value_mappings）的格式：physical_values 是物理值数组，或 physical_condition 是 SQL 条件片段（二选一）
"""

_USER_PROMPT_TEMPLATE = """## 当前本体上下文

### 已有语义类（可作为 parent_uri 或 domain/range）：
{existing_classes}

### 已有对象属性（关系）：
{existing_relations}

### 已有值映射域：
{existing_value_domains}

---

## 用户需求

{user_request}

---

请将上述需求转换为 OntologySpec JSON（只输出 JSON，不要有任何解释文字）："""


def _extract_json(text: str) -> Optional[Dict]:
    """从 LLM 输出中提取 JSON（处理 markdown 代码块包裹的情况）"""
    # 去除 markdown 代码块
    text = text.strip()
    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if code_block:
        text = code_block.group(1).strip()

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试找到第一个 { 到最后一个 } 之间的内容
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
    return None


def _build_ontology_context(mapping_file=None) -> Dict[str, str]:
    """从当前 mapping + TTL 中提取上下文字符串"""
    from app.ontology.skill import OntologyBuilderSkill

    skill = OntologyBuilderSkill(mapping_file=mapping_file)
    skill.load()

    # 用 mapping 的 object_mappings 作为已知类列表
    om_list = skill._mapping_raw.get("object_mappings", [])
    class_lines = []
    for om in om_list[:60]:  # 限制长度
        lc = om.get("logic_class", "")
        label = om.get("label_cn", "")
        table = om.get("physical_table") or "(virtual)"
        virtual_flag = " ✓virtual" if om.get("virtual") else ""
        class_lines.append(f"  {lc}  [{label}]  → {table}{virtual_flag}")

    # 关系列表（只取前 50 条）
    rm_list = skill._mapping_raw.get("relation_mappings", [])
    rel_lines = []
    for rm in rm_list[:50]:
        uri = rm.get("logic_relation", "")
        domain = rm.get("domain_class", "")
        rng = rm.get("range_class", "")
        strategy = rm.get("strategy", "")
        rel_lines.append(f"  {uri}  ({domain} → {rng})  [{strategy}]")

    # 值域列表
    vm_dict = skill._mapping_raw.get("value_mappings", {})
    domain_lines = []
    for domain, vals in vm_dict.items():
        if isinstance(vals, dict):
            val_keys = [k for k in vals.keys() if not k.startswith("_")]
            domain_lines.append(f"  {domain}: {', '.join(val_keys[:8])}")

    return {
        "existing_classes": "\n".join(class_lines) if class_lines else "（暂无）",
        "existing_relations": "\n".join(rel_lines) if rel_lines else "（暂无）",
        "existing_value_domains": "\n".join(domain_lines) if domain_lines else "（暂无）",
    }


class OntologyNLAssistant:
    """
    自然语言 → OntologySpec → 执行 全流程助手

    Usage:
        assistant = OntologyNLAssistant()
        result = assistant.process("添加一个机械臂类，继承自Equipment，物理表 robot_arms")
        print(result)
    """

    def __init__(self, mapping_file=None):
        self._mapping_file = mapping_file

    def nl_to_spec(self, user_request: str) -> Dict[str, Any]:
        """
        将自然语言转换为 OntologySpec JSON（不执行变更）。

        Returns:
            {
              "success": bool,
              "spec": dict | None,       # OntologySpec JSON
              "raw_llm_output": str,     # LLM 原始输出
              "error": str | None
            }
        """
        # 加载上下文
        try:
            ctx = _build_ontology_context(self._mapping_file)
        except Exception as e:
            logger.warning("[nl_assistant] Failed to load context: %s", e)
            ctx = {
                "existing_classes": "（加载失败）",
                "existing_relations": "（加载失败）",
                "existing_value_domains": "（加载失败）",
            }

        prompt = _USER_PROMPT_TEMPLATE.format(
            user_request=user_request,
            **ctx,
        )

        # 调用 LLM
        try:
            from app.services.llm_provider import get_llm_provider
            llm = get_llm_provider()
            raw = llm.generate(prompt=prompt, system_prompt=_SYSTEM_PROMPT)
        except Exception as e:
            return {
                "success": False,
                "spec": None,
                "raw_llm_output": "",
                "error": f"LLM call failed: {e}",
            }

        # 提取 JSON
        spec = _extract_json(raw)
        if spec is None:
            return {
                "success": False,
                "spec": None,
                "raw_llm_output": raw,
                "error": "LLM output is not valid JSON",
            }

        return {
            "success": True,
            "spec": spec,
            "raw_llm_output": raw,
            "error": None,
        }

    def preview(self, user_request: str) -> Dict[str, Any]:
        """
        NL → spec → preview（不执行变更，返回预览结果）

        Returns:
            { spec, preview_result, nl_to_spec_error }
        """
        nl_result = self.nl_to_spec(user_request)
        if not nl_result["success"]:
            return {
                "success": False,
                "stage": "nl_to_spec",
                "error": nl_result["error"],
                "raw_llm_output": nl_result["raw_llm_output"],
            }

        spec_dict = nl_result["spec"]

        from app.ontology.skill import preview_from_dict
        preview_result = preview_from_dict(spec_dict, mapping_file=self._mapping_file)

        return {
            "success": True,
            "spec": spec_dict,
            "preview": preview_result.to_dict(),
            "has_errors": preview_result.has_errors,
        }

    def process(
        self,
        user_request: str,
        auto_commit: bool = True,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        全流程：NL → spec → preview → (commit) → diagnose

        Args:
            user_request: 自然语言描述
            auto_commit: 是否在无 error 时自动提交（默认 True）
            force: 是否在有 error 时强制提交

        Returns:
            完整的流程结果字典
        """
        # Step 1: NL → spec
        nl_result = self.nl_to_spec(user_request)
        if not nl_result["success"]:
            return {
                "success": False,
                "stage": "nl_to_spec",
                "error": nl_result["error"],
                "raw_llm_output": nl_result.get("raw_llm_output", ""),
                "spec": None,
                "preview": None,
                "commit": None,
                "diagnose": None,
            }

        spec_dict = nl_result["spec"]

        # Step 2: preview
        from app.ontology.skill import OntologyBuilderSkill, _parse_spec_dict
        skill = OntologyBuilderSkill(mapping_file=self._mapping_file)
        skill.load()
        parsed_spec = _parse_spec_dict(spec_dict)
        skill.stage(parsed_spec)
        preview_result = skill.preview()

        result: Dict[str, Any] = {
            "success": False,
            "stage": "preview",
            "spec": spec_dict,
            "preview": preview_result.to_dict(),
            "has_errors": preview_result.has_errors,
            "commit": None,
            "diagnose": None,
        }

        # Step 3: commit
        if auto_commit and (not preview_result.has_errors or force):
            commit_result = skill.commit(force=force)
            result["commit"] = commit_result.to_dict()
            result["success"] = commit_result.success
            result["stage"] = "commit"

            # Step 4: diagnose（仅在 commit 成功时）
            if commit_result.success:
                try:
                    diag_skill = OntologyBuilderSkill(mapping_file=self._mapping_file).load()
                    result["diagnose"] = diag_skill.diagnose()
                    result["stage"] = "done"
                except Exception as e:
                    logger.warning("[nl_assistant] diagnose failed: %s", e)
                    result["diagnose"] = {"error": str(e)}
        elif preview_result.has_errors:
            result["success"] = False
            result["stage"] = "blocked_by_errors"
            result["error"] = (
                f"Preview found {preview_result.summary['errors']} error(s). "
                "Set force=True to override."
            )
        else:
            # auto_commit=False: 只返回 preview，不提交
            result["success"] = True
            result["stage"] = "preview_only"

        return result


# ─── 模块级便捷函数 ───────────────────────────────────────────────

def nl_to_spec(user_request: str, mapping_file=None) -> Dict[str, Any]:
    """自然语言 → OntologySpec（不执行）"""
    return OntologyNLAssistant(mapping_file=mapping_file).nl_to_spec(user_request)


def nl_preview(user_request: str, mapping_file=None) -> Dict[str, Any]:
    """自然语言 → 预览变更（不执行）"""
    return OntologyNLAssistant(mapping_file=mapping_file).preview(user_request)


def nl_process(
    user_request: str,
    auto_commit: bool = True,
    force: bool = False,
    mapping_file=None,
) -> Dict[str, Any]:
    """自然语言 → 全流程（preview + commit + diagnose）"""
    return OntologyNLAssistant(mapping_file=mapping_file).process(
        user_request, auto_commit=auto_commit, force=force
    )
