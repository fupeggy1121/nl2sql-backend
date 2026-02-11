#!/usr/bin/env python3
"""导入表向量关系"""
from app.services.supabase_client import SupabaseClient
from datetime import datetime

client = SupabaseClient()

# 定义表关系
relations = [
    ('batches', 'sub_batches', '一对多', 'batch_id', '生产批次与子批次的层级关系'),
    ('batches', 'wafers', '一对多', 'batch_id', '生产批次与晶圆的关联'),
    ('sub_batches', 'wafer_inspection_results', '一对多', 'sub_batch_id', '子批次与检测结果的关联'),
    ('stations', 'production_events', '一对多', 'station_code', '生产站点与事件的关联'),
    ('equipment', 'production_events', '一对多', 'equipment_id', '设备与事件的关联'),
]

print("\n导入表关系注释...")

for parent, child, rel_type, fk, desc in relations:
    try:
        annotation = {
            'parent_table': parent,
            'child_table': child,
            'relation_type': rel_type,
            'foreign_key': fk,
            'description_cn': desc,
            'status': 'approved',
            'created_by': 'system',
            'reviewed_by': 'system',
            'created_at': datetime.now().isoformat()
        }
        
        client.client.table('schema_relation_annotations').insert(annotation).execute()
        print(f"  ✓ {parent} → {child}")
    except Exception as e:
        print(f"  ✗ {parent} → {child}: {str(e)[:50]}")

print("✓ 完成")
