#!/usr/bin/env python3
"""
测试表名修复功能 - 确保 NL2SQL 转换器能正确处理不存在的表名
"""

import asyncio
import json
from app.services.nl2sql_enhanced import get_enhanced_nl2sql_converter
from app.services.supabase_client import SupabaseClient

async def test_table_name_validation():
    """测试表名验证和修正"""
    
    print("\n" + "="*70)
    print("测试表名修复功能")
    print("="*70)
    
    converter = get_enhanced_nl2sql_converter()
    supabase = SupabaseClient()
    
    # 刷新元数据
    converter.refresh_metadata()
    
    # 获取有效的表名
    metadata = converter.annotation_metadata.get('tables', {})
    print(f"\n已加载 {len(metadata)} 张表:")
    for table_name, table_info in sorted(metadata.items())[:10]:
        cn_name = table_info.get('name_cn', '')
        print(f"  • {table_name:<35} → {cn_name}")
    
    # 测试用例
    test_cases = [
        {
            'nl': '查询当前状态为可用的载具',
            'expected_table': 'carriers',
            'description': '查询载具（应该映射到 carriers）'
        },
        {
            'nl': '查询所有订单',
            'expected_table': 'production_orders',
            'description': '查询订单（应该映射到 production_orders）'
        },
        {
            'nl': '查询所有产品',
            'expected_table': 'products',
            'description': '查询产品'
        },
        {
            'nl': '查询所有设备信息',
            'expected_table': 'equipment',
            'description': '查询设备'
        },
        {
            'nl': '查询晶圆信息',
            'expected_table': 'wafers',
            'description': '查询晶圆'
        }
    ]
    
    print("\n" + "="*70)
    print("测试用例")
    print("="*70)
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试 {i}: {test_case['description']}")
        print(f"  输入: {test_case['nl']}")
        print(f"  预期表: {test_case['expected_table']}")
        
        sql = converter.convert(test_case['nl'])
        
        if sql:
            print(f"  生成的 SQL:")
            # 格式化显示 SQL
            for line in sql.split(';')[0].split('\n'):
                print(f"    {line}")
            
            # 检查 SQL 中是否包含预期的表名
            if test_case['expected_table'].lower() in sql.lower():
                print(f"  ✅ 通过：SQL 包含预期的表名 '{test_case['expected_table']}'")
                passed += 1
            else:
                print(f"  ❌ 失败：SQL 不包含预期的表名 '{test_case['expected_table']}'")
                failed += 1
        else:
            print(f"  ❌ 失败：SQL 生成返回 None")
            failed += 1
    
    print("\n" + "="*70)
    print(f"测试结果统计")
    print("="*70)
    print(f"✅ 通过: {passed}/{len(test_cases)}")
    print(f"❌ 失败: {failed}/{len(test_cases)}")
    print(f"\n得分: {passed}/{len(test_cases)} ({100*passed//len(test_cases)}%)")
    
    if failed == 0:
        print("\n🎉 所有测试通过！表名映射功能工作正常")
    else:
        print(f"\n⚠️ 有 {failed} 个测试失败，需要进一步调试")

if __name__ == "__main__":
    asyncio.run(test_table_name_validation())
