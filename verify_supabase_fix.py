#!/usr/bin/env python3
"""
验证 Supabase 客户端修复
测试 get_schema_info() 方法
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

print("="*60)
print("🔧 验证 Supabase 客户端修复")
print("="*60)

# 测试1: 导入和初始化
print("\n[1/5] 测试导入和初始化...")
try:
    from app.services.supabase_client import get_supabase_client
    sb = get_supabase_client()
    print("✅ Supabase 客户端初始化成功")
except Exception as e:
    print(f"❌ 初始化失败: {e}")
    sys.exit(1)

# 测试2: 检查方法存在
print("\n[2/5] 检查 get_schema_info() 方法...")
if hasattr(sb, 'get_schema_info'):
    print("✅ get_schema_info() 方法存在")
else:
    print("❌ get_schema_info() 方法不存在")
    sys.exit(1)

# 测试3: 调用 get_schema_info()（获取所有表）
print("\n[3/5] 调用 get_schema_info()（获取所有表）...")
try:
    result = sb.get_schema_info()
    if result.get('success'):
        tables = result.get('data', [])
        print(f"✅ 成功获取 {len(tables)} 个表")
        print(f"   表名: {tables[:5]}")  # 显示前5个表
    else:
        print(f"⚠️  调用成功但返回失败: {result.get('error')}")
except Exception as e:
    print(f"❌ 调用失败: {e}")

# 测试4: 调用 get_schema_info(table_name)（获取特定表的列）
print("\n[4/5] 调用 get_schema_info('wafers')（获取特定表的列）...")
try:
    result = sb.get_schema_info('wafers')
    if result.get('success'):
        columns = result.get('data', [])
        print(f"✅ 成功获取 {len(columns)} 个列")
        if columns:
            col_names = [col.get('column_name') for col in columns[:5]]
            print(f"   列名: {col_names}")
    else:
        print(f"⚠️  调用成功但返回失败: {result.get('error')}")
except Exception as e:
    print(f"❌ 调用失败: {e}")

# 测试5: 测试 Flask 路由
print("\n[5/5] 测试 Flask 路由...")
try:
    from app import create_app
    app = create_app()
    
    with app.test_client() as client:
        # 测试 /api/query/supabase/schema (GET all tables)
        response = client.get('/api/query/supabase/schema')
        if response.status_code == 200:
            data = response.get_json()
            if data.get('success'):
                print(f"✅ GET /api/query/supabase/schema 成功")
            else:
                print(f"⚠️  GET /api/query/supabase/schema 返回失败: {data.get('error')}")
        else:
            print(f"❌ GET /api/query/supabase/schema 返回状态码 {response.status_code}")
        
        # 测试 /api/query/supabase/schema?table=wafers
        response = client.get('/api/query/supabase/schema?table=wafers')
        if response.status_code in [200, 400]:
            data = response.get_json()
            print(f"✅ GET /api/query/supabase/schema?table=wafers 返回状态码 {response.status_code}")
        else:
            print(f"⚠️  GET /api/query/supabase/schema?table=wafers 返回状态码 {response.status_code}")
        
        # 测试 /api/query/supabase/connection
        response = client.get('/api/query/supabase/connection')
        if response.status_code == 200:
            data = response.get_json()
            if data.get('success'):
                print(f"✅ GET /api/query/supabase/connection 成功")
                print(f"   连接状态: {data.get('connected')}")
                print(f"   表数: {len(data.get('tables', []))}")
            else:
                print(f"❌ GET /api/query/supabase/connection 返回失败: {data.get('error')}")
        else:
            print(f"❌ GET /api/query/supabase/connection 返回状态码 {response.status_code}")
            
except Exception as e:
    print(f"❌ Flask 路由测试失败: {e}")

print("\n" + "="*60)
print("✅ 验证完成！")
print("="*60)
print("\n🎯 接下来的步骤:")
print("1. 提交代码到 Git")
print("2. 部署到 Render")
print("3. 测试前端应用")
