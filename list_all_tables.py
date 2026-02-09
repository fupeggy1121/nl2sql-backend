#!/usr/bin/env python3
"""获取Supabase中的所有表（完整列表）"""

import json
from app.services.supabase_client import get_supabase_client

def get_all_tables():
    """从 information_schema 获取所有表"""
    client = get_supabase_client()
    
    try:
        # 直接使用 Supabase 客户端的 RPC 或查询方法
        # 首先尝试查询 information_schema.tables
        result = client.client.table('information_schema.tables').select('table_name').eq(
            'table_schema', 'public'
        ).execute()
        
        print("方法1: 直接查询 information_schema.tables")
        print(f"结果: {result}")
        
    except Exception as e:
        print(f"方法1 失败: {str(e)}")
    
    print("\n" + "=" * 60)
    print("方法2: 尝试通过 information_schema 检索所有表")
    print("=" * 60)
    
    try:
        # 使用 Supabase 的 REST API 来执行自定义查询
        # 构造正确的 SQL 查询
        query = """
        SELECT 
            table_name,
            table_type,
            table_schema
        FROM information_schema.tables 
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name
        """
        
        # 尝试使用 RPC 或者其他方式
        from postgrest import AsyncPostgrestQueryBuilder
        import asyncio
        
        # 获取连接信息
        client_obj = client.client
        print(f"\nSupabase 客户端信息:")
        print(f"  Base URL: {client_obj.base_url if hasattr(client_obj, 'base_url') else '未知'}")
        
    except Exception as e:
        print(f"方法2 失败: {str(e)}")
    
    print("\n" + "=" * 60)
    print("方法3: 枚举更多已知表名")
    print("=" * 60)
    
    # 尝试更多的表名
    possible_tables = [
        'device', 'equipment', 'production_orders', 'products',
        'equipment_list', 'devices', 'production', 'machines',
        'oee_metrics', 'shift_data', 'downtime', 'orders',
        'materials', 'users', 'roles', 'permissions',
        'logs', 'audit', 'settings', 'config',
        'inventory', 'warehouses', 'locations',
        'suppliers', 'vendors', 'customers',
        'employees', 'departments', 'positions',
        'shifts', 'schedules', 'attendance',
        'maintenance', 'repairs', 'inspections',
        'quality_control', 'defects', 'testing',
        'bom', 'components', 'assemblies',
        'routes', 'stations', 'processes',
        'recipes', 'formulations', 'specifications',
        'batches', 'lots', 'serials',
        'documents', 'attachments', 'files',
        'alerts', 'notifications', 'messages',
        'dashboards', 'reports', 'analytics',
        # 更多系统表
        'pg_tables', 'pg_class', 'pg_namespace'
    ]
    
    found_tables = []
    not_found = []
    
    for table_name in possible_tables:
        try:
            # 尝试 SELECT COUNT(*) 来检查表是否存在
            result = client.client.table(table_name).select('*', count='exact').limit(0).execute()
            found_tables.append({
                'name': table_name,
                'rows': result.count if hasattr(result, 'count') else 0
            })
            print(f"✓ {table_name:<30} ({result.count if hasattr(result, 'count') else '?'} 行)")
        except Exception as e:
            not_found.append(table_name)
    
    print(f"\n找到的表数: {len(found_tables)}")
    if not_found:
        print(f"未找到的表数: {len(not_found)}")
    
    return found_tables

if __name__ == "__main__":
    tables = get_all_tables()
