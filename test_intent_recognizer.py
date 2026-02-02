#!/usr/bin/env python3
"""
意图识别 API 测试脚本
验证后端 /api/query/recognize-intent 接口
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.intent_recognizer import IntentRecognizer
import json

# 测试用例
TEST_CASES = [
    {
        'query': '返回 wafers 表的前300条数据',
        'expected_intent': 'direct_query',
        'expected_entities': ['table', 'limit']
    },
    {
        'query': '查询今天的产量',
        'expected_intent': 'query_production',
        'expected_entities': ['timeRange']
    },
    {
        'query': '本月的良品率是多少',
        'expected_intent': 'query_quality',
        'expected_entities': ['timeRange', 'metrics']
    },
    {
        'query': '设备A的OEE和稼动率',
        'expected_intent': 'query_equipment',
        'expected_entities': ['equipment', 'metrics']
    },
    {
        'query': '生成本月的生产报表',
        'expected_intent': 'generate_report',
        'expected_entities': ['timeRange']
    },
    {
        'query': '比较本月和上月的产量',
        'expected_intent': 'compare_analysis',
        'expected_entities': ['metrics']
    }
]


def run_tests():
    """运行所有测试"""
    print('=' * 70)
    print('意图识别 API 测试')
    print('=' * 70)
    print()
    
    # 初始化识别器（不使用 LLM，仅使用规则引擎）
    recognizer = IntentRecognizer(llm_provider=None)
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(TEST_CASES, 1):
        query = test_case['query']
        expected_intent = test_case['expected_intent']
        expected_entities = test_case['expected_entities']
        
        print(f"[测试 {i}/{len(TEST_CASES)}]")
        print(f"查询: {query}")
        
        # 执行识别
        result = recognizer.recognize(query)
        
        # 检查结果
        intent_match = result['intent'] == expected_intent
        entities_match = all(
            entity in result['entities'] 
            for entity in expected_entities
        )
        
        success = intent_match and entities_match
        
        print(f"期望意图: {expected_intent}")
        print(f"识别意图: {result['intent']}")
        print(f"置信度: {result['confidence']:.2f}")
        print(f"识别方法: {', '.join(result['methodsUsed'])}")
        print(f"提取的实体: {json.dumps(result['entities'], ensure_ascii=False, indent=2)}")
        
        if result['clarifications']:
            print(f"需要澄清: {json.dumps(result['clarifications'], ensure_ascii=False)}")
        
        status = '✅ PASS' if success else '❌ FAIL'
        print(f"状态: {status}")
        print('-' * 70)
        print()
        
        if success:
            passed += 1
        else:
            failed += 1
    
    # 输出总结
    print('=' * 70)
    print('测试总结')
    print('=' * 70)
    print(f'总计: {len(TEST_CASES)} 个测试')
    print(f'通过: {passed} ✅')
    print(f'失败: {failed} ❌')
    print(f'成功率: {passed/len(TEST_CASES)*100:.1f}%')
    print()
    
    return failed == 0


def test_api_integration():
    """测试 Flask API 集成"""
    print('=' * 70)
    print('Flask API 集成测试')
    print('=' * 70)
    print()
    
    try:
        from run import app
        
        with app.test_client() as client:
            # 测试基本功能
            print("[测试 1] 正常请求")
            response = client.post(
                '/api/query/recognize-intent',
                json={'query': '查询今天的产量'},
                content_type='application/json'
            )
            
            print(f"状态码: {response.status_code}")
            result = response.get_json()
            print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
            print()
            
            if response.status_code != 200:
                print("❌ API 返回非 200 状态码")
                return False
            
            # 测试空请求
            print("[测试 2] 缺失 query 参数")
            response = client.post(
                '/api/query/recognize-intent',
                json={},
                content_type='application/json'
            )
            
            print(f"状态码: {response.status_code}")
            result = response.get_json()
            print(f"错误: {result.get('error')}")
            print()
            
            if response.status_code != 400:
                print("❌ 应该返回 400 状态码")
                return False
            
            # 测试空查询
            print("[测试 3] 空查询字符串")
            response = client.post(
                '/api/query/recognize-intent',
                json={'query': '   '},
                content_type='application/json'
            )
            
            print(f"状态码: {response.status_code}")
            result = response.get_json()
            print(f"错误: {result.get('error')}")
            print()
            
            if response.status_code != 400:
                print("❌ 应该返回 400 状态码")
                return False
            
            print("✅ Flask API 集成测试通过")
            return True
            
    except Exception as e:
        print(f"❌ Flask 测试失败: {str(e)}")
        return False


def test_performance():
    """性能测试"""
    print('=' * 70)
    print('性能测试')
    print('=' * 70)
    print()
    
    import time
    
    recognizer = IntentRecognizer(llm_provider=None)
    
    test_query = '最近7天各产线的良品率对比'
    iterations = 10
    
    print(f"测试查询: {test_query}")
    print(f"迭代次数: {iterations}")
    print()
    
    times = []
    for i in range(iterations):
        start = time.time()
        result = recognizer.recognize(test_query)
        elapsed = (time.time() - start) * 1000  # 转换为毫秒
        times.append(elapsed)
    
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    
    print(f"平均响应时间: {avg_time:.2f}ms")
    print(f"最小响应时间: {min_time:.2f}ms")
    print(f"最大响应时间: {max_time:.2f}ms")
    print()
    
    if avg_time < 10:  # 应该在 10ms 以内
        print("✅ 性能测试通过（响应时间 < 10ms）")
        return True
    else:
        print("⚠️ 性能较慢（响应时间 > 10ms）")
        return False


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='意图识别 API 测试')
    parser.add_argument('--type', choices=['unit', 'api', 'perf', 'all'], 
                       default='all', help='测试类型')
    args = parser.parse_args()
    
    results = []
    
    if args.type in ['unit', 'all']:
        results.append(('单元测试', run_tests()))
    
    if args.type in ['api', 'all']:
        results.append(('API 集成测试', test_api_integration()))
    
    if args.type in ['perf', 'all']:
        results.append(('性能测试', test_performance()))
    
    print()
    print('=' * 70)
    print('最终结果')
    print('=' * 70)
    
    for name, passed in results:
        status = '✅' if passed else '❌'
        print(f"{status} {name}")
    
    all_passed = all(passed for _, passed in results)
    exit(0 if all_passed else 1)
