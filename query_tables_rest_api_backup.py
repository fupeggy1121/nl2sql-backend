#!/usr/bin/env python3
"""
应急方案：使用 Supabase REST API 替代 PostgreSQL 直接连接
当 DNS 或网络出现问题时使用
"""

from app.services.supabase_client import SupabaseClient
import json

def get_all_tables_via_rest_api():
    """使用 REST API 获取所有表"""
    
    print("=" * 70)
    print("应急方案：使用 REST API 查询表")
    print("=" * 70)
    
    client = SupabaseClient()
    
    # 扩展的表名列表
    possible_tables = [
        # 已知的表
        'quality_records', 'oee_records', 'sub_batches', 'parameters',
        'stations', 'products', 'batches', 'production_orders',
        'equipment', 'equipment_groups', 'annotation_audit_log',
        
        # 新发现的表
        'wafer_inspection_results', 'wafers', 'wafer_carrier_contents',
        'production_events', 'chat_messages', 'carriers',
        'parameter_group_parameters', 'process_route_stations',
        'parameter_groups', 'process_routes', 'product_boms',
        'chat_sessions', 'schema_column_annotations', 'equipment',
        'custom_process_rules', 'schema_table_annotations', 'feedback',
        'sub_batch_process_log', 'intent_feedback', 'query_result_feedback',
        'saved_reports', 'batch_remarks', 'parameter_equipment',
        'schema_relation_annotations',
        
        # 其他可能的表
        'approved_schema_metadata', 'schema_annotations'
    ]
    
    found_tables = []
    not_found = []
    
    print("\n扫描表...")
    print("-" * 70)
    
    for table_name in sorted(set(possible_tables)):
        try:
            result = client.client.table(table_name).select('*', count='exact').limit(0).execute()
            row_count = result.count if hasattr(result, 'count') else 0
            found_tables.append({
                'name': table_name,
                'rows': row_count,
                'accessible': True
            })
            status = "✓"
            print(f"{status} {table_name:<35} ({row_count:>7,} 行)")
        except Exception as e:
            not_found.append(table_name)
    
    print("-" * 70)
    print(f"\n✓ 通过 REST API 找到 {len(found_tables)} 张表")
    print(f"✗ 无法访问 {len(not_found)} 张表 (可能是权限问题)")
    
    # 排序
    found_tables_sorted = sorted(found_tables, key=lambda x: x['rows'], reverse=True)
    
    # 显示统计
    total_rows = sum(t['rows'] for t in found_tables)
    
    print("\n" + "=" * 70)
    print("表统计 (按行数排序)")
    print("=" * 70)
    
    print(f"\n{'表名':<35} | {'行数':>8}")
    print("-" * 50)
    
    for table in found_tables_sorted:
        print(f"{table['name']:<35} | {table['rows']:>8,}")
    
    print("-" * 50)
    print(f"{'总计':<35} | {total_rows:>8,}")
    
    # 输出报告
    report = {
        'method': 'Supabase REST API',
        'status': 'success',
        'total_tables': len(found_tables),
        'total_rows': total_rows,
        'tables': found_tables_sorted,
        'note': '通过 REST API 获取（权限受限，某些表可能不可见）'
    }
    
    print("\n" + "=" * 70)
    print("JSON 格式输出")
    print("=" * 70)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    
    # 保存报告
    with open('database_tables_rest_api_backup.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ 报告已保存到: database_tables_rest_api_backup.json")
    
    return found_tables_sorted


def get_table_details_rest_api(table_name):
    """获取单个表的详细信息"""
    client = SupabaseClient()
    
    try:
        result = client.client.table(table_name).select('*').limit(1).execute()
        
        if result.data:
            columns = list(result.data[0].keys())
            return {
                'name': table_name,
                'columns': columns,
                'column_count': len(columns),
                'sample_data': result.data[0]
            }
        else:
            return {
                'name': table_name,
                'columns': [],
                'column_count': 0,
                'sample_data': None
            }
    except Exception as e:
        return {
            'name': table_name,
            'error': str(e)
        }


def main():
    print("\n")
    
    # 获取所有表
    tables = get_all_tables_via_rest_api()
    
    # 获取前 3 个表的详细信息
    if tables:
        print("\n" + "=" * 70)
        print("前 3 个表的详细结构")
        print("=" * 70)
        
        for table in tables[:3]:
            print(f"\n表: {table['name']}")
            print(f"行数: {table['rows']}")
            
            details = get_table_details_rest_api(table['name'])
            if 'columns' in details:
                print(f"列数: {details['column_count']}")
                print("列名:")
                for col in details['columns'][:10]:  # 显示前 10 列
                    print(f"  - {col}")
                if len(details['columns']) > 10:
                    print(f"  ... 还有 {len(details['columns']) - 10} 列")
    
    print("\n" + "=" * 70)
    print("✓ 应急方案执行完毕")
    print("=" * 70)
    print(f"\n如果你看到了表列表，说明 REST API 工作正常。")
    print(f"DNS 问题可能是临时的，请稍后重试 PostgreSQL 连接。")
    print(f"\n运行命令重试:")
    print(f"  python find_all_tables_comprehensive.py")


if __name__ == "__main__":
    main()
