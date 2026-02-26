-- ============================================================
-- Phase 5: CIM Schema v2 — 安全清理废弃表
-- 
-- 逐块执行，每块独立安全，执行后验证再继续下一块
-- 不 DROP 任何列（current_station_code/name, next_station_code/name,
-- is_hold 仍被前端/API 使用）
-- ============================================================


-- ═══════════════════════════════════════════════════════════════
-- Block 1: 移除 split RPC 中对 wafer_carrier_contents 的双写
-- 影响: 停止向 wafer_carrier_contents 写入新数据
-- 风险: 无 — 所有读取已切换到 wafers 表
-- ═══════════════════════════════════════════════════════════════

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
  -- 1. 读取并锁定批次
  SELECT * INTO v_batch FROM batches WHERE id = p_batch_id::uuid FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Batch not found: %', p_batch_id;
  END IF;

  IF v_batch.is_hold = true THEN
    RAISE EXCEPTION 'Batch is on HOLD, cannot split';
  END IF;

  -- 获取站点ID
  IF v_batch.current_station_id IS NOT NULL THEN
    v_station_id := v_batch.current_station_id;
  ELSE
    SELECT s.id INTO v_station_id
    FROM stations s WHERE s.code = v_batch.current_station_code LIMIT 1;
  END IF;

  -- 2. 遍历创建新子批次
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

    -- 只更新 wafers 表（不再双写 wafer_carrier_contents）
    UPDATE wafers SET
      sublot_id  = v_new_sub_id,
      carrier_id = v_carrier_id::uuid,
      updated_at = now()
    WHERE wafer_id_code IN (SELECT jsonb_array_elements_text(v_wafer_ids));

    v_created_ids := array_append(v_created_ids, v_new_sub_id::text);
  END LOOP;

  -- 3. 双写事件日志
  INSERT INTO batch_events (event_type, target_type, target_id, payload, triggered_by)
  VALUES (
    'split', 'batch', p_batch_id::uuid,
    jsonb_build_object(
      'batch_code', v_batch.batch_code,
      'station_code', COALESCE((SELECT code FROM stations WHERE id = v_station_id), v_batch.current_station_code),
      'new_sub_batch_ids', to_jsonb(v_created_ids),
      'split_config', p_split_config
    ),
    'system'
  );

  INSERT INTO batch_operation_logs (
    batch_id, batch_code, operation_type, from_station, operator_id, remarks,
    good_qty_before, defect_qty_before, details
  ) VALUES (
    p_batch_id, v_batch.batch_code, 'split',
    COALESCE((SELECT code FROM stations WHERE id = v_station_id), v_batch.current_station_code),
    'system',
    format('批次%s拆批，新增%s个子批次', v_batch.batch_code, array_length(v_created_ids, 1)),
    v_batch.good_qty, v_batch.defect_qty,
    jsonb_build_object('new_sub_batch_ids', to_jsonb(v_created_ids), 'split_config', p_split_config)
  );

  -- 4. 返回结果
  SELECT jsonb_build_object(
    'batch', row_to_json(b),
    'new_sub_batch_ids', to_jsonb(v_created_ids)
  ) INTO v_result FROM batches b WHERE b.id = p_batch_id::uuid;

  RETURN v_result;
END;
$$;

-- 验证 Block 1:
SELECT proname, pg_get_function_arguments(oid) AS args
FROM pg_proc WHERE proname = 'batch_confirm_split';


-- ═══════════════════════════════════════════════════════════════
-- Block 2: DROP wafer_carrier_contents 表
-- 前置条件: Block 1 已执行 (split RPC 不再写入此表)
-- 影响: 删除废弃表
-- 风险: 无 — 所有读写已切换到 wafers 表
-- ═══════════════════════════════════════════════════════════════

DROP TABLE IF EXISTS wafer_carrier_contents;

-- 验证 Block 2:
SELECT EXISTS (
  SELECT 1 FROM information_schema.tables
  WHERE table_schema = 'public' AND table_name = 'wafer_carrier_contents'
) AS table_still_exists;
-- 预期: false


-- ═══════════════════════════════════════════════════════════════
-- Block 3: 迁移历史 batch_operation_logs → batch_events
-- 将旧日志数据复制到 batch_events，保留原始时间戳
-- ═══════════════════════════════════════════════════════════════

INSERT INTO batch_events (event_type, target_type, target_id, payload, triggered_by, created_at)
SELECT
  bol.operation_type,
  'batch',
  bol.batch_id::uuid,
  jsonb_build_object(
    'batch_code', bol.batch_code,
    'from_station', bol.from_station,
    'to_station', bol.to_station,
    'remarks', bol.remarks,
    'good_qty_before', bol.good_qty_before,
    'defect_qty_before', bol.defect_qty_before,
    'good_qty_after', bol.good_qty_after,
    'defect_qty_after', bol.defect_qty_after,
    'details', bol.details,
    'migrated_from', 'batch_operation_logs',
    'original_id', bol.id
  ),
  COALESCE(bol.operator_id, 'system'),
  bol.created_at
FROM batch_operation_logs bol
WHERE NOT EXISTS (
  -- 避免重复导入：跳过已由 Phase 4 双写产生的记录
  SELECT 1 FROM batch_events be
  WHERE be.target_id = bol.batch_id::uuid
    AND be.event_type = bol.operation_type
    AND be.created_at = bol.created_at
);

-- 验证 Block 3:
SELECT
  (SELECT COUNT(*) FROM batch_operation_logs) AS old_log_count,
  (SELECT COUNT(*) FROM batch_events) AS new_event_count,
  (SELECT COUNT(*) FROM batch_events WHERE payload->>'migrated_from' = 'batch_operation_logs') AS migrated_count;


-- ═══════════════════════════════════════════════════════════════
-- Block 4: 移除所有 RPC 中对 batch_operation_logs 的双写
-- 前置条件: Block 3 已执行 (历史数据已迁移)
-- 影响: 4 个 RPC 函数只写 batch_events
-- ═══════════════════════════════════════════════════════════════

-- 4a: outstation — 移除 batch_operation_logs 写入
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

  -- 获取当前站点
  IF v_batch.current_station_id IS NOT NULL THEN
    SELECT * INTO v_from_station FROM stations WHERE id = v_batch.current_station_id;
  ELSE
    SELECT * INTO v_from_station FROM stations WHERE code = v_batch.current_station_code LIMIT 1;
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
  ELSE
    IF v_batch.next_station_code IS NULL OR v_batch.next_station_code = '' THEN
      RAISE EXCEPTION 'Next station is not defined for batch %', p_batch_id;
    END IF;
  END IF;

  -- 统计良品/不良品
  SELECT
    COUNT(*) FILTER (WHERE w->>'type' IN ('GOOD', 'GoodSample', 'GOOD_SAMPLE')),
    COUNT(*) FILTER (WHERE w->>'type' = 'REJECT')
  INTO v_good_total, v_defect_total
  FROM jsonb_array_elements(p_wafer_results) AS w;

  -- 更新主批次
  UPDATE batches SET
    status = '待进站',
    current_station_code = COALESCE(v_next_station.code, v_batch.next_station_code),
    current_station_name = COALESCE(v_next_station.name, v_batch.next_station_name),
    current_station_id   = v_next_station_id,
    good_qty = v_good_total, defect_qty = v_defect_total,
    equipment_code = NULL, equipment_name = NULL, equipment_chamber = NULL,
    next_station_code = NULL, next_station_name = NULL,
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

  -- 只写 batch_events（不再写 batch_operation_logs）
  INSERT INTO batch_events (event_type, target_type, target_id, payload, triggered_by)
  VALUES (
    'outstation', 'batch', p_batch_id::uuid,
    jsonb_build_object(
      'batch_code', v_batch.batch_code,
      'from_station', COALESCE(v_from_station.code, v_batch.current_station_code),
      'from_station_name', COALESCE(v_from_station.name, v_batch.current_station_name),
      'to_station', COALESCE(v_next_station.code, v_batch.next_station_code),
      'to_station_name', COALESCE(v_next_station.name, v_batch.next_station_name),
      'good_qty_before', v_batch.good_qty, 'defect_qty_before', v_batch.defect_qty,
      'good_qty_after', v_good_total, 'defect_qty_after', v_defect_total,
      'wafer_count', jsonb_array_length(p_wafer_results)
    ),
    'system'
  );

  SELECT row_to_json(b) INTO v_result FROM batches b WHERE b.id = p_batch_id::uuid;
  RETURN v_result;
END;
$$;


-- 4b: instation — 移除 batch_operation_logs 写入
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
  IF v_batch.is_hold = true THEN RAISE EXCEPTION 'Batch is on HOLD, cannot proceed with instation'; END IF;

  -- 获取站点
  IF v_batch.current_station_id IS NOT NULL THEN
    SELECT * INTO v_station FROM stations WHERE id = v_batch.current_station_id;
  ELSE
    SELECT * INTO v_station FROM stations WHERE code = v_batch.current_station_code LIMIT 1;
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

  -- 更新主批次
  UPDATE batches SET
    status = '加工中',
    equipment_code = COALESCE(p_equipment_code, equipment_code),
    equipment_name = COALESCE(p_equipment_name, equipment_name),
    equipment_chamber = COALESCE(p_equipment_chamber, equipment_chamber),
    current_station_name = COALESCE(v_station.name, current_station_name),
    current_station_id = COALESCE(v_station.id, current_station_id),
    next_station_code = v_next_station.st_code,
    next_station_name = v_next_station.st_name,
    updated_at = now()
  WHERE id = p_batch_id::uuid;

  -- 更新子批次
  UPDATE sub_batches SET
    status = '加工中', equipment_id = v_equipment_id,
    next_station_id = v_next_station.st_id, updated_at = now()
  WHERE id = ANY(p_sub_batch_ids::uuid[]);

  -- 只写 batch_events
  INSERT INTO batch_events (event_type, target_type, target_id, payload, triggered_by)
  VALUES (
    'instation', 'batch', p_batch_id::uuid,
    jsonb_build_object(
      'batch_code', v_batch.batch_code,
      'station_code', COALESCE(v_station.code, v_batch.current_station_code),
      'station_name', COALESCE(v_station.name, ''),
      'equipment_code', p_equipment_code, 'equipment_name', p_equipment_name,
      'equipment_chamber', p_equipment_chamber, 'equipment_id', v_equipment_id,
      'next_station_code', v_next_station.st_code, 'next_station_name', v_next_station.st_name,
      'sub_batch_count', array_length(p_sub_batch_ids, 1)
    ),
    p_operator
  );

  SELECT row_to_json(b) INTO v_result FROM batches b WHERE b.id = p_batch_id::uuid;
  RETURN v_result;
END;
$$;


-- 4c: split — 移除 batch_operation_logs 写入 (同时已无 wafer_carrier_contents)
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
  IF v_batch.is_hold = true THEN RAISE EXCEPTION 'Batch is on HOLD, cannot split'; END IF;

  IF v_batch.current_station_id IS NOT NULL THEN
    v_station_id := v_batch.current_station_id;
  ELSE
    SELECT s.id INTO v_station_id FROM stations s WHERE s.code = v_batch.current_station_code LIMIT 1;
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

  -- 只写 batch_events
  INSERT INTO batch_events (event_type, target_type, target_id, payload, triggered_by)
  VALUES (
    'split', 'batch', p_batch_id::uuid,
    jsonb_build_object(
      'batch_code', v_batch.batch_code,
      'station_code', COALESCE((SELECT code FROM stations WHERE id = v_station_id), v_batch.current_station_code),
      'new_sub_batch_ids', to_jsonb(v_created_ids),
      'split_config', p_split_config
    ),
    'system'
  );

  SELECT jsonb_build_object('batch', row_to_json(b), 'new_sub_batch_ids', to_jsonb(v_created_ids))
  INTO v_result FROM batches b WHERE b.id = p_batch_id::uuid;
  RETURN v_result;
END;
$$;


-- 4d: merge — 移除 batch_operation_logs 写入
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

  -- 只写 batch_events
  INSERT INTO batch_events (event_type, target_type, target_id, payload, triggered_by)
  VALUES (
    'merge', 'batch', p_target_batch_id::uuid,
    jsonb_build_object(
      'batch_code', v_target_batch.batch_code,
      'source_sub_batch_ids', to_jsonb(p_source_sub_batch_ids),
      'merged_count', v_merged_count,
      'good_qty_before', v_target_batch.good_qty, 'defect_qty_before', v_target_batch.defect_qty,
      'good_qty_after', v_total_good, 'defect_qty_after', v_total_defect
    ),
    'system'
  );

  SELECT row_to_json(b) INTO v_result FROM batches b WHERE b.id = p_target_batch_id::uuid;
  RETURN v_result;
END;
$$;

-- 验证 Block 4:
SELECT proname, pg_get_function_arguments(oid) AS args
FROM pg_proc
WHERE proname IN ('batch_confirm_outstation', 'batch_confirm_instation', 'batch_confirm_split', 'batch_confirm_merge')
ORDER BY proname;


-- ═══════════════════════════════════════════════════════════════
-- Block 5: DROP batch_operation_logs 表
-- 前置条件: Block 3 + Block 4 已执行
--   - 历史数据已迁移到 batch_events
--   - RPC 不再写入此表
-- 需配合: TS 代码 operationLogService.ts 已更新（不再读取此表）
-- ═══════════════════════════════════════════════════════════════

DROP TABLE IF EXISTS batch_operation_logs;

-- 验证 Block 5:
SELECT EXISTS (
  SELECT 1 FROM information_schema.tables
  WHERE table_schema = 'public' AND table_name = 'batch_operation_logs'
) AS table_still_exists;
-- 预期: false


-- ═══════════════════════════════════════════════════════════════
-- Block 6: 最终验证
-- ═══════════════════════════════════════════════════════════════

-- 6a: 确认废弃表已删除
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('wafer_carrier_contents', 'batch_operation_logs');
-- 预期: 0 行

-- 6b: 确认 batch_events 包含所有历史数据
SELECT
  COUNT(*) AS total_events,
  COUNT(*) FILTER (WHERE payload->>'migrated_from' = 'batch_operation_logs') AS migrated_events,
  COUNT(*) FILTER (WHERE payload->>'migrated_from' IS NULL) AS native_events
FROM batch_events;

-- 6c: 确认 4 个 RPC 函数正常
SELECT proname FROM pg_proc
WHERE proname LIKE 'batch_confirm_%' ORDER BY proname;
