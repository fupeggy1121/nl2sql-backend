#!/usr/bin/env python3
"""完全扫描所有Supabase表"""

import json
from app.services.supabase_client import SupabaseClient

def comprehensive_table_scan():
    """全面扫描所有表"""
    client = SupabaseClient()
    
    # 扩展的搜索词表
    extended_keywords = [
        # 已知表
        'equipment', 'production_orders', 'products', 'stations', 'batches', 'quality_records',
        
        # 设备相关
        'equipment_list', 'device', 'devices', 'machine', 'machines', 'equipment_group',
        'equipment_groups', 'equipment_status', 'equipment_config', 'equipment_maintenance',
        'device_list', 'device_status', 'device_config',
        
        # 生产相关
        'production', 'productions', 'production_list', 'production_status',
        'order', 'orders', 'order_list', 'order_status', 'order_items', 'order_detail',
        'production_order', 'work_order', 'work_orders', 'wo', 'wos',
        'batch', 'batch_list', 'batch_status', 'batch_detail', 'batch_records',
        'lot', 'lots', 'lot_list',
        'recipe', 'recipes', 'recipe_list', 'recipe_detail',
        'process', 'processes', 'process_list', 'process_detail', 'process_step', 'process_steps',
        'route', 'routes', 'route_list', 'production_route', 'production_routes',
        'operation', 'operations', 'operation_list',
        'step', 'steps', 'procedure', 'procedures',
        
        # 产品相关
        'product', 'product_list', 'product_status', 'product_detail', 'product_info',
        'sku', 'skus', 'sku_list',
        'component', 'components', 'component_list',
        'assembly', 'assemblies', 'assembly_list',
        'bom', 'bom_item', 'bom_items', 'bom_list', 'bill_of_materials',
        
        # 质量相关
        'quality', 'quality_list', 'quality_status', 'quality_data', 'quality_metrics',
        'quality_control', 'quality_records', 'quality_check', 'quality_checks',
        'qc', 'qc_records', 'qc_data', 'qc_list',
        'defect', 'defects', 'defect_list', 'defect_records',
        'inspection', 'inspections', 'inspection_list', 'inspection_records', 'inspection_data',
        'test', 'tests', 'test_list', 'test_records', 'test_data', 'test_results',
        'testing', 'testing_list', 'testing_records',
        'oee', 'oee_metrics', 'oee_data', 'oee_records',
        
        # 物料相关
        'material', 'materials', 'material_list', 'material_data',
        'inventory', 'inventory_list', 'inventory_status', 'inventory_detail',
        'warehouse', 'warehouses', 'warehouse_list',
        'location', 'locations', 'location_list',
        'stock', 'stocks', 'stock_list', 'stock_level',
        'supplier', 'suppliers', 'supplier_list',
        'vendor', 'vendors', 'vendor_list',
        
        # 人员相关
        'employee', 'employees', 'employee_list', 'employee_info',
        'operator', 'operators', 'operator_list',
        'user', 'users', 'user_list', 'user_info',
        'staff', 'staff_list', 'staff_info',
        'department', 'departments', 'department_list',
        'team', 'teams', 'team_list',
        'position', 'positions', 'position_list',
        'role', 'roles', 'role_list',
        'permission', 'permissions', 'permission_list',
        
        # 班次/时间相关
        'shift', 'shifts', 'shift_list', 'shift_schedule',
        'schedule', 'schedules', 'schedule_list',
        'attendance', 'attendance_list', 'attendance_records',
        'time', 'time_log', 'time_logs', 'time_tracking',
        'schedule_detail', 'schedule_items',
        
        # 维护相关
        'maintenance', 'maintenance_list', 'maintenance_records', 'maintenance_schedule',
        'repair', 'repairs', 'repair_list', 'repair_records',
        'downtime', 'downtime_list', 'downtime_records',
        'pm', 'pm_records',  # Preventive Maintenance
        'mro', 'mro_records',  # Maintenance, Repair, Operations
        
        # 性能/指标相关
        'metric', 'metrics', 'metric_list', 'metric_data',
        'kpi', 'kpi_list', 'kpi_data', 'kpi_records',
        'performance', 'performance_data', 'performance_metrics',
        'efficiency', 'efficiency_data',
        'throughput', 'throughput_data',
        'yield', 'yield_data', 'yield_records',
        'scrap', 'scrap_data', 'scrap_records',
        'rework', 'rework_data', 'rework_records',
        
        # 文档/附件相关
        'document', 'documents', 'document_list',
        'attachment', 'attachments', 'attachment_list',
        'file', 'files', 'file_list',
        'drawing', 'drawings', 'drawing_list',
        'specification', 'specifications', 'spec', 'specs',
        'manual', 'manuals', 'manual_list',
        
        # 审计/日志相关
        'audit', 'audit_list', 'audit_records', 'audit_log', 'audit_logs',
        'log', 'logs', 'log_list', 'log_data', 'event_log', 'event_logs',
        'annotation', 'annotation_list', 'annotation_records', 'annotation_audit_log',
        'history', 'history_list', 'history_records', 'change_log',
        'tracking', 'tracking_list', 'tracking_records',
        
        # 配置/设置相关
        'config', 'configuration', 'config_list', 'config_data',
        'setting', 'settings', 'setting_list',
        'parameter', 'parameters', 'parameter_list',
        'alert', 'alerts', 'alert_list', 'alert_rules',
        'notification', 'notifications', 'notification_list',
        'notification_template', 'notification_templates',
        'email', 'email_template', 'email_templates',
        'sms', 'sms_template', 'sms_templates',
        
        # 数据/分析相关
        'data', 'data_list', 'data_records', 'data_detail',
        'report', 'reports', 'report_list', 'report_template', 'report_templates',
        'dashboard', 'dashboards', 'dashboard_list',
        'analytics', 'analytics_data', 'analytics_records',
        'statistic', 'statistics', 'statistic_data',
        'summary', 'summary_data', 'summary_records',
        
        # 交易/订单相关
        'transaction', 'transactions', 'transaction_list', 'transaction_records',
        'purchase_order', 'purchase_orders', 'po', 'pos',
        'sales_order', 'sales_orders', 'so', 'sos',
        'customer', 'customers', 'customer_list', 'customer_info',
        'account', 'accounts', 'account_list',
        'invoice', 'invoices', 'invoice_list',
        'receipt', 'receipts', 'receipt_list',
        
        # 其他可能的表
        'sub_batch', 'sub_batches', 'sub_batch_list',
        'line', 'lines', 'line_list', 'line_items',
        'item', 'items', 'item_list',
        'detail', 'details', 'detail_list',
        'record', 'records', 'record_list',
        'data_point', 'data_points',
        'measurement', 'measurements',
        'reading', 'readings',
        'value', 'values',
        'tag', 'tags', 'tag_list',
        'attribute', 'attributes', 'attribute_list',
        'property', 'properties', 'property_list',
        'status', 'status_list',
        'state', 'state_list',
        'type', 'type_list',
        'category', 'categories', 'category_list',
        'group', 'groups', 'group_list',
        'class', 'class_list', 'classification', 'classifications',
        'parent', 'parent_list', 'relationship', 'relationships',
        'mapping', 'mappings', 'mapping_list',
        'lookup', 'lookup_list', 'lookup_table', 'lookup_tables',
        'reference', 'references', 'reference_list',
        'code', 'code_list', 'code_table',
        'definition', 'definitions', 'definition_list',
    ]
    
    print("=" * 80)
    print("完全数据库表扫描 - 尝试所有可能的表名")
    print("=" * 80)
    print(f"正在扫描 {len(extended_keywords)} 个可能的表名...\n")
    
    found_tables = {}
    
    for table_name in sorted(set(extended_keywords)):
        try:
            result = client.client.table(table_name).select('*', count='exact').limit(0).execute()
            row_count = result.count if hasattr(result, 'count') else 0
            found_tables[table_name] = row_count
            print(f"✓ {table_name:<40} ({row_count:>8} 行)")
        except Exception:
            pass
    
    # 排序和分析结果
    sorted_tables = sorted(found_tables.items(), key=lambda x: x[1], reverse=True)
    
    print("\n" + "=" * 80)
    print(f"扫描完成 - 总共找到 {len(found_tables)} 个表")
    print("=" * 80)
    
    print("\n表列表 (按行数降序):")
    print("-" * 80)
    print(f"{'表名':<40} | {'行数':>8}")
    print("-" * 80)
    total_rows = 0
    for table_name, row_count in sorted_tables:
        print(f"{table_name:<40} | {row_count:>8,} 行")
        total_rows += row_count
    
    print("-" * 80)
    print(f"{'总计':<40} | {total_rows:>8,} 行")
    
    # JSON 输出
    print("\n" + "=" * 80)
    print("JSON 格式:")
    print("=" * 80)
    output = {
        'database': 'Supabase PostgreSQL',
        'scan_timestamp': __import__('datetime').datetime.now().isoformat(),
        'total_tables_found': len(found_tables),
        'total_rows': total_rows,
        'tables': [{'name': name, 'rows': rows} for name, rows in sorted_tables]
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    
    return found_tables

if __name__ == "__main__":
    comprehensive_table_scan()
