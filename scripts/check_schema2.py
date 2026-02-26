#!/usr/bin/env python3
"""Check actual PostgreSQL column types via execute_sql RPC."""
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

def run_sql(sql):
    r = requests.post(f'{url}/rest/v1/rpc/execute_sql', headers=headers, json={'query': sql})
    if r.status_code == 200:
        return r.json()
    else:
        print(f'  Error: {r.text[:200]}')
        return []

# Get column info using pg_catalog instead of information_schema
for tbl in ['batches', 'sub_batches', 'wafers', 'wafer_carrier_contents', 'carriers']:
    sql = f"""
    SELECT a.attname as col, 
           t.typname as typ,
           CASE WHEN a.attnotnull THEN 'NN' ELSE 'NULL' END as nullable,
           pg_get_expr(d.adbin, d.adrelid) as dflt
    FROM pg_attribute a
    JOIN pg_type t ON a.atttypid = t.oid
    LEFT JOIN pg_attrdef d ON a.attrelid = d.adrelid AND a.attnum = d.adnum
    WHERE a.attrelid = 'public.{tbl}'::regclass
      AND a.attnum > 0 AND NOT a.attisdropped
    ORDER BY a.attnum
    """
    print(f'\n=== {tbl} ===')
    rows = run_sql(sql)
    for r in rows:
        col = r.get('col', '')
        typ = r.get('typ', '')
        null = r.get('nullable', '')
        dflt = str(r.get('dflt', ''))[:50] if r.get('dflt') else '-'
        print(f'  {col:30} {typ:10} {null:4} default={dflt}')

# Check FK constraints
print('\n=== Foreign Key constraints on sub_batches ===')
rows = run_sql("""
SELECT conname, pg_get_constraintdef(oid) as def
FROM pg_constraint
WHERE conrelid = 'public.sub_batches'::regclass AND contype = 'f'
""")
for r in rows:
    print(f"  {r.get('conname','')}: {r.get('def','')}")

print('\n=== Foreign Key constraints on wafers ===')
rows = run_sql("""
SELECT conname, pg_get_constraintdef(oid) as def
FROM pg_constraint
WHERE conrelid = 'public.wafers'::regclass AND contype = 'f'
""")
for r in rows:
    print(f"  {r.get('conname','')}: {r.get('def','')}")

print('\n=== Foreign Key constraints on wafer_carrier_contents ===')
rows = run_sql("""
SELECT conname, pg_get_constraintdef(oid) as def
FROM pg_constraint
WHERE conrelid = 'public.wafer_carrier_contents'::regclass AND contype = 'f'
""")
for r in rows:
    print(f"  {r.get('conname','')}: {r.get('def','')}")

# Check sample data
print('\n=== Sample wafer_carrier_contents (1 row) ===')
rows = run_sql("SELECT * FROM wafer_carrier_contents LIMIT 1")
if rows:
    print(json.dumps(rows[0], indent=2, default=str))

print('\n=== Sample wafers (1 row) ===')
rows = run_sql("SELECT * FROM wafers LIMIT 1")
if rows:
    print(json.dumps(rows[0], indent=2, default=str))

print('\nDONE')
