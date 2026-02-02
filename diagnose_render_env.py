#!/usr/bin/env python3
"""
Render 环境变量诊断工具
检查 Supabase 相关的环境变量是否正确设置
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("Render 环境变量诊断报告")
print("=" * 60)

# 检查 Supabase 相关环境变量
env_vars_to_check = [
    'DB_HOST',
    'DB_PORT',
    'DB_USER',
    'DB_PASSWORD',
    'DB_NAME',
    'SUPABASE_URL',
    'SUPABASE_ANON_KEY',
    'SUPABASE_SERVICE_KEY'
]

print("\n📋 环境变量检查：\n")
for var in env_vars_to_check:
    value = os.getenv(var)
    if value:
        # 隐藏敏感信息
        if 'PASSWORD' in var or 'KEY' in var:
            masked = value[:10] + '...' if len(value) > 10 else value
        else:
            masked = value
        print(f"✅ {var:25} = {masked}")
    else:
        print(f"❌ {var:25} = <NOT SET>")

# 测试数据库连接
print("\n🔗 数据库连接测试：\n")
try:
    import psycopg2
    db_host = os.getenv('DB_HOST')
    db_port = int(os.getenv('DB_PORT', 5432))
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    db_name = os.getenv('DB_NAME')
    
    if all([db_host, db_user, db_password, db_name]):
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_name,
            connect_timeout=5
        )
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.close()
        conn.close()
        print("✅ PostgreSQL 连接成功")
    else:
        print("❌ 缺少数据库凭证")
except Exception as e:
    print(f"❌ PostgreSQL 连接失败: {str(e)}")

# 测试后端 API
print("\n🌐 后端 API 健康检查：\n")
try:
    response = requests.get('http://localhost:8000/api/query/health', timeout=5)
    if response.status_code == 200:
        print("✅ 后端 API 响应正常")
        print(f"   响应: {response.json()}")
    else:
        print(f"⚠️  后端返回状态码: {response.status_code}")
except Exception as e:
    print(f"❌ 无法连接到后端: {str(e)}")

print("\n" + "=" * 60)
print("✅ 诊断完成")
print("=" * 60)
