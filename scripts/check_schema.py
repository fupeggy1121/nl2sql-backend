#!/usr/bin/env python3
"""Check actual PostgreSQL column types for affected tables."""
import os, json, requests
from dotenv import load_dotenv
load_dotenv()

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY')
headers = {
    'apikey': key,
    'Authorization': f'Bearer {key}',
    'Content-Type': 'application/json'
}

sql = """
SELECT table_name, column_name, udt_name, is_nullable, 
       LEFT(COALESCE(column_default::text, ''), 50) as col_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('batches','sub_batches','wafers','wafer_carrier_contents','carriers','stations')
ORDER BY table_name, ordinal_position
"""

r = requests.post(
    f'{url}/rest/v1/rpc/execute_sql',
    headers=headers,
    json={'query': sql}
)

if r.status_code == 200:
    data = r.json()
    if isinstance(data, list):
        current_table = ''
        for row in data:
            tbl = row.get('table_name', '')
            if tbl != current_table:
                current_table = tbl
                print(f'\n=== {tbl} ===')
            col = row.get('column_name', '')
            typ = row.get('udt_name', '')
            null_val = row.get('is_nullable', '')
            dflt = row.get('col_default', '') or '-'
            print(f'  {col:30} {typ:15} null={null_val:3} default={dflt}')
    else:
        print(json.dumps(data, indent=2)[:2000])
else:
    print(f'Error {r.status_code}: {r.text[:500]}')

# Also check row counts
print('\n=== Row Counts ===')
for tbl in ['batches', 'sub_batches', 'wafers', 'wafer_carrier_contents', 'carriers']:
    sql2 = f"SELECT COUNT(*) as cnt FROM {tbl}"
    r2 = requests.post(f'{url}/rest/v1/rpc/execute_sql', headers=headers, json={'query': sql2})
    if r2.status_code == 200:
        d = r2.json()
        cnt = d[0]['cnt'] if isinstance(d, list) and d else '?'
        print(f'  {tbl:30} {cnt} rows')

# Check existing constraints on wafers
print('\n=== Existing constraints on wafers ===')
sql3 = """
SELECT conname, contype, pg_get_constraintdef(oid) as def
FROM pg_constraint
WHERE conrelid = 'public.wafers'::regclass
"""
r3 = requests.post(f'{url}/rest/v1/rpc/execute_sql', headers=headers, json={'query': sql3})
if r3.status_code == 200:
    for row in r3.json():
        print(f"  {row.get('conname',''):40} {row.get('def','')}")

print('\nDONE')
