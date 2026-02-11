#!/usr/bin/env python3
"""直接查询 schema 信息表的结构和内容"""

from app.services.supabase_client import SupabaseClient

def main():
    client = SupabaseClient()
    
    print("\n" + "="*80)
    print("检查 schema_column_annotations 表内容")
    print("="*80)
    
    try:
        result = client.client.table('schema_column_annotations').select('*').limit(5).execute()
        print(f"✓ 记录数: {len(result.data)}")
        if result.data:
            for i, record in enumerate(result.data, 1):
                print(f"\n记录 {i}:")
                for key in sorted(record.keys()):
                    val = record[key]
                    if isinstance(val, str) and len(val) > 50:
                        val = val[:47] + "..."
                    print(f"  {key}: {val}")
    except Exception as e:
        print(f"✗ 错误: {e}")
    
    print("\n" + "="*80)
    print("检查 schema_table_annotations 表内容")
    print("="*80)
    
    try:
        result = client.client.table('schema_table_annotations').select('*').limit(5).execute()
        print(f"✓ 记录数: {len(result.data)}")
        if result.data:
            for i, record in enumerate(result.data, 1):
                print(f"\n记录 {i}:")
                for key in sorted(record.keys()):
                    val = record[key]
                    if isinstance(val, str) and len(val) > 50:
                        val = val[:47] + "..."
                    print(f"  {key}: {val}")
    except Exception as e:
        print(f"✗ 错误: {e}")
    
    print("\n" + "="*80)
    print("检查 schema_relation_annotations 表内容")
    print("="*80)
    
    try:
        result = client.client.table('schema_relation_annotations').select('*').limit(5).execute()
        print(f"✓ 记录数: {len(result.data)}")
        if result.data:
            for i, record in enumerate(result.data, 1):
                print(f"\n记录 {i}:")
                for key in sorted(record.keys()):
                    val = record[key]
                    if isinstance(val, str) and len(val) > 50:
                        val = val[:47] + "..."
                    print(f"  {key}: {val}")
        else:
            print("(表为空)")
    except Exception as e:
        print(f"✗ 错误: {e}")

if __name__ == "__main__":
    main()
