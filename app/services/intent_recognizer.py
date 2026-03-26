"""
Intent recognition service - Python implementation
Supports hybrid rule-based and LLM approach
"""

from typing import Dict, List, Optional, Any
import re
import logging
import json
# Forward to ontology-based synonym_manager (lazy import to avoid circular deps)
def map_table_name(keyword: str) -> str:
    from app.services.synonym_manager import synonym_manager
    return synonym_manager.map_table_name(keyword)

def is_valid_table_name(keyword: str) -> bool:
    from app.services.synonym_manager import synonym_manager
    return bool(synonym_manager.map_keyword_to_class(keyword))

logger = logging.getLogger(__name__)


class IntentRecognizer:
    """MES system intent recognition service with hybrid rule and LLM approach"""
    
    def __init__(self, llm_provider=None):
        """Initialize intent recognizer with optional LLM provider"""
        self.llm_provider = llm_provider
        
        # Intent configuration
        self.intents = {
            'chat': {
                'keywords': ['你好', '您好', 'hello', 'hi', '你叫什么', '你是谁', '你是什么',
                             '介绍一下', '你能做什么', '能帮我做什么', '谢谢', '感谢', '再见',
                             '拜拜', '帮帮我', '有什么功能', '怎么用', '你叫', '名字', '你的名字'],
                'entities': [],
                'description': 'General chat, greeting, or assistant introduction'
            },
            'knowledge_qa': {
                'keywords': ['是什么', '什么是', '解释', '含义', '定义', '怎么理解', '如何理解'],
                'entities': [],
                'description': 'Knowledge question-answering about MES concepts'
            },
            'direct_query': {
                'keywords': ['返回', '查询', '显示', '获取', '列出', '表', '片篮', '载具', '载体',
                            '晶圆', '检测', '批次', '设备', '质量', '缺陷', 'select', 'from'],
                'entities': ['table', 'limit', 'filters'],
                'description': 'Direct table data query'
            },
            'query_production': {
                'keywords': ['产量', '生产', '产出', '完成', '输出'],
                'entities': ['timeRange', 'productLine', 'productType'],
                'description': 'Query production data'
            },
            'query_quality': {
                'keywords': ['良品率', '合格率', '质量', '不良', '缺陷', '良率'],
                'entities': ['timeRange', 'productType', 'defectType', 'metrics'],
                'description': 'Query quality data'
            },
            'query_equipment': {
                'keywords': ['设备', '稼动率', 'OEE', '故障', '停机', '效率'],
                'entities': ['timeRange', 'equipmentId', 'workshop', 'metrics'],
                'description': 'Query equipment data'
            },
            'generate_report': {
                'keywords': ['报表', '生成', '导出', '汇总', '统计', '汇报'],
                'entities': ['reportType', 'timeRange'],
                'description': 'Generate report'
            },
            'compare_analysis': {
                'keywords': ['对比', '比较', '同比', '环比', '分析', '趋势'],
                'entities': ['timeRange', 'metrics'],
                'description': 'Comparative analysis'
            },
            'write_action': {
                'keywords': ['拆批', '拆出', '进站', '出站', '合批', '攒批', '返工', '执行', '操作'],
                'entities': ['eventType', 'lotId', 'waferList'],
                'description': 'Write/mutation operation: split lot, merge lot, rework, checkin, checkout'
            }
        }

        # 写操作意图：最高优先级检测（变更/执行类操作，走 action_executor 分支）
        # 注意：若上下文含"查询/历史/记录/统计"等读取信号，"进站/出站"应视为查询对象而非操作动词
        self._write_action_patterns = re.compile(
            r'拆(批|出|分)'
            r'|从.{0,30}(批次|Lot).{0,30}(拆|分出|析出)'
            r'|生成新批次'
            r'|新批次'
            r'|(进站|入站)'
            r'|(出站)'
            r'|(合批|攒批|并批)'
            r'|(返工)',
            re.IGNORECASE
        )
        # 如果存在查询语境关键词，"进站/出站"应被视为查询对象而非写操作动词
        self._query_context_patterns = re.compile(
            r'查询|查看|查一下|列出|显示|统计|分析|历史|记录|最近|过去|多少'
            r'|有哪些|是什么|是哪|几条|几次|报表|报告|汇总',
            re.IGNORECASE
        )
        # 纯"进站/出站"写操作：仅含动作词但不含查询语境时才算写操作
        self._checkin_action_patterns = re.compile(
            r'(进站|入站|出站)',
            re.IGNORECASE
        )

        # Greeting/chat patterns for top-priority rule match (regex)
        self._chat_patterns = re.compile(
            r'^(你好|您好|hi|hello|嗨|哈喽|hey)'
            r'|你(叫什么|是谁|是什么|能做什么|有什么功能|的名字|叫啥)'
            r'|你们?(叫什么|是谁|是什么|能做什么|有什么功能|的名字|叫啥)'
            r'|(介绍一下|介绍下)(你|您|自己|一下自己)'
            r'|(谢谢|感谢|再见|拜拜|byebye|bye)'
            r'|怎么?(称呼|叫|叫你)',
            re.IGNORECASE
        )
    
    def recognize(self, user_input: str) -> Dict[str, Any]:
        """
        Recognize user query intent using hybrid rule-based and LLM methods.

        Strategy:
          1. Fast rule-based matching with low latency
          2. LLM matching for uncertain cases (high accuracy)
          3. Merge results from both methods

        Args:
            user_input: Natural language query from user

        Returns:
            dict: Recognition result with keys: success, intent, confidence, entities, clarifications, methodsUsed
        """
        try:
            # Step 1: Rule-based matching
            rule_result = self._rule_based_match(user_input)
            
            logger.info(f"Rule match result: intent={rule_result['intent']}, "
                       f"confidence={rule_result['confidence']:.2f}")
            
            # Step 2: Return if rule confidence is high
            # Note: even for high-confidence rule matches, query_type defaults to LIST;
            # for COUNT/AGGREGATE/TREND we still need LLM judgment.
            if rule_result['confidence'] > 0.8 and rule_result.get('intent') in ('chat', 'write_action'):
                # chat / write_action 意图：规则已足够，不需要 LLM 判断 query_type
                return {
                    'success': True,
                    'intent': rule_result['intent'],
                    'confidence': rule_result['confidence'],
                    'entities': rule_result['entities'],
                    'query_type': 'LIST',
                    'target_class_hints': [],
                    'semantic_filters': [],
                    'clarifications': self._generate_clarifications(
                        rule_result['intent'],
                        rule_result['entities'],
                        rule_result['confidence']
                    ),
                    'methodsUsed': ['rule']
                }
            
            # Step 3: LLM confirmation
            try:
                llm_result = self._llm_based_match(user_input)
            except Exception as llm_err:
                logger.warning(f"LLM matching error, using rule-only fallback: {llm_err}")
                # Graceful fallback: return rule result with a slight confidence boost
                return {
                    'success': True,
                    'intent': rule_result['intent'],
                    'confidence': max(rule_result['confidence'], 0.70),
                    'entities': rule_result['entities'],
                    'query_type': 'LIST',
                    'target_class_hints': [],
                    'semantic_filters': [],
                    'intent_slots': {},
                    'clarifications': self._generate_clarifications(
                        rule_result['intent'],
                        rule_result['entities'],
                        rule_result['confidence']
                    ),
                    'methodsUsed': ['rule'],
                    'reasoning': ''
                }

            logger.info(f"LLM match result: intent={llm_result['intent']}, "
                       f"confidence={llm_result['confidence']:.2f}")
            
            # Step 4: Merge results
            merged = self._merge_results(rule_result, llm_result)
            
            return {
                'success': True,
                'intent': merged['intent'],
                'confidence': merged['confidence'],
                'entities': merged['entities'],
                # P1: 新增结构化输出字段
                'query_type': merged.get('query_type', 'LIST'),
                'target_class_hints': merged.get('target_class_hints', []),
                'semantic_filters': merged.get('semantic_filters', []),
                'intent_slots': llm_result.get('intent_slots', {}),
                'clarifications': self._generate_clarifications(
                    merged['intent'],
                    merged['entities'],
                    merged['confidence']
                ),
                'methodsUsed': merged['methodsUsed'],
                'reasoning': llm_result.get('reasoning', '')
            }
            
        except Exception as e:
            logger.error(f"Error in recognize: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'intent': 'other',
                'confidence': 0.0,
                'entities': {},
                'clarifications': [],
                'methodsUsed': []
            }
    
    def _rule_based_match(self, text: str) -> Dict[str, Any]:
        """
        Keyword-based fast intent matching.

        Returns:
            dict: Intent matching result with keys: intent, confidence, entities
        """
        normalized_input = text.lower()
        scores = {}

        # ── 优先级 0：写操作意图（变更类，走 action_executor 分支）──
        # 如果语句同时含"进/出站"和查询语境词（查询/历史/记录/统计等），视为历史查询，不走 action
        if self._write_action_patterns.search(text):
            has_query_context = self._query_context_patterns.search(text)
            if has_query_context:
                pass  # 含查询语境词（查询/记录/历史/统计等）→ 是对历史记录的查询，走 query 分支
            else:
                return {
                    'intent': 'write_action',
                    'confidence': 0.92,
                    'entities': self._extract_write_entities(text),
                }

        # ── 最高优先级：问候 / 闲聊 / 助手介绍 ──
        # 这些输入不含任何业务查询意图，必须在所有其他规则之前判断
        if self._chat_patterns.search(text):
            return {
                'intent': 'chat',
                'confidence': 0.95,
                'entities': {}
            }

        # Check if it's a direct query to a table (highest priority)
        # Look for keywords followed by table synonyms
        if any(kw in normalized_input for kw in ['查询', '返回', '显示', '获取', '列出']):
            # Extract words and check if they are table names
            words = re.findall(r'[a-zA-Z_]+|[\u4e00-\u9fff]+', text)
            for word in words:
                if is_valid_table_name(word):
                    # High confidence for direct table queries
                    scores['direct_query'] = 0.95
                    break
        
        # If no direct query found, calculate match scores for each intent
        if not scores:
            for intent_name, config in self.intents.items():
                score = 0
                keywords = config['keywords']
                
                # Count keyword matches
                for keyword in keywords:
                    if keyword.lower() in normalized_input:
                        score += 1
                
                if score > 0:
                    # Normalize score to 0-1
                    scores[intent_name] = score / len(keywords)
        
        # No match found
        if not scores:
            return {
                'intent': 'other',
                'confidence': 0.0,
                'entities': {}
            }
        
        # Get best matching intent
        best_intent = max(scores, key=scores.get)
        
        return {
            'intent': best_intent,
            'confidence': scores[best_intent],
            'entities': self._extract_entities(text, best_intent)
        }
    
    # ── P0: 本体类目录缓存（延迟加载，模块生命周期内只加载一次）──
    _ontology_class_labels: Optional[List[str]] = None

    def _get_ontology_class_labels(self) -> List[str]:
        """
        从 MappingRegistry 读取所有非虚拟本体类的 label_cn → logic_class 映射。
        延迟加载，避免循环依赖和启动耗时。
        格式: ["semi:Carrier（载具）", "semi:Equipment（设备）", ...]
        """
        if IntentRecognizer._ontology_class_labels is not None:
            return IntentRecognizer._ontology_class_labels
        try:
            from app.ontology.mapping import get_mapping
            reg = get_mapping()
            labels = [
                f"{pt.logic_class}（{pt.label_cn}）"
                for pt in reg._table_by_class.values()
                if not pt.virtual and pt.table_name
            ]
            IntentRecognizer._ontology_class_labels = labels
            logger.info(f"[intent_recognizer] Loaded {len(labels)} ontology class labels")
            return labels
        except Exception as e:
            logger.warning(f"[intent_recognizer] Failed to load ontology labels: {e}")
            IntentRecognizer._ontology_class_labels = []
            return []

    def _llm_based_match(self, text: str) -> Dict[str, Any]:
        """
        半导体制造领域专用意图识别 (P0+P1 改造版本)。

        改造内容：
          P0 - 注入本体类目录 + 半导体术语词典到 prompt，提升领域识别精度
          P1 - 新增 query_type (LIST/COUNT/AGGREGATE/TREND) 和 target_class_hints 字段

        Returns:
            dict: 包含 intent, confidence, entities, query_type,
                  target_class_hints, semantic_filters, reasoning
        """
        if not self.llm_provider:
            logger.warning("LLM provider not available, returning empty LLM result")
            return {
                'intent': 'other',
                'confidence': 0.0,
                'entities': {},
                'query_type': 'LIST',
                'target_class_hints': [],
                'semantic_filters': [],
                'reasoning': 'LLM provider not available'
            }

        # P0: 注入本体类目录
        class_labels = self._get_ontology_class_labels()
        class_list_str = "\n".join(f"  - {lbl}" for lbl in class_labels) if class_labels else "  （本体类目录暂不可用）"

        prompt = f"""你是半导体CIM/MES系统的查询意图分析专家。请分析用户输入的查询意图，并填充语义槽。

## 可查询的本体类（业务对象）
{class_list_str}

## 半导体行业常用术语对照
- 片篮 / 载具 / Carrier / FOUP / SMIF Pod → semi:Carrier
- 批次 / Lot / 投片批 → semi:ProductionLot
- 子批次 / 本地批 / Batch → semi:Sublot
- WIP / 在制 / 在制品 → semi:wafer （status=Running/执行中）
- 设备 / 机台 / Equipment → semi:Equipment
- 工序 / 工艺站点 / Station → semi:ProcessStation
- 工艺路线 / Route → semi:Route
- 产品模型 / ProductModel → semi:ProductModel
- 工单 / 排程 / Order → semi:ProductionOrder
- 配方 / Recipe → semi:Recipe
- 物料 / Material → semi:Material
- 辅料 / Auxiliary → semi:Auxiliary

## 生产事件记录域术语对照
- 过站记录 / 进出站记录 / 所有操作记录 / 批次历史 / 所有事件记录 → semi:ProductionEventRecord（父类，含所有子类型）
- 进站记录 / 进站历史 / 入站记录 / 进站操作记录 → semi:CheckInEventRecord
- 出站记录 / 出站历史 / 出站操作记录 → semi:CheckOutEventRecord
- 拆批记录 / 拆批历史 / 拆批操作 → semi:SplitEventRecord
- 并批记录 / 合批记录 → semi:MergeEventRecord
- 攒批记录 / 批次合并记录 → semi:AccumulateEventRecord
- 扣留记录 / hold记录 → semi:HoldEventRecord
- 释放记录 / release记录 / 取消扣留记录 → semi:ReleaseEventRecord
- 不良录入 / NG记录 / 不良记录 → semi:NGRecordEventRecord
- 量测记录 / 量测数据 / 量测参数 / 量测结果 / 量测参数值 / 量测值 / 制程参数 / 参数采集记录 → semi:WaferMeasurementSnapshot（量测快照层，查看具体参数数据时用）
- 量测录入事件 / 量测录入 / 谁录入了量测 → semi:MeasurementPassRecord（量测事件层，查看录入人/录入时间时用）
⚠ 注意区分："过站记录"特指进站/出站事件（CheckIn/CheckOut），不是量测参数记录（WaferMeasurementSnapshot）

## 仓库管理域（WMS）术语对照
- 入库 / 入库记录 / 入库明细 / 物料入库 / 入库数量 → semi:InboundEventRecord
- 入库单 / 入库记录单 / 入库凭证 → semi:InboundBill
- 入库申请 / 入库申请单 → semi:InboundRequest
- 出库 / 出库记录 / 出库明细 / 物料出库 / 领料记录 / 出库数量 → semi:OutboundEventRecord
- 出库单 / 出库记录单 / 出库凭证 → semi:OutboundBill
- 出库申请 / 领料申请 → semi:OutboundRequest
- 库存 / 在库 / 库存量 / 库存分布 / 实时库存 → semi:Inventory
- 仓库 / 库位 / 库区 / 各仓库 → semi:WarehouseLocation
- 物料批次 / 来料批次 / 入库批次 → semi:MaterialBatch

## query_type 判断规则
- LIST    : 查询列表 / 显示所有 / 返回记录 / 按某字段排序取前N（无需分组汇总，"列表"是完整词，不要拆分）
- COUNT   : 统计数量 / 有多少 / 数一数（量词类问题）
- AGGREGATE: 需要先按某维度 GROUP BY 再汇总（求和/计数/平均/最大最小），常见场景：各X的Y总计、某指标排名Top N（排名前需先聚合）、良率、稼动率
- TREND   : 趋势 / 对比 / 同比 / 环比 / 按时间分组

## 判断 AGGREGATE vs LIST 的关键区别
- 有"各X"/"按X分组"/"每个X"等分组维度词 → AGGREGATE（需 GROUP BY）
- "排名/Top N"单独出现但无分组维度词 → LIST（仅 ORDER BY + LIMIT）
- "排名/Top N" + 聚合词（总量/数量/合计/汇总/总计）同时出现 → AGGREGATE

## intent_slots 语义槽说明（用于定向 SQL 构造）
每个槽位对应 SQL 的一个核心要素，无法确定时填 null：
- subject      : 查询主体对象（自然语言，对应 FROM 的主表），如 "入库记录" / "物料" / "库存"
- action       : 查询动作，枚举: "查询列表" / "统计聚合" / "计数" / "趋势分析"
- dimension_by : GROUP BY 维度（聚合时必填），如 "物料" / "仓库" / "工序"
- metric       : SELECT 聚合指标（聚合时必填），如 "入库数量" / "库存数量" / "批次数"
- sort_order   : 排序方向 "DESC" | "ASC"（无排序要求时填 null）
- limit_n      : 取前N条的整数（如 Top3 → 3，无限制时填 null）
  ⚠ 用户说"所有"/"全部"/"all"时 limit_n 必须填 null，禁止猜测一个小数值
- filter_hints : 过滤条件列表（自然语言），如 ["状态=已完成", "时间范围=本月", "仓库=仓库01"]
- reasoning    : 槽填充的简短推理说明

## Few-shot 示例（含 intent_slots）
Q: "查询可用的片篮列表"
A: intent=direct_query, query_type=LIST, target_class_hints=["semi:Carrier"],
   semantic_filters=[{{"attribute":"status","semantic_value":"Available"}}],
   intent_slots={{"subject":"载具","action":"查询列表","dimension_by":null,"metric":null,"sort_order":null,"limit_n":null,"filter_hints":["状态=可用"],"reasoning":"列表查询，过滤可用状态"}}

Q: "统计当前在制的批次数量"
A: intent=query_production, query_type=COUNT, target_class_hints=["semi:ProductionLot"],
   semantic_filters=[{{"attribute":"lot_status","semantic_value":"Running"}}],
   intent_slots={{"subject":"批次","action":"计数","dimension_by":null,"metric":"批次数量","sort_order":null,"limit_n":null,"filter_hints":["状态=在制"],"reasoning":"COUNT查询在制批次"}}

Q: "本月各工序的设备稼动率"
A: intent=query_equipment, query_type=AGGREGATE, target_class_hints=["semi:Equipment","semi:ProcessStation"],
   semantic_filters=[],
   intent_slots={{"subject":"设备","action":"统计聚合","dimension_by":"工序","metric":"稼动率","sort_order":null,"limit_n":null,"filter_hints":["时间范围=本月"],"reasoning":"按工序分组计算设备稼动率"}}

Q: "统计入库数量排名Top3的物料"
A: intent=generate_report, query_type=AGGREGATE, target_class_hints=["semi:InboundEventRecord"],
   semantic_filters=[],
   intent_slots={{"subject":"入库记录","action":"统计聚合","dimension_by":"物料","metric":"入库数量","sort_order":"DESC","limit_n":3,"filter_hints":[],"reasoning":"按物料分组汇总入库数量，降序取前3"}}

Q: "各仓库的库存分布"
A: intent=generate_report, query_type=AGGREGATE, target_class_hints=["semi:Inventory","semi:WarehouseLocation"],
   semantic_filters=[],
   intent_slots={{"subject":"库存","action":"统计聚合","dimension_by":"仓库","metric":"库存数量","sort_order":null,"limit_n":null,"filter_hints":[],"reasoning":"按仓库维度统计库存分布"}}

Q: "过去7天良率趋势"
A: intent=query_quality, query_type=TREND, target_class_hints=["semi:ProductionLot"],
   semantic_filters=[{{"attribute":"timeRange","semantic_value":"last_7_days"}}],
   intent_slots={{"subject":"批次","action":"趋势分析","dimension_by":"日期","metric":"良率","sort_order":"ASC","limit_n":null,"filter_hints":["时间范围=过去7天"],"reasoning":"按日期分组统计良率趋势"}}

Q: "你好"
A: intent=chat, query_type=LIST, target_class_hints=[], semantic_filters=[],
   intent_slots={{"subject":null,"action":null,"dimension_by":null,"metric":null,"sort_order":null,"limit_n":null,"filter_hints":[],"reasoning":"闲聊，无业务查询意图"}}

Q: "查询批次A001的所有过站记录"
A: intent=direct_query, query_type=LIST, target_class_hints=["semi:CheckInEventRecord","semi:CheckOutEventRecord"],
   semantic_filters=[{{"attribute":"lot_code","semantic_value":"A001"}}],
   intent_slots={{"subject":"过站记录","action":"查询列表","dimension_by":null,"metric":null,"sort_order":null,"limit_n":null,"filter_hints":["批次=A001"],"reasoning":"过站记录=进站+出站事件，不是量测参数记录；lot_code过滤A001"}}

Q: "查询批次LT-2024的进站记录"
A: intent=direct_query, query_type=LIST, target_class_hints=["semi:CheckInEventRecord"],
   semantic_filters=[{{"attribute":"lot_code","semantic_value":"LT-2024"}}],
   intent_slots={{"subject":"进站记录","action":"查询列表","dimension_by":null,"metric":null,"sort_order":null,"limit_n":null,"filter_hints":["批次=LT-2024"],"reasoning":"进站记录→CheckInEventRecord（operation_type=8）"}}

Q: "查询批次LT-2024的量测记录"
A: intent=direct_query, query_type=LIST, target_class_hints=["semi:WaferMeasurementSnapshot"],
   semantic_filters=[{{"attribute":"lot_code","semantic_value":"LT-2024"}}],
   intent_slots={{"subject":"量测数据","action":"查询列表","dimension_by":null,"metric":null,"sort_order":null,"limit_n":null,"filter_hints":["批次=LT-2024"],"reasoning":"量测记录/量测数据→WaferMeasurementSnapshot（快照层），查看参数值"}}

Q: "谁录入了量测数据"
A: intent=direct_query, query_type=LIST, target_class_hints=["semi:MeasurementPassRecord"],
   semantic_filters=[],
   intent_slots={{"subject":"量测录入事件","action":"查询列表","dimension_by":null,"metric":null,"sort_order":null,"limit_n":null,"filter_hints":[],"reasoning":"关注录入人→MeasurementPassRecord（事件层），查create_user"}}

Q: "查一下那个批次的数据"
A: intent=need_clarification, query_type=LIST, target_class_hints=[], semantic_filters=[],
   clarification_question="请问您想查询的是哪个批次号？（例如：LT-2024-001）",
   intent_slots={{"subject":null,"action":null,"dimension_by":null,"metric":null,"sort_order":null,"limit_n":null,"filter_hints":[],"reasoning":"缺少批次号和查询类型，无法生成SQL"}}

Q: "查询批次的所有进站记录"
A: intent=need_clarification, query_type=LIST, target_class_hints=["semi:CheckInEventRecord"], semantic_filters=[],
   clarification_question="请问您想查询哪个批次的进站记录？请提供批次号（例如：LT-2024-001）",
   intent_slots={{"subject":"进站记录","action":"查询列表","dimension_by":null,"metric":null,"sort_order":null,"limit_n":null,"filter_hints":[],"reasoning":"进站记录类型明确（CheckInEventRecord），但缺少批次号过滤，不宜全表扫描"}}

## 何时使用 need_clarification
以下任一情况使用：
1. 查询对象完全不明确（无批次号/设备/工序）且查询类型也未知，置信度 < 0.65
2. 查询类型明确是事件记录类（CheckInEventRecord/CheckOutEventRecord/MeasurementPassRecord/WaferMeasurementSnapshot 等），但没有指定批次号/lot_code 过滤条件（全表扫描风险）
⚠ 不要滥用——主数据查询（Carrier/Equipment/ProcessStation/Inventory 等）即使无过滤也可直接生成 SQL。

## 当前用户输入
"{text}"

## 输出要求
必须返回合法 JSON，不允许有注释或 markdown 代码块：
{{
    "intent": "direct_query|query_production|query_quality|query_equipment|generate_report|compare_analysis|chat|knowledge_qa|explain|write_action|need_clarification",
    "query_type": "LIST|COUNT|AGGREGATE|TREND",
    "target_class_hints": ["semi:Carrier"],
    "semantic_filters": [{{"attribute": "status", "semantic_value": "Available"}}],
    "clarification_question": "仅在 intent=need_clarification 时填写，其余填 null",
    "intent_slots": {{
        "subject": "查询主体（自然语言）或 null",
        "action": "查询列表|统计聚合|计数|趋势分析",
        "dimension_by": "聚合维度或 null",
        "metric": "聚合指标或 null",
        "sort_order": "DESC|ASC|null",
        "limit_n": null,
        "filter_hints": [],
        "reasoning": "槽填充推理说明"
    }},
    "confidence": 0.95,
    "entities": {{"timeRange": "today", "table": "carrier"}},
    "reasoning": "意图判断理由"
}}"""

        response = ""
        try:
            response = self.llm_provider.generate(prompt)

            # 去除 markdown 代码块包裹（若存在）
            stripped = response.strip()
            if stripped.startswith('```'):
                lines = stripped.splitlines()
                json_str = '\n'.join(
                    line for line in lines[1:]
                    if not line.strip().startswith('```')
                )
            else:
                json_str = stripped

            result = json.loads(json_str)

            return {
                'intent': result.get('intent', 'other'),
                'confidence': float(result.get('confidence', 0.0)),
                'entities': result.get('entities', {}),
                'query_type': result.get('query_type', 'LIST'),
                'target_class_hints': result.get('target_class_hints', []),
                'semantic_filters': result.get('semantic_filters', []),
                'intent_slots': result.get('intent_slots', {}),
                'reasoning': result.get('reasoning', '')
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"LLM raw response: {response[:500]}")
            return {
                'intent': 'other',
                'confidence': 0.0,
                'entities': {},
                'query_type': 'LIST',
                'target_class_hints': [],
                'semantic_filters': [],
                'intent_slots': {},
                'reasoning': 'JSON parse failed',
                'llm_raw_response': response
            }
        except Exception as e:
            logger.error(f"LLM matching error: {e}")
            return {
                'intent': 'other',
                'confidence': 0.0,
                'entities': {},
                'query_type': 'LIST',
                'target_class_hints': [],
                'semantic_filters': [],
                'intent_slots': {},
                'reasoning': f'LLM error: {str(e)}'
            }
    
    def _extract_write_entities(self, text: str) -> Dict[str, Any]:
        """
        从写操作指令中提取 eventType、lotId、waferList 实体。
        示例: "从批次 LOT-001 中拆出晶圆 W001,W002,W003，生成新批次"
        """
        entities: Dict[str, Any] = {"eventType": None, "lotId": None, "waferList": []}

        # 事件类型
        if re.search(r'拆(批|出|分)|析出|生成新批次', text, re.IGNORECASE):
            entities["eventType"] = "SPLIT"
        elif re.search(r'(合批|攒批|并批)', text, re.IGNORECASE):
            entities["eventType"] = "MERGE"
        elif re.search(r'返工', text, re.IGNORECASE):
            entities["eventType"] = "REWORK"
        elif re.search(r'(进站|入站)', text, re.IGNORECASE):
            entities["eventType"] = "CHECKIN"
        elif re.search(r'出站', text, re.IGNORECASE):
            entities["eventType"] = "CHECKOUT"

        # 批次 ID
        lot_match = re.search(r'(?:批次|Lot)[\s:：]*([A-Za-z0-9\-_]+)', text, re.IGNORECASE)
        if lot_match:
            entities["lotId"] = lot_match.group(1)

        # 晶圆列表
        wafer_match = re.search(r'晶圆[\s:：]*([A-Za-z0-9][A-Za-z0-9,，\s\-_]*)', text, re.IGNORECASE)
        if wafer_match:
            raw = wafer_match.group(1)
            entities["waferList"] = [w.strip() for w in re.split(r'[,，\s]+', raw) if w.strip()]

        return entities

    def _extract_entities(self, text: str, intent: str) -> Dict[str, Any]:
        """
        Extract entity information from user input.

        Supported entity types:
          - timeRange: time range
          - table: table name
          - limit: record limit
          - metrics: metrics to query
          - equipment: equipment IDs
          - productLine: product line
        """
        entities = {}
        
        # Time range extraction
        time_patterns = {
            r'今天|今日': 'today',
            r'昨天|昨日': 'yesterday',
            r'本周|这周': 'this_week',
            r'上周|上星期': 'last_week',
            r'本月|这个月': 'this_month',
            r'上月|上个月': 'last_month',
        }
        
        for pattern, value in time_patterns.items():
            if re.search(pattern, text):
                entities['timeRange'] = value
                break
        
        # Numeric time range extraction
        num_time_match = re.search(r'(?:最近|过去|最)?\s*(\d+)\s*(?:天|周|月)', text)
        if num_time_match and 'timeRange' not in entities:
            number = num_time_match.group(1)
            unit = re.search(r'天|周|月', num_time_match.group(0)).group(0)
            entities['timeRange'] = f"{number}{unit}"
        
        # Table name extraction - Pattern 1: "表名表" format
        table_match = re.search(r'(?:查询|返回|显示|获取)?\s*(\w+)\s*表', text)
        if table_match:
            raw_table_name = table_match.group(1)
            # Apply synonym mapping to convert user input to actual table name
            entities['table'] = map_table_name(raw_table_name)
            # Also store the raw table name for reference
            entities['raw_table_name'] = raw_table_name
        
        # Pattern 2: Direct table name/synonym after query keyword (without "表")
        # This handles cases like "查询片篮", "显示载具", "查询晶圆的信息", "显示所有晶圆载体"
        if 'table' not in entities:
            # Look for query keywords followed by table names
            # Extract content after query keywords
            keyword_pattern = r'(?:查询|返回|显示|获取)\s*(.+?)$'
            keyword_match = re.search(keyword_pattern, text)
            
            if keyword_match:
                candidate_text = keyword_match.group(1).strip()
                
                # First remove common function words and suffixes
                # This helps identify the core table name
                cleaned_text = re.sub(r'^(?:所有|所有的|当前|各种|全部)', '', candidate_text)
                cleaned_text = re.sub(r'(?:的信息|的数据|的|表|数据|信息|状态)$', '', cleaned_text).strip()
                
                # Strategy: try to extract table names with multiple approaches
                candidates_to_try = []
                
                # Approach 1: Try the cleaned text as continuous block
                candidates_to_try.append(cleaned_text)
                
                # Approach 2: Try individual two-character sequences (common in Chinese)
                if len(cleaned_text) >= 2:
                    for i in range(len(cleaned_text) - 1):
                        candidates_to_try.append(cleaned_text[i:i+2])
                
                # Approach 3: Try individual three-character sequences
                if len(cleaned_text) >= 3:
                    for i in range(len(cleaned_text) - 2):
                        candidates_to_try.append(cleaned_text[i:i+3])
                
                # Approach 4: Try individual characters (as a last resort)
                for char in cleaned_text:
                    candidates_to_try.append(char)
                
                # Try each candidate (longest first)
                matched = False
                for candidate in sorted(set(candidates_to_try), key=len, reverse=True):
                    if is_valid_table_name(candidate):
                        mapped_name = map_table_name(candidate)
                        entities['table'] = mapped_name
                        entities['raw_table_name'] = candidate
                        matched = True
                        break
                
                # 反馈学习: 如果查询词看起来像表名但未匹配，记录到候选队列
                if not matched and cleaned_text and len(cleaned_text) >= 2:
                    self._record_unmatched_table_term(cleaned_text, text)
        
        # LIMIT extraction
        limit_match = re.search(r'(?:前\s*)?(\d+)\s*(?:条|条数|行|rows)', text)
        if limit_match:
            entities['limit'] = int(limit_match.group(1))
        
        # Metric extraction
        metric_mapping = {
            '产量': 'output_qty',
            '良品率': 'yield_rate',
            '良率': 'yield_rate',
            'oee': 'oee',
            '稼动率': 'utilization_rate',
            '效率': 'efficiency',
            '停机': 'downtime'
        }
        
        metrics = []
        for keyword, metric in metric_mapping.items():
            if keyword.lower() in text.lower():
                metrics.append(metric)
        
        if metrics:
            entities['metrics'] = list(set(metrics))
        
        # Equipment extraction
        equipment_match = re.search(r'(?:设备|设备号|设备ID)\s*[:：]?\s*(\w+)', text)
        if equipment_match:
            entities['equipment'] = equipment_match.group(1)
        
        # Product line extraction
        product_line_match = re.search(r'(?:产品线|产线)\s*[:：]?\s*(\w+)', text)
        if product_line_match:
            entities['productLine'] = product_line_match.group(1)
        
        return entities
    
    def _merge_results(self, rule_result: Dict, llm_result: Dict) -> Dict[str, Any]:
        """
        Merge results from rule-based and LLM methods.

        Strategy:
          1. Prioritize LLM intent judgment (more accurate)
          2. Merge entity extraction results from both methods
          3. Use higher confidence score
          4. P1: propagate query_type / target_class_hints / semantic_filters from LLM
        """
        return {
            'intent': llm_result.get('intent', rule_result['intent']),
            'confidence': max(
                rule_result['confidence'],
                llm_result.get('confidence', 0.0)
            ),
            'entities': {
                **rule_result.get('entities', {}),
                **llm_result.get('entities', {})
            },
            # P1: 新增结构化字段，来自 LLM 半导体专用 prompt
            'query_type': llm_result.get('query_type', 'LIST'),
            'target_class_hints': llm_result.get('target_class_hints', []),
            'semantic_filters': llm_result.get('semantic_filters', []),
            'methodsUsed': ['rule', 'llm']
        }
    
    def _generate_clarifications(self, intent: str, entities: Dict, confidence: float) -> List[str]:
        """
        Generate clarification questions based on recognition result.

        Returns:
            list: List of clarification questions for user
        """
        clarifications = []
        
        # Low confidence
        if confidence < 0.5:
            clarifications.append('Your intent is not clear enough. Please provide more information.')
            return clarifications
        
        # Generate clarifications based on intent type
        if intent == 'query_production':
            if not entities.get('timeRange'):
                clarifications.append('Please specify the time range you want to query.')
            if not entities.get('productLine') and not entities.get('productType'):
                clarifications.append('Please specify the product line or product type.')
        
        elif intent == 'query_quality':
            if not entities.get('timeRange'):
                clarifications.append('Please specify the time range.')
            if not entities.get('metrics'):
                clarifications.append('Which quality metrics are you interested in?')
        
        elif intent == 'query_equipment':
            if not entities.get('metrics'):
                clarifications.append('Which equipment metric do you want to know?')
            if not entities.get('timeRange'):
                clarifications.append('Please specify the time range.')
        
        elif intent == 'generate_report':
            if not entities.get('reportType'):
                clarifications.append('Please specify the report type.')
            if not entities.get('timeRange'):
                clarifications.append('Please specify the time range for the report.')
        
        elif intent == 'compare_analysis':
            if not entities.get('metrics'):
                clarifications.append('Please specify which metrics to compare.')
            if not entities.get('timeRange'):
                clarifications.append('Please specify the time range for comparison.')
        
        return clarifications

    def _record_unmatched_table_term(self, term: str, original_query: str):
        """
        记录未匹配的查询词到候选队列 (异步 / 非阻塞)

        当意图识别无法将用户输入映射到已知表名时调用。
        系统会自动累计频次，管理员可在前端审批并创建新映射。
        """
        try:
            from app.services.synonym_manager import synonym_manager
            synonym_manager.record_unmatched_term(term, original_query)
        except Exception as e:
            # 反馈记录失败不应影响主流程
            logger.debug(f"记录未匹配词失败 (非关键): {e}")

    def to_frontend_format(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert backend recognition result to frontend UserIntent interface format.

        Frontend UserIntent interface specification:
          type: 'query' | 'report' | 'analysis' | 'comparison' | 'direct_table_query'
          entities: dict with keys metric, timeRange, equipment, shift, comparison, tableName, limit
          confidence: float between 0 and 1
          clarifications: list of strings

        Args:
            result: Output from recognize() method

        Returns:
            dict: UserIntent object compatible with frontend interface
        """
        intent = result.get('intent', 'other')
        entities = result.get('entities', {})
        
        # Map backend intent types to frontend types
        intent_type_mapping = {
            'direct_query': 'direct_table_query',
            'query_production': 'query',
            'query_quality': 'query',
            'query_equipment': 'query',
            'generate_report': 'report',
            'compare_analysis': 'analysis'
        }
        
        frontend_type = intent_type_mapping.get(intent, 'query')
        
        # Auto-detect if comparison analysis
        if entities.get('comparison') or 'comparison' in result.get('methodsUsed', []):
            frontend_type = 'comparison'
        
        # Build frontend-format entities object
        frontend_entities = {
            'metric': entities.get('metric', 'general'),
            'timeRange': entities.get('timeRange', ''),
            'equipment': entities.get('equipment', []) or entities.get('equipmentId', []),
            'shift': entities.get('shift', []),
            'comparison': entities.get('comparison', False)
        }
        
        # Add tableName and limit for direct query
        if intent == 'direct_query':
            frontend_entities['tableName'] = entities.get('tableName', '')
            frontend_entities['limit'] = entities.get('limit')
        
        # Convert equipment to list if not already
        if frontend_entities['equipment'] and not isinstance(frontend_entities['equipment'], list):
            frontend_entities['equipment'] = [frontend_entities['equipment']]
        
        return {
            'success': True,
            'intent': intent,
            'type': frontend_type,
            'entities': frontend_entities,
            'confidence': result.get('confidence', 0.0),
            'clarifications': result.get('clarifications', [])
        }


def get_intent_recognizer(llm_provider=None) -> IntentRecognizer:
    """Get intent recognizer instance"""
    return IntentRecognizer(llm_provider=llm_provider)
