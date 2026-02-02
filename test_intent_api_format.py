"""
意图识别 API 响应格式验证测试
确保后端返回的 UserIntent 对象结构与前端接口保持一致
"""

import sys
import json
from typing import Dict, Any

# 前端定义的 UserIntent 接口
class UserIntentSchema:
    """前端 UserIntent 接口的 Python 表示"""
    
    VALID_TYPES = {'query', 'report', 'analysis', 'comparison', 'direct_table_query'}
    
    @staticmethod
    def validate(obj: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证对象是否符合 UserIntent 接口
        
        期望的结构:
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
            "confidence": number (0-1),
            "clarifications": string[]
        }
        
        Returns:
            {"valid": bool, "errors": list[str]}
        """
        errors = []
        
        # 检查必需字段
        required_fields = ['type', 'entities', 'confidence', 'clarifications']
        for field in required_fields:
            if field not in obj:
                errors.append(f"Missing required field: {field}")
        
        # 检查 type
        if 'type' in obj and obj['type'] not in UserIntentSchema.VALID_TYPES:
            errors.append(
                f"Invalid type '{obj['type']}'. Must be one of: {UserIntentSchema.VALID_TYPES}"
            )
        
        # 检查 entities 结构
        if 'entities' in obj:
            entities = obj['entities']
            required_entity_fields = ['metric', 'timeRange', 'equipment', 'shift', 'comparison']
            
            for field in required_entity_fields:
                if field not in entities:
                    errors.append(f"Missing entities.{field}")
            
            # 检查类型
            if 'metric' in entities and not isinstance(entities['metric'], str):
                errors.append(f"entities.metric must be string, got {type(entities['metric'])}")
            
            if 'timeRange' in entities and not isinstance(entities['timeRange'], str):
                errors.append(f"entities.timeRange must be string, got {type(entities['timeRange'])}")
            
            if 'equipment' in entities and not isinstance(entities['equipment'], list):
                errors.append(f"entities.equipment must be array, got {type(entities['equipment'])}")
            
            if 'shift' in entities and not isinstance(entities['shift'], list):
                errors.append(f"entities.shift must be array, got {type(entities['shift'])}")
            
            if 'comparison' in entities and not isinstance(entities['comparison'], bool):
                errors.append(f"entities.comparison must be boolean, got {type(entities['comparison'])}")
            
            # 检查可选字段类型
            if 'tableName' in entities and not isinstance(entities['tableName'], (str, type(None))):
                errors.append(f"entities.tableName must be string or null, got {type(entities['tableName'])}")
            
            if 'limit' in entities and not isinstance(entities['limit'], (int, type(None))):
                errors.append(f"entities.limit must be number or null, got {type(entities['limit'])}")
        
        # 检查 confidence
        if 'confidence' in obj:
            conf = obj['confidence']
            if not isinstance(conf, (int, float)):
                errors.append(f"confidence must be number, got {type(conf)}")
            elif not (0 <= conf <= 1):
                errors.append(f"confidence must be between 0 and 1, got {conf}")
        
        # 检查 clarifications
        if 'clarifications' in obj:
            if not isinstance(obj['clarifications'], list):
                errors.append(f"clarifications must be array, got {type(obj['clarifications'])}")
            else:
                for i, item in enumerate(obj['clarifications']):
                    if not isinstance(item, str):
                        errors.append(f"clarifications[{i}] must be string, got {type(item)}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


def test_response_format():
    """测试 API 响应格式"""
    import requests
    
    print("=" * 60)
    print("意图识别 API 响应格式验证")
    print("=" * 60)
    
    # 测试用例
    test_cases = [
        {
            'query': '返回 wafers 表的前300条数据',
            'expected_type': 'direct_table_query',
            'description': '直接表查询'
        },
        {
            'query': '查询今天的产量',
            'expected_type': 'query',
            'description': '生产查询'
        },
        {
            'query': '本月良品率是多少',
            'expected_type': 'query',
            'description': '质量查询'
        },
        {
            'query': '生成本周报表',
            'expected_type': 'report',
            'description': '报表生成'
        },
        {
            'query': '比较最近7天和上月的产量',
            'expected_type': 'analysis',
            'description': '对比分析'
        }
    ]
    
    api_url = 'http://localhost:5000/api/query/recognize-intent'
    
    print(f"\n📍 API 端点: {api_url}\n")
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"测试 {i}: {test_case['description']}")
        print(f"  输入: {test_case['query']}")
        
        try:
            response = requests.post(
                api_url,
                json={'query': test_case['query']},
                timeout=5
            )
            
            print(f"  状态码: {response.status_code}")
            
            if response.status_code != 200:
                print(f"  ❌ 失败: HTTP {response.status_code}")
                print(f"  响应: {response.text}")
                failed += 1
                print()
                continue
            
            data = response.json()
            
            # 验证格式
            validation = UserIntentSchema.validate(data)
            
            if not validation['valid']:
                print(f"  ❌ 格式验证失败:")
                for error in validation['errors']:
                    print(f"     - {error}")
                failed += 1
            else:
                # 检查意图类型是否符合预期
                if data.get('type') == test_case['expected_type']:
                    print(f"  ✅ 通过")
                    print(f"     意图类型: {data['type']}")
                    print(f"     置信度: {data['confidence']:.2f}")
                    print(f"     实体: {json.dumps(data['entities'], ensure_ascii=False, indent=6)}")
                    if data['clarifications']:
                        print(f"     澄清: {data['clarifications']}")
                    passed += 1
                else:
                    print(f"  ⚠️  意图类型不匹配")
                    print(f"     期望: {test_case['expected_type']}")
                    print(f"     实际: {data.get('type')}")
                    failed += 1
        
        except requests.exceptions.ConnectionError:
            print(f"  ❌ 无法连接到 API（请确保服务在运行）")
            failed += 1
        except Exception as e:
            print(f"  ❌ 错误: {str(e)}")
            failed += 1
        
        print()
    
    # 总结
    print("=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return failed == 0


def test_offline_format():
    """离线测试格式转换"""
    print("\n" + "=" * 60)
    print("离线格式转换测试")
    print("=" * 60)
    
    # 模拟后端返回的结果
    backend_result = {
        'success': True,
        'intent': 'direct_query',
        'confidence': 0.95,
        'entities': {
            'tableName': 'wafers',
            'limit': 300,
            'metric': 'general',
            'timeRange': '',
            'equipment': [],
            'shift': [],
            'comparison': False
        },
        'clarifications': [],
        'methodsUsed': ['rule']
    }
    
    print("\n📊 后端返回结果:")
    print(json.dumps(backend_result, ensure_ascii=False, indent=2))
    
    # 模拟格式转换
    from app.services.intent_recognizer import IntentRecognizer
    recognizer = IntentRecognizer()
    
    frontend_format = recognizer.to_frontend_format(backend_result)
    
    print("\n🎯 转换后的前端格式:")
    print(json.dumps(frontend_format, ensure_ascii=False, indent=2))
    
    # 验证格式
    validation = UserIntentSchema.validate(frontend_format)
    
    print("\n✔️ 格式验证:")
    if validation['valid']:
        print("  ✅ 符合前端接口规范")
    else:
        print("  ❌ 格式验证失败:")
        for error in validation['errors']:
            print(f"     - {error}")
    
    return validation['valid']


if __name__ == '__main__':
    import os
    
    # 检查是否在本地测试
    if os.getenv('TEST_OFFLINE'):
        success = test_offline_format()
    else:
        success = test_response_format()
    
    sys.exit(0 if success else 1)
