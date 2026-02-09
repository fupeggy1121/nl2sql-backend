#!/usr/bin/env python3
"""直接查询 information_schema 获取所有表"""

import json
from app.services.supabase_client import SupabaseClient

def get_all_tables_via_sql():
    """通过执行SQL查询获取所有表"""
    client = SupabaseClient()
    
    print("=" * 70)
    print("Supabase 数据库 - 所有表列表")
    print("=" * 70)
    
    try:
        # 使用 Supabase 的 rpc 调用或直接查询
        # 首先，尝试从已知的系统视图或表获取信息
        
        # 方法：通过尝试查询多个大表来推断存在的表
        # 我们需要一个全面的表名列表
        
        # 从 Supabase 的元数据API获取表列表
        response = client.client.table('information_schema_tables').select('*').execute()
        print(f"通过 information_schema_tables 查询:\n{response}")
        
    except Exception as e:
        print(f"方法失败: {str(e)}")
    
    print("\n使用系统目录查询...")
    
    try:
        # 尝试从 pg_tables 视图获取（如果可访问）
        response = client.client.table('pg_tables').select('tablename').execute()
        print(f"\n从 pg_tables 获取的表:")
        for row in response.data:
            print(f"  - {row.get('tablename')}")
            
    except Exception as e:
        print(f"pg_tables 查询失败: {str(e)}")
    
    # 最后，尝试一个更广泛的表名列表
    print("\n" + "=" * 70)
    print("系统化扫描 - 尝试常见的表名模式")
    print("=" * 70)
    
    common_prefixes = [
        # 设备和工业相关
        'equipment', 'device', 'machine', 'station',
        # 生产相关
        'production', 'order', 'batch', 'lot', 'recipe',
        # 产品相关
        'product', 'sku', 'component', 'assembly', 'bom',
        # 质量相关
        'quality', 'defect', 'inspection', 'testing', 'test',
        # 物料相关
        'material', 'inventory', 'warehouse', 'stock',
        # 工艺相关
        'process', 'step', 'operation', 'route',
        # 人员相关
        'employee', 'operator', 'user', 'staff',
        # 系统相关
        'audit', 'log', 'config', 'setting', 'alert', 'notification',
        # 其他
        'data', 'report', 'dashboard', 'metric', 'kpi',
    ]
    
    found_tables = []
    
    # 扩展搜索：尝试单数和复数形式
    search_tables = set()
    for prefix in common_prefixes:
        search_tables.add(prefix)
        search_tables.add(prefix + 's')
        search_tables.add(prefix + '_list')
        search_tables.add(prefix + 'es')
        search_tables.add(prefix + '_data')
        search_tables.add(prefix + '_info')
        search_tables.add(prefix + '_records')
    
    # 也添加一些我们已知的表
    search_tables.update(['equipment', 'production_orders', 'products', 'stations', 'batches'])
    
    for table_name in sorted(search_tables):
        try:
            result = client.client.table(table_name).select('*', count='exact').limit(0).execute()
            row_count = result.count if hasattr(result, 'count') else 0
            found_tables.append({
                'name': table_name,
                'rows': row_count
            })
            print(f"✓ {table_name:<30} ({row_count:>6} 行)")
        except Exception:
            pass
    
    print("\n" + "=" * 70)
    print(f"总共找到 {len(found_tables)} 个表")
    print("=" * 70)
    
    # 按行数降序排列
    found_tables_sorted = sorted(found_tables, key=lambda x: x['rows'], reverse=True)
    
    print("\n表列表 (按行数降序):")
    print("-" * 70)
    total_rows = 0
    for table in found_tables_sorted:
        print(f"{table['name']:<35} | {table['rows']:>6} 行")
        total_rows += table['rows']
    
    print("-" * 70)
    print(f"{'总计':<35} | {total_rows:>6} 行")
    
    # 输出JSON格式
    print("\n" + "=" * 70)
    print("JSON 格式输出:")
    print("=" * 70)
    output = {
        'database': 'Supabase PostgreSQL',
        'total_tables': len(found_tables),
        'total_rows': total_rows,
        'tables': found_tables_sorted
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    
    return found_tables

if __name__ == "__main__":
    get_all_tables_via_sql()
