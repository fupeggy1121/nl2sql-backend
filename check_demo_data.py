#!/usr/bin/env python3
"""
检查演示数据是否被插入
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from supabase import create_client
import json

load_dotenv()

# 初始化 Supabase
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_ANON_KEY')

if not supabase_url or not supabase_key:
    print("❌ SUPABASE_URL or SUPABASE_ANON_KEY not configured")
    sys.exit(1)

supabase = create_client(supabase_url, supabase_key)

print("📊 检查数据库中的标注数据")
print("=" * 50)

# 检查表级标注
try:
    result = supabase.table('schema_table_annotations').select("*").execute()
    print(f"\n📋 表级标注 ({len(result.data)} 条):")
    for item in result.data:
        print(f"  - {item.get('table_name')}: status={item.get('status')}")
except Exception as e:
    print(f"❌ 查询表级标注失败: {e}")

# 检查列级标注
try:
    result = supabase.table('schema_column_annotations').select("*").execute()
    print(f"\n📊 列级标注 ({len(result.data)} 条):")
    for item in result.data:
        print(f"  - {item.get('table_name')}.{item.get('column_name')}: status={item.get('status')}")
except Exception as e:
    print(f"❌ 查询列级标注失败: {e}")

# 检查待审核数据
try:
    result = supabase.table('schema_table_annotations').select("*").eq("status", "pending").execute()
    print(f"\n⏳ 待审核的表 ({len(result.data)} 条):")
    if result.data:
        print(json.dumps(result.data, indent=2, ensure_ascii=False))
    else:
        print("  (没有待审核的表)")
except Exception as e:
    print(f"❌ 查询待审核数据失败: {e}")
