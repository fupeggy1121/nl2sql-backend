#!/usr/bin/env python3
"""
🚀 Schema 标注系统 - 快速部署指南

此脚本提供完整的部署步骤和必要的 SQL 代码
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

print("""
╔═══════════════════════════════════════════════════════════════╗
║          🚀 Schema 标注系统 - 快速部署指南                     ║
║                                                               ║
║  将数据库 Schema 通过 LLM 进行语义标注,                        ║
║  并支持中文名称、描述、业务含义等丰富元数据                   ║
╚═══════════════════════════════════════════════════════════════╝

📋 部署检查清单
""")

# 步骤 1: 验证环境
print("\n[步骤 1/5] ✅ 环境验证")
print("─" * 60)
required_env = {
    'SUPABASE_URL': '✓' if os.getenv('SUPABASE_URL') else '✗',
    'SUPABASE_ANON_KEY': '✓' if os.getenv('SUPABASE_ANON_KEY') else '✗',
    'DEEPSEEK_API_KEY': '✓' if os.getenv('DEEPSEEK_API_KEY') else '✗',
}
for var, status in required_env.items():
    print(f"  {status} {var}")

if '✗' in required_env.values():
    print("\n❌ 缺少必要的环境变量。请检查 .env 文件")
    exit(1)

print("\n✅ 所有环境变量已配置\n")

# 步骤 2: 创建数据库表
print("[步骤 2/5] 📊 创建数据库表")
print("─" * 60)
print("""
需要在 Supabase 中创建 4 个标注表:

1️⃣  schema_table_annotations       - 表级标注
2️⃣  schema_column_annotations      - 列级标注  
3️⃣  schema_relation_annotations    - 关系标注
4️⃣  annotation_audit_log           - 审计日志

【方式 A: 在 Supabase 控制台执行 (推荐)】

1. 打开 https://supabase.com 并登录
2. 进入您的项目
3. 左侧菜单选择 "SQL Editor"
4. 点击 "New query"
5. 打开文件: migration.sql (已在项目根目录)
6. 复制全部内容到编辑器
7. 点击 "Run" 执行

【方式 B: 使用命令行】

如果您有 psql 和 Supabase 数据库密码:

    python execute_psql_migration.py

""")

# 步骤 3: 扫描 Schema
print("[步骤 3/5] 🔍 扫描数据库 Schema")
print("─" * 60)
print("""
一旦数据库表创建完成，运行以下命令发现所有表和列:

    python app/tools/scan_schema.py

这会生成 schema_discovery.json，包含所有数据库元数据。
""")

# 步骤 4: 生成 LLM 标注
print("[步骤 4/5] 🤖 LLM 自动标注")
print("─" * 60)
print("""
运行以下命令使用 DeepSeek 生成初始标注:

    python app/tools/auto_annotate_schema.py

这会:
  1. 读取扫描的 Schema
  2. 调用 DeepSeek LLM 生成中英文标注
  3. 保存到数据库 (状态: pending)
  4. 显示生成的标注预览

⏱️  首次运行可能需要 1-5 分钟，具体取决于表的数量和 API 响应速度。
💡 如果需要跳过某些表，可编辑 auto_annotate_schema.py
""")

# 步骤 5: 审核和批准
print("[步骤 5/5] ✅ 审核和批准标注")
print("─" * 60)
print("""
启动后端应用并通过 API 审核标注:

    python run.py

然后使用 API 端点:

【查看待审核的表标注】
    GET http://localhost:5000/api/schema/tables/pending
    
【查看待审核的列标注】
    GET http://localhost:5000/api/schema/columns/pending
    
【批准标注】
    POST http://localhost:5000/api/schema/tables/{id}/approve
    Body: {"reviewer": "your_name", "notes": "approved"}
    
【拒绝标注】
    POST http://localhost:5000/api/schema/tables/{id}/reject
    Body: {"reviewer": "your_name", "reason": "需要修改"}
    
【编辑标注】
    PUT http://localhost:5000/api/schema/tables/{id}
    Body: {"table_name_cn": "修改后的名称", ...}
    
【获取所有已批准的标注】
    GET http://localhost:5000/api/schema/metadata
    
【查看标注统计】
    GET http://localhost:5000/api/schema/status

📌 完成后，这些批准的标注会被用于改进 NL2SQL 的理解
""")

# 总结
print("\n" + "=" * 60)
print("🎯 完整部署流程总结")
print("=" * 60)
print("""
1. ✅ 验证环境变量               (已完成)
2. 📊 创建数据库表                (使用 migration.sql 手动执行)
3. 🔍 扫描 Schema                (python app/tools/scan_schema.py)
4. 🤖 LLM 标注                   (python app/tools/auto_annotate_schema.py)
5. ✅ 审核批准                    (通过 API 或前端界面)
6. 🔗 集成到 NL2SQL              (修改 nl2sql.py 使用标注元数据)

下一步: 请先执行 migration.sql 创建数据库表
""")

print("\n💾 SQL 脚本位置: ./migration.sql")
print("📖 详细文档: ./SCHEMA_ANNOTATION_GUIDE.md")
print("🚀 快速开始: ./SCHEMA_ANNOTATION_QUICK_REF.md\n")
