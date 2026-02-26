-- ============================================================
-- Phase 4: CIM Schema v2 — RPC 函数重写 + 清理废弃列
-- 
-- 执行方式: 在 Supabase SQL Editor 中分块执行
-- 注意: 本迁移保留旧表和列（标记为废弃），不删除数据
-- ============================================================


-- ═══════════════════════════════════════════════════════════════
-- Block 1: 重写出站确认 RPC (v2)
-- 变更:
--   - 使用 current_station_id 代替 current_station_code
--   - 同时写入 batch_events + batch_operation_logs (双写过渡)
--   - 更新 wafers.wafer_type 代替只更新 wafer_carrier_contents
-- ═══════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION batch_confirm_outstation(
  p_batch_id        text,
  p_wafer_results   jsonb,       -- [{wafer_id, type: 'GOOD'|'GoodSample'|'REJECT', sublot_id}]
  p_sub_batches     jsonb        -- [{id, sublot_id}]
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_batch           record;
  v_next_station    record;     -- v2: 从 stations 表查询
  v_from_station    record;     -- v2: 完整站点信息
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
  -- 1. 读取并锁定批次
  SELECT * INTO v_batch FROM batches WHERE id = p_batch_id::uuid FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Batch not found: %', p_batch_id;
  END IF;

  -- v2: 获取当前站点信息 (优先用 current_station_id)
  IF v_batch.current_station_id IS NOT NULL THEN
    SELECT * INTO v_from_station FROM stations WHERE id = v_batch.current_station_id;
  ELSE
    SELECT * INTO v_from_station FROM stations WHERE code = v_batch.current_station_code LIMIT 1;
  END IF;

  -- v2: 计算下一站点 (通过工艺路线)
  v_next_station_id := NULL;
  IF v_from_station.id IS NOT NULL THEN
    SELECT st.id, st.code, st.name
    INTO v_next_station
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
    ORDER BY prs.sequence
    LIMIT 1;

    IF v_next_station.id IS NOT NULL THEN
      v_next_station_id := v_next_station.id;
    ELSE
      RAISE EXCEPTION 'Next station not found for batch % at station %', p_batch_id, v_from_station.code;
    END IF;
  ELSE
    -- 回退: 用旧字段
    IF v_batch.next_station_code IS NULL OR v_batch.next_station_code = '' THEN
      RAISE EXCEPTION 'Next station is not defined for batch %', p_batch_id;
    END IF;
  END IF;

  -- 2. 统计良品和不良品总数
  SELECT
    COUNT(*) FILTER (WHERE w->>'type' IN ('GOOD', 'GoodSample', 'GOOD_SAMPLE')),
    COUNT(*) FILTER (WHERE w->>'type' = 'REJECT')
  INTO v_good_total, v_defect_total
  FROM jsonb_array_elements(p_wafer_results) AS w;

  -- 3. 更新主批次 (v2: 同时设置 current_station_id)
  UPDATE batches SET
    status               = '待进站',
    current_station_code  = COALESCE(v_next_station.code, v_batch.next_station_code),
    current_station_name  = COALESCE(v_next_station.name, v_batch.next_station_name),
    current_station_id    = v_next_station_id,
    good_qty             = v_good_total,
    defect_qty           = v_defect_total,
    equipment_code       = NULL,
    equipment_name       = NULL,
    equipment_chamber    = NULL,
    next_station_code    = NULL,
    next_station_name    = NULL,
    updated_at           = now()
  WHERE id = p_batch_id::uuid;

  -- 4. 逐个更新子批次
  FOR v_sub IN SELECT * FROM jsonb_array_elements(p_sub_batches) LOOP
    v_sub_id   := v_sub->>'id';
    v_sublot_id := v_sub->>'sublot_id';

    SELECT
      COUNT(*) FILTER (WHERE w->>'type' IN ('GOOD', 'GoodSample', 'GOOD_SAMPLE')),
      COUNT(*) FILTER (WHERE w->>'type' = 'REJECT')
    INTO v_sub_good, v_sub_defect
    FROM jsonb_array_elements(p_wafer_results) AS w
    WHERE w->>'sublot_id' = v_sublot_id;

    UPDATE sub_batches SET
      status     = '待进站',
      good_qty   = v_sub_good,
      defect_qty = v_sub_defect,
      -- v2: 更新 next_station_id
      next_station_id = NULL,
      updated_at = now()
    WHERE id = v_sub_id::uuid;
  END LOOP;

  -- 5. v2: 更新 wafers.wafer_type
  UPDATE wafers SET
    wafer_type = CASE
      WHEN wr->>'type' = 'REJECT' THEN 'REJECT'
      WHEN wr->>'type' = 'GoodSample' THEN 'GOOD_SAMPLE'
      ELSE 'GOOD'
    END,
    updated_at = now()
  FROM (SELECT * FROM jsonb_array_elements(p_wafer_results) AS wr) AS sub(wr)
  WHERE wafers.id = (sub.wr->>'wafer_id')::uuid;

  -- 6. 双写: batch_events (v2) + batch_operation_logs (旧)
  INSERT INTO batch_events (event_type, target_type, target_id, payload, triggered_by)
  VALUES (
    'outstation', 'batch', p_batch_id::uuid,
    jsonb_build_object(
      'batch_code', v_batch.batch_code,
      'from_station', COALESCE(v_from_station.code, v_batch.current_station_code),
      'from_station_name', COALESCE(v_from_station.name, v_batch.current_station_name),
      'to_station', COALESCE(v_next_station.code, v_batch.next_station_code),
      'to_station_name', COALESCE(v_next_station.name, v_batch.next_station_name),
      'good_qty_before', v_batch.good_qty,
      'defect_qty_before', v_batch.defect_qty,
      'good_qty_after', v_good_total,
      'defect_qty_after', v_defect_total,
      'wafer_count', jsonb_array_length(p_wafer_results)
    ),
    'system'
  );

  INSERT INTO batch_operation_logs (
    batch_id, batch_code, operation_type,
    from_station, to_station, operator_id,
    remarks,
    good_qty_before, defect_qty_before,
    good_qty_after, defect_qty_after,
    details
  ) VALUES (
    p_batch_id, v_batch.batch_code, 'outstation',
    COALESCE(v_from_station.code, v_batch.current_station_code),
    COALESCE(v_next_station.code, v_batch.next_station_code),
    'system',
    format('批次%s出站', v_batch.batch_code),
    v_batch.good_qty, v_batch.defect_qty,
    v_good_total, v_defect_total,
    jsonb_build_object('wafer_count', jsonb_array_length(p_wafer_results))
  );

  -- 7. 返回更新后的批次
  SELECT row_to_json(b) INTO v_result FROM batches b WHERE b.id = p_batch_id::uuid;
  RETURN v_result;
END;
$$;


-- ═══════════════════════════════════════════════════════════════
-- Block 2: 重写进站确认 RPC (v2)
-- 变更:
--   - 通过 current_station_id 查站点 (回退到 current_station_code)
--   - 更新 sub_batches.equipment_id / next_station_id
--   - 双写 batch_events + batch_operation_logs
-- ═══════════════════════════════════════════════════════════════

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
  v_station         record;   -- v2: 完整站点信息
  v_next_station    record;
  v_route_station   record;
  v_equipment_id    uuid;
  v_result          jsonb;
BEGIN
  -- 1. 读取并锁定批次
  SELECT * INTO v_batch FROM batches WHERE id = p_batch_id::uuid FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Batch not found: %', p_batch_id;
  END IF;

  IF v_batch.status <> '待进站' THEN
    RAISE EXCEPTION 'Batch status must be 待进站, got: %', v_batch.status;
  END IF;

  IF v_batch.is_hold = true THEN
    RAISE EXCEPTION 'Batch is on HOLD, cannot proceed with instation';
  END IF;

  -- v2: 获取当前站点信息 (优先 current_station_id)
  IF v_batch.current_station_id IS NOT NULL THEN
    SELECT * INTO v_station FROM stations WHERE id = v_batch.current_station_id;
  ELSE
    SELECT * INTO v_station FROM stations WHERE code = v_batch.current_station_code LIMIT 1;
  END IF;

  -- v2: 查设备 ID
  IF p_equipment_code IS NOT NULL THEN
    SELECT id INTO v_equipment_id FROM equipment WHERE code = p_equipment_code LIMIT 1;
  END IF;

  -- 计算下一站点（通过工艺路线）
  v_next_station := NULL;
  IF v_station.id IS NOT NULL THEN
    SELECT prs.* INTO v_route_station
    FROM process_route_stations prs
    WHERE prs.station_id = v_station.id
    ORDER BY prs.sequence
    LIMIT 1;

    IF v_route_station IS NOT NULL THEN
      SELECT prs.*, st.code AS st_code, st.name AS st_name, st.id AS st_id
      INTO v_next_station
      FROM process_route_stations prs
      JOIN stations st ON st.id = prs.station_id
      WHERE prs.route_id = v_route_station.route_id
        AND prs.sequence > v_route_station.sequence
      ORDER BY prs.sequence
      LIMIT 1;
    END IF;
  END IF;

  -- 4. 更新主批次 (v2: 同时设置 current_station_id)
  UPDATE batches SET
    status               = '加工中',
    equipment_code       = COALESCE(p_equipment_code, equipment_code),
    equipment_name       = COALESCE(p_equipment_name, equipment_name),
    equipment_chamber    = COALESCE(p_equipment_chamber, equipment_chamber),
    current_station_name = COALESCE(v_station.name, current_station_name),
    current_station_id   = COALESCE(v_station.id, current_station_id),
    next_station_code    = v_next_station.st_code,
    next_station_name    = v_next_station.st_name,
    updated_at           = now()
  WHERE id = p_batch_id::uuid;

  -- 5. 更新子批次 (v2: equipment_id, next_station_id)
  UPDATE sub_batches SET
    status          = '加工中',
    equipment_id    = v_equipment_id,
    next_station_id = v_next_station.st_id,
    updated_at      = now()
  WHERE id = ANY(p_sub_batch_ids::uuid[]);

  -- 6. 双写: batch_events (v2) + batch_operation_logs (旧)
  INSERT INTO batch_events (event_type, target_type, target_id, payload, triggered_by)
  VALUES (
    'instation', 'batch', p_batch_id::uuid,
    jsonb_build_object(
      'batch_code', v_batch.batch_code,
      'station_code', COALESCE(v_station.code, v_batch.current_station_code),
      'station_name', COALESCE(v_station.name, ''),
      'equipment_code', p_equipment_code,
      'equipment_name', p_equipment_name,
      'equipment_chamber', p_equipment_chamber,
      'equipment_id', v_equipment_id,
      'next_station_code', v_next_station.st_code,
      'next_station_name', v_next_station.st_name,
      'sub_batch_count', array_length(p_sub_batch_ids, 1)
    ),
    p_operator
  );

  INSERT INTO batch_operation_logs (
    batch_id, batch_code, operation_type,
    from_station, to_station, operator_id,
    remarks,
    good_qty_before, defect_qty_before,
    good_qty_after, defect_qty_after,
    details
  ) VALUES (
    p_batch_id, v_batch.batch_code, 'instation',
    COALESCE(v_station.code, v_batch.current_station_code),
    COALESCE(v_station.code, v_batch.current_station_code),
    p_operator,
    format('批次%s在%s进站，设备: %s', v_batch.batch_code, COALESCE(v_station.name, v_batch.current_station_code), COALESCE(p_equipment_code, 'N/A')),
    v_batch.good_qty, v_batch.defect_qty,
    v_batch.good_qty, v_batch.defect_qty,
    jsonb_build_object(
      'equipment_code', p_equipment_code,
      'equipment_name', p_equipment_name,
      'equipment_chamber', p_equipment_chamber,
      'sub_batch_count', array_length(p_sub_batch_ids, 1)
    )
  );

  -- 7. 返回更新后的批次
  SELECT row_to_json(b) INTO v_result FROM batches b WHERE b.id = p_batch_id::uuid;
  RETURN v_result;
END;
$$;


-- ═══════════════════════════════════════════════════════════════
-- Block 3: 重写拆批确认 RPC (v2)
-- 变更:
--   - 更新 wafers.sublot_id + carrier_id 代替 wafer_carrier_contents
--   - 新子批次设置 lot_id
--   - 双写 batch_events
-- ═══════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION batch_confirm_split(
  p_batch_id      text,
  p_split_config  jsonb    -- {new_sub_batches: [{sub_batch_code, wafer_ids: string[], carrier_id}]}
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

  -- v2: 获取站点ID (优先 current_station_id)
  IF v_batch.current_station_id IS NOT NULL THEN
    v_station_id := v_batch.current_station_id;
  ELSE
    SELECT s.id INTO v_station_id
    FROM stations s WHERE s.code = v_batch.current_station_code
    LIMIT 1;
  END IF;

  -- 2. 遍历创建新子批次
  FOR v_new_sub IN SELECT * FROM jsonb_array_elements(p_split_config->'new_sub_batches') LOOP
    v_code       := v_new_sub->>'sub_batch_code';
    v_carrier_id := v_new_sub->>'carrier_id';
    v_wafer_ids  := v_new_sub->'wafer_ids';
    v_wafer_count := jsonb_array_length(v_wafer_ids);
    v_new_sub_id := gen_random_uuid();

    -- v2: 创建新子批次 (含 lot_id)
    INSERT INTO sub_batches (
      id, batch_id, sub_batch_code, current_carrier_id, current_station_id,
      lot_id,
      total_qty, good_qty, defect_qty, status, created_at, updated_at
    )
    VALUES (
      v_new_sub_id,
      p_batch_id::uuid,
      v_code,
      v_carrier_id::uuid,
      v_station_id,
      p_batch_id::uuid,      -- lot_id = batch_id
      v_wafer_count,
      v_wafer_count,
      0,
      v_batch.status,
      now(),
      now()
    );

    -- v2: 更新 wafers 表的 sublot_id + carrier_id (代替 wafer_carrier_contents)
    UPDATE wafers SET
      sublot_id  = v_new_sub_id,
      carrier_id = v_carrier_id::uuid,
      updated_at = now()
    WHERE wafer_id_code IN (
      SELECT jsonb_array_elements_text(v_wafer_ids)
    );

    -- 向后兼容: 同时更新 wafer_carrier_contents (如果存在)
    UPDATE wafer_carrier_contents SET
      sub_batch_id = v_new_sub_id,
      carrier_id   = v_carrier_id::uuid,
      updated_at   = now()
    WHERE wafer_id IN (
      SELECT w.id FROM wafers w
      WHERE w.wafer_id_code IN (
        SELECT jsonb_array_elements_text(v_wafer_ids)
      )
    );

    v_created_ids := array_append(v_created_ids, v_new_sub_id::text);
  END LOOP;

  -- 3. 双写: batch_events + batch_operation_logs
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
    batch_id, batch_code, operation_type,
    from_station, operator_id, remarks,
    good_qty_before, defect_qty_before,
    details
  ) VALUES (
    p_batch_id, v_batch.batch_code, 'split',
    COALESCE((SELECT code FROM stations WHERE id = v_station_id), v_batch.current_station_code),
    'system',
    format('批次%s拆批，新增%s个子批次', v_batch.batch_code, array_length(v_created_ids, 1)),
    v_batch.good_qty, v_batch.defect_qty,
    jsonb_build_object(
      'new_sub_batch_ids', to_jsonb(v_created_ids),
      'split_config', p_split_config
    )
  );

  -- 4. 返回结果
  SELECT jsonb_build_object(
    'batch', row_to_json(b),
    'new_sub_batch_ids', to_jsonb(v_created_ids)
  ) INTO v_result
  FROM batches b WHERE b.id = p_batch_id::uuid;

  RETURN v_result;
END;
$$;


-- ═══════════════════════════════════════════════════════════════
-- Block 4: 重写并批确认 RPC (v2)
-- 变更:
--   - 更新合并后 wafers.sublot_id (如果子批次换了 batch_id)
--   - 双写 batch_events
-- ═══════════════════════════════════════════════════════════════

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
  -- 1. 读取并锁定目标批次
  SELECT * INTO v_target_batch FROM batches WHERE id = p_target_batch_id::uuid FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Target batch not found: %', p_target_batch_id;
  END IF;

  -- 2. 校验所有源子批次在同一站点
  SELECT COUNT(DISTINCT current_station_id) AS station_count
  INTO v_station_check
  FROM sub_batches
  WHERE id = ANY(p_source_sub_batch_ids::uuid[]);

  IF v_station_check.station_count > 1 THEN
    RAISE EXCEPTION 'All source sub-batches must be at the same station for merge';
  END IF;

  -- 3. 将源子批次转移到目标批次 (v2: 同时更新 lot_id)
  UPDATE sub_batches SET
    batch_id   = p_target_batch_id::uuid,
    lot_id     = p_target_batch_id::uuid,
    updated_at = now()
  WHERE id = ANY(p_source_sub_batch_ids::uuid[]);

  GET DIAGNOSTICS v_merged_count = ROW_COUNT;

  -- v2: 更新关联 wafers 的 lot_id
  UPDATE wafers SET
    lot_id     = p_target_batch_id::uuid,
    batch_id   = p_target_batch_id::uuid,
    updated_at = now()
  WHERE sublot_id = ANY(p_source_sub_batch_ids::uuid[]);

  -- 4. 重算目标批次数量
  SELECT
    COALESCE(SUM(total_qty), 0),
    COALESCE(SUM(good_qty), 0),
    COALESCE(SUM(defect_qty), 0)
  INTO v_total_qty, v_total_good, v_total_defect
  FROM sub_batches
  WHERE batch_id = p_target_batch_id::uuid;

  UPDATE batches SET
    total_qty  = v_total_qty,
    good_qty   = v_total_good,
    defect_qty = v_total_defect,
    updated_at = now()
  WHERE id = p_target_batch_id::uuid;

  -- 5. 双写: batch_events + batch_operation_logs
  INSERT INTO batch_events (event_type, target_type, target_id, payload, triggered_by)
  VALUES (
    'merge', 'batch', p_target_batch_id::uuid,
    jsonb_build_object(
      'batch_code', v_target_batch.batch_code,
      'source_sub_batch_ids', to_jsonb(p_source_sub_batch_ids),
      'merged_count', v_merged_count,
      'good_qty_before', v_target_batch.good_qty,
      'defect_qty_before', v_target_batch.defect_qty,
      'good_qty_after', v_total_good,
      'defect_qty_after', v_total_defect
    ),
    'system'
  );

  INSERT INTO batch_operation_logs (
    batch_id, batch_code, operation_type,
    from_station, operator_id, remarks,
    good_qty_before, defect_qty_before,
    good_qty_after, defect_qty_after,
    details
  ) VALUES (
    p_target_batch_id, v_target_batch.batch_code, 'merge',
    COALESCE((SELECT code FROM stations WHERE id = v_target_batch.current_station_id), v_target_batch.current_station_code),
    'system',
    format('并批操作：%s个子批次合并到批次%s', v_merged_count, v_target_batch.batch_code),
    v_target_batch.good_qty, v_target_batch.defect_qty,
    v_total_good, v_total_defect,
    jsonb_build_object(
      'source_sub_batch_ids', to_jsonb(p_source_sub_batch_ids),
      'merged_count', v_merged_count
    )
  );

  -- 6. 返回结果
  SELECT row_to_json(b) INTO v_result FROM batches b WHERE b.id = p_target_batch_id::uuid;
  RETURN v_result;
END;
$$;


-- ═══════════════════════════════════════════════════════════════
-- Block 5: 标记废弃列（添加注释，不删除）
-- 后续 Phase 5 可安全 DROP 这些列
-- ═══════════════════════════════════════════════════════════════

-- wafer_carrier_contents 表标记为废弃
COMMENT ON TABLE wafer_carrier_contents IS '⚠️ DEPRECATED (v2) — 数据已反规范化到 wafers 表 (sublot_id, carrier_id, slot_number, wafer_type)。保留用于向后兼容，新增数据同时写入双表。';

-- batches 废弃列标记
COMMENT ON COLUMN batches.current_station_code IS '⚠️ DEPRECATED — 使用 current_station_id (FK → stations.id) 代替';
COMMENT ON COLUMN batches.current_station_name IS '⚠️ DEPRECATED — 通过 current_station_id JOIN stations 获取';
COMMENT ON COLUMN batches.next_station_code IS '⚠️ DEPRECATED — 由工艺路线动态计算';
COMMENT ON COLUMN batches.next_station_name IS '⚠️ DEPRECATED — 由工艺路线动态计算';
COMMENT ON COLUMN batches.is_hold IS '⚠️ DEPRECATED — 将迁移到 batch_events hold/unhold 事件';

-- batch_operation_logs 表标记为废弃
COMMENT ON TABLE batch_operation_logs IS '⚠️ DEPRECATED (v2) — 新事件写入 batch_events 表。此表保留历史数据和向后兼容双写。';


-- ═══════════════════════════════════════════════════════════════
-- Block 6: 验证查询
-- ═══════════════════════════════════════════════════════════════

-- 验证 1: RPC 函数存在且签名正确
SELECT proname, pg_get_function_arguments(oid) AS args
FROM pg_proc
WHERE proname IN ('batch_confirm_outstation', 'batch_confirm_instation', 'batch_confirm_split', 'batch_confirm_merge')
ORDER BY proname;

-- 验证 2: batch_events 表可写入
SELECT COUNT(*) AS event_count FROM batch_events;

-- 验证 3: 废弃注释已写入
SELECT obj_description('wafer_carrier_contents'::regclass) AS wcc_comment;
SELECT obj_description('batch_operation_logs'::regclass) AS bol_comment;
