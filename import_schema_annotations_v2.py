#!/usr/bin/env python3
"""
优化的 Schema 注释导入工具 - 支持批次处理和恢复
"""

import json
from datetime import datetime
from app.services.supabase_client import SupabaseClient
import time

# 简化的表业务定义
TABLE_DEFS = {
    'wafer_inspection_results': ('晶圆检测结果', '记录晶圆在各检测站的检验数据'),
    'quality_records': ('质量记录', '产品质量测量和检验数据'),
    'production_events': ('生产事件', '生产过程中的各类事件'),
    'batches': ('生产批次', '生产批次的主记录'),
    'sub_batches': ('子批次', '批次的细分单位'),
    'products': ('产品', '产品信息及规格'),
    'stations': ('生产站点', '工作站点定义'),
    'equipment': ('设备', '生产设备信息'),
    'parameters': ('参数', '工艺参数定义'),
    'process_routes': ('工艺路线', '产品生产路线'),
    'wafers': ('晶圆', '晶圆产品信息'),
    'oee_records': ('OEE记录', '设备综合效率记录'),
    'chat_messages': ('聊天消息', '对话系统消息'),
    'carriers': ('载体', '装载容器信息'),
}

def import_table_annotations_batch():
    """批次导入表注释"""
    print("\n导入表注释...")
    client = SupabaseClient()
    created = 0
    updated = 0
    
    for table_name, (name_cn, description) in TABLE_DEFS.items():
        try:
            annotation = {
                'table_name': table_name,
                'table_name_cn': name_cn,
                'description_cn': description,
                'description_en': description,
                'business_meaning': f'{name_cn}管理',
                'use_case': '生产管理',
                'status': 'approved',
                'created_by': 'system',
                'reviewed_by': 'system'
            }
            
            # 检查存在
            existing = client.client.table('schema_table_annotations').select('*').eq('table_name', table_name).execute()
            
            if existing.data:
                annotation['updated_at'] = datetime.now().isoformat()
                client.client.table('schema_table_annotations').update(annotation).eq('table_name', table_name).execute()
                updated += 1
            else:
                annotation['created_at'] = datetime.now().isoformat()
                client.client.table('schema_table_annotations').insert(annotation).execute()
                created += 1
                
        except Exception as e:
            print(f"  ✗ {table_name}: {str(e)[:50]}")
        
        time.sleep(0.1)  # 避免 API 限流
    
    print(f"✓ 表注释: 创建 {created} 条，更新 {updated} 条")
    return created + updated


def import_column_annotations_batch():
    """批次导入列注释"""
    print("\n导入列注释（批处理）...")
    client = SupabaseClient()
    
    # 读取生成的 schema
    with open('database_schema.json', 'r', encoding='utf-8') as f:
        schema_data = json.load(f)
    
    created = 0
    updated = 0
    skipped = 0
    
    # 常用列的预定义
    common_cols = {
        'id': ('编号', '唯一标识符'),
        'created_at': ('创建时间', '记录创建的时间'),
        'updated_at': ('更新时间', '记录最后更新的时间'),
        'status': ('状态', '资源的当前状态'),
        'batch_id': ('批次ID', '关联的生产批次'),
    }
    
    total_cols = 0
    for table_name, table_info in schema_data['tables'].items():
        if table_info['status'] != 'success':
            continue
            
        for col in table_info.get('columns', []):
            total_cols += 1
            col_name = col['name']
            
            try:
                # 检查是否已存在
                existing = client.client.table('schema_column_annotations').select('id').eq('table_name', table_name).eq('column_name', col_name).limit(1).execute()
                
                annotation = {
                    'table_name': table_name,
                    'column_name': col_name,
                    'column_name_cn': col.get('description', col_name),
                    'data_type': col.get('type', 'unknown'),
                    'description_cn': f'{col_name} 字段',
                    'description_en': f'{col_name} field',
                    'example_value': col.get('sample_value', '')[:100] if col.get('sample_value') else '',
                    'status': 'pending',
                    'created_by': 'system',
                }
                
                # 应用预定义
                if col_name in common_cols:
                    cn_name, description = common_cols[col_name]
                    annotation.update({
                        'column_name_cn': cn_name,
                        'description_cn': description,
                        'status': 'approved',
                        'reviewed_by': 'system'
                    })
                
                if existing.data:
                    annotation['updated_at'] = datetime.now().isoformat()
                    client.client.table('schema_column_annotations').update(annotation).eq('table_name', table_name).eq('column_name', col_name).execute()
                    updated += 1
                else:
                    annotation['created_at'] = datetime.now().isoformat()
                    client.client.table('schema_column_annotations').insert(annotation).execute()
                    created += 1
                
                # 每 50 条暂停
                if (created + updated) % 50 == 0:
                    print(f"  已处理 {created + updated} 列...")
                    time.sleep(0.5)
                    
            except Exception as e:
                skipped += 1
                if skipped <= 3:  # 只显示前 3 个错误
                    print(f"  ✗ {table_name}.{col_name}: {str(e)[:50]}")
            
            time.sleep(0.02)  # 避免 API 限流
    
    print(f"✓ 列注释: 创建 {created} 条，更新 {updated} 条，跳过 {skipped} 条 (共 {total_cols} 列)")
    return created + updated


def import_relation_annotations_batch():
    """导入表关系注释"""
    print("\n导入关系注释...")
    client = SupabaseClient()
    
    relations = [
        ('batches', 'sub_batches', '一对多', 'batch_id'),
        ('batches', 'wafers', '一对多', 'batch_id'),
        ('sub_batches', 'wafer_inspection_results', '一对多', 'sub_batch_id'),
        ('stations', 'production_events', '一对多', 'station_code'),
        ('equipment', 'production_events', '一对多', 'equipment_id'),
    ]
    
    created = 0
    for parent, child, rel_type, fk in relations:
        try:
            annotation = {
                'parent_table': parent,
                'child_table': child,
                'relation_type': rel_type,
                'foreign_key': fk,
                'description_cn': f'{parent} 与 {child} 的关联',
                'status': 'approved',
                'created_by': 'system',
                'reviewed_by': 'system',
                'created_at': datetime.now().isoformat()
            }
            
            # 先删除再插入（简化更新逻辑）
            client.client.table('schema_relation_annotations').delete().eq('parent_table', parent).eq('child_table', child).execute()
            client.client.table('schema_relation_annotations').insert(annotation).execute()
            created += 1
            print(f"  ✓ {parent} → {child}")
            
        except Exception as e:
            print(f"  ✗ {parent} → {child}: {str(e)[:50]}")
        
        time.sleep(0.1)
    
    print(f"✓ 关系注释: 新增 {created} 条")
    return created


def main():
    print("\n" + "="*70)
    print("Schema 注释导入 (优化版本 - 支持批处理)")
    print("="*70)
    
    try:
        # 导入表注释
        t1 = import_table_annotations_batch()
        
        # 导入列注释
        t2 = import_column_annotations_batch()
        
        # 导入关系注释
        t3 = import_relation_annotations_batch()
        
        # 统计
        print("\n" + "="*70)
        print("导入完成")
        print("="*70)
        print(f"\n总计导入: {t1 + t2 + t3} 条记录")
        print(f"  • 表注释: {t1} 条")
        print(f"  • 列注释: {t2} 条")
        print(f"  • 关系注释: {t3} 条")
        print("\n✓ 现在可以从以下表查询:")
        print("  • schema_table_annotations")
        print("  • schema_column_annotations")
        print("  • schema_relation_annotations")
        
    except KeyboardInterrupt:
        print("\n中断导入")
    except Exception as e:
        print(f"\n错误: {e}")


if __name__ == "__main__":
    main()
