"""
query_decomposer — 多步查询分解节点

将复杂的用户查询分解为可执行的子查询步骤。
例如: "对比本月和上月各产线的产量" →
  1. 查询本月各产线产量
  2. 查询上月各产线产量
  3. 合并对比

对于简单查询（单表、无对比、无多步逻辑），直接 passthrough。
"""

import json
import logging
from app.agent.state import AgentState
from app.agent.llm import get_agent_llm

logger = logging.getLogger(__name__)

# 需要分解的复杂查询特征
COMPLEX_INDICATORS = [
    "对比", "比较", "同比", "环比", "和…相比",
    "分别", "各自", "每个…的…和…",
    "趋势", "变化", "增长率", "下降率",
    "先…再…", "然后", "之后",
    "最高的…中", "排名前…的…的",
    "compare", "vs", "trend", "growth",
]


def _is_complex_query(user_input: str, query_plan: dict) -> bool:
    """判断是否为复杂查询（需要分解）"""
    user_lower = user_input.lower()

    # 关键词检测
    for indicator in COMPLEX_INDICATORS:
        if indicator in user_lower or indicator in user_input:
            return True

    # 多指标 + 多表联查的检测
    metrics = query_plan.get("metrics", [])
    if len(metrics) > 2:
        return True

    return False


def query_decomposer_node(state: AgentState) -> dict:
    """
    查询分解节点。

    - 简单查询 → passthrough（不修改 state）
    - 复杂查询 → 使用 LLM 分解为子步骤，将分解方案写入 query_plan

    输入: user_input, query_plan
    输出: query_plan (增强版，含 sub_queries)
    """
    user_input = state.get("user_input", "")
    query_plan = state.get("query_plan", {})

    # 简单查询直接跳过
    if not _is_complex_query(user_input, query_plan):
        logger.info("[query_decomposer] Simple query, skipping decomposition")
        return {}

    logger.info(f"[query_decomposer] Complex query detected, decomposing: "
                f"{user_input[:80]}...")

    try:
        # 获取 Schema 上下文
        from app.agent.tools.schema_tools import get_schema_context
        schema_context = get_schema_context.invoke({"user_input": user_input})

        llm = get_agent_llm()

        decompose_prompt = f"""你是一个 MES 系统的 SQL 查询专家。

用户提出了一个复杂的查询需求，需要你将其分解为可执行的子查询步骤。

{schema_context}

【用户查询】
{user_input}

【分解规则】
1. 每个子查询应该是一个独立可执行的 SQL 查询
2. 子查询按执行顺序排列
3. 如果子查询之间有依赖关系，在 depends_on 中标注
4. 对于对比/比较类查询，分别查询各部分数据
5. 如果查询足够简单（只需一个 SQL），返回单个子查询即可
6. 子查询的 description 用中文描述

【输出 JSON 格式】
{{
  "is_multi_step": true/false,
  "strategy": "对比分析/分步聚合/单步查询",
  "sub_queries": [
    {{
      "step": 1,
      "description": "查询描述",
      "focus": "本步骤关注的数据维度",
      "sql_hint": "可选的 SQL 构建提示",
      "depends_on": []
    }}
  ],
  "merge_strategy": "横向对比/纵向合并/独立展示"
}}

仅输出 JSON，不要包含其他文本。"""

        response = llm.invoke(decompose_prompt)
        content = response.content.strip()

        # 清理 markdown 代码块
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()
        if content.startswith("json"):
            content = content[4:].strip()

        decomposition = json.loads(content)

        if decomposition.get("is_multi_step"):
            sub_queries = decomposition.get("sub_queries", [])
            logger.info(f"[query_decomposer] Decomposed into "
                        f"{len(sub_queries)} sub-queries, "
                        f"strategy: {decomposition.get('strategy')}")

            # 将分解方案合并到 query_plan
            enhanced_plan = {**query_plan}
            enhanced_plan["decomposition"] = decomposition
            enhanced_plan["is_multi_step"] = True
            enhanced_plan["sub_queries"] = sub_queries
            enhanced_plan["merge_strategy"] = decomposition.get(
                "merge_strategy", "独立展示"
            )

            return {"query_plan": enhanced_plan}
        else:
            logger.info("[query_decomposer] LLM determined single-step query")
            return {}

    except json.JSONDecodeError as e:
        logger.warning(f"[query_decomposer] Failed to parse LLM response: {e}")
        return {}
    except Exception as e:
        logger.error(f"[query_decomposer] Error: {e}", exc_info=True)
        return {}
