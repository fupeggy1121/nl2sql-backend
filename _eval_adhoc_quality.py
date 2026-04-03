"""
即席路径 SQL 质量评估：with_hint vs without_hint
运行 90 条明确语义查询 + 10 条模糊查询，对比双路径 SQL 质量。

评估维度:
  table_accuracy: 实际使用的表与 expected_tables 的 F1
  column_accuracy: expected_columns 是否出现在 SQL 文本中
  syntax_valid:    SQL 能否成功执行（rows not None）
  no_hallucination: should_not_contain 中的词是否出现在 SQL

调用方式:
  .venv/bin/python _eval_adhoc_quality.py
  .venv/bin/python _eval_adhoc_quality.py --no-hint   # 强制禁用 pattern hint
  .venv/bin/python _eval_adhoc_quality.py --limit 20  # 只跑前N条
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from typing import List, Optional, Set

sys.path.insert(0, "/Users/fupeggy/NL2SQL")

from app.ontology.mapping import get_mapping
from app.services.mysql_executor import MySQLExecutor

# ── 评估数据集 ──────────────────────────────────────────────────────────────

@dataclass
class EvalCase:
    id: int
    query: str
    expected_tables: List[str]         # 期望 SQL 引用的表（F1 计算）
    expected_columns: List[str]        # 期望出现在 SELECT 中的列（文本匹配）
    should_not_contain: List[str] = field(default_factory=list)  # 不应出现的词（幻觉检测）
    ambiguous: bool = False            # True = 模糊查询，不纳入整体分数


EVAL_CASES: List[EvalCase] = [
    # ── 单表简单统计（15条）────────────────────────────────────────────────
    EvalCase(1, "查询本月各产品的批次数量",
             ["matrix_routerx_operation_lot"],
             ["product_id", "current_lot_code"],
             should_not_contain=["wafer"]),
    EvalCase(2, "统计各工艺站点当前在制批次数",
             ["matrix_routerx_operation_lot"],
             ["process_id", "status"],
             should_not_contain=[]),
    EvalCase(3, "查询本周新开批次列表",
             ["matrix_routerx_operation_lot"],
             ["current_lot_code", "gmt_create"],
             should_not_contain=[]),
    EvalCase(4, "各产品本月完成批次数量统计",
             ["matrix_routerx_operation_lot"],
             ["product_id"],
             should_not_contain=[]),
    EvalCase(5, "查询当前暂停（status=30）的批次列表",
             ["matrix_routerx_operation_lot"],
             ["status", "current_lot_code"],
             should_not_contain=[]),
    EvalCase(6, "统计各子批次的晶圆数量",
             ["matrix_routerx_operation_lot_wafer"],
             ["lot_id"],
             should_not_contain=[]),
    EvalCase(7, "查询最近7天创建的批次",
             ["matrix_routerx_operation_lot"],
             ["gmt_create", "current_lot_code"],
             should_not_contain=[]),
    EvalCase(8, "各工站本月处理的批次总数",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["process_code"],
             should_not_contain=[]),
    EvalCase(9, "查询process_status=200（完成）的批次数量",
             ["matrix_routerx_operation_lot"],
             ["process_status"],
             should_not_contain=[]),
    EvalCase(10, "统计各片篮当前承载的晶圆数量",
             ["matrix_routerx_operation_lot_wafer"],
             ["carrier_code"],
             should_not_contain=[]),
    EvalCase(11, "本月各状态批次数量汇总",
             ["matrix_routerx_operation_lot"],
             ["status"],
             should_not_contain=[]),
    EvalCase(12, "查询最近创建的10个批次",
             ["matrix_routerx_operation_lot"],
             ["current_lot_code", "gmt_create"],
             should_not_contain=[]),
    EvalCase(13, "各工艺路线当前批次分布",
             ["matrix_routerx_operation_lot"],
             ["parent_id"],
             should_not_contain=[]),
    EvalCase(14, "查询今日完成出站的批次列表",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["gmt_create"],
             should_not_contain=[]),
    EvalCase(15, "统计每个产品型号的平均批次晶圆数",
             ["matrix_routerx_operation_lot_wafer", "matrix_routerx_operation_lot"],
             ["lot_id"],
             should_not_contain=[]),

    # ── 多表 JOIN（20条）───────────────────────────────────────────────────
    EvalCase(16, "查询各工站名称及当前在制批次数",
             ["matrix_routerx_operation_lot", "matrix_routerx_config_process"],
             ["process_id", "name"],
             should_not_contain=[]),
    EvalCase(17, "查询批次号LOT-001的所有过站记录",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["lot_code", "operation_type"],
             should_not_contain=[]),
    EvalCase(18, "查各工站当前各状态晶圆数量分布",
             ["matrix_routerx_operation_lot_wafer", "matrix_routerx_operation_lot", "matrix_routerx_config_process"],
             ["status", "lot_id", "process_id"],
             should_not_contain=[]),
    EvalCase(19, "查询本月各出站批次（operation_type=9）的晶圆明细",
             ["matrix_routerx_operation_lot_batch_resume_log",
              "matrix_routerx_operation_lot_batch_resume_log_detail",
              "matrix_routerx_operation_lot_batch_resume_wafer_detail_log"],
             ["batch_resume_log_id", "batch_resume_detail_log_id", "wafer_id"],
             should_not_contain=[]),
    EvalCase(20, "查询最近进站（operation_type=8）记录并关联批次信息",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["operation_type", "lot_code"],
             should_not_contain=[]),
    EvalCase(21, "各工艺站点平均停留时间（从进站到出站）",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["process_code", "operation_type", "gmt_create"],
             should_not_contain=[]),
    EvalCase(22, "查询当前在制晶圆的工站分布",
             ["matrix_routerx_operation_lot_wafer", "matrix_routerx_operation_lot"],
             ["lot_id", "status"],
             should_not_contain=[]),
    EvalCase(23, "查询各批次从开批到现在的天数",
             ["matrix_routerx_operation_lot"],
             ["gmt_create", "current_lot_code"],
             should_not_contain=[]),
    EvalCase(24, "统计各产品过站次数排名",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["lot_code", "process_code"],
             should_not_contain=[]),
    EvalCase(25, "查询所有子批次及其对应主批次信息",
             ["matrix_routerx_operation_lot"],
             ["parent_id", "current_lot_code"],
             should_not_contain=[]),
    EvalCase(26, "查询包含返工晶圆的批次列表",
             ["matrix_routerx_operation_lot_batch_resume_wafer_detail_log"],
             ["wafer_type"],
             should_not_contain=[]),
    EvalCase(27, "各批次最后一次过站记录",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["lot_code", "gmt_create"],
             should_not_contain=[]),
    EvalCase(28, "查询今日出站批次及对应工站名称",
             ["matrix_routerx_operation_lot_batch_resume_log", "matrix_routerx_config_process"],
             ["operation_type", "process_code"],
             should_not_contain=[]),
    EvalCase(29, "统计各片篮承载批次的工站分布",
             ["matrix_routerx_operation_lot_wafer", "matrix_routerx_operation_lot"],
             ["carrier_code", "process_id"],
             should_not_contain=[]),
    EvalCase(30, "查询批次过站历史中连续两次退返的记录",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["lot_code", "operation_type"],
             should_not_contain=[]),
    EvalCase(31, "各工站本月进站出站批次对比",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["process_code", "operation_type"],
             should_not_contain=[]),
    EvalCase(32, "查询晶圆级别的NG记录及原因",
             ["matrix_routerx_operation_lot_batch_resume_wafer_detail_log"],
             ["wafer_type", "ng_code"],
             should_not_contain=[]),
    EvalCase(33, "查询各工艺站点配置信息",
             ["matrix_routerx_config_process"],
             ["name", "code", "type"],
             should_not_contain=[]),
    EvalCase(34, "统计各批次的总晶圆数和NG数",
             ["matrix_routerx_operation_lot_batch_resume_wafer_detail_log"],
             ["wafer_type", "batch_resume_detail_log_id"],
             should_not_contain=[]),
    EvalCase(35, "查询各批次子批次数量",
             ["matrix_routerx_operation_lot"],
             ["parent_id"],
             should_not_contain=[]),

    # ── 时间序列（15条）───────────────────────────────────────────────────
    EvalCase(36, "最近30天每日新开批次数量趋势",
             ["matrix_routerx_operation_lot"],
             ["gmt_create"],
             should_not_contain=[]),
    EvalCase(37, "最近7天各工站每日在制批次变化",
             ["matrix_routerx_operation_lot"],
             ["gmt_create", "process_id"],
             should_not_contain=[]),
    EvalCase(38, "本月每周过站总次数统计",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["gmt_create"],
             should_not_contain=[]),
    EvalCase(39, "过去3个月每月批次完成数量趋势",
             ["matrix_routerx_operation_lot"],
             ["process_status", "gmt_create"],
             should_not_contain=[]),
    EvalCase(40, "今日各小时进站批次数量",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["operation_type", "gmt_create"],
             should_not_contain=[]),
    EvalCase(41, "最近7天每天的NG晶圆数量",
             ["matrix_routerx_operation_lot_batch_resume_wafer_detail_log"],
             ["wafer_type", "gmt_create"],
             should_not_contain=[]),
    EvalCase(42, "本季度各月批次开工数量",
             ["matrix_routerx_operation_lot"],
             ["gmt_create"],
             should_not_contain=[]),
    EvalCase(43, "最近30天各工站在制批次日均数量",
             ["matrix_routerx_operation_lot"],
             ["process_id", "gmt_create"],
             should_not_contain=[]),
    EvalCase(44, "本月各日批次完成数量（process_status=200）",
             ["matrix_routerx_operation_lot"],
             ["process_status", "gmt_create"],
             should_not_contain=[]),
    EvalCase(45, "最近14天晶圆总数日变化趋势",
             ["matrix_routerx_operation_lot_wafer"],
             ["gmt_create"],
             should_not_contain=[]),
    EvalCase(46, "过去1个月每周NG批次数量",
             ["matrix_routerx_operation_lot_batch_resume_wafer_detail_log"],
             ["wafer_type", "gmt_create"],
             should_not_contain=[]),
    EvalCase(47, "最近7天各产品类型每日过站次数",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["gmt_create", "lot_code"],
             should_not_contain=[]),
    EvalCase(48, "今日到昨日在制批次数量变化对比",
             ["matrix_routerx_operation_lot"],
             ["status", "gmt_create"],
             should_not_contain=[]),
    EvalCase(49, "本月各工站每日产出批次数",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["process_code", "gmt_create"],
             should_not_contain=[]),
    EvalCase(50, "过去6个月批次总量及完成率月度趋势",
             ["matrix_routerx_operation_lot"],
             ["process_status", "gmt_create"],
             should_not_contain=[]),

    # ── 状态码过滤（15条）─────────────────────────────────────────────────
    EvalCase(51, "查询在进站中（process_status=40）的子批次列表",
             ["matrix_routerx_operation_lot"],
             ["process_status", "parent_id"],
             should_not_contain=[]),
    EvalCase(52, "查询所有已结批（status=90或process_status=200）的批次",
             ["matrix_routerx_operation_lot"],
             ["status"],
             should_not_contain=[]),
    EvalCase(53, "查询当前在制（status=50）的主批次数量",
             ["matrix_routerx_operation_lot"],
             ["status", "parent_id"],
             should_not_contain=[]),
    EvalCase(54, "查询operation_type=9（出站）的最新50条记录",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["operation_type"],
             should_not_contain=[]),
    EvalCase(55, "查询wafer_type为reject的晶圆列表",
             ["matrix_routerx_operation_lot_batch_resume_wafer_detail_log"],
             ["wafer_type"],
             should_not_contain=[]),
    EvalCase(56, "统计各operation_type的过站记录数量",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["operation_type"],
             should_not_contain=[]),
    EvalCase(57, "查询status=30（暂停）的子批次",
             ["matrix_routerx_operation_lot"],
             ["status", "parent_id"],
             should_not_contain=[]),
    EvalCase(58, "查询进站失败（operation_type=8且本月有异常）记录",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["operation_type", "gmt_create"],
             should_not_contain=[]),
    EvalCase(59, "统计各批次的NG晶圆占比",
             ["matrix_routerx_operation_lot_batch_resume_wafer_detail_log"],
             ["wafer_type", "batch_resume_detail_log_id"],
             should_not_contain=[]),
    EvalCase(60, "查询所有active（未删除）的子批次",
             ["matrix_routerx_operation_lot"],
             ["parent_id"],
             should_not_contain=[]),
    EvalCase(61, "查询operation_type=16（攒批）的最近记录",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["operation_type"],
             should_not_contain=[]),
    EvalCase(62, "统计各工站各状态的批次数量矩阵",
             ["matrix_routerx_operation_lot"],
             ["process_id", "status"],
             should_not_contain=[]),
    EvalCase(63, "查询process_status不为200（未完成）的批次",
             ["matrix_routerx_operation_lot"],
             ["process_status"],
             should_not_contain=[]),
    EvalCase(64, "查询所有返工（operation_type=12或13）相关记录",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["operation_type"],
             should_not_contain=[]),
    EvalCase(65, "统计各子批次的过站次数（按lot分组）",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["lot_code"],
             should_not_contain=[]),

    # ── 跨事件类型（15条）─────────────────────────────────────────────────
    EvalCase(66, "查询攒批操作（op=16）的源批次和目标批次对应关系",
             ["matrix_routerx_operation_lot_batch_resume_log",
              "matrix_routerx_operation_lot_batch_resume_log_detail"],
             ["operation_type", "batch_resume_log_id"],
             should_not_contain=[]),
    EvalCase(67, "查询拆批（operation_type=15）后产生的子批次",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["operation_type", "lot_code"],
             should_not_contain=[]),
    EvalCase(68, "查询开批到第一次进站的时间间隔",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["operation_type", "lot_code", "gmt_create"],
             should_not_contain=[]),
    EvalCase(69, "统计本月各类operation_type事件发生次数",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["operation_type"],
             should_not_contain=[]),
    EvalCase(70, "查询有NG记录的批次的完整过站历史",
             ["matrix_routerx_operation_lot_batch_resume_log",
              "matrix_routerx_operation_lot_batch_resume_wafer_detail_log"],
             ["lot_code", "operation_type", "wafer_type"],
             should_not_contain=[]),
    EvalCase(71, "查询片篮更换（op=17）记录及前后批次",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["operation_type", "lot_code"],
             should_not_contain=[]),
    EvalCase(72, "统计各批次的进站次数和出站次数差（滞留检测）",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["operation_type", "lot_code"],
             should_not_contain=[]),
    EvalCase(73, "查询本周发生返工（op=12）的批次列表",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["operation_type", "gmt_create"],
             should_not_contain=[]),
    EvalCase(74, "查询出站后未在48小时内再次进站的批次",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["operation_type", "lot_code", "gmt_create"],
             should_not_contain=[]),
    EvalCase(75, "统计各工站的在制时间（进站到出站平均时长）",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["process_code", "operation_type", "gmt_create"],
             should_not_contain=[]),
    EvalCase(76, "查询当月所有倒篮（op=3）操作记录",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["operation_type", "gmt_create"],
             should_not_contain=[]),
    EvalCase(77, "查询从开批到结批的完整生命周期记录",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["operation_type", "lot_code"],
             should_not_contain=[]),
    EvalCase(78, "统计各批次的NG发现工序分布",
             ["matrix_routerx_operation_lot_batch_resume_log",
              "matrix_routerx_operation_lot_batch_resume_wafer_detail_log"],
             ["process_code", "wafer_type"],
             should_not_contain=[]),
    EvalCase(79, "查询最近一次出站后状态未更新的批次",
             ["matrix_routerx_operation_lot_batch_resume_log",
              "matrix_routerx_operation_lot"],
             ["operation_type", "status"],
             should_not_contain=[]),
    EvalCase(80, "统计各批次在各工站的停留次数",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["lot_code", "process_code"],
             should_not_contain=[]),

    # ── 聚合+分组（10条）─────────────────────────────────────────────────
    EvalCase(81, "各工序站点平均加工批次数（按月）",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["process_code", "gmt_create"],
             should_not_contain=[]),
    EvalCase(82, "查询本月批次数量TOP10的工站",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["process_code"],
             should_not_contain=[]),
    EvalCase(83, "统计各产品本月过站总次数",
             ["matrix_routerx_operation_lot_batch_resume_log",
              "matrix_routerx_operation_lot"],
             ["lot_code"],
             should_not_contain=[]),
    EvalCase(84, "计算各工站的批次吞吐量（进出站对数）",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["process_code", "operation_type"],
             should_not_contain=[]),
    EvalCase(85, "按工站统计NG晶圆数量排名",
             ["matrix_routerx_operation_lot_batch_resume_log",
              "matrix_routerx_operation_lot_batch_resume_wafer_detail_log"],
             ["process_code", "wafer_type"],
             should_not_contain=[]),
    EvalCase(86, "各批次平均在制时间（天）排名",
             ["matrix_routerx_operation_lot"],
             ["gmt_create", "current_lot_code"],
             should_not_contain=[]),
    EvalCase(87, "按月汇总各状态的批次数量变化",
             ["matrix_routerx_operation_lot"],
             ["status", "gmt_create"],
             should_not_contain=[]),
    EvalCase(88, "查询批次数量超过平均值的工站",
             ["matrix_routerx_operation_lot"],
             ["process_id"],
             should_not_contain=[]),
    EvalCase(89, "统计各工站在制批次数量与完成批次数量对比",
             ["matrix_routerx_operation_lot", "matrix_routerx_config_process"],
             ["process_id", "status"],
             should_not_contain=[]),
    EvalCase(90, "查询各批次的首次进站工站",
             ["matrix_routerx_operation_lot_batch_resume_log"],
             ["lot_code", "process_code", "operation_type"],
             should_not_contain=[]),

    # ── 模糊查询（10条，单独评估，不纳入整体分数）──────────────────────
    EvalCase(91, "最近有问题的批次",
             [],  # 模糊，plausible_tables由人工判断
             [],
             ambiguous=True),
    EvalCase(92, "看一下生产情况",
             [],
             [],
             ambiguous=True),
    EvalCase(93, "哪些批次需要关注",
             [],
             [],
             ambiguous=True),
    EvalCase(94, "查一下昨天的数据",
             [],
             [],
             ambiguous=True),
    EvalCase(95, "最近产量怎么样",
             [],
             [],
             ambiguous=True),
    EvalCase(96, "有没有异常情况",
             [],
             [],
             ambiguous=True),
    EvalCase(97, "查查最近的良率",
             [],
             [],
             ambiguous=True),
    EvalCase(98, "生产线状态如何",
             [],
             [],
             ambiguous=True),
    EvalCase(99, "有问题的晶圆在哪里",
             [],
             [],
             ambiguous=True),
    EvalCase(100, "本月总结一下",
              [],
              [],
              ambiguous=True),
]


# ── SQL 生成（with/without hint）──────────────────────────────────────────

def gen_sql_with_hint(query: str) -> Optional[str]:
    """带 match_query_pattern hint 的 LLM SQL 生成（当前默认行为）"""
    from app.agents.analysis_agent.nodes.method_selector import _llm_gen_adhoc_sql
    result = _llm_gen_adhoc_sql(query)
    return result.get("sql") if result else None


def gen_sql_without_hint(query: str) -> Optional[str]:
    """禁用 pattern_hint 的 LLM SQL 生成"""
    from app.agents.analysis_agent.nodes.method_selector import _llm_gen_adhoc_sql
    from app.ontology import mapping as mapping_mod

    # monkey-patch: 临时让 match_query_pattern 返回 None
    orig = mapping_mod.MappingDictionary.match_query_pattern
    mapping_mod.MappingDictionary.match_query_pattern = lambda self, q: None
    try:
        result = _llm_gen_adhoc_sql(query)
    finally:
        mapping_mod.MappingDictionary.match_query_pattern = orig
    return result.get("sql") if result else None


# ── 评估指标 ──────────────────────────────────────────────────────────────

def _extract_tables_from_sql(sql: str) -> Set[str]:
    """从 SQL 文本中提取所有表名（FROM / JOIN 后面的词）"""
    pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    return {m.group(1).lower() for m in re.finditer(pattern, sql, re.IGNORECASE)}


def _f1(predicted: Set[str], expected: List[str]) -> float:
    if not expected:
        return 1.0  # 无期望表时不扣分
    expected_set = {t.lower() for t in expected}
    if not predicted:
        return 0.0
    tp = len(predicted & expected_set)
    precision = tp / len(predicted)
    recall = tp / len(expected_set)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _column_accuracy(sql: str, expected_columns: List[str]) -> float:
    if not expected_columns:
        return 1.0
    sql_lower = sql.lower()
    hits = sum(1 for col in expected_columns if col.lower() in sql_lower)
    return hits / len(expected_columns)


def _no_hallucination(sql: str, should_not_contain: List[str]) -> bool:
    sql_lower = sql.lower()
    for word in should_not_contain:
        if word.lower() in sql_lower:
            return False
    return True


def evaluate_sql(sql: Optional[str], case: EvalCase, exec_: MySQLExecutor) -> dict:
    if sql is None:
        return {"syntax_valid": False, "table_f1": 0.0, "col_acc": 0.0, "no_halluc": True, "rows": None}

    # syntax_valid: 执行不报错
    rows = exec_.execute_query(sql)
    syntax_valid = (rows is not None)

    tables_used = _extract_tables_from_sql(sql)
    return {
        "syntax_valid": syntax_valid,
        "table_f1": _f1(tables_used, case.expected_tables),
        "col_acc": _column_accuracy(sql, case.expected_columns),
        "no_halluc": _no_hallucination(sql, case.should_not_contain),
        "rows": len(rows) if rows else 0,
        "tables_used": sorted(tables_used),
    }


# ── 主流程 ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-hint", action="store_true", help="只跑 without_hint 路径")
    parser.add_argument("--limit", type=int, default=len(EVAL_CASES))
    parser.add_argument("--output", default="/tmp/eval_adhoc_results.json")
    args = parser.parse_args()

    exec_ = MySQLExecutor()
    if not exec_.connect():
        print("FATAL: 无法连接数据库")
        sys.exit(1)
    print(f"DB 连接成功，开始评估 {min(args.limit, len(EVAL_CASES))} 条查询...\n")

    cases = EVAL_CASES[:args.limit]
    results = []
    clear_cases = [c for c in cases if not c.ambiguous]
    ambig_cases = [c for c in cases if c.ambiguous]

    agg_with = {"syntax": [], "table_f1": [], "col_acc": [], "no_halluc": []}
    agg_without = {"syntax": [], "table_f1": [], "col_acc": [], "no_halluc": []}

    for i, case in enumerate(cases):
        tag = "[模糊]" if case.ambiguous else f"[{i+1}/{len(cases)}]"
        print(f"{tag} {case.query[:50]}")

        # with hint
        t0 = time.time()
        sql_with = gen_sql_with_hint(case.query)
        t_with = time.time() - t0

        # without hint
        t0 = time.time()
        sql_without = gen_sql_without_hint(case.query) if not args.no_hint else sql_with
        t_without = time.time() - t0

        score_with = evaluate_sql(sql_with, case, exec_)
        score_without = evaluate_sql(sql_without, case, exec_)

        row = {
            "id": case.id,
            "query": case.query,
            "ambiguous": case.ambiguous,
            "with_hint": {**score_with, "sql": sql_with, "latency_s": round(t_with, 1)},
            "without_hint": {**score_without, "sql": sql_without, "latency_s": round(t_without, 1)},
        }
        results.append(row)

        with_ok = "✓" if score_with["syntax_valid"] else "✗"
        without_ok = "✓" if score_without["syntax_valid"] else "✗"
        print(f"  with_hint: {with_ok} f1={score_with['table_f1']:.2f}  "
              f"without_hint: {without_ok} f1={score_without['table_f1']:.2f}")

        if not case.ambiguous:
            agg_with["syntax"].append(score_with["syntax_valid"])
            agg_with["table_f1"].append(score_with["table_f1"])
            agg_with["col_acc"].append(score_with["col_acc"])
            agg_with["no_halluc"].append(score_with["no_halluc"])
            agg_without["syntax"].append(score_without["syntax_valid"])
            agg_without["table_f1"].append(score_without["table_f1"])
            agg_without["col_acc"].append(score_without["col_acc"])
            agg_without["no_halluc"].append(score_without["no_halluc"])

    # ── 汇总 ──
    def avg(lst): return sum(lst) / len(lst) if lst else 0.0

    n = len(clear_cases)
    print(f"\n{'='*60}")
    print(f"评估完成（{n} 条明确查询 + {len(ambig_cases)} 条模糊查询）")
    print(f"\n{'指标':<20}{'with_hint':>12}{'without_hint':>14}{'差值':>10}")
    print("-" * 56)
    metrics = [
        ("syntax_valid", "syntax"),
        ("table_f1", "table_f1"),
        ("col_accuracy", "col_acc"),
        ("no_hallucination", "no_halluc"),
    ]
    summary = {}
    for label, key in metrics:
        w = avg(agg_with[key])
        wo = avg(agg_without[key])
        diff = wo - w
        arrow = "↑" if diff > 0.01 else ("↓" if diff < -0.01 else "≈")
        print(f"  {label:<18}{w:>10.3f}{wo:>14.3f}  {diff:+.3f} {arrow}")
        summary[label] = {"with_hint": round(w, 3), "without_hint": round(wo, 3), "diff": round(diff, 3)}

    # ── 延迟统计 ──
    all_latencies_with = [r["with_hint"]["latency_s"] for r in results]
    all_latencies_without = [r["without_hint"]["latency_s"] for r in results]

    def pct(lst, p):
        s = sorted(lst)
        idx = int(len(s) * p / 100)
        return s[min(idx, len(s) - 1)]

    print(f"\n{'='*60}")
    print("延迟统计（秒）:")
    print(f"  {'':18}{'with_hint':>10}{'without_hint':>14}")
    print(f"  {'avg':18}{avg(all_latencies_with):>10.1f}{avg(all_latencies_without):>14.1f}")
    print(f"  {'p50':18}{pct(all_latencies_with,50):>10.1f}{pct(all_latencies_without,50):>14.1f}")
    print(f"  {'p90':18}{pct(all_latencies_with,90):>10.1f}{pct(all_latencies_without,90):>14.1f}")
    print(f"  {'p99':18}{pct(all_latencies_with,99):>10.1f}{pct(all_latencies_without,99):>14.1f}")
    print(f"  {'max':18}{max(all_latencies_with):>10.1f}{max(all_latencies_without):>14.1f}")

    # Top-10 最慢查询
    top_slow = sorted(results, key=lambda r: r["with_hint"]["latency_s"], reverse=True)[:10]
    print("\n  Top-10 最慢查询（with_hint）:")
    for r in top_slow:
        print(f"    [{r['id']:3d}] {r['with_hint']['latency_s']:5.1f}s  {r['query'][:50]}")

    summary["latency"] = {
        "with_hint": {"avg": round(avg(all_latencies_with), 1),
                      "p50": pct(all_latencies_with, 50),
                      "p90": pct(all_latencies_with, 90),
                      "max": max(all_latencies_with)},
        "without_hint": {"avg": round(avg(all_latencies_without), 1),
                         "p50": pct(all_latencies_without, 50),
                         "p90": pct(all_latencies_without, 90),
                         "max": max(all_latencies_without)},
    }

    # 决策建议
    wo_syntax = avg(agg_without["syntax"])
    w_syntax = avg(agg_with["syntax"])
    print(f"\n{'='*60}")
    print("决策建议:")
    if avg(agg_without["table_f1"]) >= avg(agg_with["table_f1"]) * 0.95 and wo_syntax >= 0.9:
        print("  → without_hint 表现与 with_hint 相当，可以移除 match_query_pattern() 调用")
    elif avg(agg_without["table_f1"]) < avg(agg_with["table_f1"]) - 0.1:
        print("  → without_hint 比 with_hint 差超过10%，建议保留 hint（但提升 build_table_catalog 质量后重测）")
    else:
        print("  → 差距在 5-10%，建议提高 hint 置信度门槛（hits >= 2 才触发）后重测")

    # 保存结果
    final = {"summary": summary, "cases": results}
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存: {args.output}")


if __name__ == "__main__":
    main()
