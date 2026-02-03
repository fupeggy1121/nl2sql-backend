"""
Intent recognition service - Python implementation
Supports hybrid rule-based and LLM approach
"""

from typing import Dict, List, Optional, Any
import re
import logging
import json

logger = logging.getLogger(__name__)


class IntentRecognizer:
    """MES system intent recognition service with hybrid rule and LLM approach"""
    
    def __init__(self, llm_provider=None):
        """Initialize intent recognizer with optional LLM provider"""
        self.llm_provider = llm_provider
        
        # Intent configuration
        self.intents = {
            'direct_query': {
                'keywords': ['返回', '查询', '显示', '获取', '列出', '表', 'select', 'from'],
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
            }
        }
    
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
            
            # Step 3: LLM confirmation
            llm_result = self._llm_based_match(user_input)
            
            logger.info(f"LLM match result: intent={llm_result['intent']}, "
                       f"confidence={llm_result['confidence']:.2f}")
            
            # Step 4: Merge results
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
        Keyword-based fast intent matching.

        Returns:
            dict: Intent matching result with keys: intent, confidence, entities
        """
        normalized_input = text.lower()
        scores = {}
        
        # Calculate match scores for each intent
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
    
    def _llm_based_match(self, text: str) -> Dict[str, Any]:
        """
        Intent recognition using DeepSeek LLM.

        Returns:
            dict: LLM matching result with keys: intent, confidence, entities, reasoning
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
        
        prompt = f"""Analyze the user query intent in MES system.

Possible intent types and descriptions:
{chr(10).join(f"- {k}: {v['description']}" for k, v in self.intents.items())}

User input: "{text}"

Return analysis result in JSON format (must be valid JSON):
{{
    "intent": "intent_type",
    "confidence": 0.95,
    "entities": {{
        "timeRange": "time_range",
        "metric": "metric"
    }},
    "reasoning": "reason_for_judgment"
}}"""
        
        try:
            response = self.llm_provider.generate(prompt)
            
            # Auto-remove markdown code block wrapper (e.g. ```json ... ```)
            if response.strip().startswith('```'):
                lines = response.strip().splitlines()
                json_str = '\n'.join(line for line in lines[1:] if not line.strip().startswith('```'))
            else:
                json_str = response
            
            # Parse JSON result
            result = json.loads(json_str)
            
            return {
                'intent': result.get('intent', 'other'),
                'confidence': float(result.get('confidence', 0.0)),
                'entities': result.get('entities', {}),
                'reasoning': result.get('reasoning', '')
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {str(e)}")
            logger.error(f"LLM raw response: {response}")
            return {
                'intent': 'other',
                'confidence': 0.0,
                'entities': {},
                'reasoning': 'Failed to parse LLM response',
                'llm_raw_response': response
            }
        except Exception as e:
            logger.error(f"LLM matching error: {str(e)}")
            logger.error(f"LLM raw response: {response}")
            return {
                'intent': 'other',
                'confidence': 0.0,
                'entities': {},
                'reasoning': f'LLM error: {str(e)}',
                'llm_raw_response': response
            }
    
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
        
        # Table name extraction
        table_match = re.search(r'(?:查询|返回|显示|获取)?\s*(\w+)\s*表', text)
        if table_match:
            entities['table'] = table_match.group(1)
        
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
