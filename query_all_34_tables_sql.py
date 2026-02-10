#!/usr/bin/env python3
"""使用Supabase SQL执行获取所有34张表的信息"""

import json
from app.services.supabase_client import SupabaseClient

def get_all_tables_with_sql():
    """通过SQL执行获取所有表"""
    client = SupabaseClient()
    
    print("=" * 80)
    print("Supabase 完整表列表 - 通过SQL查询")
    print("=" * 80)
    
    # SQL查询获取所有表的信息
    query = """
    SELECT 
        t.tablename,
        COALESCE(s.n_live_tup, 0) as row_count,
        COUNT(a.attname) as column_count
    FROM pg_catalog.pg_tables t
    LEFT JOIN pg_catalog.pg_attribute a 
        ON (SELECT oid FROM pg_catalog.pg_class WHERE relname = t.tablename) = a.attrelid
        AND a.attnum > 0 
        AND NOT a.attisdropped
    LEFT JOIN pg_stat_user_tables s 
        ON t.tablename = s.relname
    WHERE t.schemaname = 'public'
    GROUP BY t.tablename, s.n_live_tup
    ORDER BY row_count DESC
    """
    
    print("\n使用Supabase官方SQL编辑器:")
    print("-" * 80)
    print("请在 Supabase 仪表板 → SQL 编辑器中运行以下查询：\n")
    print(query)
    
    print("\n" + "=" * 80)
    print("或者，使用以下Python脚本连接到数据库:")
    print("=" * 80)
    
    print("\n[方法1] 通过 Supabase RPC (如果可用)...")
    try:
        result = client.client.rpc('exec_sql', {'sql': query}).execute()
        print("✓ 通过 RPC 执行成功!")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    except Exception as e:
        error_msg = str(e)
        print(f"✗ RPC 方法失败: {error_msg[:100]}")
    
    print("\n[方法2] 通过直接PostgreSQL连接...")
    print("""
推荐使用直接的PostgreSQL连接，代码示例：

    import psycopg2
    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    
    # 连接Supabase PostgreSQL
    conn = psycopg2.connect(
        dbname=os.getenv('SUPABASE_DB_NAME'),
        user=os.getenv('SUPABASE_DB_USER'),
        password=os.getenv('SUPABASE_DB_PASSWORD'),
        host=os.getenv('SUPABASE_DB_HOST'),
        port=5432
    )
    
    cursor = conn.cursor()
    
    query = '''SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public' ORDER BY tablename'''
    
    cursor.execute(query)
    results = cursor.fetchall()
    
    print(f"总共找到 {len(results)} 张表：")
    for row in results:
        print(f"  - {row[0]}")
    
    cursor.close()
    conn.close()
    """)
    
    print("\n[方法3] 在Supabase SQL编辑器中查看结果...")
    print("""
    1. 访问 Supabase 仪表板
    2. 选择你的项目
    3. 进入 SQL 编辑器
    4. 运行上面给出的查询
    5. 导出结果为 CSV 或 JSON
    """)

if __name__ == "__main__":
    get_all_tables_with_sql()
