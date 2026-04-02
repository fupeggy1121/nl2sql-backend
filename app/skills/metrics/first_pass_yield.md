---
skill_name: first_pass_yield
zh_names:
  - 一次良率
  - 首次合格率
  - 直通率
  - FPY
  - first pass yield
  - 首次良率
  - 一次通过率
compute_mode: python_compute
standard_definition: "一次良率 = 首次检验合格晶圆数 / 首次检验总晶圆数 × 100%"
formula: "good_count(rn=1, wafer_type='good', ng_code IS NULL) / total_count(rn=1) * 100"
required_tables:
  - matrix_routerx_operation_lot_batch_resume_log
  - matrix_routerx_operation_lot_batch_resume_log_detail
  - matrix_routerx_operation_lot_batch_resume_wafer_detail_log
anchor_table: matrix_routerx_operation_lot_batch_resume_log
auto_filter: "operation_type = 9 AND (deleted = 0 OR deleted IS NULL)"
raw_sql_template: |
  SELECT wdl.wafer_id, log.process_code, log.product_code,
         DATE(log.gmt_create) AS report_date,
         wdl.wafer_type, wdl.ng_code,
         ROW_NUMBER() OVER (
           PARTITION BY wdl.wafer_id, log.process_code
           ORDER BY log.gmt_create ASC
         ) AS rn
  FROM matrix_routerx_operation_lot_batch_resume_log log
  JOIN matrix_routerx_operation_lot_batch_resume_log_detail d
       ON d.batch_resume_log_id = log.id
  JOIN matrix_routerx_operation_lot_batch_resume_wafer_detail_log wdl
       ON wdl.batch_resume_detail_log_id = d.id
  WHERE log.operation_type = 9
    AND (log.deleted = 0 OR log.deleted IS NULL)
    {WHERE_EXTRA}
granularity:
  - daily
  - by_process
  - by_product
---

# 一次良率 (First Pass Yield / FPY)

## 定义

一次良率衡量的是晶圆在某工站**首次出站检验**中即合格的比例。返工后恢复为 good 的晶圆**不计入**分子。

## 计算逻辑

1. **数据范围**: 取 CheckOut (operation_type=9) 的晶圆出站记录
2. **首次判定**: 按 `(wafer_id, process_code)` 分组，按 `gmt_create ASC` 排序，取 `ROW_NUMBER = 1` 的记录（即首次出站）
3. **合格判定**: `wafer_type = 'good'`（或 NULL 视为 good）且 `ng_code IS NULL 或为空`
4. **公式**: `FPY = 首次出站合格晶圆数 / 首次出站总晶圆数 × 100%`

## 粒度

- **按工站**: GROUP BY process_code
- **按产品**: GROUP BY product_code
- **按日期**: GROUP BY DATE(gmt_create)
- **组合**: 以上维度可任意组合

## 注意事项

- `wafer_type` 为 NULL 时默认按 good 处理（`COALESCE(wafer_type, 'good')`）
- 同一晶圆在同一工站可能出站多次（返工场景），仅取首次
- 需排除已逻辑删除的记录（`deleted = 0 OR deleted IS NULL`）
