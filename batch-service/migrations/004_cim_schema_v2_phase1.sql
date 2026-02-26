-- ============================================================
-- Migration 004: CIM Schema v2 — Phase 1
-- 向后兼容：仅增列 + 创建新表 + 数据回填，不删除任何现有列/表
-- ============================================================
-- 执行前请确保已备份数据库
-- 执行方式：通过 Supabase SQL Editor 或 psql 逐段执行
-- ============================================================

BEGIN;

-- ─────────────────────────────────────────────────────────────
-- 1. wafers 表：新增列（合并 wafer_carrier_contents 的字段）
-- ─────────────────────────────────────────────────────────────

-- lot_id: 冗余快捷字段，避免 sublot→lot 两跳查询
ALTER TABLE wafers ADD COLUMN IF NOT EXISTS lot_id uuid;

-- sublot_id: 当前归属子批次
ALTER TABLE wafers ADD COLUMN IF NOT EXISTS sublot_id uuid;

-- carrier_id: 当前所处片篮（从 wafer_carrier_contents 合并）
ALTER TABLE wafers ADD COLUMN IF NOT EXISTS carrier_id uuid;

-- slot_number: 片篮中的槽位编号
ALTER TABLE wafers ADD COLUMN IF NOT EXISTS slot_number integer;

-- wafer_type: GOOD / GOOD_SAMPLE / REJECT
ALTER TABLE wafers ADD COLUMN IF NOT EXISTS wafer_type text;

-- ingot_id: 原料晶棒编号
ALTER TABLE wafers ADD COLUMN IF NOT EXISTS ingot_id text;

-- work_order_id: 所属工单
ALTER TABLE wafers ADD COLUMN IF NOT EXISTS work_order_id uuid;

-- wafer_id: 业务唯一编号（目标字段名，暂与 wafer_id_code 共存）
ALTER TABLE wafers ADD COLUMN IF NOT EXISTS wafer_id text;

-- ─────────────────────────────────────────────────────────────
-- 2. sub_batches 表：新增列
-- ─────────────────────────────────────────────────────────────

-- lot_id: 与 batch_id 含义相同，为语义对齐准备
ALTER TABLE sub_batches ADD COLUMN IF NOT EXISTS lot_id uuid;

-- equipment_id: 当前加工机台
ALTER TABLE sub_batches ADD COLUMN IF NOT EXISTS equipment_id uuid;

-- next_station_id: 下一站点
ALTER TABLE sub_batches ADD COLUMN IF NOT EXISTS next_station_id uuid;

-- ─────────────────────────────────────────────────────────────
-- 3. batches 表：新增列
-- ─────────────────────────────────────────────────────────────

-- current_station_id: uuid FK 替代 current_station_code（text）
ALTER TABLE batches ADD COLUMN IF NOT EXISTS current_station_id uuid;

-- work_order_id: 关联工单
ALTER TABLE batches ADD COLUMN IF NOT EXISTS work_order_id uuid;

COMMIT;

-- ============================================================
-- Phase 1b: 约束（单独事务，避免 DDL 锁冲突）
-- ============================================================

BEGIN;

-- wafers 约束
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'chk_wafer_type_v2'
  ) THEN
    ALTER TABLE wafers ADD CONSTRAINT chk_wafer_type_v2
      CHECK (wafer_type IS NULL OR wafer_type IN ('GOOD', 'GOOD_SAMPLE', 'REJECT'));
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'chk_slot_range_v2'
  ) THEN
    ALTER TABLE wafers ADD CONSTRAINT chk_slot_range_v2
      CHECK (slot_number IS NULL OR (slot_number >= 1 AND slot_number <= 25));
  END IF;
END $$;

-- 同一片篮同一槽位唯一（部分唯一索引，NULL 不冲突）
CREATE UNIQUE INDEX IF NOT EXISTS idx_wafers_carrier_slot_v2
  ON wafers (carrier_id, slot_number) WHERE carrier_id IS NOT NULL AND slot_number IS NOT NULL;

-- wafers.wafer_id 唯一索引（回填后会有值）
CREATE UNIQUE INDEX IF NOT EXISTS idx_wafers_wafer_id_v2
  ON wafers (wafer_id) WHERE wafer_id IS NOT NULL;

-- wafers 新列的常用索引
CREATE INDEX IF NOT EXISTS idx_wafers_lot_id_v2 ON wafers (lot_id) WHERE lot_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_wafers_sublot_id_v2 ON wafers (sublot_id) WHERE sublot_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_wafers_carrier_id_v2 ON wafers (carrier_id) WHERE carrier_id IS NOT NULL;

-- sub_batches 索引
CREATE INDEX IF NOT EXISTS idx_sub_batches_lot_id_v2 ON sub_batches (lot_id) WHERE lot_id IS NOT NULL;

COMMIT;

-- ============================================================
-- Phase 1c: 创建 batch_events 统一事件表
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS batch_events (
  id            uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type    text          NOT NULL,
  target_type   text          NOT NULL,
  target_id     uuid          NOT NULL,
  lot_id        uuid,
  sublot_id     uuid,
  payload       jsonb,
  operator_id   uuid,
  station_id    uuid,
  equipment_id  uuid,
  operated_at   timestamptz   NOT NULL DEFAULT now(),
  created_at    timestamptz   NOT NULL DEFAULT now(),

  CONSTRAINT chk_target_type CHECK (target_type IN ('LOT', 'SUBLOT', 'WAFER'))
);

-- 事件表索引
CREATE INDEX IF NOT EXISTS idx_events_lot
  ON batch_events (lot_id, operated_at DESC);

CREATE INDEX IF NOT EXISTS idx_events_sublot
  ON batch_events (sublot_id, operated_at DESC);

CREATE INDEX IF NOT EXISTS idx_events_target
  ON batch_events (target_type, target_id, operated_at DESC);

CREATE INDEX IF NOT EXISTS idx_events_type_time
  ON batch_events (event_type, operated_at DESC);

CREATE INDEX IF NOT EXISTS idx_events_payload
  ON batch_events USING GIN (payload);

-- 禁止修改历史记录
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_rules WHERE rulename = 'no_update_events'
  ) THEN
    CREATE RULE no_update_events AS ON UPDATE TO batch_events DO INSTEAD NOTHING;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_rules WHERE rulename = 'no_delete_events'
  ) THEN
    CREATE RULE no_delete_events AS ON DELETE TO batch_events DO INSTEAD NOTHING;
  END IF;
END $$;

-- RLS: 基本读取权限
ALTER TABLE batch_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS "Allow service_role full access"
  ON batch_events FOR ALL
  USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "Allow read for authenticated"
  ON batch_events FOR SELECT
  USING (true);

-- 权限授予
GRANT ALL ON batch_events TO service_role;
GRANT SELECT ON batch_events TO authenticated;
GRANT SELECT ON batch_events TO anon;

COMMIT;

-- ============================================================
-- Phase 1d: 数据回填（在新列中填充对应的值）
-- ============================================================

BEGIN;

-- ① wafers ← wafer_carrier_contents（合并 carrier/slot/type/sublot）
UPDATE wafers w SET
  carrier_id  = wcc.carrier_id,
  slot_number = wcc.slot_number,
  wafer_type  = CASE
    WHEN wcc.wafer_type = 'GoodSample' THEN 'GOOD_SAMPLE'
    WHEN wcc.wafer_type = 'GOOD'       THEN 'GOOD'
    WHEN wcc.wafer_type = 'REJECT'     THEN 'REJECT'
    ELSE UPPER(REPLACE(wcc.wafer_type, 'Good', 'GOOD'))
  END,
  sublot_id   = wcc.sub_batch_id
FROM wafer_carrier_contents wcc
WHERE wcc.wafer_id = w.id;

-- ② wafers.lot_id ← wafers.batch_id（同一物理值，语义重命名准备）
UPDATE wafers SET lot_id = batch_id WHERE batch_id IS NOT NULL AND lot_id IS NULL;

-- ③ wafers.wafer_id ← wafers.wafer_id_code（字段重命名准备）
UPDATE wafers SET wafer_id = wafer_id_code WHERE wafer_id_code IS NOT NULL AND wafer_id IS NULL;

-- ④ sub_batches.lot_id ← sub_batches.batch_id
UPDATE sub_batches SET lot_id = batch_id WHERE batch_id IS NOT NULL AND lot_id IS NULL;

-- ⑤ batches.current_station_id ← stations.id（通过 code 查找）
UPDATE batches b SET current_station_id = s.id
FROM stations s
WHERE s.code = b.current_station_code
  AND b.current_station_id IS NULL;

COMMIT;

-- ============================================================
-- Phase 1e: 回填验证查询（不修改数据，仅检查）
-- ============================================================

-- 验证 1: wafers 新列填充率
SELECT
  COUNT(*) AS total_wafers,
  COUNT(lot_id) AS has_lot_id,
  COUNT(sublot_id) AS has_sublot_id,
  COUNT(carrier_id) AS has_carrier_id,
  COUNT(slot_number) AS has_slot_number,
  COUNT(wafer_type) AS has_wafer_type,
  COUNT(wafer_id) AS has_wafer_id
FROM wafers;

-- 验证 2: wafer_carrier_contents 与 wafers 新列数据一致性
SELECT COUNT(*) AS mismatched
FROM wafer_carrier_contents wcc
JOIN wafers w ON wcc.wafer_id = w.id
WHERE wcc.carrier_id != w.carrier_id
   OR wcc.slot_number != w.slot_number
   OR wcc.sub_batch_id != w.sublot_id;

-- 验证 3: sub_batches.lot_id 填充
SELECT COUNT(*) AS total, COUNT(lot_id) AS has_lot_id
FROM sub_batches;

-- 验证 4: batches.current_station_id 填充
SELECT COUNT(*) AS total, COUNT(current_station_id) AS has_station_id
FROM batches;

-- 验证 5: batch_events 表已创建
SELECT COUNT(*) AS events_count FROM batch_events;
