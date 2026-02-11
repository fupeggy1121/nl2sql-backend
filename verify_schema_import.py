#!/usr/bin/env python3
"""验证 schema 导入结果"""
from app.services.supabase_client import SupabaseClient

client = SupabaseClient()

print("\n" + "="*70)
print("Schema 注释导入验证")
print("="*70)

# 统计每个表
for table_name in ['schema_table_annotations', 'schema_column_annotations', 'schema_relation_annotations']:
    try:
        result = client.client.table(table_name).select('*', count='exact').execute()
        count = result.count if hasattr(result, 'count') else len(result.data or [])
        print(f"\n✓ {table_name}")
        print(f"  记录数: {count}")
        
        if result.data and len(result.data) > 0:
            print(f"  样本数据:")
            for item in result.data[:2]:
                if table_name == 'schema_table_annotations':
                    print(f"    - {item.get('table_name')}: {item.get('table_name_cn')}")
                elif table_name == 'schema_column_annotations':
                    print(f"    - {item.get('table_name')}.{item.get('column_name')}: {item.get('column_name_cn')}")
                elif table_name == 'schema_relation_annotations':
                    print(f"    - {item.get('parent_table')} → {item.get('child_table')}")
    except Exception as e:
        print(f"\n✗ {table_name}: {str(e)[:80]}")

print("\n" + "="*70)
