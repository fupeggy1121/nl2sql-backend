#!/usr/bin/env python3
"""获取Supabase数据库表的详细信息"""

import json
from app.services.supabase_client import get_supabase_client

def get_table_schema(client, table_name):
    """获取表的schema信息"""
    try:
        # 获取一行数据来确定列
        result = client.client.table(table_name).select('*').limit(1).execute()
        
        schema = {
            'table_name': table_name,
            'row_count': 0,
            'columns': []
        }
        
        # 获取列信息
        if result.data:
            schema['columns'] = list(result.data[0].keys())
        
        # 获取行数
        count_result = client.client.table(table_name).select('*', count='exact').execute()
        schema['row_count'] = count_result.count if hasattr(count_result, 'count') else len(count_result.data)
        
        return schema
    except Exception as e:
        return {
            'table_name': table_name,
            'error': str(e)
        }

def main():
    """主函数"""
    client = get_supabase_client()
    
    tables = ['equipment', 'production_orders', 'products']
    
    print("=" * 60)
    print("Supabase 数据库表详细信息")
    print("=" * 60)
    
    all_info = {
        'database': 'Supabase PostgreSQL',
        'tables': [],
        'total_tables': len(tables)
    }
    
    for table_name in tables:
        print(f"\n表: {table_name}")
        print("-" * 40)
        
        schema = get_table_schema(client, table_name)
        all_info['tables'].append(schema)
        
        print(f"  行数: {schema.get('row_count', 0)}")
        print(f"  列数: {len(schema.get('columns', []))}")
        print(f"  列名:")
        for col in schema.get('columns', []):
            print(f"    - {col}")
        
        # 获取样本数据
        try:
            result = client.client.table(table_name).select('*').limit(1).execute()
            if result.data:
                print(f"\n  样本数据:")
                sample = result.data[0]
                for key, value in sample.items():
                    value_str = str(value)[:50] + '...' if len(str(value)) > 50 else str(value)
                    print(f"    {key}: {value_str}")
        except Exception as e:
            print(f"  获取样本数据失败: {str(e)}")
    
    print("\n" + "=" * 60)
    print(f"总表数: {len(tables)}")
    print("=" * 60)
    
    # 输出 JSON 格式
    print("\nJSON 格式:")
    print(json.dumps(all_info, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
