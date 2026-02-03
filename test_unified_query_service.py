"""
统一查询服务测试
"""

import asyncio
import json
from app.services.unified_query_service import (
    get_unified_query_service,
    QueryIntent,
    QueryType
)


async def test_unified_query_service():
    """测试统一查询服务"""
    
    service = get_unified_query_service()
    print("\n" + "="*70)
    print("统一查询服务测试")
    print("="*70)
    
    # 测试1: 简单的OEE查询
    print("\n[测试1] 简单的OEE查询")
    print("-" * 70)
    
    query1 = "查询今天各设备的OEE数据"
    print(f"查询: {query1}")
    
    try:
        query_plan, query_result = await service.process_natural_language_query(
            query1,
            execution_mode='explain'
        )
        
        print(f"\n✅ 意图识别结果:")
        print(f"  • 查询类型: {query_plan.query_intent.query_type.value}")
        print(f"  • 指标: {query_plan.query_intent.metric}")
        print(f"  • 时间范围: {query_plan.query_intent.time_range}")
        print(f"  • 置信度: {query_plan.query_intent.confidence:.2%}")
        print(f"  • 需要澄清: {query_plan.query_intent.clarification_needed}")
        
        if query_plan.generated_sql:
            print(f"\n✅ 生成的SQL:")
            print(f"  {query_plan.generated_sql}")
        
        if query_plan.explanation:
            print(f"\n✅ SQL解释:")
            print(f"  {query_plan.explanation}")
        
        if query_plan.requires_clarification:
            print(f"\n⚠️ 需要澄清:")
            print(f"  {query_plan.clarification_message}")
    
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    # 测试2: 对比查询
    print("\n\n[测试2] 对比查询")
    print("-" * 70)
    
    query2 = "对比本周不同设备的OEE"
    print(f"查询: {query2}")
    
    try:
        query_plan, query_result = await service.process_natural_language_query(
            query2,
            execution_mode='explain'
        )
        
        print(f"\n✅ 意图识别结果:")
        print(f"  • 查询类型: {query_plan.query_intent.query_type.value}")
        print(f"  • 对比: {query_plan.query_intent.comparison}")
        print(f"  • 置信度: {query_plan.query_intent.confidence:.2%}")
        
        if query_plan.generated_sql:
            print(f"\n✅ 生成的SQL:")
            print(f"  {query_plan.generated_sql}")
    
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    # 测试3: 模糊查询（需要澄清）
    print("\n\n[测试3] 模糊查询（需要澄清）")
    print("-" * 70)
    
    query3 = "查询数据"
    print(f"查询: {query3}")
    
    try:
        query_plan, query_result = await service.process_natural_language_query(
            query3,
            execution_mode='explain'
        )
        
        print(f"\n⚠️ 意图识别结果:")
        print(f"  • 查询类型: {query_plan.query_intent.query_type.value}")
        print(f"  • 需要澄清: {query_plan.query_intent.clarification_needed}")
        print(f"  • 置信度: {query_plan.query_intent.confidence:.2%}")
        
        if query_plan.query_intent.clarification_questions:
            print(f"\n❓ 澄清问题:")
            for i, q in enumerate(query_plan.query_intent.clarification_questions, 1):
                print(f"  {i}. {q}")
    
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    # 测试4: 测试schema上下文
    print("\n\n[测试4] Schema上下文")
    print("-" * 70)
    
    query4 = "查询生产订单"
    print(f"查询: {query4}")
    
    try:
        query_plan, query_result = await service.process_natural_language_query(
            query4,
            execution_mode='explain'
        )
        
        if query_plan.schema_context:
            print(f"\n✅ Schema上下文:")
            print(f"  • 相关表: {query_plan.schema_context.get('tables', [])}")
            print(f"  • 总列数: {query_plan.schema_context.get('total_columns', 0)}")
            print(f"  • 元数据更新时间: {query_plan.schema_context.get('metadata_updated')}")
    
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    # 测试5: Schema元数据
    print("\n\n[测试5] Schema元数据")
    print("-" * 70)
    
    try:
        metadata = service.nl2sql_converter.get_metadata_summary()
        print(f"\n✅ 元数据摘要:")
        print(f"  • 表数量: {metadata.get('tables', 0)}")
        print(f"  • 列数量: {metadata.get('columns', 0)}")
        print(f"  • 表名: {metadata.get('table_names', [])}")
        print(f"  • 最后更新: {metadata.get('last_updated')}")
    
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    print("\n" + "="*70)
    print("测试完成")
    print("="*70)


async def test_query_plan_serialization():
    """测试查询计划序列化"""
    
    service = get_unified_query_service()
    
    print("\n" + "="*70)
    print("查询计划序列化测试")
    print("="*70)
    
    query = "查询今天的OEE"
    
    try:
        query_plan, _ = await service.process_natural_language_query(query)
        
        # 序列化为JSON
        plan_dict = query_plan.to_dict()
        plan_json = json.dumps(plan_dict, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 序列化成功:")
        print(plan_json[:500] + "..." if len(plan_json) > 500 else plan_json)
        
        # 验证可以再次反序列化
        plan_data = json.loads(plan_json)
        print(f"\n✅ 反序列化成功:")
        print(f"  • 查询类型: {plan_data['query_intent']['query_type']}")
        print(f"  • 生成SQL: {bool(plan_data['generated_sql'])}")
    
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    print("\n" + "="*70)


async def main():
    """主测试函数"""
    await test_unified_query_service()
    await test_query_plan_serialization()


if __name__ == '__main__':
    asyncio.run(main())
