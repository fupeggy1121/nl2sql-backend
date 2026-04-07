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
compute_tool: first_pass_yield_computer
standard_definition: "一次良率 = 首次检验合格晶圆数 / 首次检验总晶圆数 × 100%"
formula: "good_count(rn=1 ASC, wafer_type='good', ng_code IS NULL) / total_count(rn=1) * 100"
required_columns:
  - wafer_id
  - process_code
  - wafer_type
  - ng_code
  - rn
  - product_code
  - report_date
rn_order: ASC
granularity:
  - daily
  - by_process
  - by_product
required_entities:
  - semi:CheckOutEventRecord
  - semi:WaferTransitionSnapshot
---

# 一次良率 (First Pass Yield / FPY)

## 定义

一次良率衡量的是晶圆在某工站**首次出站检验**中即合格的比例。返工后恢复为 good 的晶圆**不计入**分子。

## 计算逻辑

1. **数据范围**: 取 CheckOut (operation_type=9) 的晶圆出站记录
2. **首次判定**: 按 `(wafer_id, process_code)` 分组，按 **`l.gmt_create ASC`** 排序（`l` 为批次主表 `matrix_routerx_operation_lot_batch_resume_log`），取 `ROW_NUMBER = 1` 的记录（即首次出站）
3. **合格判定**: `wafer_type = 'good'`（或 NULL 视为 good）且 `ng_code IS NULL 或为空`
4. **公式**: `FPY = 首次出站合格晶圆数 / 首次出站总晶圆数 × 100%`

## 粒度

- **按工站**: GROUP BY process_code
- **按产品**: GROUP BY product_code
- **按日期**: GROUP BY DATE(**l.gmt_create**)  ← 必须用批次主表时间戳
- **组合**: 以上维度可任意组合

## 注意事项

- `wafer_type` 为 NULL 时 Python 层自动处理，SQL 无需 COALESCE
- 同一晶圆在同一工站可能出站多次（返工场景），仅取首次
- 需排除已逻辑删除的记录（`l.deleted = 0 OR l.deleted IS NULL`）
- **时间过滤必须用 `l.gmt_create`**（批次主表时间戳），不能用 `w.gmt_create`（明细表），以保证与综合良率使用同一时间基准，确保两者可对比
- **ROW_NUMBER 排序必须用 `l.gmt_create ASC`**，不能用 `w.gmt_create`
- **适用站点**：良率计算仅针对量测类型站点（Measurement Station）的 CheckOut 记录；工艺站点出站时无 `wafer_type` 判定，其良率定义另行维护
- **返工场景**：返工子路径的量测站点与主路径为同一 `process_code`，`waferID` 不变。一次良率取首次出站（`rn=1 ASC`），返工后再经过该量测站点的记录 `rn > 1`，不会混入计算，无需额外过滤
- **全流程串联良率**：用户未指定站点时，SQL 应返回全量站点数据（不加 process_code 过滤），Python 层会按 process_code 分组各自计算站点良率，再对所有站点良率连乘得到全流程一次良率；用户指定了站点（提到 process_code 或站点名），SQL 加 `WHERE process_code = '...'` 精确过滤
