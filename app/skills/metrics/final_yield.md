---
skill_name: final_yield
zh_names:
  - 综合良率
  - 最终良率
  - 累计良率
  - overall yield
  - final yield
  - 成品良率
  - 出货良率
  - Yield
  - 良率
  - 出站良率
  - 工序良率
  - 批次良率
compute_mode: python_compute
standard_definition: "综合良率 = 最终检验合格晶圆数 / 最终检验总晶圆数 × 100%"
formula: "good_count(rn=1 DESC, wafer_type='good', ng_code IS NULL) / total_count(rn=1 DESC) * 100"
required_columns:
  - wafer_id
  - process_code
  - wafer_type
  - ng_code
  - rn
  - product_code
  - report_date
rn_order: DESC
granularity:
  - daily
  - by_process
  - by_product
---

# 综合良率 (Final Yield)

## 定义

综合良率衡量的是晶圆在某工站**最后一次出站检验**中合格的比例。返工后恢复为 good 的晶圆**计入**分子。

## 计算逻辑

1. **数据范围**: 取 CheckOut (operation_type=9) 的晶圆出站记录
2. **末次判定**: 按 `(wafer_id, process_code)` 分组，按 `gmt_create DESC` 排序，取 `ROW_NUMBER = 1` 的记录（即末次出站）
3. **合格判定**: `wafer_type = 'good'`（或 NULL 视为 good）且 `ng_code IS NULL 或为空`
4. **公式**: `Final Yield = 末次出站合格晶圆数 / 末次出站总晶圆数 × 100%`

## 与一次良率的区别

| 维度 | 一次良率 (FPY) | 综合良率 (Final Yield) |
|------|----------------|----------------------|
| 排序 | ASC (首次) | DESC (末次) |
| 返工恢复 | 不计入 | 计入 |
| 衡量重点 | 工艺首次通过能力 | 综合产出质量 |

## 粒度

- **按工站**: GROUP BY process_code
- **按产品**: GROUP BY product_code
- **按日期**: GROUP BY DATE(gmt_create)

## 注意事项

- 综合良率 >= 一次良率（因为返工恢复的晶圆会提升综合良率）
- `wafer_type` 为 NULL 时默认按 good 处理
- 需排除已逻辑删除的记录
