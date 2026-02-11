#!/usr/bin/env python3
"""
测试查询执行器 - 验证WHERE条件是否被正确处理
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from app.services.query_executor import QueryExecutor
from app.services.supabase_client import SupabaseClient
from app.services.postgresql_executor import PostgreSQLExecutor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_direct_sql_execution():
    """测试SQL WHERE条件是否被正确执行"""
    
    print("\n" + "="*70)
    print("测试 SQL WHERE 条件执行")
    print("="*70)
    
    # 初始化Supabase客户端
    sb_client = SupabaseClient()
    if not sb_client.is_connected():
        print("❌ Supabase client not connected")
        return False
    
    print("✅ Supabase client connected")
    
    # 创建查询执行器
    executor = QueryExecutor(sb_client)
    
    # 测试查询
    test_queries = [
        {
            'name': '查询所有可用的载具',
            'sql': "SELECT * FROM carriers WHERE status = 'available';",
            'expected_filter': 'available'
        },
        {
            'name': '查询所有正在使用的载具',
            'sql': "SELECT * FROM carriers WHERE status = 'in_use';",
            'expected_filter': 'in_use'
        },
        {
            'name': '查询可用载具的数量',
            'sql': "SELECT COUNT(*) as count FROM carriers WHERE status = 'available';",
            'expected_filter': 'available'
        },
    ]
    
    all_passed = True
    
    for test in test_queries:
        print(f"\n测试: {test['name']}")
        print(f"SQL: {test['sql']}")
        
        # 执行查询
        result = executor.execute_query(test['sql'])
        
        if result['success']:
            data = result['data']
            count = result['count']
            print(f"✅ 查询成功: 返回 {count} 条记录")
            
            # 验证结果中的过滤条件
            if count > 0:
                # 检查第一条记录是否包含status字段
                first_row = data[0]
                if 'status' in first_row:
                    status_value = first_row['status']
                    print(f"   第一条数据的status: {status_value}")
                    if status_value == test['expected_filter']:
                        print(f"   ✅ 过滤条件正确应用")
                    else:
                        print(f"   ⚠️ 过滤条件可能未正确应用")
                        # 检查所有返回的status值
                        statuses = [row.get('status') for row in data]
                        unique_statuses = set(statuses)
                        print(f"   返回的所有status值: {unique_statuses}")
                        if unique_statuses == {test['expected_filter']}:
                            print(f"   ✅ 实际上过滤条件正确")
                        else:
                            print(f"   ❌ 过滤条件未正确应用！")
                            all_passed = False
                else:
                    print(f"   ⚠️ 结果中没有status字段")
            else:
                print(f"   ℹ️ 没有返回数据（可能该条件下确实没有数据）")
        else:
            print(f"❌ 查询失败: {result.get('error')}")
            all_passed = False
    
    # 总结
    print("\n" + "="*70)
    if all_passed:
        print("✅ 所有测试通过！")
    else:
        print("❌ 某些测试失败")
    print("="*70)
    
    return all_passed

def compare_results():
    """比较直接SQL执行和旧方法的结果"""
    print("\n" + "="*70)
    print("比较 PostgreSQL 直接执行 vs PostgREST API 执行")
    print("="*70)
    
    sql = "SELECT * FROM carriers WHERE status = 'available';"
    
    # 方式1: PostgreSQL直接连接
    print("\n【方式1: PostgreSQL 直接连接】")
    pg_executor = PostgreSQLExecutor()
    if pg_executor.connect():
        pg_executor.cursor.execute(sql)
        rows = pg_executor.cursor.fetchall()
        print(f"✅ 返回 {len(rows)} 条记录")
        pg_executor.close()
    else:
        print("❌ PostgreSQL连接失败")
        return False
    
    # 方式2: 使用QueryExecutor（应该使用PostgreSQL直接连接）
    print("\n【方式2: QueryExecutor（改进版）】")
    sb_client = SupabaseClient()
    executor = QueryExecutor(sb_client)
    result = executor.execute_query(sql)
    
    if result['success']:
        print(f"✅ 返回 {result['count']} 条记录")
        return result['count'] == len(rows)
    else:
        print(f"❌ 查询失败: {result['error']}")
        return False

if __name__ == '__main__':
    # 运行测试
    try:
        test_passed = test_direct_sql_execution()
        
        # 额外的对比测试
        # compare_passed = compare_results()
        
        sys.exit(0 if test_passed else 1)
    except Exception as e:
        logger.error(f"Test error: {str(e)}")
        sys.exit(1)
