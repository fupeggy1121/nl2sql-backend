#!/usr/bin/env python3
"""
CIM Schema v2 — 导入新列和新表的 schema 注释到 Supabase
Phase 3: 为 Phase 1 新增的列和 batch_events 表添加 NL2SQL 注释
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.supabase_client import SupabaseClient


# ── 新增表定义 ──
NEW_TABLE_ANNOTATIONS = [
    {
        'table_name': 'batch_events',
        'table_name_cn': '批次事件',
        'description_cn': '记录批次生命周期中的所有操作事件（进站/出站/拆并批等），追加写入不可变',
        'description_en': 'Immutable append-only event log for batch lifecycle operations',
        'business_meaning': '批次操作历史追溯，审计日志',
        'use_case': '查询批次操作历史、追溯问题批次的操作时间线',
        'status': 'approved',
        'created_by': 'system',
        'reviewed_by': 'system',
    },
]

# ── 新增列定义 ──
NEW_COLUMN_ANNOTATIONS = [
    # wafers 表 v2 新列
    {'table_name': 'wafers', 'column_name': 'lot_id', 'column_name_cn': '批次ID', 'data_type': 'uuid', 'description_cn': '所属批次(Lot)的ID，等同于 batch_id', 'example_value': 'uuid'},
    {'table_name': 'wafers', 'column_name': 'sublot_id', 'column_name_cn': '子批次ID', 'data_type': 'uuid', 'description_cn': '所属子批次(Sublot)的ID，直接引用 sub_batches.id', 'example_value': 'uuid'},
    {'table_name': 'wafers', 'column_name': 'carrier_id', 'column_name_cn': '载具ID', 'data_type': 'uuid', 'description_cn': '当前所在载具的ID，直接引用 carriers.id', 'example_value': 'uuid'},
    {'table_name': 'wafers', 'column_name': 'slot_number', 'column_name_cn': '槽位号', 'data_type': 'integer', 'description_cn': '在载具中的槽位编号(1~25)', 'example_value': '5'},
    {'table_name': 'wafers', 'column_name': 'wafer_type', 'column_name_cn': '晶圆类型', 'data_type': 'text', 'description_cn': '晶圆类型: GOOD(良品)/GOOD_SAMPLE(良品取样)/REJECT(不良品)', 'example_value': 'GOOD'},
    {'table_name': 'wafers', 'column_name': 'ingot_id', 'column_name_cn': '锭号', 'data_type': 'text', 'description_cn': '晶圆来源锭号', 'example_value': 'ING-2026-001'},
    {'table_name': 'wafers', 'column_name': 'work_order_id', 'column_name_cn': '工单ID', 'data_type': 'uuid', 'description_cn': '关联的生产工单ID', 'example_value': 'uuid'},
    {'table_name': 'wafers', 'column_name': 'wafer_id', 'column_name_cn': '晶圆编号', 'data_type': 'text', 'description_cn': '晶圆唯一业务编号(等同于 wafer_id_code)', 'example_value': 'W-2026-00001'},
    # batches 表 v2 新列
    {'table_name': 'batches', 'column_name': 'current_station_id', 'column_name_cn': '当前站点ID', 'data_type': 'uuid', 'description_cn': '当前所在工艺站点的ID，外键引用 stations.id', 'example_value': 'uuid'},
    {'table_name': 'batches', 'column_name': 'work_order_id', 'column_name_cn': '工单ID', 'data_type': 'uuid', 'description_cn': '关联的生产工单ID', 'example_value': 'uuid'},
    # sub_batches 表 v2 新列
    {'table_name': 'sub_batches', 'column_name': 'lot_id', 'column_name_cn': '批次ID', 'data_type': 'uuid', 'description_cn': '所属批次(Lot)的ID，等同于 batch_id', 'example_value': 'uuid'},
    {'table_name': 'sub_batches', 'column_name': 'equipment_id', 'column_name_cn': '设备ID', 'data_type': 'uuid', 'description_cn': '当前使用的设备ID，外键引用 equipment.id', 'example_value': 'uuid'},
    {'table_name': 'sub_batches', 'column_name': 'next_station_id', 'column_name_cn': '下一站点ID', 'data_type': 'uuid', 'description_cn': '下一个工艺站点的ID，外键引用 stations.id', 'example_value': 'uuid'},
    # batch_events 表列
    {'table_name': 'batch_events', 'column_name': 'id', 'column_name_cn': '事件ID', 'data_type': 'uuid', 'description_cn': '事件唯一标识', 'example_value': 'uuid'},
    {'table_name': 'batch_events', 'column_name': 'event_type', 'column_name_cn': '事件类型', 'data_type': 'text', 'description_cn': '操作类型: instation/outstation/split/merge/carrier_change等', 'example_value': 'instation'},
    {'table_name': 'batch_events', 'column_name': 'target_type', 'column_name_cn': '目标类型', 'data_type': 'text', 'description_cn': '事件作用对象类型: batch/sublot/wafer/carrier', 'example_value': 'batch'},
    {'table_name': 'batch_events', 'column_name': 'target_id', 'column_name_cn': '目标ID', 'data_type': 'uuid', 'description_cn': '事件作用对象的ID', 'example_value': 'uuid'},
    {'table_name': 'batch_events', 'column_name': 'payload', 'column_name_cn': '事件数据', 'data_type': 'jsonb', 'description_cn': '事件详细数据(JSON)，包含操作前后状态', 'example_value': '{"from_station": "ST-01", "to_station": "ST-02"}'},
    {'table_name': 'batch_events', 'column_name': 'triggered_by', 'column_name_cn': '操作人', 'data_type': 'text', 'description_cn': '触发事件的操作人ID', 'example_value': 'operator-001'},
    {'table_name': 'batch_events', 'column_name': 'created_at', 'column_name_cn': '创建时间', 'data_type': 'timestamptz', 'description_cn': '事件发生时间', 'example_value': '2026-02-26T10:30:00Z'},
]


def main():
    client = SupabaseClient()
    
    # 1. 导入新表注释
    print("=== 导入 v2 表注释 ===")
    for ann in NEW_TABLE_ANNOTATIONS:
        table_name = ann['table_name']
        try:
            existing = client.client.table('schema_table_annotations').select('id').eq('table_name', table_name).execute()
            if existing.data:
                client.client.table('schema_table_annotations').update(ann).eq('table_name', table_name).execute()
                print(f"  ✅ 更新: {table_name}")
            else:
                client.client.table('schema_table_annotations').insert(ann).execute()
                print(f"  ✅ 新增: {table_name}")
        except Exception as e:
            print(f"  ❌ {table_name}: {e}")

    # 2. 导入新列注释
    print("\n=== 导入 v2 列注释 ===")
    for col in NEW_COLUMN_ANNOTATIONS:
        table_name = col['table_name']
        col_name = col['column_name']
        annotation = {
            **col,
            'status': 'approved',
            'created_by': 'system',
            'reviewed_by': 'system',
        }
        try:
            existing = client.client.table('schema_column_annotations').select('id').eq('table_name', table_name).eq('column_name', col_name).limit(1).execute()
            if existing.data:
                client.client.table('schema_column_annotations').update(annotation).eq('table_name', table_name).eq('column_name', col_name).execute()
                print(f"  ✅ 更新: {table_name}.{col_name}")
            else:
                client.client.table('schema_column_annotations').insert(annotation).execute()
                print(f"  ✅ 新增: {table_name}.{col_name}")
        except Exception as e:
            print(f"  ❌ {table_name}.{col_name}: {e}")

    print("\n✅ v2 schema 注释导入完成")


if __name__ == '__main__':
    main()
