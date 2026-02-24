-- ============================================================
-- 热修复 v2：修复 RPC 函数中的两个类型不匹配问题
-- 
-- 问题1：batches.id 等列是 uuid，参数是 text → 添加 ::uuid 转换
-- 问题2：updated_at/created_at 是 timestamptz，不能用 now()::text → 改为 now()
--
-- 直接复制此文件全部内容到 Supabase SQL Editor 中执行即可。
-- 此文件使用 CREATE OR REPLACE 不会删除已有数据。
-- ============================================================

-- 1. 出站确认 RPC
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
  v_next_station    text;
  v_next_station_nm text;
  v_from_station    text;
  v_from_station_nm text;
  v_good_total      integer;
  v_defect_total    integer;
  v_sub             jsonb;
  v_sub_id          text;
  v_sublot_id       text;
  v_sub_good        integer;
  v_sub_defect      integer;
  v_result          jsonb;
BEGIN
  SELECT * INTO v_batch FROM batches WHERE id = p_batch_id::uuid FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Batch not found: %', p_batch_id;
  END IF;

  v_from_station    := v_batch.current_station_code;
  v_from_station_nm := v_batch.current_station_name;
  v_next_station    := v_batch.next_station_code;
  v_next_station_nm := v_batch.next_station_name;

  IF v_next_station IS NULL OR v_next_station = '' THEN
    RAISE EXCEPTION 'Next station is not defined for batch %', p_batch_id;
  END IF;

  SELECT
    COUNT(*) FILTER (WHERE w->>'type' IN ('GOOD', 'GoodSample')),
    COUNT(*) FILTER (WHERE w->>'type' = 'REJECT')
  INTO v_good_total, v_defect_total
  FROM jsonb_array_elements(p_wafer_results) AS w;

  UPDATE batches SET
    status               = '待进站',
    current_station_code  = v_next_station,
    current_station_name  = v_next_station_nm,
    good_qty             = v_good_total,
    defect_qty           = v_defect_total,
    equipment_code       = NULL,
    equipment_name       = NULL,
    equipment_chamber    = NULL,
    next_station_code    = NULL,
    next_station_name    = NULL,
    updated_at           = now()
  WHERE id = p_batch_id::uuid;

  FOR v_sub IN SELECT * FROM jsonb_array_elements(p_sub_batches) LOOP
    v_sub_id   := v_sub->>'id';
    v_sublot_id := v_sub->>'sublot_id';

    SELECT
      COUNT(*) FILTER (WHERE w->>'type' IN ('GOOD', 'GoodSample')),
      COUNT(*) FILTER (WHERE w->>'type' = 'REJECT')
    INTO v_sub_good, v_sub_defect
    FROM jsonb_array_elements(p_wafer_results) AS w
    WHERE w->>'sublot_id' = v_sublot_id;

    UPDATE sub_batches SET
      status     = '待进站',
      good_qty   = v_sub_good,
      defect_qty = v_sub_defect,
      updated_at = now()
    WHERE id = v_sub_id::uuid;
  END LOOP;

  INSERT INTO batch_operation_logs (
    batch_id, batch_code, operation_type,
    from_station, to_station, operator_id,
    remarks,
    good_qty_before, defect_qty_before,
    good_qty_after, defect_qty_after,
    details
  ) VALUES (
    p_batch_id, v_batch.batch_code, 'outstation',
    v_from_station, v_next_station, 'system',
    format('批次%s从%s出站，进入%s待进站', v_batch.batch_code, v_from_station_nm, v_next_station_nm),
    v_batch.good_qty, v_batch.defect_qty,
    v_good_total, v_defect_total,
    jsonb_build_object('wafer_count', jsonb_array_length(p_wafer_results))
  );

  SELECT row_to_json(b) INTO v_result FROM batches b WHERE b.id = p_batch_id::uuid;
  RETURN v_result;
END;
$$;

GRANT EXECUTE ON FUNCTION batch_confirm_outstation(text, jsonb, jsonb) TO service_role;


-- 2. 进站确认 RPC
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
  v_station_code    text;
  v_station_name    text;
  v_next_code       text;
  v_next_name       text;
  v_route_station   record;
  v_next_rs         record;
  v_result          jsonb;
BEGIN
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

  v_station_code := v_batch.current_station_code;

  SELECT s.name INTO v_station_name
  FROM stations s WHERE s.code = v_station_code;

  SELECT prs.* INTO v_route_station
  FROM process_route_stations prs
  JOIN stations st ON st.id = prs.station_id
  WHERE st.code = v_station_code
  ORDER BY prs.sequence
  LIMIT 1;

  IF v_route_station IS NOT NULL THEN
    SELECT prs.*, st.code AS st_code, st.name AS st_name
    INTO v_next_rs
    FROM process_route_stations prs
    JOIN stations st ON st.id = prs.station_id
    WHERE prs.route_id = v_route_station.route_id
      AND prs.sequence > v_route_station.sequence
    ORDER BY prs.sequence
    LIMIT 1;

    IF v_next_rs IS NOT NULL THEN
      v_next_code := v_next_rs.st_code;
      v_next_name := v_next_rs.st_name;
    END IF;
  END IF;

  UPDATE batches SET
    status             = '加工中',
    equipment_code     = COALESCE(p_equipment_code, equipment_code),
    equipment_name     = COALESCE(p_equipment_name, equipment_name),
    equipment_chamber  = COALESCE(p_equipment_chamber, equipment_chamber),
    current_station_name = v_station_name,
    next_station_code  = v_next_code,
    next_station_name  = v_next_name,
    updated_at         = now()
  WHERE id = p_batch_id::uuid;

  UPDATE sub_batches SET
    status     = '加工中',
    updated_at = now()
  WHERE id = ANY(p_sub_batch_ids::uuid[]);

  INSERT INTO batch_operation_logs (
    batch_id, batch_code, operation_type,
    from_station, to_station, operator_id,
    remarks,
    good_qty_before, defect_qty_before,
    good_qty_after, defect_qty_after,
    details
  ) VALUES (
    p_batch_id, v_batch.batch_code, 'instation',
    v_station_code, v_station_code, p_operator,
    format('批次%s在%s进站，设备: %s', v_batch.batch_code, COALESCE(v_station_name, v_station_code), COALESCE(p_equipment_code, 'N/A')),
    v_batch.good_qty, v_batch.defect_qty,
    v_batch.good_qty, v_batch.defect_qty,
    jsonb_build_object(
      'equipment_code', p_equipment_code,
      'equipment_name', p_equipment_name,
      'equipment_chamber', p_equipment_chamber,
      'sub_batch_count', array_length(p_sub_batch_ids, 1)
    )
  );

  SELECT row_to_json(b) INTO v_result FROM batches b WHERE b.id = p_batch_id::uuid;
  RETURN v_result;
END;
$$;

GRANT EXECUTE ON FUNCTION batch_confirm_instation(text, text[], text, text, text, text) TO service_role;


-- 3. 拆批确认 RPC
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
  v_new_sub_id  text;
  v_station_id  text;
  v_created_ids text[] := '{}';
  v_result      jsonb;
BEGIN
  SELECT * INTO v_batch FROM batches WHERE id = p_batch_id::uuid FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Batch not found: %', p_batch_id;
  END IF;

  IF v_batch.is_hold = true THEN
    RAISE EXCEPTION 'Batch is on HOLD, cannot split';
  END IF;

  SELECT s.id::text INTO v_station_id
  FROM stations s WHERE s.code = v_batch.current_station_code
  LIMIT 1;

  FOR v_new_sub IN SELECT * FROM jsonb_array_elements(p_split_config->'new_sub_batches') LOOP
    v_code       := v_new_sub->>'sub_batch_code';
    v_carrier_id := v_new_sub->>'carrier_id';
    v_wafer_ids  := v_new_sub->'wafer_ids';
    v_wafer_count := jsonb_array_length(v_wafer_ids);
    v_new_sub_id := gen_random_uuid()::text;

    INSERT INTO sub_batches (id, batch_id, sub_batch_code, current_carrier_id, current_station_id, total_qty, good_qty, defect_qty, status, created_at, updated_at)
    VALUES (
      v_new_sub_id::uuid,
      p_batch_id::uuid,
      v_code,
      v_carrier_id::uuid,
      v_station_id::uuid,
      v_wafer_count,
      v_wafer_count,
      0,
      v_batch.status,
      now(),
      now()
    );

    UPDATE wafer_carrier_contents SET
      sub_batch_id = v_new_sub_id::uuid,
      carrier_id   = v_carrier_id::uuid,
      updated_at   = now()
    WHERE wafer_id IN (
      SELECT w.id FROM wafers w
      WHERE w.wafer_id_code IN (
        SELECT jsonb_array_elements_text(v_wafer_ids)
      )
    );

    v_created_ids := array_append(v_created_ids, v_new_sub_id);
  END LOOP;

  INSERT INTO batch_operation_logs (
    batch_id, batch_code, operation_type,
    from_station, operator_id, remarks,
    good_qty_before, defect_qty_before,
    details
  ) VALUES (
    p_batch_id, v_batch.batch_code, 'split',
    v_batch.current_station_code, 'system',
    format('批次%s在%s进行拆批，新增%s个子批次', v_batch.batch_code, v_batch.current_station_code, array_length(v_created_ids, 1)),
    v_batch.good_qty, v_batch.defect_qty,
    jsonb_build_object(
      'new_sub_batch_ids', to_jsonb(v_created_ids),
      'split_config', p_split_config
    )
  );

  SELECT jsonb_build_object(
    'batch', row_to_json(b),
    'new_sub_batch_ids', to_jsonb(v_created_ids)
  ) INTO v_result
  FROM batches b WHERE b.id = p_batch_id::uuid;

  RETURN v_result;
END;
$$;

GRANT EXECUTE ON FUNCTION batch_confirm_split(text, jsonb) TO service_role;


-- 4. 并批确认 RPC
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
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Target batch not found: %', p_target_batch_id;
  END IF;

  SELECT COUNT(DISTINCT current_station_id) AS station_count
  INTO v_station_check
  FROM sub_batches
  WHERE id = ANY(p_source_sub_batch_ids::uuid[]);

  IF v_station_check.station_count > 1 THEN
    RAISE EXCEPTION 'All source sub-batches must be at the same station for merge';
  END IF;

  UPDATE sub_batches SET
    batch_id   = p_target_batch_id::uuid,
    updated_at = now()
  WHERE id = ANY(p_source_sub_batch_ids::uuid[]);

  GET DIAGNOSTICS v_merged_count = ROW_COUNT;

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

  INSERT INTO batch_operation_logs (
    batch_id, batch_code, operation_type,
    from_station, operator_id, remarks,
    good_qty_before, defect_qty_before,
    good_qty_after, defect_qty_after,
    details
  ) VALUES (
    p_target_batch_id, v_target_batch.batch_code, 'merge',
    v_target_batch.current_station_code, 'system',
    format('并批操作：%s个子批次合并到批次%s', v_merged_count, v_target_batch.batch_code),
    v_target_batch.good_qty, v_target_batch.defect_qty,
    v_total_good, v_total_defect,
    jsonb_build_object(
      'source_sub_batch_ids', to_jsonb(p_source_sub_batch_ids),
      'merged_count', v_merged_count
    )
  );

  SELECT row_to_json(b) INTO v_result FROM batches b WHERE b.id = p_target_batch_id::uuid;
  RETURN v_result;
END;
$$;

GRANT EXECUTE ON FUNCTION batch_confirm_merge(text, text[]) TO service_role;
