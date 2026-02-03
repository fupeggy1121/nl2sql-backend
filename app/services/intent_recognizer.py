"""
意图识别服务 - Python 实现
支持规则引擎 + LLM 混合方式
"""

from typing import Dict, List, Optional, Any
import re
import logging
import json

logger = logging.getLogger(__name__)


class IntentRecognizer:
    """
    MES 系统意图识别服务
    采用轻量级规则 + LLM 混合方式
    """
    
    def __init__(self, llm_provider=None):
        """
        初始化意图识别器
        
        try:
            response = self.llm_provider.generate(prompt)
            # 自动去除 markdown 代码块包裹（如 ```json ... ``` 或 ``` ... ```）
            if response.strip().startswith('```'):
                # 去除开头的 ```json 或 ```
                lines = response.strip().splitlines()
                # 跳过第一行（```json 或 ```）
                json_str = '\n'.join(line for line in lines[1:] if not line.strip().startswith('```'))
            else:
                json_str = response
            # 解析 JSON 结果
            result = json.loads(json_str)
            return {
                'intent': result.get('intent', 'other'),
                'confidence': float(result.get('confidence', 0.0)),
                'entities': result.get('entities', {}),
                'reasoning': result.get('reasoning', '')
            }
                'description': '直接查询表数据'
            },
            'query_production': {
                'keywords': ['产量', '生产', '产出', '完成', '输出'],
                'entities': ['timeRange', 'productLine', 'productType'],
                'description': '查询生产数据'
            },
            'query_quality': {
                'keywords': ['良品率', '合格率', '质量', '不良', '缺陷', '良率'],
                'entities': ['timeRange', 'productType', 'defectType', 'metrics'],
                'description': '查询质量数据'
            },
            'query_equipment': {
                'keywords': ['设备', '稼动率', 'OEE', '故障', '停机', '效率'],
                'entities': ['timeRange', 'equipmentId', 'workshop', 'metrics'],
                'description': '查询设备数据'
            },
            'generate_report': {
                'keywords': ['报表', '生成', '导出', '汇总', '统计', '汇报'],
                'entities': ['reportType', 'timeRange'],
                'description': '生成报表'
            },
            'compare_analysis': {
                'keywords': ['对比', '比较', '同比', '环比', '分析', '趋势'],
                'entities': ['timeRange', 'metrics'],
                'description': '对比分析'
            }
        }
    
    def recognize(self, user_input: str) -> Dict[str, Any]:
        """
        识别用户查询意图 - 混合方式
        
        策略:
        1. 先用规则快速匹配（低延迟）
        2. 规则不确定时调用 LLM（高准确）
        3. 合并两种方法的结果
        
        Args:
            user_input: 用户输入的自然语言查询
            
        Returns:
            {
                'success': bool,
                'intent': str,
                'confidence': float (0-1),
                'entities': dict,
                'clarifications': list[str],
                'methodsUsed': list[str],
                'reasoning': str (optional)
            }
        """
        try:
            # 第一步：规则匹配
            rule_result = self._rule_based_match(user_input)
            
            logger.info(f"Rule match result: intent={rule_result['intent']}, "
                       f"confidence={rule_result['confidence']:.2f}")
            
            # 第二步：如果规则置信度高，直接返回
            if rule_result['confidence'] > 0.8:
                return {
                    'success': True,
                    'intent': rule_result['intent'],
                    'confidence': rule_result['confidence'],
                    'entities': rule_result['entities'],
                    'clarifications': self._generate_clarifications(
                        rule_result['intent'],
                        rule_result['entities'],
                        rule_result['confidence']
                    ),
                    'methodsUsed': ['rule']
                }
            
            # 第三步：LLM 确认
            llm_result = self._llm_based_match(user_input)
            
            logger.info(f"LLM match result: intent={llm_result['intent']}, "
                       f"confidence={llm_result['confidence']:.2f}")
            
            # 第四步：合并结果
            merged = self._merge_results(rule_result, llm_result)
            
            return {
                'success': True,
                'intent': merged['intent'],
                'confidence': merged['confidence'],
                'entities': merged['entities'],
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
        基于关键词的快速匹配
        
        Returns:
            {
                'intent': str,
                'confidence': float,
                'entities': dict
            }
        """
        normalized_input = text.lower()
        scores = {}
        
        # 计算每个意图的匹配分数
        for intent_name, config in self.intents.items():
            score = 0
            keywords = config['keywords']
            
            # 统计关键词匹配数
            for keyword in keywords:
                if keyword.lower() in normalized_input:
                    score += 1
            
            if score > 0:
                # 归一化分数（0-1）
                scores[intent_name] = score / len(keywords)
        
        # 没有匹配
        if not scores:
            return {
                'intent': 'other',
                'confidence': 0.0,
                'entities': {}
            }
        
        # 获取最佳匹配意图
        best_intent = max(scores, key=scores.get)
        
        return {
            'intent': best_intent,
            'confidence': scores[best_intent],
            'entities': self._extract_entities(text, best_intent)
        }
    
    def _llm_based_match(self, text: str) -> Dict[str, Any]:
        """
        使用 DeepSeek LLM 进行意图识别
        
        Returns:
            {
                'intent': str,
                'confidence': float,
                'entities': dict,
                'reasoning': str (optional)
            }
        """
        if not self.llm_provider:
            logger.warning("LLM provider not available, returning empty LLM result")
            return {
                'intent': 'other',
                'confidence': 0.0,
                'entities': {},
                'reasoning': 'LLM provider not available'
            }
        
        intent_list = ', '.join(self.intents.keys())
        
        prompt = f"""分析用户在 MES 系统中的查询意图。

可能的意图类型及描述:
{chr(10).join(f"- {k}: {v['description']}" for k, v in self.intents.items())}

用户输入: "{text}"

请返回 JSON 格式的分析结果（必须是有效的 JSON）:
{{
    "intent": "意图类型",
    "confidence": 0.95,
    "entities": {{
        "timeRange": "时间范围",
        "metric": "指标"
    }},
    "reasoning": "判断理由"
}}"""
        
        try:
            response = self.llm_provider.generate(prompt)
            
            # 解析 JSON 结果
            result = json.loads(response)
            
            return {
                'intent': result.get('intent', 'other'),
                'confidence': float(result.get('confidence', 0.0)),
                'entities': result.get('entities', {}),
                'reasoning': result.get('reasoning', '')
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {str(e)}")
            logger.error(f"LLM 原始响应: {response}")
            return {
                'intent': 'other',
                'confidence': 0.0,
                'entities': {},
                'reasoning': 'Failed to parse LLM response',
                'llm_raw_response': response
            }
        except Exception as e:
            logger.error(f"LLM matching error: {str(e)}")
            logger.error(f"LLM 原始响应: {response}")
            return {
                'intent': 'other',
                'confidence': 0.0,
                'entities': {},
                'reasoning': f'LLM error: {str(e)}',
                'llm_raw_response': response
            }
    
    def _extract_entities(self, text: str, intent: str) -> Dict[str, Any]:
        """
        从用户输入中提取实体信息
        
        支持的实体类型:
        - timeRange: 时间范围
        - table: 表名
        - limit: 记录数限制
        - metrics: 指标
        - equipment: 设备ID
        - productLine: 产品线
        """
        entities = {}
        
        # 时间范围提取
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
        
        # 数字时间范围提取
        num_time_match = re.search(r'(?:最近|过去|最)?\s*(\d+)\s*(?:天|周|月)', text)
        if num_time_match and 'timeRange' not in entities:
            number = num_time_match.group(1)
            unit = re.search(r'天|周|月', num_time_match.group(0)).group(0)
            entities['timeRange'] = f"{number}{unit}"
        
        # 表名提取
        table_match = re.search(r'(?:查询|返回|显示|获取)?\s*(\w+)\s*表', text)
        if table_match:
            entities['table'] = table_match.group(1)
        
        # LIMIT 提取
        limit_match = re.search(r'(?:前\s*)?(\d+)\s*(?:条|条数|行|rows)', text)
        if limit_match:
            entities['limit'] = int(limit_match.group(1))
        
        # 指标提取
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
            entities['metrics'] = list(set(metrics))  # 去重
        
        # 设备提取
        equipment_match = re.search(r'(?:设备|设备号|设备ID)\s*[:：]?\s*(\w+)', text)
        if equipment_match:
            entities['equipment'] = equipment_match.group(1)
        
        # 产品线提取
        product_line_match = re.search(r'(?:产品线|产线)\s*[:：]?\s*(\w+)', text)
        if product_line_match:
            entities['productLine'] = product_line_match.group(1)
        
        return entities
    
    def _merge_results(self, rule_result: Dict, llm_result: Dict) -> Dict[str, Any]:
        """
        合并规则引擎和 LLM 的结果
        
        策略:
        1. 优先使用 LLM 的意图判断（更准确）
        2. 合并两种方法的实体提取结果
        3. 取较高的置信度
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
            'methodsUsed': ['rule', 'llm']
        }
    
    def _generate_clarifications(self, intent: str, entities: Dict, confidence: float) -> List[str]:
        """
        根据识别结果生成澄清问题
        
        Returns:
            澄清问题列表
        """
        clarifications = []
        
        # 置信度过低
        if confidence < 0.5:
            clarifications.append('您的意图不够清晰，请提供更多信息。')
            return clarifications
        
        # 根据意图类型生成澄清
        if intent == 'query_production':
            if not entities.get('timeRange'):
                clarifications.append('请指定您想查询的时间范围（如：今天、本周、上月）')
            if not entities.get('productLine') and not entities.get('productType'):
                clarifications.append('请指定具体的产品线或产品类型')
        
        elif intent == 'query_quality':
            if not entities.get('timeRange'):
                clarifications.append('请指定查询的时间范围')
            if not entities.get('metrics'):
                clarifications.append('您想了解哪个质量指标？• 良品率 • 合格率 • 缺陷率')
        
        elif intent == 'query_equipment':
            if not entities.get('metrics'):
                clarifications.append('您想了解哪个设备指标？• OEE • 稼动率 • 故障时间')
            if not entities.get('timeRange'):
                clarifications.append('请指定查询的时间范围')
        
        elif intent == 'generate_report':
            if not entities.get('reportType'):
                clarifications.append('请指定报表类型（如：日报、周报、月报、生产报表、质量报表）')
            if not entities.get('timeRange'):
                clarifications.append('请指定报表的时间范围')
        
        elif intent == 'compare_analysis':
            if not entities.get('metrics'):
                clarifications.append('请指定要对比的指标')
            if not entities.get('timeRange'):
                clarifications.append('请指定对比的时间范围（如：同比上月、环比上周）')
        
        return clarifications


    def to_frontend_format(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        将后端识别结果转换为前端 UserIntent 接口格式
        
        前端 UserIntent 接口要求:
        {
            "type": "query" | "report" | "analysis" | "comparison" | "direct_table_query",
            "entities": {
                "metric": string,
                "timeRange": string,
                "equipment": string[],
                "shift": string[],
                "comparison": boolean,
                "tableName"?: string,
                "limit"?: number
            },
            "confidence": number,
            "clarifications": string[]
        }
        
        Args:
            result: 后端 recognize() 方法的返回结果
            
        Returns:
            符合前端 UserIntent 接口的对象
        """
        intent = result.get('intent', 'other')
        entities = result.get('entities', {})
        
        # 映射后端意图类型到前端类型
        intent_type_mapping = {
            'direct_query': 'direct_table_query',
            'query_production': 'query',
            'query_quality': 'query',
            'query_equipment': 'query',
            'generate_report': 'report',
            'compare_analysis': 'analysis'
        }
        
        frontend_type = intent_type_mapping.get(intent, 'query')
        
        # 自动检测是否是对比分析
        if entities.get('comparison') or 'comparison' in result.get('methodsUsed', []):
            frontend_type = 'comparison'
        
        # 构建前端格式的实体对象
        frontend_entities = {
            'metric': entities.get('metric', 'general'),
            'timeRange': entities.get('timeRange', ''),
            'equipment': entities.get('equipment', []) or entities.get('equipmentId', []),
            'shift': entities.get('shift', []),
            'comparison': entities.get('comparison', False)
        }
        
        # 如果是直接查询，添加 tableName 和 limit
        if intent == 'direct_query':
            frontend_entities['tableName'] = entities.get('tableName', '')
            frontend_entities['limit'] = entities.get('limit')
        
        # 如果 equipment 不是列表，转换为列表
        if frontend_entities['equipment'] and not isinstance(frontend_entities['equipment'], list):
            frontend_entities['equipment'] = [frontend_entities['equipment']]
        
        return {
            'type': frontend_type,
            'entities': frontend_entities,
            'confidence': result.get('confidence', 0.0),
            'clarifications': result.get('clarifications', [])
        }


def get_intent_recognizer(llm_provider=None) -> IntentRecognizer:
    """获取意图识别器实例"""
    return IntentRecognizer(llm_provider=llm_provider)
