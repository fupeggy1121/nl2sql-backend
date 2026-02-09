#!/usr/bin/env python3
"""获取所有Supabase表的详细结构信息"""

import json
from app.services.supabase_client import SupabaseClient

def get_table_details(client, table_name):
    """获取单个表的详细信息"""
    try:
        # 获取数据和列信息
        result = client.client.table(table_name).select('*').limit(1).execute()
        
        details = {
            'name': table_name,
            'columns': [],
            'row_count': 0,
            'sample_row': None
        }
        
        # 获取列信息
        if result.data:
            details['columns'] = list(result.data[0].keys())
            details['sample_row'] = result.data[0]
        
        # 获取行数
        count_result = client.client.table(table_name).select('*', count='exact').limit(0).execute()
        details['row_count'] = count_result.count if hasattr(count_result, 'count') else 0
        
        return details
    except Exception as e:
        return {
            'name': table_name,
            'error': str(e)
        }

def main():
    """主函数"""
    client = SupabaseClient()
    
    # 所有找到的表
    tables = [
        'quality_records',
        'oee_records',
        'sub_batches',
        'parameters',
        'stations',
        'products',
        'batches',
        'production_orders',
        'equipment',
        'equipment_groups',
        'annotation_audit_log'
    ]
    
    print("=" * 80)
    print("Supabase 数据库 - 所有表详细结构")
    print("=" * 80)
    
    all_tables_info = {
        'database': 'Supabase PostgreSQL',
        'scan_date': __import__('datetime').datetime.now().isoformat(),
        'total_tables': len(tables),
        'tables': []
    }
    
    for table_name in tables:
        print(f"\n{'=' * 80}")
        print(f"表: {table_name}")
        print(f"{'=' * 80}")
        
        details = get_table_details(client, table_name)
        
        if 'error' in details:
            print(f"错误: {details['error']}")
            all_tables_info['tables'].append(details)
            continue
        
        print(f"行数: {details['row_count']}")
        print(f"列数: {len(details['columns'])}")
        print(f"\n列名 ({len(details['columns'])} 个):")
        print("-" * 80)
        for i, col in enumerate(details['columns'], 1):
            print(f"  {i:2d}. {col}")
        
        if details['sample_row']:
            print(f"\n样本数据 (第1行):")
            print("-" * 80)
            for key, value in details['sample_row'].items():
                # 格式化输出值
                if isinstance(value, (list, dict)):
                    value_str = str(value)[:100] + '...' if len(str(value)) > 100 else str(value)
                elif isinstance(value, str):
                    value_str = value[:80] + '...' if len(value) > 80 else value
                else:
                    value_str = str(value)
                print(f"  {key:<30} : {value_str}")
        
        all_tables_info['tables'].append({
            'name': details['name'],
            'row_count': details['row_count'],
            'column_count': len(details['columns']),
            'columns': details['columns']
        })
    
    # 总结
    print(f"\n{'=' * 80}")
    print("数据库总结")
    print(f"{'=' * 80}")
    
    total_rows = sum(t.get('row_count', 0) for t in all_tables_info['tables'] if 'row_count' in t)
    total_columns = sum(t.get('column_count', 0) for t in all_tables_info['tables'] if 'column_count' in t)
    
    print(f"总表数: {len(tables)}")
    print(f"总行数: {total_rows:,}")
    print(f"总列数: {total_columns}")
    
    # 按行数排序的表列表
    sorted_tables = sorted(
        [t for t in all_tables_info['tables'] if 'row_count' in t],
        key=lambda x: x['row_count'],
        reverse=True
    )
    
    print(f"\n表的行数分布:")
    print("-" * 80)
    for table in sorted_tables:
        print(f"  {table['name']:<35} : {table['row_count']:>8,} 行 ({table['column_count']} 列)")
    
    # 导出 JSON
    print(f"\n{'=' * 80}")
    print("详细信息 (JSON格式)")
    print(f"{'=' * 80}\n")
    print(json.dumps(all_tables_info, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
