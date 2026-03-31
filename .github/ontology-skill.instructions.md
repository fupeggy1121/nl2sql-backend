---
applyTo: "**"
---

# Ontology Builder Skill — Copilot 自动调用规则

## 何时自动调用本技能

**当用户用自然语言描述以下任意意图时，Copilot 必须自动调用本体建模技能（Ontology Builder Skill），而不是手动编辑 TTL 或 mapping JSON 文件：**

### 触发关键词（任意匹配）

- 描述**添加/增加/新增**一个类、实体、概念、设备类型、工站类型、物料类型
- 描述**修改/更新/调整**某个本体类的属性、注释、父类、映射表
- 描述**添加/定义**一条关系（`hasSomething`, `belongsTo`, `isPartOf` 等）
- 描述**添加/扩展**值映射（状态枚举、设备状态、批次状态等）
- 描述**添加数据属性**（某个类新增一个字段/列/属性）
- 使用"本体"、"TTL"、"owl"、"mapping"、"语义模型"、"映射字典"等词汇
- 描述物理表与语义类之间的新映射关系
- 询问本体健康状况、覆盖率、未映射关系等诊断信息

## 调用流程（Copilot 必须遵循）

1. **识别意图**：确认用户在描述本体变更需求
2. **调用 NL 全流程**：使用 `OntologyNLAssistant.process()` 方法
3. **展示结果**：向用户呈现 spec、preview、commit 结果及诊断报告
4. **确认/修正**：如果 preview 有 errors，向用户说明并询问是否 force 提交

## 代码入口

```python
# 完整流程（推荐）
from app.ontology.skill_assistant import nl_process
result = nl_process(user_request, auto_commit=True)

# 只预览，不提交
from app.ontology.skill_assistant import nl_preview
result = nl_preview(user_request)

# 只转换为 spec，不执行
from app.ontology.skill_assistant import nl_to_spec
result = nl_to_spec(user_request)

# 诊断当前健康状况
from app.ontology.skill import diagnose_ontology
diag = diagnose_ontology()
```

## API 端点（后端已运行时）

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/ontology-skill/nl-process` | 自然语言全流程 |
| POST | `/api/ontology-skill/nl-preview` | 自然语言预览（不提交） |
| POST | `/api/ontology-skill/nl-to-spec` | 自然语言转 spec JSON |
| GET  | `/api/ontology-skill/diagnose`   | 本体健康诊断 |
| POST | `/api/ontology-skill/preview`    | 结构化 spec 预览 |
| POST | `/api/ontology-skill/commit`     | 结构化 spec 提交 |

## 关键文件位置

```
app/ontology/
  skill.py              # 核心技能引擎（Staged Builder）
  skill_assistant.py    # NL → OntologySpec LLM 转换器
  skill_cli.py          # CLI 入口
  data/
    semi-cim-ontology.ttl    # OWL 本体定义（自动维护）
    mapping_prod.json         # 物理映射字典（自动维护）
    mapping_changelog.jsonl   # 变更历史
    versions/                 # TTL 版本快照
```

## OntologySpec 结构参考

```json
{
  "message": "变更说明",
  "author": "用户名",
  "classes": [{
    "uri": "semi:ClassName",
    "label": "中文名(EnglishName)",
    "comment": "语义描述",
    "parent_uri": "semi:ParentClass",
    "physical_table": "table_name",
    "primary_key": "id",
    "label_cn": "中文名",
    "key_columns": ["id", "code", "status"],
    "properties": {"semi:hasCode": "code_column"}
  }],
  "relations": [{
    "uri": "semi:relationName",
    "domain_uri": "semi:Source",
    "range_uri": "semi:Target",
    "strategy": "ForeignKey",
    "join_logic": {
      "source_table": "src_table",
      "source_key": "fk_column",
      "target_table": "tgt_table",
      "target_key": "id"
    }
  }],
  "data_properties": [{
    "uri": "semi:hasPropName",
    "domain_uris": ["semi:ClassName"],
    "range_type": "xsd:string"
  }],
  "value_mappings": [{
    "domain": "semi:StatusDomain",
    "semantic_value": "StatusKey",
    "physical_condition": "status = 1"
  }]
}
```

## 安全规则

- 提交前**必须**先调用 `preview()`，有 `error` 时不得自动提交（需用户确认 `force=True`）
- `warning` 级别不阻断提交，只需在回复中提醒用户
- 所有写操作均为原子操作（.tmp + rename），失败时自动回滚内存状态
- TTL 每次提交自动创建版本快照，支持回滚
