#!/usr/bin/env python3
"""
将提取的 Schema 信息导入到数据库的注释表中
"""

import json
from datetime import datetime
from app.services.supabase_client import SupabaseClient

# 表的中文注释和业务定义（从 extract_all_tables_schema.py 中的定义）
TABLE_BUSINESS_DEFINITIONS = {
    'wafer_inspection_results': {
        'table_name_cn': '晶圆检测结果',
        'description_cn': '记录晶圆在各检测站的检验数据和检验结果',
        'description_en': 'Wafer inspection results at various testing stations',
        'business_meaning': '追踪晶圆产品质量，支持质量管理和流程改进',
        'use_case': '质量检测、不良品分析、工艺优化'
    },
    'quality_records': {
        'table_name_cn': '质量记录',
        'description_cn': '存储产品的质量测量和检验数据',
        'description_en': 'Product quality measurements and inspection data',
        'business_meaning': '质量数据管理和质量体系维护',
        'use_case': '质量统计、管制图、过程能力分析'
    },
    'production_events': {
        'table_name_cn': '生产事件',
        'description_cn': '记录生产过程中发生的各类事件（设备、参数、人工等）',
        'description_en': 'Production events including equipment, parameters, and manual events',
        'business_meaning': '实时追踪生产过程，提供过程透明度',
        'use_case': '生产监控、事件追踪、根本原因分析'
    },
    'batches': {
        'table_name_cn': '生产批次',
        'description_cn': '生产批次的主记录，关联订单、产品和生产计划',
        'description_en': 'Master record for production batches',
        'business_meaning': '批次级别的生产管理和追踪',
        'use_case': '生产排期、批次追踪、生产报表'
    },
    'sub_batches': {
        'table_name_cn': '子批次',
        'description_cn': '生产批次的细分单位，支持多级生产分解',
        'description_en': 'Production batch subdivisions',
        'business_meaning': '支持更细粒度的生产管理和追踪',
        'use_case': '生产分解、流程管理、进度追踪'
    },
    'products': {
        'table_name_cn': '产品',
        'description_cn': '产品信息及规格定义',
        'description_en': 'Product information and specifications',
        'business_meaning': '产品主数据管理',
        'use_case': '产品编码、规格管理、产品类别'
    },
    'stations': {
        'table_name_cn': '生产站点',
        'description_cn': '生产线上的工作站点定义和配置',
        'description_en': 'Production workstation definitions and configurations',
        'business_meaning': '生产设施管理和产能规划',
        'use_case': '工艺流程定义、产能管理、工艺参数配置'
    },
    'equipment': {
        'table_name_cn': '设备',
        'description_cn': '生产设备信息及技术参数',
        'description_en': 'Equipment information and technical parameters',
        'business_meaning': '设备资产管理和维护追踪',
        'use_case': '设备清单、维保记录、故障报警'
    },
    'parameters': {
        'table_name_cn': '参数',
        'description_cn': '工艺参数和测量参数的定义',
        'description_en': 'Process and measurement parameter definitions',
        'business_meaning': '参数主数据管理',
        'use_case': '参数编码、参数规范、参数值管理'
    },
    'process_routes': {
        'table_name_cn': '工艺路线',
        'description_cn': '产品生产的完整工艺路线定义',
        'description_en': 'Complete production process routes for products',
        'business_meaning': '工艺流程管理和标准化',
        'use_case': '工艺设计、流程优化、工艺变更'
    },
    'wafers': {
        'table_name_cn': '晶圆',
        'description_cn': '晶圆产品的基础信息和状态追踪',
        'description_en': 'Wafer product information and status tracking',
        'business_meaning': '晶圆级别的生产追踪',
        'use_case': '晶圆追踪、产品编码、状态管理'
    },
    'oee_records': {
        'table_name_cn': 'OEE 记录',
        'description_cn': '设备综合效率（OEE）的记录和分析',
        'description_en': 'Equipment Overall Equipment Effectiveness (OEE) records',
        'business_meaning': '设备效率管理和性能改进',
        'use_case': 'OEE 计算、效率分析、设备评估'
    },
    'chat_messages': {
        'table_name_cn': '聊天消息',
        'description_cn': 'NL2SQL 对话系统的消息记录',
        'description_en': 'NL2SQL conversation system message records',
        'business_meaning': '用户交互和疑问追踪',
        'use_case': '对话历史、用户行为分析、系统改进'
    },
    'carriers': {
        'table_name_cn': '载体',
        'description_cn': '晶圆运输和存储的装载容器信息',
        'description_en': 'Wafer transport and storage container information',
        'business_meaning': '物流管理和库存追踪',
        'use_case': '物流管理、库存管理、容器追踪'
    },
}

# 常用列的业务定义
COLUMN_BUSINESS_DEFINITIONS = {
    'id': {
        'column_name_cn': '编号',
        'description_cn': '资源的唯一标识符（主键）',
        'description_en': 'Unique identifier for the resource (primary key)',
        'business_meaning': '全局唯一标识',
        'example_value': 'UUID 或自增整数',
        'value_range': '不重复的自增或随机值'
    },
    'created_at': {
        'column_name_cn': '创建时间',
        'description_cn': '记录创建的时间戳',
        'description_en': 'Record creation timestamp',
        'business_meaning': '数据来源时间追踪',
        'example_value': '2026-02-11T10:30:45',
        'value_range': 'UTC 时间戳，不可修改'
    },
    'updated_at': {
        'column_name_cn': '更新时间',
        'description_cn': '记录最后更新的时间戳',
        'description_en': 'Record last update timestamp',
        'business_meaning': '数据变更历史追踪',
        'example_value': '2026-02-11T10:30:45',
        'value_range': 'UTC 时间戳，自动更新'
    },
    'status': {
        'column_name_cn': '状态',
        'description_cn': '资源的当前状态',
        'description_en': 'Current status of the resource',
        'business_meaning': '生命周期管理',
        'example_value': 'active, pending, completed, cancelled',
        'value_range': '预定义的状态值'
    },
    'batch_id': {
        'column_name_cn': '批次 ID',
        'description_cn': '关联的生产批次编号',
        'description_en': 'Associated production batch ID',
        'business_meaning': '批次级数据关联',
        'example_value': 'BATCH-2026-001',
        'value_range': '有效的批次编号'
    },
    'product_id': {
        'column_name_cn': '产品 ID',
        'description_cn': '关联的产品编号',
        'description_en': 'Associated product ID',
        'business_meaning': '产品维度的数据聚合',
        'example_value': 'PROD-001',
        'value_range': '有效的产品编号'
    },
}


class SchemaAnnotationImporter:
    def __init__(self):
        self.client = SupabaseClient()
        self.created_count = 0
        self.updated_count = 0
        self.errors = []
    
    def import_table_annotations(self):
        """导入表注释到数据库"""
        print("\n" + "="*80)
        print("导入表注释 (schema_table_annotations)")
        print("="*80)
        
        # 读取提取的 schema 信息
        with open('database_schema.json', 'r', encoding='utf-8') as f:
            schema_data = json.load(f)
        
        for table_name, table_info in schema_data['tables'].items():
            # 仅导入有业务定义的表
            if table_name not in TABLE_BUSINESS_DEFINITIONS:
                continue
            
            business_def = TABLE_BUSINESS_DEFINITIONS[table_name]
            
            # 构建注释记录
            annotation = {
                'table_name': table_name,
                'table_name_cn': business_def['table_name_cn'],
                'description_cn': business_def['description_cn'],
                'description_en': business_def['description_en'],
                'business_meaning': business_def['business_meaning'],
                'use_case': business_def['use_case'],
                'status': 'approved',
                'created_by': 'system',
                'reviewed_by': 'system'
            }
            
            # 检查是否存在
            try:
                existing = self.client.client.table('schema_table_annotations').select('*').eq('table_name', table_name).execute()
                
                if existing.data:
                    # 更新
                    annotation['updated_at'] = datetime.utcnow().isoformat()
                    self.client.client.table('schema_table_annotations').update(annotation).eq('table_name', table_name).execute()
                    self.updated_count += 1
                    print(f"✓ 更新表注释: {table_name}")
                else:
                    # 创建
                    annotation['created_at'] = datetime.utcnow().isoformat()
                    self.client.client.table('schema_table_annotations').insert(annotation).execute()
                    self.created_count += 1
                    print(f"✓ 创建表注释: {table_name}")
            except Exception as e:
                error_msg = f"表 {table_name}: {str(e)}"
                self.errors.append(error_msg)
                print(f"✗ 错误: {error_msg}")
    
    def import_column_annotations(self):
        """导入列注释到数据库"""
        print("\n" + "="*80)
        print("导入列注释 (schema_column_annotations)")
        print("="*80)
        
        with open('database_schema.json', 'r', encoding='utf-8') as f:
            schema_data = json.load(f)
        
        imported_columns = set()
        
        for table_name, table_info in schema_data['tables'].items():
            if table_info['status'] != 'success':
                continue
            
            for col in table_info.get('columns', []):
                col_name = col['name']
                column_key = f"{table_name}.{col_name}"
                
                # 避免重复导入
                if column_key in imported_columns:
                    continue
                
                # 构建列注释
                annotation = {
                    'table_name': table_name,
                    'column_name': col_name,
                    'column_name_cn': col.get('description', col_name),
                    'data_type': col.get('type', 'unknown'),
                    'description_cn': f"{table_name} 表的 {col_name} 列",
                    'description_en': f"{col_name} column in {table_name} table",
                    'business_meaning': '业务含义待补充',
                    'example_value': col.get('sample_value', ''),
                    'value_range': '值范围待补充',
                    'status': 'pending',  # 待审核
                    'created_by': 'system',
                    'reviewed_by': None
                }
                
                # 使用预定义的列注释
                if col_name in COLUMN_BUSINESS_DEFINITIONS:
                    predefined = COLUMN_BUSINESS_DEFINITIONS[col_name]
                    annotation.update(predefined)
                    annotation['status'] = 'approved'
                    annotation['reviewed_by'] = 'system'
                
                try:
                    # 检查是否存在
                    existing = self.client.client.table('schema_column_annotations').select('*').eq('table_name', table_name).eq('column_name', col_name).execute()
                    
                    if existing.data:
                        # 更新
                        annotation['updated_at'] = datetime.utcnow().isoformat()
                        self.client.client.table('schema_column_annotations').update(annotation).eq('table_name', table_name).eq('column_name', col_name).execute()
                        self.updated_count += 1
                    else:
                        # 创建
                        annotation['created_at'] = datetime.utcnow().isoformat()
                        self.client.client.table('schema_column_annotations').insert(annotation).execute()
                        self.created_count += 1
                    
                    imported_columns.add(column_key)
                    if self.created_count % 10 == 0 or self.updated_count % 10 == 0:
                        print(f"✓ 已处理 {len(imported_columns)} 列")
                        
                except Exception as e:
                    error_msg = f"{table_name}.{col_name}: {str(e)}"
                    self.errors.append(error_msg)
        
        print(f"✓ 完成列注释导入: 创建 {self.created_count} 条，更新 {self.updated_count} 条")
    
    def import_relation_annotations(self):
        """导入表关系注释"""
        print("\n" + "="*80)
        print("导入表关系注释 (schema_relation_annotations)")
        print("="*80)
        
        # 定义表间的主要关系
        relations = [
            {
                'parent_table': 'batches',
                'child_table': 'sub_batches',
                'relation_type': 'one-to-many',
                'foreign_key': 'batch_id',
                'description_cn': '生产批次与子批次的层级关系',
                'business_meaning': '支持多级批次管理'
            },
            {
                'parent_table': 'batches',
                'child_table': 'wafers',
                'relation_type': 'one-to-many',
                'foreign_key': 'batch_id',
                'description_cn': '生产批次与晶圆的关联',
                'business_meaning': '批次级晶圆追踪'
            },
            {
                'parent_table': 'products',
                'child_table': 'batches',
                'relation_type': 'one-to-many',
                'foreign_key': 'product_id',
                'description_cn': '产品与生产批次的关联',
                'business_meaning': '产品级别的生产计划'
            },
            {
                'parent_table': 'stations',
                'child_table': 'production_events',
                'relation_type': 'one-to-many',
                'foreign_key': 'station_code',
                'description_cn': '生产站点与生产事件的关联',
                'business_meaning': '站点级的事件追踪'
            },
            {
                'parent_table': 'equipment',
                'child_table': 'production_events',
                'relation_type': 'one-to-many',
                'foreign_key': 'equipment_id',
                'description_cn': '设备与生产事件的关联',
                'business_meaning': '设备级的事件追踪'
            },
        ]
        
        for relation in relations:
            try:
                # 检查是否存在
                existing = self.client.client.table('schema_relation_annotations').select('*').eq('parent_table', relation['parent_table']).eq('child_table', relation['child_table']).execute()
                
                annotation = relation.copy()
                annotation['status'] = 'approved'
                annotation['created_by'] = 'system'
                annotation['reviewed_by'] = 'system'
                
                if existing.data:
                    annotation['updated_at'] = datetime.utcnow().isoformat()
                    self.client.client.table('schema_relation_annotations').update(annotation).eq('parent_table', relation['parent_table']).eq('child_table', relation['child_table']).execute()
                    self.updated_count += 1
                    print(f"✓ 更新关系: {relation['parent_table']} → {relation['child_table']}")
                else:
                    annotation['created_at'] = datetime.utcnow().isoformat()
                    self.client.client.table('schema_relation_annotations').insert(annotation).execute()
                    self.created_count += 1
                    print(f"✓ 创建关系: {relation['parent_table']} → {relation['child_table']}")
                    
            except Exception as e:
                error_msg = f"关系 {relation['parent_table']}→{relation['child_table']}: {str(e)}"
                self.errors.append(error_msg)
                print(f"✗ 错误: {error_msg}")
    
    def generate_import_report(self):
        """生成导入报告"""
        print("\n" + "="*80)
        print("导入完成统计")
        print("="*80)
        print(f"\n✓ 创建数量: {self.created_count}")
        print(f"✓ 更新数量: {self.updated_count}")
        
        if self.errors:
            print(f"\n⚠ 错误数量: {len(self.errors)}")
            for error in self.errors:
                print(f"  - {error}")
        else:
            print("\n✓ 无错误")
        
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'created': self.created_count,
            'updated': self.updated_count,
            'errors': self.errors
        }
        
        with open('schema_import_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print("\n✓ 报告已保存到: schema_import_report.json")


def main():
    print("\n")
    importer = SchemaAnnotationImporter()
    
    # 导入表注释
    importer.import_table_annotations()
    
    # 导入列注释
    importer.import_column_annotations()
    
    # 导入关系注释
    importer.import_relation_annotations()
    
    # 生成报告
    importer.generate_import_report()
    
    print("\n" + "="*80)
    print("所有 Schema 信息已导入到数据库")
    print("="*80)
    print("\n现在可以从以下表查询:")
    print("  • schema_table_annotations - 表的业务定义")
    print("  • schema_column_annotations - 列的业务定义") 
    print("  • schema_relation_annotations - 表间关系")
    print("\nNL2SQL 可以在查询前动态加载这些元数据来提升准确度。")


if __name__ == "__main__":
    main()
