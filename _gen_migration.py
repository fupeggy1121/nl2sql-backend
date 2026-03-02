#!/usr/bin/env python3
"""One-shot script: generate migrations/create_class_synonyms.sql"""
import sys
sys.path.insert(0, '/Users/fupeggy/NL2SQL')

from app.config.ontology_synonyms import CLASS_SYNONYMS, RELATION_SYNONYMS

lines = []

lines.append("""\
-- ============================================================
-- Migration: class_synonyms (ontology-based synonym table)
-- Safe to run multiple times (IF NOT EXISTS + ON CONFLICT DO NOTHING)
-- Run in Supabase SQL Editor
-- ============================================================

-- 1. DDL -------------------------------------------------------
CREATE TABLE IF NOT EXISTS class_synonyms (
    id              BIGSERIAL PRIMARY KEY,
    target_uri      TEXT NOT NULL,           -- e.g. 'semi:Equipment'
    target_label_cn TEXT,                    -- e.g. '设备'
    target_type     TEXT DEFAULT 'class',    -- 'class' | 'relation'
    synonym         TEXT NOT NULL,           -- e.g. '机台'
    source          TEXT DEFAULT 'builtin',  -- 'builtin' | 'manual' | 'auto'
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    created_by      TEXT DEFAULT 'system',
    UNIQUE (target_uri, synonym)
);

CREATE INDEX IF NOT EXISTS idx_cs_synonym ON class_synonyms (synonym);
CREATE INDEX IF NOT EXISTS idx_cs_uri     ON class_synonyms (target_uri);
CREATE INDEX IF NOT EXISTS idx_cs_active  ON class_synonyms (is_active);

-- 2. Seed: canonical ontology synonyms from ontology_synonyms.py --------
INSERT INTO class_synonyms (target_uri, target_label_cn, target_type, synonym, source, created_by)
VALUES""")

rows = []
for uri, info in CLASS_SYNONYMS.items():
    for syn in info['synonyms']:
        s = syn.replace("'", "''")
        l = info['label_cn'].replace("'", "''")
        rows.append(f"  ('{uri}', '{l}', 'class', '{s}', 'builtin', 'system')")
for uri, info in RELATION_SYNONYMS.items():
    for syn in info['synonyms']:
        s = syn.replace("'", "''")
        l = info['label_cn'].replace("'", "''")
        rows.append(f"  ('{uri}', '{l}', 'relation', '{s}', 'builtin', 'system')")

lines.append(",\n".join(rows) + "\nON CONFLICT (target_uri, synonym) DO NOTHING;")

lines.append("""
-- 3. Migrate legacy table_synonyms → class_synonyms -------------------
--    Crosswalk maps Demo_Fab v1 physical table names → semi: URIs
INSERT INTO class_synonyms (target_uri, target_label_cn, target_type, synonym, source, created_by)
SELECT
    CASE ts.table_name
        WHEN 'wafers'                   THEN 'semi:Wafer'
        WHEN 'batches'                  THEN 'semi:ProductionLot'
        WHEN 'carriers'                 THEN 'semi:Carrier'
        WHEN 'equipment'                THEN 'semi:Equipment'
        WHEN 'process_steps'            THEN 'semi:ProcessStation'
        WHEN 'stations'                 THEN 'semi:ProcessStation'
        WHEN 'recipes'                  THEN 'semi:Recipe'
        WHEN 'sub_batches'              THEN 'semi:Sublot'
        WHEN 'production_orders'        THEN 'semi:ProductionOrder'
        WHEN 'products'                 THEN 'semi:Product'
        WHEN 'product_boms'             THEN 'semi:BOM'
        WHEN 'process_routes'           THEN 'semi:Route'
        WHEN 'batch_events'             THEN 'semi:Action'
        WHEN 'alarms'                   THEN 'semi:Action'
        WHEN 'defect_records'           THEN 'semi:Wafer'
        WHEN 'maintenance_records'      THEN 'semi:Equipment'
        WHEN 'production_records'       THEN 'semi:ProductionLot'
        WHEN 'quality_records'          THEN 'semi:Wafer'
        WHEN 'wafer_inspection_results' THEN 'semi:Wafer'
        ELSE NULL
    END                                                          AS target_uri,
    CASE ts.table_name
        WHEN 'wafers'                   THEN '晶圆'
        WHEN 'batches'                  THEN '批次'
        WHEN 'carriers'                 THEN '载具'
        WHEN 'equipment'                THEN '设备'
        WHEN 'process_steps'            THEN '工艺站点'
        WHEN 'stations'                 THEN '工艺站点'
        WHEN 'recipes'                  THEN '工艺配方'
        WHEN 'sub_batches'              THEN '子批次'
        WHEN 'production_orders'        THEN '生产工单'
        WHEN 'products'                 THEN '产品'
        WHEN 'product_boms'             THEN '物料清单'
        WHEN 'process_routes'           THEN '工艺路线'
        WHEN 'batch_events'             THEN '生产动作/事件'
        WHEN 'alarms'                   THEN '告警/动作'
        WHEN 'defect_records'           THEN '晶圆缺陷记录'
        WHEN 'maintenance_records'      THEN '设备维护记录'
        WHEN 'production_records'       THEN '生产记录'
        WHEN 'quality_records'          THEN '质量记录'
        WHEN 'wafer_inspection_results' THEN '晶圆检测结果'
        ELSE ts.table_name
    END                                                          AS target_label_cn,
    'class'                                                      AS target_type,
    ts.synonym                                                   AS synonym,
    COALESCE(ts.source, 'builtin')                               AS source,
    COALESCE(ts.created_by, 'migration')                         AS created_by
FROM table_synonyms ts
WHERE
    ts.synonym IS NOT NULL
    AND ts.synonym != ''
    AND (
        CASE ts.table_name
            WHEN 'wafers'                   THEN 'semi:Wafer'
            WHEN 'batches'                  THEN 'semi:ProductionLot'
            WHEN 'carriers'                 THEN 'semi:Carrier'
            WHEN 'equipment'                THEN 'semi:Equipment'
            WHEN 'process_steps'            THEN 'semi:ProcessStation'
            WHEN 'stations'                 THEN 'semi:ProcessStation'
            WHEN 'recipes'                  THEN 'semi:Recipe'
            WHEN 'sub_batches'              THEN 'semi:Sublot'
            WHEN 'production_orders'        THEN 'semi:ProductionOrder'
            WHEN 'products'                 THEN 'semi:Product'
            WHEN 'product_boms'             THEN 'semi:BOM'
            WHEN 'process_routes'           THEN 'semi:Route'
            WHEN 'batch_events'             THEN 'semi:Action'
            WHEN 'alarms'                   THEN 'semi:Action'
            WHEN 'defect_records'           THEN 'semi:Wafer'
            WHEN 'maintenance_records'      THEN 'semi:Equipment'
            WHEN 'production_records'       THEN 'semi:ProductionLot'
            WHEN 'quality_records'          THEN 'semi:Wafer'
            WHEN 'wafer_inspection_results' THEN 'semi:Wafer'
            ELSE NULL
        END
    ) IS NOT NULL
ON CONFLICT (target_uri, synonym) DO NOTHING;

-- 4. Verify result -------------------------------------------------
SELECT target_uri, target_label_cn, target_type, COUNT(*) AS cnt
FROM class_synonyms
GROUP BY target_uri, target_label_cn, target_type
ORDER BY target_type, target_uri;
""")

sql = "\n".join(lines)
out = '/Users/fupeggy/NL2SQL/migrations/create_class_synonyms.sql'
with open(out, 'w', encoding='utf-8') as f:
    f.write(sql)

total_values = sql.count("'semi:")
print(f"Written to {out}")
print(f"Lines: {sql.count(chr(10))}")
print(f"semi: URI references in VALUES: {total_values}")
