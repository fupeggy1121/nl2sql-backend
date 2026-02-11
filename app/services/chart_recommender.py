"""
图表类型智能推荐服务
基于 SQL 结构、数据特征、查询意图综合判断最优 ECharts 图表类型
支持规则引擎 + LLM 双模式
"""

import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ─── 图表类型常量 ────────────────────────────────────
CHART_TABLE = 'table'
CHART_BAR = 'bar'
CHART_LINE = 'line'
CHART_PIE = 'pie'
CHART_SCATTER = 'scatter'
CHART_CARD = 'card'       # 单值 KPI 卡片
CHART_GROUPED_BAR = 'grouped_bar'

# ─── 时间类型字段关键词 ────────────────────────────────
TIME_KEYWORDS = {
    'date', 'time', 'datetime', 'timestamp', 'created_at', 'updated_at',
    'created_time', 'update_time', 'start_time', 'end_time', 'day', 'month',
    'year', 'week', 'hour', 'minute', 'period', 'shift_date', 'production_date',
    'record_date', 'report_date', 'log_time', 'occur_time',
}

# ─── 分类/维度字段关键词 ───────────────────────────────
CATEGORY_KEYWORDS = {
    'type', 'status', 'category', 'name', 'level', 'group', 'class',
    'department', 'line', 'station', 'shift', 'model', 'product', 'region',
    'equipment', 'machine', 'area', 'zone', 'team', 'grade', 'priority',
}


class ChartRecommender:
    """图表类型智能推荐器"""

    def __init__(self, llm_provider=None):
        self.llm_provider = llm_provider

    # ─── 主入口 ──────────────────────────────────────
    def recommend(
        self,
        sql: str,
        data: List[Dict[str, Any]],
        query_intent: Optional[Dict[str, Any]] = None,
        use_llm: bool = True,
    ) -> Dict[str, Any]:
        """
        综合推荐图表类型

        Returns:
            {
                "type": "bar",
                "title": "各设备可用数量统计",
                "xAxisField": "equipment_name",
                "yAxisField": "count",
                "seriesField": null,
                "confidence": 0.9,
                "reason": "两列 (类别+数值) 适合柱状图展示"
            }
        """
        # 1. 提取数据特征
        features = self._extract_features(sql, data)
        logger.info(f"Chart features: cols={features['col_count']}, rows={features['row_count']}, "
                     f"time_cols={features['time_cols']}, num_cols={features['numeric_cols']}, "
                     f"cat_cols={features['category_cols']}")

        # 2. 规则引擎推荐
        rule_result = self._rule_based_recommend(features, query_intent)

        # 3. 如果开启 LLM 且置信度不够高，用 LLM 进行二次验证/修正
        if use_llm and self.llm_provider and rule_result.get('confidence', 0) < 0.85:
            try:
                llm_result = self._llm_recommend(sql, features, query_intent)
                if llm_result and llm_result.get('confidence', 0) > rule_result.get('confidence', 0):
                    llm_result['reason'] = f"[AI] {llm_result.get('reason', '')}"
                    return llm_result
            except Exception as e:
                logger.warning(f"LLM chart recommendation failed, using rule-based: {e}")

        return rule_result

    # ─── 数据特征提取 ─────────────────────────────────
    def _extract_features(self, sql: str, data: List[Dict]) -> Dict[str, Any]:
        row_count = len(data)
        if row_count == 0:
            return {
                'row_count': 0, 'col_count': 0, 'columns': [],
                'time_cols': [], 'numeric_cols': [], 'category_cols': [],
                'string_cols': [], 'has_aggregation': False,
                'has_group_by': False, 'has_order_by': False,
                'is_single_value': False,
            }

        columns = list(data[0].keys())
        col_count = len(columns)

        # 按列分析数据类型
        time_cols, numeric_cols, category_cols, string_cols = [], [], [], []

        for col in columns:
            col_lower = col.lower()
            # 时间列
            if any(kw in col_lower for kw in TIME_KEYWORDS):
                time_cols.append(col)
                continue
            # 采样前 10 行判断类型
            sample = [row[col] for row in data[:10] if row.get(col) is not None]
            if not sample:
                string_cols.append(col)
                continue
            if all(isinstance(v, (int, float)) for v in sample):
                numeric_cols.append(col)
            elif any(kw in col_lower for kw in CATEGORY_KEYWORDS):
                category_cols.append(col)
            else:
                # 尝试检查值的唯一数 — 低基数视为分类
                unique_vals = set(str(v) for v in sample)
                if len(unique_vals) <= min(10, row_count * 0.5):
                    category_cols.append(col)
                else:
                    string_cols.append(col)

        # SQL 特征
        sql_upper = sql.upper() if sql else ''
        has_agg = bool(re.search(r'\b(COUNT|SUM|AVG|MIN|MAX)\s*\(', sql_upper))
        has_group = bool(re.search(r'\bGROUP\s+BY\b', sql_upper))
        has_order = bool(re.search(r'\bORDER\s+BY\b', sql_upper))

        # 单值检测（如 SELECT COUNT(*)）
        is_single_value = (row_count == 1 and col_count == 1)

        return {
            'row_count': row_count,
            'col_count': col_count,
            'columns': columns,
            'time_cols': time_cols,
            'numeric_cols': numeric_cols,
            'category_cols': category_cols,
            'string_cols': string_cols,
            'has_aggregation': has_agg,
            'has_group_by': has_group,
            'has_order_by': has_order,
            'is_single_value': is_single_value,
        }

    # ─── 规则引擎 ─────────────────────────────────────
    def _rule_based_recommend(
        self, features: Dict[str, Any], intent: Optional[Dict] = None
    ) -> Dict[str, Any]:
        f = features
        row_count = f['row_count']
        col_count = f['col_count']
        time_cols = f['time_cols']
        numeric_cols = f['numeric_cols']
        category_cols = f['category_cols']

        # 默认 fallback
        result = {
            'type': CHART_TABLE,
            'title': '查询结果',
            'xAxisField': None,
            'yAxisField': None,
            'seriesField': None,
            'confidence': 0.5,
            'reason': '默认表格展示',
        }

        # ── 规则 1: 空数据 ──
        if row_count == 0:
            result.update(type=CHART_TABLE, confidence=1.0, reason='无数据，使用表格')
            return result

        # ── 规则 2: 单值聚合 (如 COUNT=238) → card ──
        if f['is_single_value']:
            col = f['columns'][0]
            result.update(
                type=CHART_CARD,
                title=self._gen_title_for_single_value(col, intent),
                yAxisField=col,
                confidence=0.95,
                reason='单值聚合结果，使用 KPI 卡片'
            )
            return result

        # ── 规则 3: 1 行多列 (多指标聚合) → card / pie ──
        if row_count == 1 and len(numeric_cols) >= 2:
            result.update(
                type=CHART_PIE,
                title=self._gen_title(intent, '多指标分布'),
                xAxisField=None,
                yAxisField=None,
                confidence=0.8,
                reason='单行多数值列，使用饼图展示分布'
            )
            return result

        # ── 规则 4: 时间列 + 数值列 → line 趋势图 ──
        if time_cols and numeric_cols:
            y_field = numeric_cols[0]
            series = numeric_cols[1] if len(numeric_cols) > 1 else None
            result.update(
                type=CHART_LINE,
                title=self._gen_title(intent, f'{y_field} 变化趋势'),
                xAxisField=time_cols[0],
                yAxisField=y_field,
                seriesField=series,
                confidence=0.92,
                reason='包含时间字段和数值字段，使用折线图展示趋势'
            )
            return result

        # ── 规则 5: 分类列 + 1 个数值列 + 少量行 → bar ──
        if category_cols and len(numeric_cols) == 1 and row_count <= 30:
            result.update(
                type=CHART_BAR,
                title=self._gen_title(intent, f'按 {category_cols[0]} 统计 {numeric_cols[0]}'),
                xAxisField=category_cols[0],
                yAxisField=numeric_cols[0],
                confidence=0.9,
                reason='类别 + 数值，使用柱状图'
            )
            return result

        # ── 规则 6: 分类列 + 多数值列 → grouped_bar ──
        if category_cols and len(numeric_cols) >= 2 and row_count <= 30:
            result.update(
                type=CHART_GROUPED_BAR,
                title=self._gen_title(intent, f'按 {category_cols[0]} 多指标对比'),
                xAxisField=category_cols[0],
                yAxisField=numeric_cols[0],
                seriesField=None,  # 前端遍历所有数值列
                confidence=0.85,
                reason='类别 + 多数值列，使用分组柱状图'
            )
            return result

        # ── 规则 7: 两列（分类+数值）且行数 <= 8 → pie ──
        if col_count == 2 and len(numeric_cols) == 1 and row_count <= 8:
            non_num = [c for c in f['columns'] if c not in numeric_cols]
            result.update(
                type=CHART_PIE,
                title=self._gen_title(intent, f'{numeric_cols[0]} 分布'),
                xAxisField=non_num[0] if non_num else None,
                yAxisField=numeric_cols[0],
                confidence=0.88,
                reason='两列且行数少，使用饼图展示占比'
            )
            return result

        # ── 规则 8: 两数值列 → scatter ──
        if len(numeric_cols) >= 2 and (not category_cols) and (not time_cols):
            result.update(
                type=CHART_SCATTER,
                title=self._gen_title(intent, f'{numeric_cols[0]} vs {numeric_cols[1]}'),
                xAxisField=numeric_cols[0],
                yAxisField=numeric_cols[1],
                confidence=0.75,
                reason='两个数值列无分类维度，使用散点图'
            )
            return result

        # ── 规则 9: 超过 20 行详细记录 → table ──
        if row_count > 20:
            result.update(
                type=CHART_TABLE,
                title=self._gen_title(intent, '查询明细'),
                confidence=0.85,
                reason=f'返回 {row_count} 行详细记录，默认使用表格'
            )
            return result

        # ── 规则 10: 聚合 + GROUP BY 无时间列 → bar ──
        if f['has_aggregation'] and f['has_group_by'] and not time_cols:
            x = category_cols[0] if category_cols else (f['string_cols'][0] if f['string_cols'] else f['columns'][0])
            y = numeric_cols[0] if numeric_cols else f['columns'][-1]
            result.update(
                type=CHART_BAR,
                title=self._gen_title(intent, f'分组统计'),
                xAxisField=x,
                yAxisField=y,
                confidence=0.82,
                reason='聚合 + 分组查询，使用柱状图'
            )
            return result

        return result

    # ─── LLM 推荐 ─────────────────────────────────────
    def _llm_recommend(
        self, sql: str, features: Dict, intent: Optional[Dict]
    ) -> Optional[Dict[str, Any]]:
        """调用 LLM 基于数据上下文判断最佳图表类型"""
        col_summary = ', '.join(features['columns'][:15])
        sample_row = str(features.get('columns', [])[:5])
        intent_nl = intent.get('natural_language', '') if intent else ''

        prompt = f"""你是一个数据可视化专家。请根据以下信息推荐最合适的 ECharts 图表类型。

SQL 查询: {sql[:300]}
用户问题: {intent_nl}
列名: {col_summary}
行数: {features['row_count']}
时间列: {features['time_cols']}
数值列: {features['numeric_cols']}
分类列: {features['category_cols']}
是否聚合: {features['has_aggregation']}
是否分组: {features['has_group_by']}

可选图表类型: table, bar, line, pie, scatter, card, grouped_bar

请严格返回 JSON（不要 markdown 代码块），格式:
{{"type": "bar", "title": "图表标题", "xAxisField": "字段名", "yAxisField": "字段名", "seriesField": null, "confidence": 0.9, "reason": "推荐理由"}}
"""
        import json
        raw = self.llm_provider.generate(prompt)
        if not raw:
            return None
        # 提取 JSON
        raw = raw.strip()
        # 去除可能的 markdown 代码块
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        try:
            result = json.loads(raw)
            # 校验必需字段
            if 'type' not in result:
                return None
            result.setdefault('confidence', 0.7)
            result.setdefault('reason', '')
            return result
        except json.JSONDecodeError:
            logger.warning(f"LLM chart recommendation not valid JSON: {raw[:200]}")
            return None

    # ─── 辅助方法 ─────────────────────────────────────
    @staticmethod
    def _gen_title(intent: Optional[Dict], fallback: str) -> str:
        if intent and intent.get('natural_language'):
            nl = intent['natural_language']
            # 取自然语言的前 30 字作为标题
            return nl[:30] + ('...' if len(nl) > 30 else '')
        return fallback

    @staticmethod
    def _gen_title_for_single_value(col: str, intent: Optional[Dict]) -> str:
        if intent and intent.get('natural_language'):
            return intent['natural_language'][:30]
        return col


# ─── 单例 ────────────────────────────────────────────
_chart_recommender = None


def get_chart_recommender(llm_provider=None) -> ChartRecommender:
    global _chart_recommender
    if _chart_recommender is None:
        _chart_recommender = ChartRecommender(llm_provider=llm_provider)
    return _chart_recommender
