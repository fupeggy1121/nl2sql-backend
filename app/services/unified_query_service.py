"""
统一查询服务 - 整合意图识别、NL2SQL转换和查询执行
处理前端发送的自然语言查询，返回SQL和数据结果
"""

import logging
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

from app.services.intent_recognizer import IntentRecognizer
from app.services.nl2sql_enhanced import get_enhanced_nl2sql_converter
from app.services.query_executor import QueryExecutor
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """查询类型枚举"""
    DIRECT_TABLE_QUERY = "direct_table_query"  # 直接表查询
    METRIC_QUERY = "metric_query"  # 指标查询 (OEE, 良率等)
    AGGREGATE_QUERY = "aggregate_query"  # 聚合查询
    COMPARISON_QUERY = "comparison_query"  # 对比查询
    TREND_QUERY = "trend_query"  # 趋势查询
    UNKNOWN = "unknown"  # 未知查询


class VisualizationType(Enum):
    """可视化类型"""
    TABLE = "table"
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    GAUGE = "gauge"


@dataclass
class QueryIntent:
    """查询意图数据模型"""
    query_type: QueryType
    natural_language: str
    metric: Optional[str] = None
    time_range: Optional[str] = None
    equipment: Optional[List[str]] = None
    shift: Optional[List[str]] = None
    table_name: Optional[str] = None
    comparison: bool = False
    confidence: float = 0.0
    clarification_needed: bool = False
    clarification_questions: Optional[List[str]] = None
    raw_intent_data: Optional[Dict[str, Any]] = None

    def to_dict(self):
        """转换为字典"""
        data = asdict(self)
        data['query_type'] = self.query_type.value if self.query_type else None
        return data


@dataclass
class QueryPlan:
    """查询计划数据模型"""
    query_intent: QueryIntent
    generated_sql: Optional[str] = None
    sql_confidence: float = 0.0
    requires_clarification: bool = False
    clarification_message: Optional[str] = None
    suggested_sql_variants: Optional[List[str]] = None
    schema_context: Optional[Dict[str, Any]] = None
    explanation: Optional[str] = None

    def to_dict(self):
        """转换为字典"""
        return {
            "query_intent": self.query_intent.to_dict() if self.query_intent else None,
            "generated_sql": self.generated_sql,
            "sql_confidence": self.sql_confidence,
            "requires_clarification": self.requires_clarification,
            "clarification_message": self.clarification_message,
            "suggested_sql_variants": self.suggested_sql_variants,
            "schema_context": self.schema_context,
            "explanation": self.explanation
        }


@dataclass
class QueryResult:
    """查询结果数据模型"""
    success: bool
    data: List[Dict[str, Any]] = None
    sql: str = None
    rows_count: int = 0
    summary: str = None
    visualization_type: VisualizationType = VisualizationType.TABLE
    actions: List[str] = None
    error_message: Optional[str] = None
    query_time_ms: float = 0.0
    generated_at: str = None

    def to_dict(self):
        """转换为字典"""
        return {
            "success": self.success,
            "data": self.data or [],
            "sql": self.sql,
            "rows_count": self.rows_count,
            "summary": self.summary,
            "visualization_type": self.visualization_type.value if self.visualization_type else "table",
            "actions": self.actions or [],
            "error_message": self.error_message,
            "query_time_ms": self.query_time_ms,
            "generated_at": self.generated_at or datetime.now().isoformat()
        }


class UnifiedQueryService:
    """统一查询服务"""

    def __init__(self):
        """初始化服务"""
        # 初始化 LLM 提供商
        self.llm_provider = get_llm_provider()
        
        # 初始化意图识别器，并传递 LLM 提供商
        self.intent_recognizer = IntentRecognizer(llm_provider=self.llm_provider)
        self.nl2sql_converter = get_enhanced_nl2sql_converter()
        self.query_executor = QueryExecutor()
        logger.info("UnifiedQueryService initialized")

    async def process_natural_language_query(
        self,
        natural_language: str,
        user_context: Optional[Dict[str, Any]] = None,
        execution_mode: str = "explain"  # "explain" or "execute"
    ) -> Tuple[QueryPlan, Optional[QueryResult]]:
        """
        处理自然语言查询的完整流程

        流程:
        1. 识别用户意图
        2. 生成SQL查询
        3. 可选: 执行查询并返回结果
        4. 返回查询计划和可选的结果

        Args:
            natural_language: 自然语言查询
            user_context: 用户上下文信息
            execution_mode: 执行模式 - "explain" 仅返回SQL，"execute" 执行并返回结果

        Returns:
            (QueryPlan, Optional[QueryResult])
        """
        import time
        start_time = time.time()

        try:
            # 1. 意图识别
            query_intent = await self._recognize_intent(
                natural_language, 
                user_context
            )

            # 2. 检查是否需要澄清
            if query_intent.clarification_needed:
                query_plan = QueryPlan(
                    query_intent=query_intent,
                    requires_clarification=True,
                    clarification_message=self._build_clarification_message(query_intent)
                )
                return query_plan, None

            # 3. 生成SQL
            sql_query, sql_variants = await self._generate_sql(
                query_intent, 
                user_context
            )

            if not sql_query:
                query_plan = QueryPlan(
                    query_intent=query_intent,
                    requires_clarification=True,
                    clarification_message="无法为您的查询生成SQL。请尝试用不同的方式描述您的问题。"
                )
                return query_plan, None

            # 4. 构建查询计划
            schema_context = await self._build_schema_context(query_intent)
            
            query_plan = QueryPlan(
                query_intent=query_intent,
                generated_sql=sql_query,
                suggested_sql_variants=sql_variants,
                schema_context=schema_context,
                sql_confidence=0.85,
                explanation=await self._generate_explanation(sql_query, query_intent)
            )

            # 5. 根据execution_mode决定是否执行
            query_result = None
            if execution_mode == "execute":
                query_result = await self._execute_query(
                    sql_query,
                    query_intent,
                    start_time
                )

            return query_plan, query_result

        except Exception as e:
            logger.error(f"Error processing natural language query: {e}", exc_info=True)
            query_intent = QueryIntent(
                query_type=QueryType.UNKNOWN,
                natural_language=natural_language
            )
            query_plan = QueryPlan(
                query_intent=query_intent,
                requires_clarification=True,
                clarification_message=f"处理您的查询时出现错误: {str(e)}"
            )
            return query_plan, None

    async def execute_approved_query(
        self,
        sql_query: str,
        query_intent: Optional[QueryIntent] = None
    ) -> QueryResult:
        """
        执行已批准的SQL查询

        Args:
            sql_query: SQL查询语句
            query_intent: 查询意图（可选，用于优化结果）

        Returns:
            QueryResult
        """
        import time
        start_time = time.time()

        try:
            return await self._execute_query(
                sql_query,
                query_intent,
                start_time
            )
        except Exception as e:
            logger.error(f"Error executing approved query: {e}", exc_info=True)
            return QueryResult(
                success=False,
                error_message=f"执行查询失败: {str(e)}",
                query_time_ms=(time.time() - start_time) * 1000,
                generated_at=datetime.now().isoformat()
            )

    async def _recognize_intent(
        self,
        natural_language: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> QueryIntent:
        """
        识别用户意图
        """
        try:
            # 使用后端的意图识别器
            intent_data = self.intent_recognizer.recognize(natural_language)

            # 检查是否需要澄清
            clarification_needed = intent_data.get('confidence', 0) < 0.6
            clarification_questions = []

            if clarification_needed:
                if not intent_data.get('metric'):
                    clarification_questions.append("您想查询哪个指标？(OEE, 良率, 效率, 停机时间等)")
                if not intent_data.get('time_range'):
                    clarification_questions.append("您想查询哪个时间段？(今天, 本周, 本月等)")

            query_type = self._map_to_query_type(intent_data)

            return QueryIntent(
                query_type=query_type,
                natural_language=natural_language,
                metric=intent_data.get('metric'),
                time_range=intent_data.get('time_range'),
                equipment=intent_data.get('equipment', []),
                shift=intent_data.get('shift', []),
                table_name=intent_data.get('table_name'),
                comparison=intent_data.get('comparison', False),
                confidence=intent_data.get('confidence', 0),
                clarification_needed=clarification_needed,
                clarification_questions=clarification_questions if clarification_needed else None,
                raw_intent_data=intent_data
            )

        except Exception as e:
            logger.error(f"Error recognizing intent: {e}", exc_info=True)
            return QueryIntent(
                query_type=QueryType.UNKNOWN,
                natural_language=natural_language,
                clarification_needed=True,
                clarification_questions=["无法理解您的查询意图，请提供更详细的信息"]
            )

    async def _generate_sql(
        self,
        query_intent: QueryIntent,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[str], Optional[List[str]]]:
        """
        基于查询意图生成SQL
        """
        try:
            # 构建优化的自然语言查询
            optimized_nl = self._build_optimized_nl_query(query_intent)

            # 使用增强的NL2SQL转换器
            sql = self.nl2sql_converter.convert(optimized_nl)

            # 生成可选的SQL变体（用于用户选择）
            sql_variants = []
            if query_intent.comparison:
                # 为对比查询生成替代SQL
                alt_nl = self._build_comparison_query(query_intent)
                alt_sql = self.nl2sql_converter.convert(alt_nl)
                if alt_sql and alt_sql != sql:
                    sql_variants.append(alt_sql)

            logger.info(f"Generated SQL: {sql}")
            return sql, sql_variants if sql_variants else None

        except Exception as e:
            logger.error(f"Error generating SQL: {e}", exc_info=True)
            return None, None

    async def _execute_query(
        self,
        sql_query: str,
        query_intent: Optional[QueryIntent],
        start_time: float
    ) -> QueryResult:
        """
        执行SQL查询
        """
        import time

        try:
            # 执行查询
            data = self.query_executor.execute_query(sql_query)

            if not data:
                return QueryResult(
                    success=True,
                    data=[],
                    sql=sql_query,
                    rows_count=0,
                    summary="查询成功但没有返回数据",
                    query_time_ms=(time.time() - start_time) * 1000,
                    generated_at=datetime.now().isoformat()
                )

            # 确定可视化类型
            viz_type = self._determine_visualization_type(query_intent, data)

            # 生成摘要
            summary = self._generate_result_summary(query_intent, data)

            return QueryResult(
                success=True,
                data=data,
                sql=sql_query,
                rows_count=len(data),
                summary=summary,
                visualization_type=viz_type,
                actions=self._determine_available_actions(query_intent),
                query_time_ms=(time.time() - start_time) * 1000,
                generated_at=datetime.now().isoformat()
            )

        except Exception as e:
            logger.error(f"Error executing query: {e}", exc_info=True)
            return QueryResult(
                success=False,
                sql=sql_query,
                error_message=f"查询执行失败: {str(e)}",
                query_time_ms=(time.time() - start_time) * 1000,
                generated_at=datetime.now().isoformat()
            )

    def _map_to_query_type(self, intent_data: Dict[str, Any]) -> QueryType:
        """将意图数据映射到查询类型"""
        if intent_data.get('table_name'):
            return QueryType.DIRECT_TABLE_QUERY
        elif intent_data.get('comparison'):
            return QueryType.COMPARISON_QUERY
        elif intent_data.get('metric'):
            return QueryType.METRIC_QUERY
        else:
            return QueryType.UNKNOWN

    def _build_optimized_nl_query(self, query_intent: QueryIntent) -> str:
        """
        根据查询意图构建优化的自然语言查询
        包含表名、列名的中文标注等信息
        """
        parts = []

        if query_intent.metric:
            parts.append(f"查询 {query_intent.metric}")

        if query_intent.time_range:
            parts.append(f"在 {query_intent.time_range}")

        if query_intent.equipment:
            parts.append(f"设备 {','.join(query_intent.equipment)}")

        if query_intent.shift:
            parts.append(f"班次 {','.join(query_intent.shift)}")

        if query_intent.comparison:
            parts.append("按设备对比")

        result = " ".join(parts) if parts else query_intent.natural_language
        return result

    def _build_comparison_query(self, query_intent: QueryIntent) -> str:
        """构建对比查询的自然语言表述"""
        return f"对比{query_intent.metric}在不同设备间的差异 {self._build_optimized_nl_query(query_intent)}"

    async def _build_schema_context(self, query_intent: QueryIntent) -> Dict[str, Any]:
        """
        构建schema上下文信息
        包含相关表、列、业务含义等
        """
        try:
            metadata = self.nl2sql_converter.get_metadata_summary()
            return {
                "tables": metadata.get("table_names", []),
                "total_columns": metadata.get("columns", 0),
                "metadata_updated": metadata.get("last_updated"),
                "relevant_context": self._extract_relevant_context(query_intent, metadata)
            }
        except Exception as e:
            logger.error(f"Error building schema context: {e}")
            return {}

    def _extract_relevant_context(
        self,
        query_intent: QueryIntent,
        metadata: Dict[str, Any]
    ) -> List[str]:
        """提取与查询相关的schema上下文"""
        context = []
        
        if query_intent.metric:
            context.append(f"查询指标: {query_intent.metric}")
        
        if query_intent.table_name:
            context.append(f"目标表: {query_intent.table_name}")
        
        return context

    async def _generate_explanation(
        self,
        sql_query: str,
        query_intent: QueryIntent
    ) -> str:
        """
        生成SQL查询的人类可读解释
        """
        try:
            # 使用LLM生成解释
            prompt = f"""
            请用中文简洁地解释以下SQL查询的含义和作用:
            
            SQL: {sql_query}
            
            查询意图: {query_intent.natural_language}
            
            请生成不超过2句话的解释。
            """
            
            explanation = self.llm_provider.generate_text(prompt)
            return explanation if explanation else "这个查询将检索符合条件的数据"

        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            return "这个查询将检索符合条件的数据"

    def _determine_visualization_type(
        self,
        query_intent: Optional[QueryIntent],
        data: List[Dict[str, Any]]
    ) -> VisualizationType:
        """
        根据查询意图和数据确定最合适的可视化类型
        """
        if not query_intent:
            return VisualizationType.TABLE

        if query_intent.comparison:
            return VisualizationType.BAR
        elif query_intent.query_type == QueryType.TREND_QUERY:
            return VisualizationType.LINE
        elif query_intent.query_type == QueryType.METRIC_QUERY:
            if query_intent.metric in ['oee', 'yield_rate', 'quality']:
                return VisualizationType.GAUGE
            return VisualizationType.LINE
        else:
            return VisualizationType.TABLE

    def _generate_result_summary(
        self,
        query_intent: Optional[QueryIntent],
        data: List[Dict[str, Any]]
    ) -> str:
        """
        生成查询结果摘要
        """
        if not data:
            return "查询返回了0条记录"

        rows_count = len(data)

        if query_intent:
            if query_intent.metric:
                return f"查询得到 {rows_count} 条{query_intent.metric}的数据记录"
            elif query_intent.table_name:
                return f"从表 {query_intent.table_name} 查询到 {rows_count} 条数据"

        return f"查询成功，返回 {rows_count} 条数据记录"

    def _determine_available_actions(self, query_intent: Optional[QueryIntent]) -> List[str]:
        """
        根据查询意图确定可用的操作
        """
        actions = ['export', 'refresh']

        if not query_intent:
            return actions

        if query_intent.comparison:
            actions.extend(['detail', 'trend'])
        elif query_intent.query_type == QueryType.METRIC_QUERY:
            actions.extend(['detail', 'drilldown', 'schedule'])
        elif query_intent.query_type == QueryType.TREND_QUERY:
            actions.extend(['detail', 'alert'])

        return list(set(actions))  # 去重

    def _build_clarification_message(self, query_intent: QueryIntent) -> str:
        """
        构建澄清信息
        """
        if query_intent.clarification_questions:
            return "为了更准确地理解您的查询，请回答以下问题：\n" + "\n".join(
                f"• {q}" for q in query_intent.clarification_questions
            )
        return "无法完全理解您的查询意图，请提供更多详细信息"


# 全局实例
_unified_query_service = None


def get_unified_query_service() -> UnifiedQueryService:
    """获取统一查询服务实例"""
    global _unified_query_service
    if _unified_query_service is None:
        _unified_query_service = UnifiedQueryService()
    return _unified_query_service
