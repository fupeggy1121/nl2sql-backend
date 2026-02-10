#!/usr/bin/env python3
"""通过SQL直接查询所有Supabase表"""

import json
from app.services.supabase_client import SupabaseClient

def get_all_tables_via_sql():
    """通过SQL查询获取所有表信息"""
    client = SupabaseClient()
    
    print("=" * 80)
    print("直接通过SQL查询 - Supabase所有表")
    print("=" * 80)
    
    try:
        # 首先获取所有表名
        print("\n[步骤1] 获取所有表名...")
        
        tables_sql = """
        SELECT 
            tablename,
            schemaname,
            tableowner
        FROM pg_catalog.pg_tables 
        WHERE schemaname = 'public'
        ORDER BY tablename
        """
        
        # 使用 Supabase 的 RPC 或直接查询
        # 我们可以尝试创建一个临时视图或使用 RPC
        # 但最直接的方式是查询一个我们知道存在的表，然后通过错误消息推断
        
        # 让我们尝试另一个方法：通过尝试访问来获取表列表
        possible_tables = get_tables_from_sql_error(client)
        
        if possible_tables:
            print(f"\n✓ 通过SQL错误消息推断找到 {len(possible_tables)} 张表")
            for table in sorted(possible_tables):
                print(f"  - {table}")
        
    except Exception as e:
        print(f"错误: {str(e)}")

def get_tables_from_sql_error(client):
    """通过SQL错误消息来推断表名"""
    # 当查询不存在的表时，Supabase会给出提示
    # 例如: "Could not find the table 'public.xxxxx' in the schema cache"
    # 这意味着系统知道所有的表
    
    print("\n[方法] 通过系统表查询...")
    
    # 尝试直接查询每一个我们知道或推测存在的表
    # 但实际上，我们需要一个更智能的方法
    
    # 让我们创建一个包含所有可能表名的列表，包括系统表
    possible_names = []
    
    # 根据Supabase的API限制，某些表可能无法通过REST API访问
    # 但我们可以尝试通过RPC或其他方式
    
    print("通过 Supabase 客户端直接查询...")
    
    # 尝试查询一些可能的表
    guessed_tables = [
        # 已知的表
        'quality_records', 'oee_records', 'sub_batches', 'parameters', 
        'stations', 'products', 'batches', 'production_orders', 
        'equipment', 'equipment_groups', 'annotation_audit_log',
        
        # 从截图中我们知道总共有34张，但我们需要找到剩余的23张
        # 尝试一些常见的表名
        'users', 'roles', 'permissions', 'settings', 'config',
        'logs', 'audit', 'documents', 'attachments',
        'customers', 'suppliers', 'vendors',
        'inventory', 'warehouse', 'stock',
        'purchase_orders', 'sales_orders', 'invoices',
        'employees', 'departments', 'shifts',
        'maintenance', 'repairs', 'inspections',
        'recipes', 'formulations', 'routes',
        'process_steps', 'operations', 'procedures',
        'components', 'assemblies', 'bom_items',
        'measurements', 'test_results', 'inspections',
        'alerts', 'notifications', 'messages',
        'reports', 'dashboards', 'analytics'
    ]
    
    found = []
    for table in sorted(set(guessed_tables)):
        try:
            result = client.client.table(table).select('*').limit(0).execute()
            found.append(table)
        except:
            pass
    
    return found

def get_all_tables_count():
    """获取所有表的计数"""
    client = SupabaseClient()
    
    print("\n" + "=" * 80)
    print("方法2: 通过创建SQL查询来获取表列表")
    print("=" * 80)
    
    # 尝试通过 RPC 函数调用
    try:
        # 检查是否有 pg_tables 或类似的 RPC
        result = client.client.rpc('get_tables').execute()
        print(f"RPC 结果: {result}")
    except Exception as e:
        print(f"RPC 调用失败: {str(e)}")
    
    # 尝试直接查询 information_schema
    print("\n方法3: 通过 SQL 查询工具...")
    print("""
    请在 Supabase SQL 编辑器中运行以下查询来获取所有表：
    
    SELECT 
        tablename,
        schemaname,
        tableowner
    FROM pg_catalog.pg_tables 
    WHERE schemaname = 'public'
    ORDER BY tablename;
    
    这会返回所有34张表的信息。
    """)

if __name__ == "__main__":
    get_all_tables_count()
    get_all_tables_via_sql()
