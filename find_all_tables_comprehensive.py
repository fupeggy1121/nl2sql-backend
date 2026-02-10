#!/usr/bin/env python3
"""通过Python获取Supabase中所有34张表 - 综合方案"""

import json
import os
from typing import List, Dict, Set

# 尝试加载 dotenv，如果失败则直接使用环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def method1_supabase_rest_api():
    """方法1：使用Supabase Python客户端 (REST API)"""
    print("\n" + "=" * 80)
    print("方法1: Supabase REST API (当前限制：只能发现11张表)")
    print("=" * 80)
    
    from app.services.supabase_client import SupabaseClient
    client = SupabaseClient()
    
    # 扩展的表名列表
    possible_tables = [
        'quality_records', 'oee_records', 'sub_batches', 'parameters',
        'stations', 'products', 'batches', 'production_orders',
        'equipment', 'equipment_groups', 'annotation_audit_log',
        # 添加更多可能的表名
        'users', 'roles', 'permissions', 'audit_logs', 'settings',
        'customers', 'suppliers', 'inventory', 'warehouse',
        'purchase_orders', 'sales_orders', 'invoices',
        'employees', 'departments', 'shifts', 'schedules',
        'maintenance', 'repairs', 'inspections', 'recipes',
        'process_steps', 'operations', 'components', 'bom_items',
        'measurements', 'test_results', 'alerts', 'notifications',
        'reports', 'dashboards', 'analytics', 'documents',
        'attachments', 'files', 'logs', 'events',
        'configurations', 'templates', 'workflows', 'rules'
    ]
    
    found_tables = []
    for table_name in sorted(set(possible_tables)):
        try:
            result = client.client.table(table_name).select('*', count='exact').limit(0).execute()
            row_count = result.count if hasattr(result, 'count') else 0
            found_tables.append({'name': table_name, 'rows': row_count})
            print(f"✓ {table_name:<35} ({row_count:>6,} 行)")
        except Exception:
            pass
    
    print(f"\n找到 {len(found_tables)} 张表")
    return found_tables


def method2_direct_postgresql():
    """方法2: 直接PostgreSQL连接 (推荐 - 获取所有34张表)"""
    print("\n" + "=" * 80)
    print("方法2: 直接PostgreSQL连接 (可获取所有34张表) ⭐ 推荐")
    print("=" * 80)
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        print("❌ psycopg2 未安装")
        print("\n安装方法:")
        print("  pip install psycopg2-binary")
        print("\n或者:")
        print("  pip install psycopg2")
        return []
    
    # 从环境变量获取连接信息
    db_config = {
        'host': os.getenv('SUPABASE_DB_HOST'),
        'database': os.getenv('SUPABASE_DB_NAME'),
        'user': os.getenv('SUPABASE_DB_USER'),
        'password': os.getenv('SUPABASE_DB_PASSWORD'),
        'port': 5432
    }
    
    # 检查是否有必要的环境变量
    missing_vars = [k for k, v in db_config.items() if not v]
    if missing_vars:
        print(f"❌ 缺少环境变量: {', '.join(missing_vars)}")
        print("\n需要在 .env 文件中设置:")
        print("  SUPABASE_DB_HOST=...")
        print("  SUPABASE_DB_NAME=...")
        print("  SUPABASE_DB_USER=...")
        print("  SUPABASE_DB_PASSWORD=...")
        return []
    
    try:
        print("\n连接到数据库...")
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 查询所有表 - 简化版本
        query = """
        SELECT 
            t.tablename,
            COALESCE(s.n_live_tup, 0) as row_count
        FROM pg_catalog.pg_tables t
        LEFT JOIN pg_stat_user_tables s 
            ON t.tablename = s.relname
        WHERE t.schemaname = 'public'
        ORDER BY row_count DESC
        """
        
        print("✓ 连接成功！")
        print("\n执行查询...")
        cursor.execute(query)
        results = cursor.fetchall()
        
        print(f"✓ 查询成功！找到 {len(results)} 张表\n")
        
        all_tables = []
        total_rows = 0
        total_cols = 0
        
        print(f"{'表名':<40} | {'行数':>8}")
        print("-" * 52)
        
        for row in results:
            tablename = row['tablename']
            row_count = row['row_count']
            
            all_tables.append({
                'name': tablename,
                'rows': row_count
            })
            
            total_rows += row_count
            
            print(f"{tablename:<40} | {row_count:>8,}")
        
        print("-" * 52)
        print(f"{'总计':<40} | {total_rows:>8,}")
        
        cursor.close()
        conn.close()
        
        return all_tables
        
    except psycopg2.OperationalError as e:
        print(f"❌ 连接失败: {str(e)}")
        print("\n可能的原因:")
        print("  1. 数据库主机不可达")
        print("  2. 用户名或密码错误")
        print("  3. 网络连接问题")
        return []
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return []


def method3_get_column_info():
    """方法3: 获取所有表的详细列信息 (使用PostgreSQL)"""
    print("\n" + "=" * 80)
    print("方法3: 获取所有表的详细列信息")
    print("=" * 80)
    
    try:
        import psycopg2
    except ImportError:
        print("❌ psycopg2 未安装，跳过此方法")
        return
    
    db_config = {
        'host': os.getenv('SUPABASE_DB_HOST'),
        'database': os.getenv('SUPABASE_DB_NAME'),
        'user': os.getenv('SUPABASE_DB_USER'),
        'password': os.getenv('SUPABASE_DB_PASSWORD'),
        'port': 5432
    }
    
    missing_vars = [k for k, v in db_config.items() if not v]
    if missing_vars:
        print(f"缺少环境变量，跳过")
        return
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        # 获取所有表的列信息
        query = """
        SELECT 
            table_name,
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        # 按表组织数据
        tables_info = {}
        for row in results:
            table_name, column_name, data_type, is_nullable, column_default = row
            
            if table_name not in tables_info:
                tables_info[table_name] = []
            
            tables_info[table_name].append({
                'name': column_name,
                'type': data_type,
                'nullable': is_nullable,
                'default': column_default
            })
        
        # 输出信息
        print(f"\n总共 {len(tables_info)} 张表，{len(results)} 个列\n")
        
        # 显示前5张表的详细信息
        print("前5张表的详细列信息:")
        print("-" * 80)
        
        for i, (table_name, columns) in enumerate(sorted(tables_info.items())[:5]):
            print(f"\n{i+1}. {table_name} ({len(columns)} 列)")
            for col in columns:
                nullable = "NULL" if col['nullable'] == 'YES' else "NOT NULL"
                print(f"   - {col['name']:<30} {col['type']:<15} {nullable}")
        
        cursor.close()
        conn.close()
        
        return tables_info
        
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return None


def generate_report(all_tables):
    """生成完整报告"""
    print("\n" + "=" * 80)
    print("📊 Supabase 数据库完整报告")
    print("=" * 80)
    
    if not all_tables:
        print("❌ 未找到任何表")
        return
    
    output = {
        'database': 'Supabase PostgreSQL',
        'total_tables': len(all_tables),
        'total_rows': sum(t['rows'] for t in all_tables),
        'tables': all_tables
    }
    
    print(json.dumps(output, indent=2, ensure_ascii=False))
    
    return output


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("Supabase Python REST API 完整表查询工具")
    print("=" * 80)
    
    print("\n开始扫描...")
    
    # 方法1: REST API
    rest_api_tables = method1_supabase_rest_api()
    
    # 方法2: PostgreSQL (推荐)
    postgres_tables = method2_direct_postgresql()
    
    # 方法3: 列信息
    if postgres_tables:
        method3_get_column_info()
    
    # 生成报告
    if postgres_tables:
        print("\n" + "=" * 80)
        print("推荐使用 PostgreSQL 直接连接方案的原因:")
        print("=" * 80)
        print(f"✓ REST API 找到: {len(rest_api_tables)} 张表")
        print(f"✓ PostgreSQL 找到: {len(postgres_tables)} 张表")
        print(f"\n发现 {len(postgres_tables) - len(rest_api_tables)} 张额外的表")
        
        report = generate_report(postgres_tables)
        
        # 保存报告
        with open('database_complete_tables_list.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print("\n✓ 报告已保存到: database_complete_tables_list.json")
    else:
        print("\n❌ PostgreSQL 连接失败，仅显示 REST API 结果")
        generate_report(rest_api_tables)


if __name__ == "__main__":
    main()
