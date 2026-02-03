#!/usr/bin/env python3
"""
执行 Schema 标注表迁移 - 通过 HTTP API
"""

import os
import sys
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到 path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

load_dotenv()

# 直接读取 SQL 文件
migration_file = project_root / "supabase" / "create_annotation_tables.py"

# 使用 exec 执行文件来获取 MIGRATION_SQL
migration_context = {}
with open(migration_file) as f:
    exec(f.read(), migration_context)

def get_migration_sql():
    return migration_context.get('MIGRATION_SQL', '')


def execute_migration_via_http():
    """通过 HTTP API 执行迁移"""
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║     执行 Schema 标注表迁移                                 ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")
    
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ 缺少 SUPABASE_URL 或 SUPABASE_ANON_KEY 环境变量")
        return False
    
    # 获取 SQL 脚本
    sql = get_migration_sql()
    
    # 将 SQL 分割成单个语句
    statements = [
        stmt.strip() 
        for stmt in sql.split(';') 
        if stmt.strip() and not stmt.strip().startswith('--')
    ]
    
    print(f"准备执行 {len(statements)} 个 SQL 语句...")
    print(f"连接到: {supabase_url[:50]}...\n")
    
    # 尝试使用 PostgreSQL 直接连接（如果 Supabase 提供连接字符串）
    # 或者我们生成一个说明让用户手动执行
    
    print("⚠️  Supabase Python SDK 的限制导致无法直接执行原生 SQL。")
    print("   请使用以下方式之一创建表:\n")
    
    return show_manual_instructions(sql)


def show_manual_instructions(sql):
    """显示手动执行说明"""
    print("━" * 70)
    print("【方法 1: 通过 Supabase 控制台】(推荐)")
    print("━" * 70)
    print("""
1. 打开 https://supabase.com 并登录
2. 进入您的项目
3. 左侧菜单选择 "SQL Editor"
4. 点击 "New query" 或 "+"
5. 将下面的 SQL 复制粘贴到编辑器
6. 点击 "Run" 或按 Ctrl+Enter 执行
7. 查看执行结果
""")
    
    print("━" * 70)
    print("【方法 2: 使用 psql 命令行】")
    print("━" * 70)
    print("""
1. 获取 Supabase PostgreSQL 连接字符串
2. 运行: psql <connection_string>
3. 粘贴下面的 SQL
4. 按 Enter 执行
""")
    
    print("━" * 70)
    print("【SQL 脚本】 (复制以下全部内容)")
    print("━" * 70)
    print(sql)
    print("━" * 70)
    
    print("\n✅ SQL 脚本已生成。请选择上述方法之一执行。")
    print("   执行后，运行以下命令验证表已创建:")
    print("   python verify_schema_annotation_setup.py")
    
    return True


if __name__ == "__main__":
    # 直接生成 SQL 并显示说明
    sql = get_migration_sql()
    
    success = show_manual_instructions(sql)
    
    # 保存 SQL 到文件以便用户直接使用
    sql_file = Path(__file__).parent / "migration.sql"
    with open(sql_file, 'w') as f:
        f.write(sql)
    
    print(f"\n💾 SQL 脚本已保存到: {sql_file}")
    print("   您可以在 Supabase SQL Editor 中打开该文件")
    
    sys.exit(0)
