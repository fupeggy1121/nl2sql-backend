#!/usr/bin/env python
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_ANON_KEY')

print(f'URL: {url}')
print(f'Key length: {len(key)}')
print()

try:
    client = create_client(url, key)
    print('✅ Client created')
    
    # 测试连接
    result = client.table('users').select('id').limit(1).execute()
    print(f'✅ Query successful: {len(result.data)} rows')
except Exception as e:
    import traceback
    print(f'❌ Error: {type(e).__name__}: {e}')
    traceback.print_exc()
