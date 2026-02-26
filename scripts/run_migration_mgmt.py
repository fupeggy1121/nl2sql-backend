#!/usr/bin/env python3
"""
Execute migration SQL via Supabase Management API.
The Management API allows executing arbitrary SQL including DDL.
Endpoint: POST https://api.supabase.com/v1/projects/{ref}/database/query
Auth: Bearer token from SUPABASE_ACCESS_TOKEN or supabase CLI login.
"""
import os, sys, json, requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

PROJECT_REF = 'kgmyhukvyygudsllypgv'
MGMT_API_URL = f'https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query'

# Try to get access token from env or supabase CLI
ACCESS_TOKEN = os.getenv('SUPABASE_ACCESS_TOKEN', '')
if not ACCESS_TOKEN:
    # Try reading from supabase CLI config
    config_path = Path.home() / '.config' / 'supabase' / 'access-token'
    if config_path.exists():
        ACCESS_TOKEN = config_path.read_text().strip()

if not ACCESS_TOKEN:
    print('ERROR: No SUPABASE_ACCESS_TOKEN found.')
    print('Please set it in .env or login via supabase CLI.')
    print('')
    print('To get a token:')
    print('1. Go to https://supabase.com/dashboard/account/tokens')
    print('2. Generate a new access token')
    print('3. Add to .env: SUPABASE_ACCESS_TOKEN=your_token_here')
    print('')
    print('Or manually execute the SQL in Supabase SQL Editor:')
    print(f'  https://supabase.com/dashboard/project/{PROJECT_REF}/sql/new')
    sys.exit(1)

headers = {
    'Authorization': f'Bearer {ACCESS_TOKEN}',
    'Content-Type': 'application/json'
}

# Read migration SQL
migration_path = Path(__file__).parent.parent / 'batch-service' / 'migrations' / '004_cim_schema_v2_phase1.sql'
full_sql = migration_path.read_text(encoding='utf-8')

# Split into BEGIN/COMMIT blocks
blocks = []
current_block = []
in_block = False
for line in full_sql.split('\n'):
    stripped = line.strip()
    if stripped == 'BEGIN;':
        in_block = True
        current_block = [line]
        continue
    elif stripped == 'COMMIT;':
        current_block.append(line)
        blocks.append('\n'.join(current_block))
        current_block = []
        in_block = False
        continue
    if in_block:
        current_block.append(line)

block_names = [
    'Phase 1a: ADD COLUMNS',
    'Phase 1b: CONSTRAINTS & INDEXES',
    'Phase 1c: CREATE batch_events TABLE',
    'Phase 1d: DATA BACKFILL',
]

def execute_sql(sql, label=''):
    """Execute SQL via Management API."""
    r = requests.post(MGMT_API_URL, headers=headers, json={'query': sql})
    if r.status_code == 200 or r.status_code == 201:
        return True, r.json() if r.text else None
    else:
        return False, f'{r.status_code}: {r.text[:500]}'

# Execute each block
for i, (block, name) in enumerate(zip(blocks, block_names)):
    print(f'\n{"="*60}')
    print(f'Block {i+1}/{len(blocks)}: {name}')
    print(f'{"="*60}')
    ok, result = execute_sql(block, name)
    if ok:
        print(f'  OK')
    else:
        print(f'  FAILED: {result}')
        if 'already exists' in str(result).lower():
            print('  (Non-critical, continuing...)')
        else:
            yn = input('  Continue anyway? (y/n): ').strip().lower()
            if yn != 'y':
                sys.exit(1)

# Validations
print(f'\n{"="*60}')
print('VALIDATION')
print(f'{"="*60}')
validations = [
    ("wafers fill rate", "SELECT COUNT(*) AS total, COUNT(lot_id) AS lot, COUNT(sublot_id) AS sublot, COUNT(carrier_id) AS carrier, COUNT(wafer_type) AS wtype, COUNT(wafer_id) AS wid FROM wafers"),
    ("data consistency", "SELECT COUNT(*) AS mismatched FROM wafer_carrier_contents wcc JOIN wafers w ON wcc.wafer_id = w.id WHERE wcc.carrier_id != w.carrier_id OR wcc.slot_number != w.slot_number OR wcc.sub_batch_id != w.sublot_id"),
    ("sub_batches.lot_id", "SELECT COUNT(*) AS total, COUNT(lot_id) AS filled FROM sub_batches"),
    ("batches.station_id", "SELECT COUNT(*) AS total, COUNT(current_station_id) AS filled FROM batches"),
    ("batch_events created", "SELECT COUNT(*) AS cnt FROM batch_events"),
]

for name, sql in validations:
    ok, result = execute_sql(sql, name)
    if ok:
        print(f'  {name}: {json.dumps(result)}')
    else:
        print(f'  {name}: ERROR - {result}')

print('\nMigration Phase 1 complete!')
