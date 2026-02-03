#!/usr/bin/env python3
"""
执行 Schema 标注表迁移
通过 Supabase 的 SQL 执行功能创建数据库表
"""

import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from app.services.supabase_client import get_supabase_client
from supabase.create_annotation_tables import get_migration_sql

load_dotenv()


def execute_migration():
    """执行数据库迁移"""
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║     执行 Schema 标注表迁移                                 ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")
    
    try:
        # 获取 Supabase 客户端
        supabase = get_supabase_client()
        
        if not supabase.is_connected():
            print("❌ 无法连接到 Supabase")
            if supabase.init_error:
                print(f"   错误: {supabase.init_error}")
            return False
        
        print("✅ Supabase 连接成功\n")
        
        # 获取 SQL 脚本
        sql = get_migration_sql()
        
        # 将 SQL 分割成单个语句（按 ; 分割并过滤空语句）
        statements = [
            stmt.strip() 
            for stmt in sql.split(';') 
            if stmt.strip() and not stmt.strip().startswith('--')
        ]
        
        print(f"准备执行 {len(statements)} 个 SQL 语句...\n")
        
        # 逐个执行 SQL 语句
        successful = 0
        failed = 0
        
        for i, stmt in enumerate(statements, 1):
            try:
                # 显示执行的操作
                first_line = stmt.split('\n')[0][:60]
                print(f"[{i}/{len(statements)}] 执行: {first_line}...")
                
                # 使用 rpc 执行原生 SQL
                # Supabase 的 Python SDK 没有直接的 SQL 执行方法
                # 我们需要使用 PostgREST API 或者通过 supabase-py 的底层方法
                
                # 更好的方法是直接调用 HTTP API
                response = supabase.client.postgrest.rpc(
                    'exec_sql',
                    {'sql': stmt},
                    count=None
                )
                print(f"    ✅ 完成")
                successful += 1
                
            except Exception as e:
                error_msg = str(e)
                # 某些错误可以忽略（如表已存在）
                if 'already exists' in error_msg.lower() or 'duplicate' in error_msg.lower():
                    print(f"    ⚠️  表或对象已存在（正常）")
                    successful += 1
                else:
                    print(f"    ❌ 失败: {error_msg[:80]}...")
                    failed += 1
        
        print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"结果: {successful} 成功, {failed} 失败")
        
        if failed == 0:
            print("\n✅ 迁移完成！所有表已创建。\n")
            print("下一步:")
            print("  1. 运行 python app/tools/scan_schema.py 扫描数据库 Schema")
            print("  2. 运行 python app/tools/auto_annotate_schema.py 进行 LLM 标注")
            print("  3. 启动后端: python run.py")
            print("  4. 调用 API 审核和批准标注")
            return True
        else:
            print(f"\n⚠️  迁移部分失败，但某些表可能已创建。")
            return False
            
    except Exception as e:
        print(f"❌ 迁移失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def execute_migration_via_sql_file():
    """通过 SQL 文件方式提示用户"""
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║     Schema 标注表迁移 - 手动执行 SQL                       ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")
    
    print("由于 Supabase Python SDK 的限制，建议通过以下方式创建表:\n")
    
    from supabase.create_annotation_tables import get_migration_sql
    
    sql = get_migration_sql()
    
    print("📋 SQL 脚本已生成。请按以下步骤操作:\n")
    print("1️⃣  打开 Supabase 控制台: https://supabase.com")
    print("2️⃣  登录您的项目")
    print("3️⃣  进入左侧菜单 'SQL Editor'")
    print("4️⃣  点击 'New query'")
    print("5️⃣  复制以下 SQL 代码粘贴到编辑器")
    print("6️⃣  点击 'Run' 执行\n")
    
    print("━" * 60)
    print("【复制以下 SQL】")
    print("━" * 60)
    print(sql)
    print("━" * 60)
    
    print("\n✅ SQL 脚本已生成完毕。")
    print("   请复制上面的 SQL 到 Supabase 控制台执行。")


if __name__ == "__main__":
    success = execute_migration()
    
    if not success:
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("\n⚠️  自动迁移失败。改用手动方式...\n")
        execute_migration_via_sql_file()
    
    sys.exit(0 if success else 1)
