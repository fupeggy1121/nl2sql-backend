#!/usr/bin/env python
"""诊断 Supabase 连接问题"""
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv('SUPABASE_URL')
anon_key = os.getenv('SUPABASE_ANON_KEY')
service_key = os.getenv('SUPABASE_SERVICE_KEY')

print("=" * 60)
print("Supabase 连接诊断")
print("=" * 60)

print("\n1️⃣ 环境变量检查:")
print(f"  SUPABASE_URL: {'✅' if url else '❌'} {url[:50] if url else 'NOT SET'}...")
print(f"  SUPABASE_ANON_KEY: {'✅' if anon_key else '❌'} (长度: {len(anon_key) if anon_key else 0})")
print(f"  SUPABASE_SERVICE_KEY: {'✅' if service_key else '❌'} (长度: {len(service_key) if service_key else 0})")

if not url or not anon_key:
    print("\n❌ 缺少必需的环境变量!")
    exit(1)

print("\n2️⃣ Supabase 项目检查:")
print(f"  项目 ID: {url.split('.')[0].replace('https://', '')}")

print("\n3️⃣ 尝试连接...")

try:
    from supabase import create_client
    
    # 先试 anon key
    print("\n  尝试使用 ANON_KEY...")
    try:
        client = create_client(url, anon_key)
        print("  ✅ Anon Key 初始化成功")
        
        # 测试连接
        result = client.table('users').select('id').limit(1).execute()
        print(f"  ✅ 连接成功! 查询返回: {len(result.data)} 行")
        
    except Exception as e:
        error_msg = str(e)
        print(f"  ❌ Anon Key 连接失败: {error_msg[:100]}")
        
        # 如果 anon key 失败，试 service key
        if service_key:
            print("\n  尝试使用 SERVICE_KEY...")
            try:
                client = create_client(url, service_key)
                print("  ✅ Service Key 初始化成功")
                
                result = client.table('users').select('id').limit(1).execute()
                print(f"  ✅ 连接成功! 查询返回: {len(result.data)} 行")
                
            except Exception as e2:
                print(f"  ❌ Service Key 也失败: {str(e2)[:100]}")
                print("\n⚠️ 两个密钥都无效!")
                print("\n可能的原因:")
                print("  1. Supabase 项目已被删除或暂停")
                print("  2. 密钥已被重新生成")
                print("  3. 密钥复制时有问题（空格、换行）")
                print("  4. 项目 ID 不匹配")
        else:
            print("\n⚠️ Anon Key 无效且未设置 Service Key")

except ImportError:
    print("  ❌ supabase-py not installed")
except Exception as e:
    print(f"  ❌ 未知错误: {e}")

print("\n" + "=" * 60)
print("📋 建议操作:")
print("=" * 60)
print("""
1. 访问 https://app.supabase.com
2. 检查项目 'kgmyhukvyygudsllypgv' 是否还存在
3. 进入 Settings → API
4. 复制 "Project URL" 和 "anon public" 密钥
5. 更新 Render 环境变量
6. Manual Deploy
7. 再次运行此脚本验证
""")
