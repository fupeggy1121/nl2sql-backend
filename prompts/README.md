# Prompt Templates — NL2SQL Agent

本目录包含所有 Agent 节点和服务中使用的 LLM 提示词模板。

**目的**: 将提示词从代码中分离，便于非开发人员调优和版本管理。

## 文件清单

| 文件 | 来源模块 | 用途 |
|------|----------|------|
| `rag_chat.txt` | `app/agent/nodes/rag_chat.py` | RAG 知识问答 + 降级回答 |
| `query_decomposer.txt` | `app/agent/nodes/query_decomposer.py` | 复杂查询分解 |
| `sql_generator.txt` | `app/agent/nodes/sql_generator.py` + `app/agent/tools/nl2sql_tools.py` | SQL 生成、多步合并、自我修正 |
| `nl2sql_enhanced.txt` | `app/services/nl2sql_enhanced.py` | 增强版 NL→SQL 转换 |
| `intent_recognizer.txt` | `app/services/intent_recognizer.py` | 意图识别分类 |
| `chart_recommender.txt` | `app/services/chart_recommender.py` | 图表类型推荐 |

## 模板变量说明

模板中使用 `{variable_name}` 表示运行时变量，例如：
- `{user_input}` — 用户原始输入
- `{schema_context}` — 数据库 Schema 上下文
- `{context}` — RAG 检索到的知识库内容
- `{error}` — SQL 执行错误信息

## 调优指南

1. 编辑 `.txt` 文件中的提示词
2. 保持 `{variable_name}` 占位符不变
3. 测试修改后的效果
4. 提交到版本控制
