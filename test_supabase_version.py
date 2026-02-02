#!/usr/bin/env python
"""测试 Supabase 版本兼容性"""
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_ANON_KEY')

print(f"Testing Supabase client initialization...")
print(f"URL: {url[:50] if url else 'NOT SET'}...")
print(f"Key length: {len(key) if key else 0}")

# 试试不同的参数方式
from supabase import create_client

# 方式 1: 位置参数（旧版本）
print("\n1️⃣  Testing positional args (old version style)...")
try:
    client = create_client(url, key)
    print("✅ Success with positional args")
except TypeError as e:
    print(f"❌ TypeError: {e}")
except Exception as e:
    print(f"❌ {type(e).__name__}: {e}")

# 方式 2: 命名参数（新版本）
print("\n2️⃣  Testing named args (new version style)...")
try:
    client = create_client(supabase_url=url, supabase_key=key)
    print("✅ Success with named args")
except TypeError as e:
    print(f"❌ TypeError: {e}")
except Exception as e:
    print(f"❌ {type(e).__name__}: {e}")

# 方式 3: 查看 create_client 的文档
print("\n3️⃣  Checking create_client signature...")
import inspect
sig = inspect.signature(create_client)
print(f"Signature: {sig}")
