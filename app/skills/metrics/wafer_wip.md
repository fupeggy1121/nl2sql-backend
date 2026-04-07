---
skill_name: wafer_wip
zh_names:
  - 在制品数量
  - WIP数量
  - 在制wafer数
  - 在机台wafer数
  - 在制品wafer
  - 各站在制品
  - 站点在制品
  - WIP分布
  - 在制品分布
  - wafer在制品
  - 当前在制品
compute_mode: sql_aggregate
standard_definition: "在制品数量 = COUNT(DISTINCT wafer记录) 当前还在线上活跃子批次中的晶圆数，按工站/产品/路线维度汇总的预定义指标；不是批次计数查询"
formula: "COUNT(DISTINCT wafer.id) WHERE lot.status=50 AND lot.parent_id!=0"
granularity:
  - 工站
  - 机台
  - 产品
  - 路线
  - 时段
required_entities:
  - semi:Wafer
  - semi:Sublot
  - semi:ProcessStation
---

# 在制品数量 (Wafer WIP)

## 定义

在制品（WIP, Work In Progress）是指当前处于生产线上、尚未完成工艺路线的晶圆数量。
以**晶圆(wafer)粒度**统计，通过子批次(Sublot)与工站关联。

## 核心逻辑

1. **数据来源**: `matrix_routerx_operation_lot_wafer`（晶圆实例表）
2. **在制判定**: 关联的批次 `lot.status = 50`（在制状态码）且 `lot.parent_id != 0`（子批次，非主批次）
3. **计数方式**: `COUNT(DISTINCT wafer.id)`，因一个 lot 可对应多行 wafer 记录，必须用 DISTINCT 去重
4. **工站关联**: 通过 `matrix_routerx_config_process` 获取工站名称、机台等维度

## 特别注意

- **必须 DISTINCT**: `COUNT(lot.id)` 会因 batch→sublot 一对多导致 wafer 行重复，必须用 `COUNT(DISTINCT wafer.id)`
- **仅计子批次**: `lot.parent_id != 0` 过滤掉主批次记录，避免重复计数
- **status = 50**: 仅统计"在制"状态批次，status 其他值代表已完成或暂停

## 支持维度

| 维度     | 对应字段                              |
|--------|--------------------------------------|
| 工站   | `matrix_routerx_config_process.name` |
| 机台   | `lot.equipment_code` 或关联设备表     |
| 产品   | `lot.product_code`                    |
| 路线   | `lot.route_code`                      |
| 时段   | `DATE(lot.gmt_modified)`              |

## 常见查询示例

```sql
-- 各工站当前在制品数
SELECT proc.name AS station, COUNT(DISTINCT w.id) AS wip_count
FROM matrix_routerx_operation_lot_wafer w
JOIN matrix_routerx_operation_lot lot
     ON lot.id = w.lot_id AND lot.parent_id != 0
LEFT JOIN matrix_routerx_config_process proc
     ON proc.id = lot.process_id
WHERE lot.status = 50
GROUP BY proc.name
ORDER BY wip_count DESC;
```
