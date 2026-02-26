#!/usr/bin/env python3
"""
Execute CIM Schema v2 Phase 1 migration via Supabase REST API.
Since execute_sql RPC only allows SELECT, we use supabase-py's admin client
to run DDL via the Management API, or guide the user to Supabase SQL Editor.

This script executes each phase as a separate SQL block via psycopg2.
If psycopg2 connection fails (e.g., DNS), it prints instructions for
manual execution in Supabase SQL Editor.
"""
import os, sys, json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# Read the migration SQL
migration_path = Path(__file__).parent.parent / 'batch-service' / 'migrations' / '004_cim_schema_v2_phase1.sql'
full_sql = migration_path.read_text(encoding='utf-8')

# Split into executable blocks (between the section markers)
# We'll extract the SQL between BEGIN/COMMIT pairs
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

# Extract validation queries (after the last COMMIT)
validation_start = full_sql.rfind('-- Phase 1e:')
validation_sql = full_sql[validation_start:] if validation_start > 0 else ''

block_names = [
    'Phase 1a: 新增列 (wafers/sub_batches/batches)',
    'Phase 1b: 约束与索引',
    'Phase 1c: 创建 batch_events 表',
    'Phase 1d: 数据回填',
]

def try_psycopg2():
    """Try to connect and execute via psycopg2."""
    try:
        import psycopg2
    except ImportError:
        print('psycopg2 not installed, skipping direct connection')
        return False

    host = os.getenv('SUPABASE_DB_HOST')
    port = os.getenv('SUPABASE_DB_PORT', '5432')
    dbname = os.getenv('SUPABASE_DB_NAME', 'postgres')
    user = os.getenv('SUPABASE_DB_USER', 'postgres')
    password = os.getenv('SUPABASE_DB_PASSWORD')

    if not all([host, password]):
        print('Missing SUPABASE_DB_* env vars')
        return False

    try:
        conn = psycopg2.connect(
            host=host, port=port, dbname=dbname,
            user=user, password=password,
            connect_timeout=10
        )
        conn.autocommit = False
        print(f'Connected to {host}:{port}/{dbname}')
    except Exception as e:
        print(f'Connection failed: {e}')
        return False

    cur = conn.cursor()

    for i, (block, name) in enumerate(zip(blocks, block_names)):
        print(f'\n{"="*60}')
        print(f'Executing: {name}')
        print(f'{"="*60}')
        try:
            # Remove BEGIN/COMMIT since we manage transactions ourselves
            sql = block.replace('BEGIN;', '').replace('COMMIT;', '').strip()
            cur.execute(sql)
            conn.commit()
            print(f'  OK: {name}')
        except Exception as e:
            conn.rollback()
            print(f'  FAILED: {e}')
            # If it's a "column already exists" type error, continue
            if 'already exists' in str(e).lower():
                print('  (Non-critical, continuing...)')
                continue
            else:
                print('  Aborting remaining blocks.')
                conn.close()
                return True  # Connected but had error

    # Run validation queries
    print(f'\n{"="*60}')
    print('Phase 1e: 验证')
    print(f'{"="*60}')

    validations = [
        ("wafers 新列填充率", """
            SELECT COUNT(*) AS total_wafers,
                   COUNT(lot_id) AS has_lot_id,
                   COUNT(sublot_id) AS has_sublot_id,
                   COUNT(carrier_id) AS has_carrier_id,
                   COUNT(slot_number) AS has_slot_number,
                   COUNT(wafer_type) AS has_wafer_type,
                   COUNT(wafer_id) AS has_wafer_id
            FROM wafers
        """),
        ("数据一致性检查", """
            SELECT COUNT(*) AS mismatched
            FROM wafer_carrier_contents wcc
            JOIN wafers w ON wcc.wafer_id = w.id
            WHERE wcc.carrier_id != w.carrier_id
               OR wcc.slot_number != w.slot_number
               OR wcc.sub_batch_id != w.sublot_id
        """),
        ("sub_batches.lot_id 填充", """
            SELECT COUNT(*) AS total, COUNT(lot_id) AS has_lot_id FROM sub_batches
        """),
        ("batches.current_station_id 填充", """
            SELECT COUNT(*) AS total, COUNT(current_station_id) AS has_station_id FROM batches
        """),
        ("batch_events 表已创建", """
            SELECT COUNT(*) AS events_count FROM batch_events
        """),
    ]

    all_ok = True
    for name, sql in validations:
        try:
            cur.execute(sql.strip())
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
            result = dict(zip(cols, rows[0])) if rows else {}
            print(f'  {name}: {json.dumps(result)}')

            # Check specific validations
            if name == "数据一致性检查" and result.get('mismatched', -1) != 0:
                print(f'    WARNING: {result["mismatched"]} mismatched rows!')
                all_ok = False
            elif name == "wafers 新列填充率":
                total = result.get('total_wafers', 0)
                for k, v in result.items():
                    if k != 'total_wafers' and v < total:
                        print(f'    WARNING: {k} only filled {v}/{total}')
        except Exception as e:
            print(f'  {name}: ERROR - {e}')
            conn.rollback()

    conn.close()

    if all_ok:
        print('\n ALL VALIDATIONS PASSED')
    else:
        print('\n SOME VALIDATIONS HAD WARNINGS — please review')

    return True


def print_manual_instructions():
    """Print instructions for manual execution in Supabase SQL Editor."""
    print('\n' + '='*60)
    print('无法直接连接数据库，请在 Supabase SQL Editor 中手动执行')
    print('='*60)
    print(f'\n打开: https://supabase.com/dashboard/project/kgmyhukvyygudsllypgv/sql/new')
    print(f'\n将以下文件内容粘贴到 SQL Editor 并执行:')
    print(f'  {migration_path}')
    print(f'\n或分段执行以下 {len(blocks)} 个 SQL 块:')
    for i, name in enumerate(block_names):
        print(f'  Block {i+1}: {name}')
    print('\n然后运行验证查询（Phase 1e 部分）确认数据正确。')


if __name__ == '__main__':
    print('CIM Schema v2 — Phase 1 Migration')
    print(f'Migration file: {migration_path}')
    print(f'SQL blocks to execute: {len(blocks)}')

    if not try_psycopg2():
        print_manual_instructions()
