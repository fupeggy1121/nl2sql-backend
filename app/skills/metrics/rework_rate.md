---
skill_name: rework_rate
zh_names:
  - 返工率
  - 重工率
  - rework rate
  - 返工比例
compute_mode: python_compute
standard_definition: "返工率 = 返工晶圆数 / 总晶圆数 × 100%"
formula: "count(visit_count > 1) / total_count * 100"
granularity:
  - daily
  - by_process
  - by_product
---

# 返工率 (Rework Rate)

## 定义

返工率衡量的是在某工站有**多次进站记录**的晶圆比例，反映工艺稳定性。

## 计算逻辑

1. **数据范围**: 取 CheckIn (operation_type=8) 的晶圆进站记录
2. **访问次数**: 按 `(wafer_id, process_code)` 分组统计进站次数 `visit_count`
3. **返工判定**: `visit_count > 1` 即该晶圆在同一工站进站超过一次
4. **公式**: `Rework Rate = visit_count > 1 的晶圆数 / 总去重晶圆数 × 100%`

## 粒度

- **按工站**: GROUP BY process_code
- **按产品**: GROUP BY product_code
- **按日期**: GROUP BY DATE(gmt_create)

## 注意事项

- 返工率统计基于 CheckIn (进站)，不是 CheckOut (出站)
- 正常晶圆 visit_count = 1，返工晶圆 visit_count > 1
- 高返工率（如 > 5%）可能表明工艺参数需要调整
