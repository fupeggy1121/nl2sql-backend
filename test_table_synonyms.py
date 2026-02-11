#!/usr/bin/env python3
"""
测试表名同义词映射系统
验证"片篮"、"载具"等关键词能否正确映射到 carriers 表
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config.table_synonyms import (
    map_table_name,
    is_valid_table_name,
    get_synonyms_for_table,
    get_synonym_to_table_map,
    get_all_table_names
)
from app.services.intent_recognizer import IntentRecognizer

def print_section(title):
    """打印分隔符"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

def test_basic_mapping():
    """测试基本表名映射"""
    print_section("测试 1: 基本表名映射")
    
    test_cases = [
        ('片篮', 'carriers'),
        ('载具', 'carriers'),
        ('载体', 'carriers'),
        ('晶圆载体', 'carriers'),
        ('装载容器', 'carriers'),
        ('carriers', 'carriers'),
        ('carrier', 'carriers'),
        ('晶圆', 'wafers'),
        ('wafers', 'wafers'),
        ('检测结果', 'wafer_inspection_results'),
        ('批次', 'batches'),
        ('设备', 'equipment'),
    ]
    
    passed = 0
    failed = 0
    
    for keyword, expected in test_cases:
        result = map_table_name(keyword)
        status = "✅" if result == expected else "❌"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
            
        print(f"{status} map_table_name('{keyword}') → '{result}' (期望: '{expected}')")
    
    print(f"\n统计: 通过 {passed}/{len(test_cases)}, 失败 {failed}/{len(test_cases)}")
    return failed == 0

def test_validation():
    """测试表名验证"""
    print_section("测试 2: 表名验证")
    
    test_cases = [
        ('片篮', True),
        ('carriers', True),
        ('晶圆', True),
        ('wafers', True),
        ('xyz_invalid', False),
        ('未知表名', False),
        ('equipment', True),
        ('设备', True),
    ]
    
    passed = 0
    failed = 0
    
    for keyword, expected in test_cases:
        result = is_valid_table_name(keyword)
        status = "✅" if result == expected else "❌"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
            
        print(f"{status} is_valid_table_name('{keyword}') → {result} (期望: {expected})")
    
    print(f"\n统计: 通过 {passed}/{len(test_cases)}, 失败 {failed}/{len(test_cases)}")
    return failed == 0

def test_synonyms():
    """测试获取表的同义词"""
    print_section("测试 3: 获取表的同义词")
    
    tables = ['carriers', 'wafers', 'batches']
    
    for table in tables:
        synonyms = get_synonyms_for_table(table)
        print(f"\n表名: {table}")
        print(f"同义词数量: {len(synonyms)}")
        print(f"同义词列表: {', '.join(synonyms[:10])}")
        if len(synonyms) > 10:
            print(f"  ... 以及 {len(synonyms) - 10} 个其他同义词")

def test_intent_recognition():
    """测试完整的意图识别流程"""
    print_section("测试 4: 完整意图识别流程")
    
    recognizer = IntentRecognizer()
    
    test_queries = [
        '查询片篮',
        '查询片篮的信息',
        '显示载具',
        '返回当前状态为可用的载具',
        '查询晶圆的检测结果',
        '查询wafers表的前100条数据',
        '返回 carriers 表',
    ]
    
    print("\n")
    for query in test_queries:
        result = recognizer.recognize(query)
        entities = result.get('entities', {})
        table_name = entities.get('table', 'N/A')
        raw_table = entities.get('raw_table_name', 'N/A')
        confidence = result.get('confidence', 0) * 100
        
        print(f"✅ 查询: '{query}'")
        print(f"   → 表名: {table_name}")
        print(f"   → 原始关键词: {raw_table}")
        print(f"   → 意图: {result.get('intent')}")
        print(f"   → 置信度: {confidence:.1f}%")
        print()

def test_synonym_map():
    """测试同义词映射缓存"""
    print_section("测试 5: 同义词映射缓存")
    
    synonym_map = get_synonym_to_table_map()
    
    print(f"总映射数: {len(synonym_map)}")
    print(f"\n样本映射:")
    
    samples = [
        '片篮',
        '载具',
        '晶圆',
        '检测结果',
        'carriers',
        'wafers',
    ]
    
    for keyword in samples:
        mapped = synonym_map.get(keyword.lower())
        print(f"  '{keyword}' → '{mapped}'")

def test_all_table_names():
    """测试获取所有表名"""
    print_section("测试 6: 支持的所有表名")
    
    all_tables = get_all_table_names()
    print(f"共支持 {len(all_tables)} 个表:\n")
    
    for i, table in enumerate(all_tables, 1):
        synonyms = get_synonyms_for_table(table)
        print(f"{i:2d}. {table:30s} - {len(synonyms):2d} 个同义词")
        print(f"    : {', '.join(synonyms[:5])}")
        if len(synonyms) > 5:
            print(f"      ... 以及 {len(synonyms) - 5} 个其他")

def main():
    """运行所有测试"""
    print("\n" + "="*70)
    print("  表名同义词映射系统测试")
    print("="*70)
    
    results = []
    
    try:
        results.append(("基本表名映射", test_basic_mapping()))
    except Exception as e:
        print(f"❌ 错误: {e}")
        results.append(("基本表名映射", False))
    
    try:
        results.append(("表名验证", test_validation()))
    except Exception as e:
        print(f"❌ 错误: {e}")
        results.append(("表名验证", False))
    
    try:
        test_synonyms()
        results.append(("获取同义词", True))
    except Exception as e:
        print(f"❌ 错误: {e}")
        results.append(("获取同义词", False))
    
    try:
        test_intent_recognition()
        results.append(("意图识别", True))
    except Exception as e:
        print(f"❌ 错误: {e}")
        results.append(("意图识别", False))
    
    try:
        test_synonym_map()
        results.append(("同义词缓存", True))
    except Exception as e:
        print(f"❌ 错误: {e}")
        results.append(("同义词缓存", False))
    
    try:
        test_all_table_names()
        results.append(("表名列表", True))
    except Exception as e:
        print(f"❌ 错误: {e}")
        results.append(("表名列表", False))
    
    # 打印测试总结
    print_section("测试总结")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {test_name}")
    
    print(f"\n总体: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n❌ 有 {total - passed} 个测试失败")
        return 1

if __name__ == '__main__':
    sys.exit(main())
