#!/usr/bin/env python3
"""
端到端测试 - 验证完整的 NL2SQL 查询流程
模拟用户输入"查询当前状态为可用的载具"的完整流程
"""

import asyncio
import json
from app.services.unified_query_service import UnifiedQueryService
from datetime import datetime

async def test_end_to_end_query():
    """测试完整的 NL2SQL 查询流程"""
    
    print("\n" + "="*70)
    print("端到端测试 - 载具查询")
    print("="*70)
    
    service = UnifiedQueryService()
    
    # 用户查询
    user_query = "查询当前状态为可用的载具"
    
    print(f"\n【用户输入】")
    print(f"  {user_query}")
    
    # 步骤 1: 意图识别
    print(f"\n【步骤 1】意图识别...")
    intent_result = service.intent_recognizer.recognize(user_query)
    print(f"  意图: {intent_result.get('intent')}")
    print(f"  置信度: {intent_result.get('confidence', 0):.2%}")
    print(f"  实体: {json.dumps(intent_result.get('entities', {}), ensure_ascii=False, indent=2)}")
    
    # 步骤 2: 执行完整的查询流程
    print(f"\n【步骤 2】执行 NL2SQL 查询流程...")
    result = await service.process_natural_language_query(user_query)
    
    print(f"  流程成功: {result.get('success', False)}")
    
    if 'query_plan' in result:
        query_plan = result['query_plan']
        print(f"\n【查询计划】")
        if query_plan.get('generated_sql'):
            print(f"  生成的 SQL:")
            for line in query_plan['generated_sql'].split('\n'):
                if line.strip():
                    print(f"    {line}")
        
        # 验证表名
        sql = query_plan.get('generated_sql', '')
        print(f"\n【表名验证】")
        if 'carriers' in sql.lower():
            print(f"  ✅ SQL 正确使用了 'carriers' 表")
        elif 'vehicles' in sql.lower():
            print(f"  ❌ SQL 错误地使用了 'vehicles' 表（不存在）")
        else:
            print(f"  ⚠️ 无法识别使用的表名")
    
    # 步骤 3: 查询结果
    if 'query_result' in result:
        query_result = result['query_result']
        print(f"\n【步骤 3】查询执行结果")
        
        if query_result.get('success', False):
            print(f"  ✅ 查询执行成功")
            print(f"  返回行数: {query_result.get('rows_count', 0)}")
            print(f"  查询用时: {query_result.get('query_time_ms', 0):.2f}ms")
            
            if query_result.get('rows_count', 0) > 0:
                print(f"\n【查询结果样本】")
                data = query_result.get('data', [])
                for i, row in enumerate(data[:3], 1):
                    print(f"  记录 {i}:")
                    for key, value in list(row.items())[:5]:  # 只显示前 5 个字段
                        print(f"    {key}: {value}")
                    if len(row) > 5:
                        print(f"    ... (共 {len(row)} 个字段)")
            else:
                print(f"  (查询返回 0 条记录)")
        else:
            print(f"  ❌ 查询执行失败")
            print(f"  错误: {query_result.get('error_message', 'Unknown error')}")
    
    print("\n" + "="*70)
    print("✅ 端到端测试完成")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(test_end_to_end_query())
