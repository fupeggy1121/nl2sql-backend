#!/usr/bin/env python3
"""
使用 psql 执行 Schema 标注表迁移
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

load_dotenv()


def get_supabase_connection_string():
    """获取 Supabase PostgreSQL 连接字符串"""
    url = os.getenv('SUPABASE_URL')  # https://xxx.supabase.co
    anon_key = os.getenv('SUPABASE_ANON_KEY')
    
    if not url or not anon_key:
        print("❌ 缺少环境变量")
        return None
    
    # 从 URL 提取项目 ID
    # https://kgmyhukvyygudsllypgv.supabase.co -> kgmyhukvyygudsllypgv
    project_id = url.split('/')[2].split('.')[0]
    
    # Supabase 的默认连接方式
    # postgresql://postgres:[password]@db.[project-id].supabase.co:5432/postgres
    # 但我们需要密码，这通常在 Supabase 设置中
    
    # 尝试使用环境变量中的 Supabase 密码（如果有的话）
    supabase_password = os.getenv('SUPABASE_DB_PASSWORD')
    
    if not supabase_password:
        print("❌ 缺少 SUPABASE_DB_PASSWORD 环境变量")
        print("   请从 Supabase 项目设置中获取数据库密码")
        return None
    
    # 构建连接字符串
    connection_string = (
        f"postgresql://postgres:{supabase_password}"
        f"@db.{project_id}.supabase.co:5432/postgres"
    )
    
    return connection_string


def execute_migration_via_psql():
    """通过 psql 执行迁移"""
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║     执行 Schema 标注表迁移 (使用 psql)                     ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")
    
    conn_string = get_supabase_connection_string()
    
    if not conn_string:
        print("\n⚠️  自动获取连接失败。")
        print("   请使用以下方式手动执行:\n")
        print("1. 登录 Supabase 控制台")
        print("2. 进入 SQL Editor")
        print("3. 打开 migration.sql 文件或复制内容")
        print("4. 执行 SQL\n")
        return False
    
    sql_file = project_root / "migration.sql"
    
    if not sql_file.exists():
        print(f"❌ SQL 文件不存在: {sql_file}")
        print("   先运行: python run_migration.py")
        return False
    
    print(f"使用连接: postgresql://postgres@db.*.supabase.co:5432/postgres\n")
    print(f"执行 SQL 文件: {sql_file}\n")
    
    try:
        # 使用 psql 执行 SQL 文件
        cmd = ['psql', conn_string, '-f', str(sql_file), '-v', 'ON_ERROR_STOP=1']
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print("✅ 迁移成功！\n")
            print(result.stdout)
            print("\n下一步:")
            print("  1. 运行: python verify_schema_annotation_setup.py")
            print("  2. 运行: python app/tools/scan_schema.py")
            print("  3. 运行: python app/tools/auto_annotate_schema.py")
            return True
        else:
            print("❌ 迁移失败！\n")
            print("STDOUT:")
            print(result.stdout)
            print("\nSTDERR:")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ 迁移超时 (超过 60 秒)")
        return False
    except FileNotFoundError:
        print("❌ 找不到 psql 命令")
        return False
    except Exception as e:
        print(f"❌ 执行出错: {str(e)}")
        return False


if __name__ == "__main__":
    success = execute_migration_via_psql()
    sys.exit(0 if success else 1)
