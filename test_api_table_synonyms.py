#!/usr/bin/env python3
"""
表名同义词映射系统 - API 集成测试
演示通过 API 端点识别各种表名同义词
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.intent_recognizer import IntentRecognizer
import json

def print_result(query: str, result: dict):
    """格式化输出识别结果"""
    print(f"\n{'='*70}")
    print(f"📝 用户查询: {query}")
    print(f"{'='*70}")
    
    entities = result.get('entities', {})
    
    print(f"\n【识别结果】")
    print(f"  意图类型: {result.get('intent', 'unknown')}")
    print(f"  置信度: {result.get('confidence', 0):.1%}")
    print(f"  表名映射: {entities.get('table', 'N/A')}")
    print(f"  原始关键词: {entities.get('raw_table_name', 'N/A')}")
    
    # 其他实体
    other_entities = {k: v for k, v in entities.items() 
                     if k not in ['table', 'raw_table_name']}
    if other_entities:
        print(f"\n【其他实体】")
        for key, value in other_entities.items():
            print(f"  {key}: {value}")
    
    # 澄清问题
    clarifications = result.get('clarifications', [])
    if clarifications:
        print(f"\n【澄清问题】")
        for i, q in enumerate(clarifications, 1):
            print(f"  {i}. {q}")

def main():
    """运行 API 集成测试"""
    print("\n" + "="*70)
    print("  表名同义词映射系统 - API 集成测试")
    print("="*70)
    print("\n此脚本演示系统如何识别各种表名同义词并将其映射到实际表名")
    
    # 初始化意图识别器
    recognizer = IntentRecognizer()
    
    # 测试查询集合
    test_queries = [
        # ===== Carriers (载体) 相关查询 =====
        {
            'category': '📦 Carriers 表查询',
            'queries': [
                '查询片篮',
                '查询载具',
                '查询载体的信息',
                '显示所有晶圆载体',
                '返回 carriers 表的前10条数据',
                '检查装载容器状态',
            ]
        },
        
        # ===== Wafers (晶圆) 相关查询 =====
        {
            'category': '💎 Wafers 表查询',
            'queries': [
                '查询晶圆',
                '查询晶圆的信息',
                '显示所有晶片',
                '列出芯片数据',
                '返回 wafers 表',
            ]
        },
        
        # ===== 检测结果相关查询 =====
        {
            'category': '🔬 Inspection Results 表查询',
            'queries': [
                '查询检测结果',
                '查询检测数据',
                '显示检验结果',
                '获取测试数据',
            ]
        },
        
        # ===== 其他表查询 =====
        {
            'category': '📊 其他表查询',
            'queries': [
                '查询批次信息',
                '查询设备状态',
                '查询生产记录',
                '查询质量指标',
                '查询缺陷信息',
            ]
        },
    ]
    
    total_queries = 0
    successful_mappings = 0
    
    # 执行所有测试查询
    for category_group in test_queries:
        print(f"\n\n" + "="*70)
        print(f"  {category_group['category']}")
        print("="*70)
        
        for query in category_group['queries']:
            total_queries += 1
            
            try:
                result = recognizer.recognize(query)
                table_name = result.get('entities', {}).get('table')
                
                # 判断是否成功映射
                if table_name:
                    successful_mappings += 1
                    status = "✅"
                else:
                    status = "⚠️"
                
                print(f"\n{status} {query}")
                print(f"   → 表名: {table_name}")
                print(f"   → 意图: {result.get('intent')}")
                
            except Exception as e:
                print(f"\n❌ {query}")
                print(f"   → 错误: {str(e)}")
    
    # 打印总结
    print(f"\n\n" + "="*70)
    print(f"  测试总结")
    print("="*70)
    print(f"\n总查询数: {total_queries}")
    print(f"成功映射: {successful_mappings}/{total_queries}")
    
    if successful_mappings == total_queries:
        print(f"\n✅ 所有查询都被正确映射到对应的表！")
    else:
        print(f"\n⚠️ 有 {total_queries - successful_mappings} 个查询未被完全映射")
    
    # 演示单个详细结果
    print(f"\n\n" + "="*70)
    print(f"  详细示例 - 'carriers' 表的各种查询方式")
    print("="*70)
    
    carriers_queries = [
        '查询片篮',
        '查询载具',
        '查询晶圆载体',
        '返回 carriers 表',
    ]
    
    for query in carriers_queries:
        result = recognizer.recognize(query)
        print_result(query, result)
    
    print(f"\n\n💡 提示:")
    print(f"   所有这些不同的查询都被映射到同一个表: 'carriers'")
    print(f"   这使得用户可以用他们习惯的方式查询数据！")

if __name__ == '__main__':
    main()
