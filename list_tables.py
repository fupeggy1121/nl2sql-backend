#!/usr/bin/env python3
"""列出Supabase中的所有表"""

from app.services.supabase_client import get_supabase_client

def list_all_tables():
    """列出所有可用的表"""
    client = get_supabase_client()
    
    # 尝试查询已知的表
    tables_to_try = [
        'device', 'equipment', 'production_orders', 'products',
        'equipment_list', 'devices', 'production', 'machines',
        'oee_metrics', 'shift_data', 'downtime'
    ]
    
    print("可用的 Supabase 数据库表:")
    print("-" * 50)
    
    available_tables = []
    for table_name in tables_to_try:
        try:
            result = client.client.table(table_name).select('*').limit(0).execute()
            available_tables.append(table_name)
            print(f"✓ {table_name}")
        except Exception as e:
            pass
    
    if not available_tables:
        print("未找到任何可访问的表")
        print("\n尝试使用 RPC 查询系统表...")
        try:
            # 使用 RPC 调用 PostgreSQL 函数来获取表列表
            result = client.client.rpc('get_tables').execute()
            print(f"RPC 结果: {result}")
        except:
            pass
    
    return available_tables

if __name__ == "__main__":
    tables = list_all_tables()
    print(f"\n总共找到 {len(tables)} 个表")
