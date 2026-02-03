#!/usr/bin/env python3
"""
Supabase 数据库迁移执行脚本
通过 PostgreSQL 直接连接执行 migration.sql
"""

import sys
import os
import logging
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from app.services.postgresql_executor import PostgreSQLExecutor

load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def verify_environment():
    """验证必要的环境变量"""
    required_vars = [
        'SUPABASE_DB_HOST',
        'SUPABASE_DB_PORT',
        'SUPABASE_DB_NAME',
        'SUPABASE_DB_USER',
        'SUPABASE_DB_PASSWORD',
    ]
    
    print("=" * 70)
    print("【环境变量检查】")
    print("=" * 70)
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # 隐藏敏感信息
            if 'PASSWORD' in var:
                display = value[:5] + "***" if len(value) > 5 else "***"
            else:
                display = value
            print(f"✅ {var:30} = {display}")
        else:
            print(f"❌ {var:30} = 未设置")
            missing.append(var)
    
    if missing:
        print(f"\n❌ 缺少环境变量: {', '.join(missing)}")
        print("\n请在 .env 文件中设置这些变量:")
        print("""
SUPABASE_DB_HOST=db.xxx.supabase.co
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=your_password_here
        """)
        return False
    
    print("\n✅ 所有必要的环境变量已设置\n")
    return True


def execute_migration():
    """执行数据库迁移"""
    print("=" * 70)
    print("【执行数据库迁移】")
    print("=" * 70 + "\n")
    
    # 获取 migration.sql 文件路径
    migration_file = project_root / "migration.sql"
    
    if not migration_file.exists():
        print(f"❌ 迁移文件不存在: {migration_file}")
        return False
    
    print(f"📄 迁移文件: {migration_file}\n")
    
    # 创建执行器并执行迁移
    executor = PostgreSQLExecutor()
    
    if not executor.connect():
        print("❌ 无法连接到数据库")
        print("\n排查步骤:")
        print("1. 确认 SUPABASE_DB_PASSWORD 是正确的")
        print("2. 确认网络连接到 Supabase")
        print("3. 尝试使用 psql 命令行连接测试")
        return False
    
    # 执行 SQL 文件
    success = executor.execute_sql_file(str(migration_file))
    
    if success:
        print("\n" + "=" * 70)
        print("【迁移验证】")
        print("=" * 70)
        
        # 验证创建的表
        tables = [
            'schema_table_annotations',
            'schema_column_annotations',
            'schema_relation_annotations',
            'annotation_audit_log'
        ]
        
        print("\n检查创建的表:\n")
        all_exist = True
        for table in tables:
            exists = executor.table_exists(table)
            status = "✅" if exists else "❌"
            print(f"  {status} {table}")
            if not exists:
                all_exist = False
        
        if all_exist:
            print("\n✅ 所有表已成功创建！\n")
            return True
        else:
            print("\n⚠️  某些表未成功创建\n")
            return False
    
    return False


def show_next_steps():
    """显示后续步骤"""
    print("=" * 70)
    print("【后续步骤】")
    print("=" * 70)
    print("""
数据库表创建完成后，请运行以下命令:

1️⃣  扫描数据库 Schema:
    .venv/bin/python app/tools/scan_schema.py

2️⃣  生成 LLM 标注:
    .venv/bin/python app/tools/auto_annotate_schema.py

3️⃣  启动后端应用:
    .venv/bin/python run.py

4️⃣  查看 API 状态:
    curl http://localhost:5000/api/schema/status
    """)


def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  🚀 Supabase 数据库迁移执行".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    # 验证环境
    if not verify_environment():
        return 1
    
    # 执行迁移
    if execute_migration():
        show_next_steps()
        return 0
    else:
        print("❌ 迁移失败")
        print("\n需要帮助?")
        print("1. 查看 DEPLOYMENT_FINAL_GUIDE.md")
        print("2. 运行 python verify_schema_annotation_setup.py 检查环境")
        print("3. 检查 Supabase 数据库密码是否正确")
        return 1


if __name__ == "__main__":
    sys.exit(main())
