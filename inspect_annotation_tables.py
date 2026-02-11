#!/usr/bin/env python3
"""检查 schema 注释表的结构"""

from app.services.supabase_client import SupabaseClient
import json

def inspect_annotation_tables():
    client = SupabaseClient()
    
    tables_to_check = [
        'schema_table_annotations',
        'schema_column_annotations', 
        'schema_relation_annotations'
    ]
    
    for table_name in tables_to_check:
        print(f"\n{'='*70}")
        print(f"表: {table_name}")
        print('='*70)
        
        try:
            # 获取表数据
            result = client.client.table(table_name).select('*').limit(1).execute()
            
            if result.data:
                print(f"✓ 表有 {len(result.data)} 条数据\n")
                sample = result.data[0]
                print("列信息:")
                for key, value in sorted(sample.items()):
                    value_str = str(value)[:60]
                    print(f"  • {key:<25} = {value_str} ({type(value).__name__})")
            else:
                print(f"⚠ 表为空\n")
                # 尝试获取一条来看结构
                result = client.client.table(table_name).select('*').limit(0).execute()
                
        except Exception as e:
            print(f"✗ 错误: {str(e)}")

if __name__ == "__main__":
    inspect_annotation_tables()
