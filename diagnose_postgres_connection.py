#!/usr/bin/env python3
"""诊断 PostgreSQL 连接问题"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

def diagnose_postgresql_connection():
    """诊断 PostgreSQL 连接"""
    
    print("=" * 70)
    print("PostgreSQL 连接诊断工具")
    print("=" * 70)
    
    # 1. 检查环境变量
    print("\n[步骤 1] 检查环境变量配置")
    print("-" * 70)
    
    config = {
        'host': os.getenv('SUPABASE_DB_HOST'),
        'database': os.getenv('SUPABASE_DB_NAME'),
        'user': os.getenv('SUPABASE_DB_USER'),
        'password': os.getenv('SUPABASE_DB_PASSWORD'),
        'port': os.getenv('SUPABASE_DB_PORT', '5432')
    }
    
    missing = []
    for key, value in config.items():
        if key == 'password':
            display = '*' * len(value) if value else '未设置'
        else:
            display = value if value else '未设置'
        
        status = "✓" if value else "✗"
        print(f"{status} {key:<15}: {display}")
        
        if not value and key != 'port':
            missing.append(key)
    
    if missing:
        print(f"\n✗ 缺少以下配置: {', '.join(missing)}")
        print("请在 .env 文件中设置这些变量")
        return False
    
    print("\n✓ 所有环境变量已配置")
    
    # 2. 检查 psycopg2
    print("\n[步骤 2] 检查 psycopg2 安装")
    print("-" * 70)
    
    try:
        import psycopg2
        print("✓ psycopg2 已安装")
    except ImportError:
        print("✗ psycopg2 未安装")
        print("\n安装方法:")
        print("  pip install psycopg2-binary")
        print("或")
        print("  pip install psycopg2")
        return False
    
    # 3. 测试网络连接
    print("\n[步骤 3] 测试网络连接")
    print("-" * 70)
    
    import socket
    try:
        socket.create_connection((config['host'], int(config['port'])), timeout=5)
        print(f"✓ 可以连接到 {config['host']}:{config['port']}")
    except socket.timeout:
        print(f"✗ 连接超时: {config['host']}:{config['port']}")
        print("  可能原因: 网络不通、防火墙阻止或主机离线")
        return False
    except socket.gaierror:
        print(f"✗ 主机名无法解析: {config['host']}")
        print("  可能原因: DNS 问题或主机名拼写错误")
        return False
    except Exception as e:
        print(f"✗ 网络连接失败: {str(e)}")
        return False
    
    # 4. 测试数据库连接
    print("\n[步骤 4] 测试数据库连接")
    print("-" * 70)
    
    try:
        conn = psycopg2.connect(
            host=config['host'],
            database=config['database'],
            user=config['user'],
            password=config['password'],
            port=config['port'],
            connect_timeout=10
        )
        print("✓ 数据库连接成功！")
        
        # 测试查询
        cursor = conn.cursor()
        
        # 获取版本
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        print(f"✓ PostgreSQL 版本: {version.split(',')[0]}")
        
        # 获取表数量
        cursor.execute("SELECT COUNT(*) FROM pg_catalog.pg_tables WHERE schemaname='public'")
        table_count = cursor.fetchone()[0]
        print(f"✓ 找到 {table_count} 张 public 表")
        
        # 获取数据库大小
        cursor.execute("""
            SELECT pg_size_pretty(pg_database.datsize) as size
            FROM (SELECT pg_database_size(current_database()) as datsize) as pg_database
        """)
        size = cursor.fetchone()[0]
        print(f"✓ 数据库大小: {size}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except psycopg2.OperationalError as e:
        error_msg = str(e)
        print(f"✗ 连接失败: {error_msg}")
        
        print("\n诊断信息:")
        if "could not translate host name" in error_msg:
            print("  ❌ 主机名无法解析")
            print("  原因: DNS 问题或主机名拼写错误")
            print("  解决: 检查 SUPABASE_DB_HOST 配置")
            
        elif "Connection refused" in error_msg:
            print("  ❌ 连接被拒绝")
            print("  原因: 数据库服务未运行或端口错误")
            print("  解决: 检查 SUPABASE_DB_PORT 配置")
            
        elif "password authentication failed" in error_msg:
            print("  ❌ 密码认证失败")
            print("  原因: 用户名或密码错误")
            print("  解决: 检查 SUPABASE_DB_USER 和 SUPABASE_DB_PASSWORD")
            
        elif "FATAL" in error_msg and "database" in error_msg:
            print("  ❌ 数据库不存在")
            print("  原因: 指定的数据库名不存在")
            print("  解决: 检查 SUPABASE_DB_NAME 配置")
            
        elif "timeout" in error_msg.lower():
            print("  ❌ 连接超时")
            print("  原因: 网络延迟或防火墙阻止")
            print("  解决: 检查网络连接和防火墙规则")
            
        else:
            print(f"  ❌ 其他错误: {error_msg[:100]}")
        
        return False
        
    except Exception as e:
        print(f"✗ 未知错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # 5. 测试查询
    print("\n[步骤 5] 测试查询所有表")
    print("-" * 70)
    
    try:
        conn = psycopg2.connect(**config)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT tablename FROM pg_catalog.pg_tables 
            WHERE schemaname='public' 
            ORDER BY tablename 
            LIMIT 5
        """)
        
        tables = cursor.fetchall()
        print(f"✓ 前 5 张表:")
        for table in tables:
            print(f"  - {table[0]}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"✗ 查询失败: {str(e)}")
        return False


def main():
    """主函数"""
    print()
    success = diagnose_postgresql_connection()
    print()
    
    if success:
        print("=" * 70)
        print("✓ 诊断完成 - 连接正常！")
        print("=" * 70)
        sys.exit(0)
    else:
        print("=" * 70)
        print("✗ 诊断完成 - 发现问题")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
