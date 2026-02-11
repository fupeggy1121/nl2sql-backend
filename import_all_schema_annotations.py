#!/usr/bin/env python3
"""
完整的 Schema 注释导入工具 - 导入全部 35 张表
从 database_schema.json 读取所有表定义并自动生成注释
"""

import json
from datetime import datetime
from app.services.supabase_client import SupabaseClient
import time

# 所有表的中文名称和描述映射
TABLE_CHINESE_NAMES = {
    'wafer_inspection_results': ('晶圆检测结果', '记录晶圆在各检测站的检验数据'),
    'quality_records': ('质量记录', '产品质量测量和检验数据'),
    'wafer_carrier_contents': ('晶圆载体内容', '晶圆在载体中的位置和状态'),
    'wafers': ('晶圆', '晶圆产品的基础信息'),
    'production_events': ('生产事件', '生产过程中发生的各类事件'),
    'oee_records': ('OEE记录', '设备综合效率记录'),
    'chat_messages': ('聊天消息', 'NL2SQL对话系统的消息'),
    'carriers': ('载体', '晶圆运输和存储的容器'),
    'parameter_group_parameters': ('参数组参数', '参数组中包含的参数'),
    'sub_batches': ('子批次', '生产批次的细分单位'),
    'parameters': ('参数', '工艺参数定义'),
    'stations': ('生产站点', '生产线上的工作站点'),
    'process_route_stations': ('工艺路线站点', '工艺路线中的站点配置'),
    'parameter_groups': ('参数组', '参数的分组管理'),
    'process_routes': ('工艺路线', '产品生产的工艺路线'),
    'products': ('产品', '产品信息和规格'),
    'batches': ('生产批次', '生产批次主记录'),
    'parameter_equipment': ('参数设备关联', '参数与设备的关联'),
    'product_boms': ('产品BOM', '产品物料清单'),
    'chat_sessions': ('聊天会话', 'NL2SQL对话会话管理'),
    'production_orders': ('生产订单', '生产订单主记录'),
    'approved_schema_metadata': ('批准的元数据', '经过审批的数据库架构元数据'),
    'custom_process_rules': ('自定义工艺规则', '用户自定义的生产规则'),
    'equipment': ('设备', '生产设备信息'),
    'schema_column_annotations': ('列注释', '数据库列的注释说明'),
    'equipment_groups': ('设备组', '设备的分组管理'),
    'schema_table_annotations': ('表注释', '数据库表的注释说明'),
    'feedback': ('用户反馈', '用户对系统的反馈'),
    'annotation_audit_log': ('注释审计日志', '注释修改的审计记录'),
    'batch_remarks': ('批次备注', '批次的备注说明'),
    'intent_feedback': ('意图反馈', 'NL2SQL意图识别的反馈'),
    'query_result_feedback': ('查询结果反馈', '查询结果的用户反馈'),
    'saved_reports': ('保存的报告', '用户保存的查询报告'),
    'schema_relation_annotations': ('关系注释', '表关系的注释说明'),
    'sub_batch_process_log': ('子批次工艺日志', '子批次的工艺过程记录'),
}


def import_all_table_annotations():
    """导入所有 35 张表的注释"""
    print("\n" + "="*70)
    print("导入所有表注释 (schema_table_annotations)")
    print("="*70)
    
    client = SupabaseClient()
    created = 0
    updated = 0
    
    # 从 database_schema.json 读取所有表
    try:
        with open('database_schema.json', 'r', encoding='utf-8') as f:
            schema_data = json.load(f)
        all_tables = schema_data.get('tables', {}).keys()
    except Exception as e:
        print(f"✗ 无法读取 database_schema.json: {e}")
        return 0
    
    print(f"\n从 database_schema.json 发现 {len(all_tables)} 张表\n")
    
    for table_name in sorted(all_tables):
        # 获取中文名和描述
        if table_name in TABLE_CHINESE_NAMES:
            name_cn, description = TABLE_CHINESE_NAMES[table_name]
            status = 'approved'
        else:
            # 自动生成（未在预定义中）
            name_cn = table_name
            description = f'{table_name} 表'
            status = 'pending'
        
        try:
            annotation = {
                'table_name': table_name,
                'table_name_cn': name_cn,
                'description_cn': description,
                'description_en': description,
                'business_meaning': f'{name_cn}管理',
                'use_case': '生产管理',
                'status': status,
                'created_by': 'system',
                'reviewed_by': 'system' if status == 'approved' else None
            }
            
            # 检查存在
            existing = client.client.table('schema_table_annotations').select('*').eq('table_name', table_name).execute()
            
            if existing.data:
                annotation['updated_at'] = datetime.now().isoformat()
                client.client.table('schema_table_annotations').update(annotation).eq('table_name', table_name).execute()
                updated += 1
                print(f"  ✓ 更新: {table_name:<35} → {name_cn}")
            else:
                annotation['created_at'] = datetime.now().isoformat()
                client.client.table('schema_table_annotations').insert(annotation).execute()
                created += 1
                print(f"  ✓ 创建: {table_name:<35} → {name_cn}")
                
        except Exception as e:
            print(f"  ✗ {table_name}: {str(e)[:50]}")
        
        time.sleep(0.05)
    
    print(f"\n✓ 表注释完成: 创建 {created} 条，更新 {updated} 条，总计 {created + updated} 条")
    return created + updated


def import_all_column_annotations():
    """导入所有列注释"""
    print("\n" + "="*70)
    print("导入所有列注释 (schema_column_annotations)")
    print("="*70)
    
    client = SupabaseClient()
    
    # 读取 schema
    with open('database_schema.json', 'r', encoding='utf-8') as f:
        schema_data = json.load(f)
    
    # 常用列的预定义
    common_cols = {
        'id': ('编号', '资源的唯一标识符（主键）', 'UUID或自增整数'),
        'created_at': ('创建时间', '记录创建的时间戳', 'UTC时间戳'),
        'updated_at': ('更新时间', '记录最后更新的时间戳', 'UTC时间戳'),
        'status': ('状态', '资源的当前状态', 'active/pending/completed'),
        'batch_id': ('批次ID', '关联的生产批次编号', '有效的批次编号'),
        'product_id': ('产品ID', '关联的产品编号', '有效的产品编号'),
        'equipment_id': ('设备ID', '关联的生产设备ID', '有效的设备编号'),
        'name': ('名称', '对象的名称', '自由文本'),
        'code': ('代码', '对象的编码', '编码值'),
    }
    
    created = 0
    updated = 0
    processed = 0
    
    for table_name, table_info in schema_data['tables'].items():
        if table_info['status'] != 'success':
            continue
            
        for col in table_info.get('columns', []):
            col_name = col['name']
            processed += 1
            
            try:
                # 检查存在
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
                    cn_name, description, example = common_cols[col_name]
                    annotation.update({
                        'column_name_cn': cn_name,
                        'description_cn': description,
                        'example_value': example,
                        'status': 'approved',
                        'reviewed_by': 'system'
                    })
                else:
                    annotation['reviewed_by'] = None
                
                if existing.data:
                    annotation['updated_at'] = datetime.now().isoformat()
                    client.client.table('schema_column_annotations').update(annotation).eq('table_name', table_name).eq('column_name', col_name).execute()
                    updated += 1
                else:
                    annotation['created_at'] = datetime.now().isoformat()
                    client.client.table('schema_column_annotations').insert(annotation).execute()
                    created += 1
                
                # 每 50 条显示进度
                if (created + updated) % 50 == 0:
                    print(f"  已处理 {created + updated} 列...")
                    
            except Exception as e:
                if processed <= 5:  # 只显示前5个错误
                    print(f"  ✗ {table_name}.{col_name}: {str(e)[:50]}")
            
            time.sleep(0.02)
    
    print(f"\n✓ 列注释完成: 创建 {created} 条，更新 {updated} 条，总计 {created + updated} 条")
    return created + updated


def main():
    print("\n" + "="*70)
    print("完整 Schema 注释导入 - 所有 35 张表 + 所有列")
    print("="*70)
    
    try:
        # 导入表注释
        t1 = import_all_table_annotations()
        
        # 导入列注释
        t2 = import_all_column_annotations()
        
        # 统计
        print("\n" + "="*70)
        print("✓ 导入完成")
        print("="*70)
        print(f"\n总导入记录数: {t1 + t2} 条")
        print(f"  • 表注释: {t1} 条")
        print(f"  • 列注释: {t2} 条")
        print("\n现在可以查询:")
        print("  • SELECT * FROM schema_table_annotations")
        print("  • SELECT * FROM schema_column_annotations")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 导入被中断")
    except Exception as e:
        print(f"\n✗ 错误: {e}")


if __name__ == "__main__":
    main()
