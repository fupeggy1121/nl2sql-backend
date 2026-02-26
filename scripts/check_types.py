#!/usr/bin/env python3
"""Check actual PostgreSQL column types using pg_typeof."""
import os, requests, json
from dotenv import load_dotenv
load_dotenv()

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
headers = {
    'apikey': key,
    'Authorization': f'Bearer {key}',
    'Content-Type': 'application/json'
}

def run_sql(sql):
    r = requests.post(f'{url}/rest/v1/rpc/execute_sql', headers=headers, json={'query': sql})
    if r.status_code == 200:
        return r.json()
    print(f'  Error: {r.text[:200]}')
    return []

# Check actual types
queries = {
    'wafers': "SELECT pg_typeof(id)::text as id_type, pg_typeof(batch_id)::text as batch_id_type FROM wafers LIMIT 1",
    'sub_batches': "SELECT pg_typeof(id)::text as id_type, pg_typeof(batch_id)::text as batch_id_type, pg_typeof(current_station_id)::text as station_id_type, pg_typeof(current_carrier_id)::text as carrier_id_type FROM sub_batches LIMIT 1",
    'batches': "SELECT pg_typeof(id)::text as id_type, pg_typeof(current_station_code)::text as station_code_type FROM batches LIMIT 1",
    'wcc': "SELECT pg_typeof(id)::text as id_type, pg_typeof(wafer_id)::text as wafer_id_type, pg_typeof(carrier_id)::text as carrier_id_type FROM wafer_carrier_contents LIMIT 1",
    'carriers': "SELECT pg_typeof(id)::text as id_type FROM carriers LIMIT 1",
    'stations': "SELECT pg_typeof(id)::text as id_type, pg_typeof(code)::text as code_type FROM stations LIMIT 1",
}

for name, sql in queries.items():
    result = run_sql(sql)
    print(f'{name}: {json.dumps(result)}')

# Check wafer_type values
print('\nwafer_type distinct values:')
result = run_sql("SELECT DISTINCT wafer_type FROM wafer_carrier_contents ORDER BY wafer_type")
print(json.dumps(result))

# Check status values
print('\nbatches.status distinct:')
result = run_sql("SELECT DISTINCT status FROM batches ORDER BY status")
print(json.dumps(result))

print('\nsub_batches.status distinct:')
result = run_sql("SELECT DISTINCT status FROM sub_batches ORDER BY status")
print(json.dumps(result))
