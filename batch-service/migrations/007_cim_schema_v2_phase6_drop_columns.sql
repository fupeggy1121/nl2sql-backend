-- ============================================================
-- Phase 6: CIM Schema v2 — DROP 废弃列 + 修复 RPC
--
-- 目标:
--   1. 修复 RPC 中 triggered_by → operator_id (匹配 batch_events 实际列名)
--   2. 修复 RPC 中 is_hold → status = '暂停'
--   3. 修复 RPC 中移除对 current_station_code 的回退依赖
--   4. DROP 5 个废弃列: current_station_code, current_station_name,
--      next_station_code, next_station_name, is_hold
--
-- 逐块执行，每块独立安全
-- ============================================================


-- ═══════════════════════════════════════════════════════════════
-- Block 1: 重写 4 个 RPC 函数
--   修复: triggered_by → operator_id
--   修复: is_hold → status = '暂停'
--   修复: 移除 current_station_code 回退逻辑
--   修复: 不再写入 current_station_code/name, next_station_code/name
--   修复: target_type 使用 'LOT' 以匹配 CHECK 约束
-- ═══════════════════════════════════════════════════════════════

-- 1a: outstation
CREATE OR REPLACE FUNCTION batch_confirm_outstation(
  p_batch_id        text,
  p_wafer_results   jsonb,
  p_sub_batches     jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_batch           record;
  v_next_station    record;
  v_from_station    record;
  v_good_total      integer;
  v_defect_total    integer;
  v_sub             jsonb;
  v_sub_id          text;
  v_sublot_id       text;
  v_sub_good        integer;
  v_sub_defect      integer;
  v_next_station_id uuid;
  v_result          jsonb;
BEGIN
  SELECT * INTO v_batch FROM batches WHERE id = p_batch_id::uuid FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Batch not found: %', p_batch_id;
  END IF;

  -- 获取当前站点（仅通过 current_station_id）
  IF v_batch.current_station_id IS NOT NULL THEN
    SELECT * INTO v_from_station FROM stations WHERE id = v_batch.current_station_id;
  ELSE
    RAISE EXCEPTION 'Batch % has no current_station_id', p_batch_id;
  END IF;

  -- 计算下一站点
  v_next_station_id := NULL;
  IF v_from_station.id IS NOT NULL THEN
    SELECT st.id, st.code, st.name INTO v_next_station
    FROM process_route_stations prs
    JOIN stations st ON st.id = prs.station_id
    WHERE prs.route_id IN (
      SELECT prs2.route_id FROM process_route_stations prs2 WHERE prs2.station_id = v_from_station.id LIMIT 1
    )
    AND prs.sequence > (
      SELECT prs3.sequence FROM process_route_stations prs3
      WHERE prs3.station_id = v_from_station.id
      AND prs3.route_id IN (SELECT prs4.route_id FROM process_route_stations prs4 WHERE prs4.station_id = v_from_station.id LIMIT 1)
      LIMIT 1
    )
    ORDER BY prs.sequence LIMIT 1;

    IF v_next_station.id IS NOT NULL THEN
      v_next_station_id := v_next_station.id;
    ELSE
      RAISE EXCEPTION 'Next station not found for batch % at station %', p_batch_id, v_from_station.code;
    END IF;
  END IF;

  -- 统计良品/不良品
  SELECT
    COUNT(*) FILTER (WHERE w->>'type' IN ('GOOD', 'GoodSample', 'GOOD_SAMPLE')),
    COUNT(*) FILTER (WHERE w->>'type' = 'REJECT')
  INTO v_good_total, v_defect_total
  FROM jsonb_array_elements(p_wafer_results) AS w;

  -- 更新主批次（不再写 current_station_code/name, next_station_code/name）
  UPDATE batches SET
    status = '待进站',
    current_station_id = v_next_station_id,
    good_qty = v_good_total, defect_qty = v_defect_total,
    equipment_code = NULL, equipment_name = NULL, equipment_chamber = NULL,
    updated_at = now()
  WHERE id = p_batch_id::uuid;

  -- 更新子批次
  FOR v_sub IN SELECT * FROM jsonb_array_elements(p_sub_batches) LOOP
    v_sub_id := v_sub->>'id';
    v_sublot_id := v_sub->>'sublot_id';

    SELECT
      COUNT(*) FILTER (WHERE w->>'type' IN ('GOOD', 'GoodSample', 'GOOD_SAMPLE')),
      COUNT(*) FILTER (WHERE w->>'type' = 'REJECT')
    INTO v_sub_good, v_sub_defect
    FROM jsonb_array_elements(p_wafer_results) AS w
    WHERE w->>'sublot_id' = v_sublot_id;

    UPDATE sub_batches SET
      status = '待进站', good_qty = v_sub_good, defect_qty = v_sub_defect,
      next_station_id = NULL, updated_at = now()
    WHERE id = v_sub_id::uuid;
  END LOOP;

  -- 更新 wafers.wafer_type
  UPDATE wafers SET
    wafer_type = CASE
      WHEN wr->>'type' = 'REJECT' THEN 'REJECT'
      WHEN wr->>'type' = 'GoodSample' THEN 'GOOD_SAMPLE'
      ELSE 'GOOD'
    END,
    updated_at = now()
  FROM (SELECT * FROM jsonb_array_elements(p_wafer_results) AS wr) AS sub(wr)
  WHERE wafers.id = (sub.wr->>'wafer_id')::uuid;

  -- 写入 batch_events（使用正确的列名 operator_id）
  INSERT INTO batch_events (event_type, target_type, target_id, lot_id, station_id, payload, operator_id)
  VALUES (
    'outstation', 'LOT', p_batch_id::uuid, p_batch_id::uuid, v_from_station.id,
    jsonb_build_object(
      'batch_code', v_batch.batch_code,
      'from_station', v_from_station.code,
      'from_station_name', v_from_station.name,
      'to_station', v_next_station.code,
      'to_station_name', v_next_station.name,
      'good_qty_before', v_batch.good_qty, 'defect_qty_before', v_batch.defect_qty,
      'good_qty_after', v_good_total, 'defect_qty_after', v_defect_total,
      'wafer_count', jsonb_array_length(p_wafer_results)
    ),
    NULL
  );

  SELECT row_to_json(b) INTO v_result FROM batches b WHERE b.id = p_batch_id::uuid;
  RETURN v_result;
END;
$$;


-- 1b: instation
CREATE OR REPLACE FUNCTION batch_confirm_instation(
  p_batch_id          text,
  p_sub_batch_ids     text[],
  p_equipment_code    text DEFAULT NULL,
  p_equipment_name    text DEFAULT NULL,
  p_equipment_chamber text DEFAULT NULL,
  p_operator          text DEFAULT 'system'
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_batch           record;
  v_station         record;
  v_next_station    record;
  v_route_station   record;
  v_equipment_id    uuid;
  v_result          jsonb;
BEGIN
  SELECT * INTO v_batch FROM batches WHERE id = p_batch_id::uuid FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Batch not found: %', p_batch_id; END IF;
  IF v_batch.status <> '待进站' THEN RAISE EXCEPTION 'Batch status must be 待进站, got: %', v_batch.status; END IF;
  IF v_batch.status = '暂停' THEN RAISE EXCEPTION 'Batch is on HOLD, cannot proceed with instation'; END IF;

  -- 获取站点（仅通过 current_station_id）
  IF v_batch.current_station_id IS NOT NULL THEN
    SELECT * INTO v_station FROM stations WHERE id = v_batch.current_station_id;
  ELSE
    RAISE EXCEPTION 'Batch % has no current_station_id', p_batch_id;
  END IF;

  -- 查设备 ID
  IF p_equipment_code IS NOT NULL THEN
    SELECT id INTO v_equipment_id FROM equipment WHERE code = p_equipment_code LIMIT 1;
  END IF;

  -- 计算下一站点
  v_next_station := NULL;
  IF v_station.id IS NOT NULL THEN
    SELECT prs.* INTO v_route_station FROM process_route_stations prs
    WHERE prs.station_id = v_station.id ORDER BY prs.sequence LIMIT 1;

    IF v_route_station IS NOT NULL THEN
      SELECT prs.*, st.code AS st_code, st.name AS st_name, st.id AS st_id
      INTO v_next_station FROM process_route_stations prs
      JOIN stations st ON st.id = prs.station_id
      WHERE prs.route_id = v_route_station.route_id AND prs.sequence > v_route_station.sequence
      ORDER BY prs.sequence LIMIT 1;
    END IF;
  END IF;

  -- 更新主批次（不再写 current_station_name, next_station_code/name）
  UPDATE batches SET
    status = '加工中',
    equipment_code = COALESCE(p_equipment_code, equipment_code),
    equipment_name = COALESCE(p_equipment_name, equipment_name),
    equipment_chamber = COALESCE(p_equipment_chamber, equipment_chamber),
    current_station_id = COALESCE(v_station.id, current_station_id),
    updated_at = now()
  WHERE id = p_batch_id::uuid;

  -- 更新子批次
  UPDATE sub_batches SET
    status = '加工中', equipment_id = v_equipment_id,
    next_station_id = v_next_station.st_id, updated_at = now()
  WHERE id = ANY(p_sub_batch_ids::uuid[]);

  -- 写入 batch_events
  INSERT INTO batch_events (event_type, target_type, target_id, lot_id, station_id, equipment_id, payload, operator_id)
  VALUES (
    'instation', 'LOT', p_batch_id::uuid, p_batch_id::uuid, v_station.id, v_equipment_id,
    jsonb_build_object(
      'batch_code', v_batch.batch_code,
      'station_code', v_station.code,
      'station_name', COALESCE(v_station.name, ''),
      'equipment_code', p_equipment_code, 'equipment_name', p_equipment_name,
      'equipment_chamber', p_equipment_chamber,
      'next_station_code', v_next_station.st_code, 'next_station_name', v_next_station.st_name,
      'sub_batch_count', array_length(p_sub_batch_ids, 1)
    ),
    NULL
  );

  SELECT row_to_json(b) INTO v_result FROM batches b WHERE b.id = p_batch_id::uuid;
  RETURN v_result;
END;
$$;


-- 1c: split
CREATE OR REPLACE FUNCTION batch_confirm_split(
  p_batch_id      text,
  p_split_config  jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_batch       record;
  v_new_sub     jsonb;
  v_code        text;
  v_carrier_id  text;
  v_wafer_ids   jsonb;
  v_wafer_count integer;
  v_new_sub_id  uuid;
  v_station_id  uuid;
  v_created_ids text[] := '{}';
  v_result      jsonb;
BEGIN
  SELECT * INTO v_batch FROM batches WHERE id = p_batch_id::uuid FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Batch not found: %', p_batch_id; END IF;
  IF v_batch.status = '暂停' THEN RAISE EXCEPTION 'Batch is on HOLD, cannot split'; END IF;

  IF v_batch.current_station_id IS NOT NULL THEN
    v_station_id := v_batch.current_station_id;
  ELSE
    RAISE EXCEPTION 'Batch % has no current_station_id', p_batch_id;
  END IF;

  FOR v_new_sub IN SELECT * FROM jsonb_array_elements(p_split_config->'new_sub_batches') LOOP
    v_code       := v_new_sub->>'sub_batch_code';
    v_carrier_id := v_new_sub->>'carrier_id';
    v_wafer_ids  := v_new_sub->'wafer_ids';
    v_wafer_count := jsonb_array_length(v_wafer_ids);
    v_new_sub_id := gen_random_uuid();

    INSERT INTO sub_batches (
      id, batch_id, sub_batch_code, current_carrier_id, current_station_id,
      lot_id, total_qty, good_qty, defect_qty, status, created_at, updated_at
    ) VALUES (
      v_new_sub_id, p_batch_id::uuid, v_code, v_carrier_id::uuid, v_station_id,
      p_batch_id::uuid, v_wafer_count, v_wafer_count, 0, v_batch.status, now(), now()
    );

    UPDATE wafers SET sublot_id = v_new_sub_id, carrier_id = v_carrier_id::uuid, updated_at = now()
    WHERE wafer_id_code IN (SELECT jsonb_array_elements_text(v_wafer_ids));

    v_created_ids := array_append(v_created_ids, v_new_sub_id::text);
  END LOOP;

  -- 写入 batch_events
  INSERT INTO batch_events (event_type, target_type, target_id, lot_id, station_id, payload, operator_id)
  VALUES (
    'split', 'LOT', p_batch_id::uuid, p_batch_id::uuid, v_station_id,
    jsonb_build_object(
      'batch_code', v_batch.batch_code,
      'station_code', (SELECT code FROM stations WHERE id = v_station_id),
      'new_sub_batch_ids', to_jsonb(v_created_ids),
      'split_config', p_split_config
    ),
    NULL
  );

  SELECT jsonb_build_object('batch', row_to_json(b), 'new_sub_batch_ids', to_jsonb(v_created_ids))
  INTO v_result FROM batches b WHERE b.id = p_batch_id::uuid;
  RETURN v_result;
END;
$$;


-- 1d: merge
CREATE OR REPLACE FUNCTION batch_confirm_merge(
  p_target_batch_id       text,
  p_source_sub_batch_ids  text[]
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_target_batch  record;
  v_station_check record;
  v_total_good    integer := 0;
  v_total_defect  integer := 0;
  v_total_qty     integer := 0;
  v_merged_count  integer;
  v_result        jsonb;
BEGIN
  SELECT * INTO v_target_batch FROM batches WHERE id = p_target_batch_id::uuid FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Target batch not found: %', p_target_batch_id; END IF;

  SELECT COUNT(DISTINCT current_station_id) AS station_count INTO v_station_check
  FROM sub_batches WHERE id = ANY(p_source_sub_batch_ids::uuid[]);
  IF v_station_check.station_count > 1 THEN
    RAISE EXCEPTION 'All source sub-batches must be at the same station for merge';
  END IF;

  UPDATE sub_batches SET batch_id = p_target_batch_id::uuid, lot_id = p_target_batch_id::uuid, updated_at = now()
  WHERE id = ANY(p_source_sub_batch_ids::uuid[]);
  GET DIAGNOSTICS v_merged_count = ROW_COUNT;

  UPDATE wafers SET lot_id = p_target_batch_id::uuid, batch_id = p_target_batch_id::uuid, updated_at = now()
  WHERE sublot_id = ANY(p_source_sub_batch_ids::uuid[]);

  SELECT COALESCE(SUM(total_qty), 0), COALESCE(SUM(good_qty), 0), COALESCE(SUM(defect_qty), 0)
  INTO v_total_qty, v_total_good, v_total_defect
  FROM sub_batches WHERE batch_id = p_target_batch_id::uuid;

  UPDATE batches SET total_qty = v_total_qty, good_qty = v_total_good, defect_qty = v_total_defect, updated_at = now()
  WHERE id = p_target_batch_id::uuid;

  -- 写入 batch_events
  INSERT INTO batch_events (event_type, target_type, target_id, lot_id, payload, operator_id)
  VALUES (
    'merge', 'LOT', p_target_batch_id::uuid, p_target_batch_id::uuid,
    jsonb_build_object(
      'batch_code', v_target_batch.batch_code,
      'source_sub_batch_ids', to_jsonb(p_source_sub_batch_ids),
      'merged_count', v_merged_count,
      'good_qty_before', v_target_batch.good_qty, 'defect_qty_before', v_target_batch.defect_qty,
      'good_qty_after', v_total_good, 'defect_qty_after', v_total_defect
    ),
    NULL
  );

  SELECT row_to_json(b) INTO v_result FROM batches b WHERE b.id = p_target_batch_id::uuid;
  RETURN v_result;
END;
$$;

-- 验证 Block 1:
SELECT proname, pg_get_function_arguments(oid) AS args
FROM pg_proc
WHERE proname IN ('batch_confirm_outstation', 'batch_confirm_instation', 'batch_confirm_split', 'batch_confirm_merge')
ORDER BY proname;
-- 预期: 4 行


-- ═══════════════════════════════════════════════════════════════
-- Block 2: DROP 废弃列
-- 前置条件: Block 1 已执行（RPC 不再引用这些列）
-- ═══════════════════════════════════════════════════════════════

ALTER TABLE batches DROP COLUMN IF EXISTS current_station_code;
ALTER TABLE batches DROP COLUMN IF EXISTS current_station_name;
ALTER TABLE batches DROP COLUMN IF EXISTS next_station_code;
ALTER TABLE batches DROP COLUMN IF EXISTS next_station_name;
ALTER TABLE batches DROP COLUMN IF EXISTS is_hold;

-- 验证 Block 2:
SELECT column_name FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'batches'
  AND column_name IN ('current_station_code', 'current_station_name', 'next_station_code', 'next_station_name', 'is_hold');
-- 预期: 0 行（所有列已删除）


-- ═══════════════════════════════════════════════════════════════
-- Block 3: 最终验证
-- ═══════════════════════════════════════════════════════════════

-- 3a: 确认列已删除
SELECT column_name FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'batches'
ORDER BY ordinal_position;

-- 3b: 确认 4 个 RPC 正常
SELECT proname FROM pg_proc
WHERE proname LIKE 'batch_confirm_%' ORDER BY proname;

-- 3c: 测试 batch_events 写入（应使用 operator_id 列）
INSERT INTO batch_events (event_type, target_type, target_id, payload, operator_id)
VALUES ('test_phase6', 'LOT', gen_random_uuid(), '{"test": true}'::jsonb, NULL);

-- 确认写入成功
SELECT id, event_type, operator_id FROM batch_events
WHERE event_type = 'test_phase6' ORDER BY created_at DESC LIMIT 1;

-- 清理测试数据
DELETE FROM batch_events WHERE event_type = 'test_phase6';
