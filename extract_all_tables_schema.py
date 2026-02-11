#!/usr/bin/env python3
"""
数据库所有表的 Schema 提取工具
从 Supabase 获取完整的表结构、列信息、类型等
生成可用的 schema 文档和 JSON 参考
"""

import json
import os
from app.services.supabase_client import SupabaseClient
from datetime import datetime

# 表说明映射（中文注释）
TABLE_DESCRIPTIONS = {
    'wafer_inspection_results': '晶圆检测结果 - 记录晶圆在各站点的检测数据和结果',
    'quality_records': '质量记录 - 存储产品质量测量和检验数据',
    'wafer_carrier_contents': '晶圆载体内容 - 晶圆在载体中的位置和状态信息',
    'wafers': '晶圆 - 晶圆基础信息（ID、批次、类型等）',
    'production_events': '生产事件 - 记录生产过程中发生的各类事件',
    'oee_records': 'OEE 记录 - 设备综合效率记录',
    'chat_messages': '聊天消息 - NL2SQL 对话系统的消息记录',
    'carriers': '载体 - 晶圆载体的基础信息',
    'parameter_group_parameters': '参数组参数 - 参数组中包含的具体参数',
    'sub_batches': '子批次 - 生产批次的细分单位',
    'parameters': '参数 - 工艺参数定义和配置',
    'stations': '生产站点 - 生产线上的工作站点',
    'process_route_stations': '工艺路线站点 - 工艺路线中的站点配置',
    'parameter_groups': '参数组 - 参数的分组管理',
    'process_routes': '工艺路线 - 产品生产的工艺路线',
    'products': '产品 - 产品信息和规格',
    'batches': '批次 - 生产批次主记录',
    'parameter_equipment': '参数设备关联 - 参数与设备的关联关系',
    'product_boms': '产品 BOM - 产品物料清单',
    'chat_sessions': '聊天会话 - NL2SQL 对话会话管理',
    'production_orders': '生产订单 - 生产订单主记录',
    'approved_schema_metadata': '批准的元数据 - 经过审批的数据库架构元数据',
    'custom_process_rules': '自定义工艺规则 - 用户自定义的生产规则',
    'equipment': '设备 - 生产设备信息',
    'schema_column_annotations': '列注释 - 数据库列的注释说明',
    'equipment_groups': '设备组 - 设备的分组管理',
    'schema_table_annotations': '表注释 - 数据库表的注释说明',
    'feedback': '用户反馈 - 用户对系统的反馈',
    'annotation_audit_log': '注释审计日志 - 注释修改的审计记录',
    'batch_remarks': '批次备注 - 批次的备注说明',
    'intent_feedback': '意图反馈 - NL2SQL 意图识别的反馈',
    'query_result_feedback': '查询结果反馈 - 查询结果的用户反馈',
    'saved_reports': '保存的报告 - 用户保存的查询报告',
    'schema_relation_annotations': '关系注释 - 表关系的注释说明',
    'sub_batch_process_log': '子批次工艺日志 - 子批次的工艺过程记录'
}

# 列名说明映射（通用列）
COLUMN_DESCRIPTIONS = {
    'id': '唯一标识符 - 主键',
    'created_at': '创建时间 - 记录创建的时间戳',
    'updated_at': '更新时间 - 记录最后更新的时间戳',
    'batch_id': '批次 ID - 关联的生产批次',
    'product_id': '产品 ID - 关联的产品',
    'equipment_id': '设备 ID - 关联的生产设备',
    'station_code': '站点代码 - 生产站点编号',
    'wafer_id': '晶圆 ID - 关联的晶圆',
    'carrier_id': '载体 ID - 关联的装载容器',
    'user_id': '用户 ID - 关联的用户',
    'status': '状态 - 记录的当前状态',
    'remarks': '备注 - 说明或备注信息',
    'name': '名称 - 对象的名称',
    'code': '代码 - 对象的编码',
    'description': '描述 - 详细说明',
    'value': '值 - 数值或参数值',
    'type': '类型 - 对象或参数的类型'
}

# 数据类型说明
TYPE_DESCRIPTIONS = {
    'bigint': '大整数 - 可存储大数值',
    'integer': '整数 - 标准整数类型',
    'smallint': '小整数 - 节省存储空间的整数',
    'numeric': '数值 - 精确的数值类型',
    'decimal': '十进制 - 用于金融数据',
    'real': '实数 - 浮点数',
    'double precision': '双精度浮点 - 高精度浮点数',
    'text': '文本 - 可变长文本',
    'varchar': '字符串 - 可变长字符串',
    'char': '字符 - 固定长字符',
    'boolean': '布尔值 - 真/假',
    'date': '日期 - 仅日期部分',
    'time': '时间 - 仅时间部分',
    'timestamp': '时间戳 - 日期时间组合',
    'interval': '时间间隔 - 时间跨度',
    'uuid': '唯一标识符 - 全局唯一ID',
    'json': 'JSON - JSON 格式数据',
    'jsonb': 'JSONB - 二进制 JSON 格式',
    'bytea': '字节数组 - 二进制数据',
}


class SchemaExtractor:
    def __init__(self):
        self.client = SupabaseClient()
        self.all_tables_info = {}
        
    def get_table_schema(self, table_name):
        """获取单个表的完整 Schema"""
        try:
            # 获取一条样本数据来推断列类型
            result = self.client.client.table(table_name).select('*').limit(1).execute()
            
            if result.data:
                sample_data = result.data[0]
                columns = list(sample_data.keys())
                
                # 尝试从 schema_column_annotations 获取列说明
                column_info = []
                for col in columns:
                    value = sample_data.get(col)
                    col_type = type(value).__name__
                    
                    # 推断 PostgreSQL 类型
                    pg_type = self._infer_pg_type(col_type, value)
                    
                    # 获取列说明（优先从 COLUMN_DESCRIPTIONS，否则使用列名）
                    description = COLUMN_DESCRIPTIONS.get(col, f'{col}')
                    
                    column_info.append({
                        'name': col,
                        'type': pg_type,
                        'python_type': col_type,
                        'nullable': value is None,
                        'description': description,
                        'sample_value': str(value)[:100] if value is not None else None
                    })
                
                return {
                    'name': table_name,
                    'description': TABLE_DESCRIPTIONS.get(table_name, ''),
                    'columns': column_info,
                    'column_count': len(columns),
                    'status': 'success'
                }
            else:
                return {
                    'name': table_name,
                    'description': TABLE_DESCRIPTIONS.get(table_name, ''),
                    'columns': [],
                    'column_count': 0,
                    'status': 'no_data'
                }
        except Exception as e:
            return {
                'name': table_name,
                'description': TABLE_DESCRIPTIONS.get(table_name, ''),
                'columns': [],
                'column_count': 0,
                'status': 'error',
                'error': str(e)
            }
    
    def _infer_pg_type(self, python_type, value):
        """从 Python 类型推断 PostgreSQL 类型"""
        type_mapping = {
            'NoneType': 'unknown',
            'int': 'integer',
            'float': 'numeric',
            'str': 'text',
            'bool': 'boolean',
            'datetime': 'timestamp',
            'dict': 'jsonb',
            'list': 'jsonb'
        }
        return type_mapping.get(python_type, 'unknown')
    
    def extract_all_tables(self, table_names):
        """提取所有表的 Schema"""
        print("\n" + "=" * 80)
        print("提取所有表的 Schema 信息")
        print("=" * 80)
        
        for i, table_name in enumerate(table_names, 1):
            print(f"\n[{i}/{len(table_names)}] 正在提取: {table_name}")
            schema = self.get_table_schema(table_name)
            self.all_tables_info[table_name] = schema
            
            if schema['status'] == 'success':
                print(f"  ✓ 找到 {schema['column_count']} 列")
            else:
                print(f"  ⚠ 状态: {schema['status']}")
        
        print("\n" + "=" * 80)
        print(f"✓ 完成 {len(self.all_tables_info)} 个表的 Schema 提取")
        print("=" * 80)
    
    def generate_markdown_doc(self):
        """生成 Markdown 格式的 Schema 文档"""
        doc = []
        doc.append("# 数据库 Schema 完整参考\n")
        doc.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        doc.append(f"总表数: {len(self.all_tables_info)}\n\n")
        
        doc.append("## 表索引\n")
        for i, table_name in enumerate(sorted(self.all_tables_info.keys()), 1):
            info = self.all_tables_info[table_name]
            doc.append(f"{i}. [{table_name}](#{table_name}) - {info.get('description', '')}\n")
        
        doc.append("\n---\n\n")
        
        # 按表生成详细文档
        for table_name in sorted(self.all_tables_info.keys()):
            info = self.all_tables_info[table_name]
            
            doc.append(f"## {table_name}\n\n")
            doc.append(f"**说明**: {info.get('description', 'N/A')}\n\n")
            doc.append(f"**列数**: {info['column_count']}\n\n")
            
            if info['status'] == 'success' and info['columns']:
                doc.append("### 列定义\n\n")
                doc.append("| 列名 | 类型 | 说明 | 示例值 |\n")
                doc.append("|------|------|------|--------|\n")
                
                for col in info['columns']:
                    sample = col['sample_value'] if col['sample_value'] else '(NULL)'
                    # 截断过长的示例
                    if len(sample) > 30:
                        sample = sample[:27] + '...'
                    
                    doc.append(f"| `{col['name']}` | {col['type']} | {col['description']} | {sample} |\n")
                
                doc.append("\n### SQL CREATE TABLE\n\n")
                doc.append("```sql\n")
                doc.append(f"CREATE TABLE {table_name} (\n")
                for col in info['columns']:
                    nullable = "NOT NULL" if not col['nullable'] else ""
                    doc.append(f"  {col['name']} {col['type']} {nullable},\n")
                doc.append(");\n")
                doc.append("```\n")
            
            doc.append("\n---\n\n")
        
        return "".join(doc)
    
    def generate_json_schema(self):
        """生成 JSON Schema 格式的文档"""
        schema_data = {
            'version': '1.0',
            'generated_at': datetime.now().isoformat(),
            'total_tables': len(self.all_tables_info),
            'tables': self.all_tables_info,
            'type_descriptions': TYPE_DESCRIPTIONS,
            'column_descriptions': COLUMN_DESCRIPTIONS
        }
        return schema_data
    
    def generate_sql_reference(self):
        """生成 SQL 查询参考"""
        sql_ref = []
        sql_ref.append("-- 数据库 Schema SQL 参考\n")
        sql_ref.append(f"-- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 统计查询
        sql_ref.append("-- ==================== 统计查询 ====================\n\n")
        sql_ref.append("-- 查看所有表的行数\n")
        sql_ref.append("SELECT\n")
        sql_ref.append("  schemaname,\n")
        sql_ref.append("  tablename,\n")
        sql_ref.append("  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size\n")
        sql_ref.append("FROM pg_tables\n")
        sql_ref.append("WHERE schemaname = 'public'\n")
        sql_ref.append("ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;\n\n")
        
        # 每个表的查询示例
        sql_ref.append("-- ==================== 表查询示例 ====================\n\n")
        for table_name in sorted(self.all_tables_info.keys()):
            info = self.all_tables_info[table_name]
            sql_ref.append(f"-- {table_name}: {info.get('description', '')}\n")
            sql_ref.append(f"SELECT COUNT(*) FROM {table_name};\n")
            sql_ref.append(f"SELECT * FROM {table_name} LIMIT 5;\n\n")
        
        return "".join(sql_ref)


def main():
    print("\n")
    
    # 所有表名列表
    all_tables = [
        'wafer_inspection_results', 'quality_records', 'wafer_carrier_contents',
        'wafers', 'production_events', 'oee_records', 'chat_messages', 'carriers',
        'parameter_group_parameters', 'sub_batches', 'parameters', 'stations',
        'process_route_stations', 'parameter_groups', 'process_routes', 'products',
        'batches', 'parameter_equipment', 'product_boms', 'chat_sessions',
        'production_orders', 'approved_schema_metadata', 'custom_process_rules',
        'equipment', 'schema_column_annotations', 'equipment_groups',
        'schema_table_annotations', 'feedback', 'annotation_audit_log',
        'batch_remarks', 'intent_feedback', 'query_result_feedback',
        'saved_reports', 'schema_relation_annotations', 'sub_batch_process_log'
    ]
    
    # 创建提取器
    extractor = SchemaExtractor()
    
    # 提取所有表的 Schema
    extractor.extract_all_tables(all_tables)
    
    # 生成 Markdown 文档
    print("\n生成 Markdown 文档...")
    markdown_doc = extractor.generate_markdown_doc()
    with open('DATABASE_SCHEMA_REFERENCE.md', 'w', encoding='utf-8') as f:
        f.write(markdown_doc)
    print("✓ 已保存到: DATABASE_SCHEMA_REFERENCE.md")
    
    # 生成 JSON Schema
    print("生成 JSON Schema...")
    json_schema = extractor.generate_json_schema()
    with open('database_schema.json', 'w', encoding='utf-8') as f:
        json.dump(json_schema, f, indent=2, ensure_ascii=False)
    print("✓ 已保存到: database_schema.json")
    
    # 生成 SQL 参考
    print("生成 SQL 参考...")
    sql_ref = extractor.generate_sql_reference()
    with open('DATABASE_SQL_REFERENCE.sql', 'w', encoding='utf-8') as f:
        f.write(sql_ref)
    print("✓ 已保存到: DATABASE_SQL_REFERENCE.sql")
    
    # 打印统计
    print("\n" + "=" * 80)
    print("Schema 提取完成统计")
    print("=" * 80)
    
    success_count = sum(1 for t in extractor.all_tables_info.values() if t['status'] == 'success')
    total_columns = sum(t['column_count'] for t in extractor.all_tables_info.values())
    
    print(f"\n✓ 成功提取: {success_count}/{len(all_tables)} 个表")
    print(f"✓ 总列数: {total_columns} 列")
    print(f"\n生成的文件:")
    print(f"  1. DATABASE_SCHEMA_REFERENCE.md - Markdown 格式参考文档")
    print(f"  2. database_schema.json - JSON 格式 Schema 数据")
    print(f"  3. DATABASE_SQL_REFERENCE.sql - SQL 查询示例和参考")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
