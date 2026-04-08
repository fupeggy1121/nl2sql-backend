---
skill_name: oee
zh_names:
  - OEE
  - 设备综合效率
  - 设备综合效能
  - Overall Equipment Effectiveness
  - 设备效率
  - 设备稼动率
  - 设备利用率
compute_mode: python_compute
compute_tool: oee_computer
standard_definition: "OEE = 可用率(Availability) × 性能率(Performance) × 良品率(Quality) × 100%"
formula: "availability * performance * quality / 10000"
required_columns:
  - equipment_id
  - equipment_code
  - status_code
  - start_time
  - end_time
  - actual_output
  - process_code
  - report_date
granularity:
  - daily
  - by_equipment
  - by_product
required_entities:
  - semi:Equipment
  - semi:EquipmentStateRecord
  - semi:CheckOutEventRecord
depends_on_skills:
  - first_pass_yield
config_file: app/skills/oee_config.json
---

# 设备综合效率 (Overall Equipment Effectiveness / OEE)

## 定义

OEE 衡量设备在**计划生产时间**内的实际产能利用程度，分解为三个独立因子相乘：

- **可用率 (Availability)**：设备实际运行时间占计划生产时间的比例
- **性能率 (Performance)**：设备运行期间的实际产出速度与理论最大速度的比值
- **良品率 (Quality)**：产出中首次合格品的比例（调用 first_pass_yield skill）

## 计算逻辑

### 1. 可用率 (Availability)

```
可用率 = 实际运行时间 / 计划生产时间 × 100%

计划生产时间 = 日历时间 - 计划停机时间
实际运行时间 = 计划生产时间 - 非计划停机时间
```

- **日历时间**：查询时间范围总时长（小时）
- **计划停机时间**：从 `oee_config.json` 的 `planned_downtime.by_equipment` 按设备读取月度固定值，按天折算（÷30×查询天数）；待接入 PM 保养计划系统后动态获取
- **非计划停机时间**：从 `equipment_oee_status` 表（关联 `equipment_oee`）中汇总；状态分类标准来自 `oee_config.json` 的 `unplanned_downtime_states`；数据源目前处于建设期（表内暂无数据），有数据后自动生效
- **无状态记录时**：`unplanned_downtime = 0`，可用率 = 100%，在结果中以 `data_coverage: no_state_records` 标注

### 2. 性能率 (Performance)

```
性能率 = (理论节拍时间 × 实际产出数量) / 实际运行时间 × 100%
```

- **理论节拍时间**：从 `oee_config.json` 的 `theoretical_cycle_time.by_equipment_recipe` 按 `(equipment_code, recipe_code)` 查找（分钟/片），有 `default` 兜底；待积累足够历史数据后可改为动态计算（历史最优节拍）
- **实际产出数量**：从 `matrix_routerx_operation_lot_batch_resume_log` (CheckOut, `operation_type=9`) JOIN `matrix_routerx_operation_lot_batch_resume_wafer_detail_log` 汇总出站晶圆数，按 equipment_code 和时间范围过滤
- **实际运行时间**：与可用率中的值一致（单位：分钟）

### 3. 良品率 (Quality)

```
良品率 = 首次检验合格晶圆数 / 首次检验总晶圆数 × 100%
```

- **调用 first_pass_yield skill**：Python 层先调用 `FirstPassYieldComputer`，传入 equipment_code 和时间范围，获取 FPY 百分比
- **无量测记录时**：良品率默认 100%，以 `quality_source: default_100` 标注

### 4. OEE 汇总

```
OEE = 可用率 × 性能率 × 良品率 / 10000
```

三因子均为百分比（0~100），相乘后除以 10000 得到最终百分比。

## 数据源概览

| 因子 | 数据源 | 状态 |
|------|--------|------|
| 计划停机 | `oee_config.json` 固定值 | ✅ 可用（待接入 PM 系统） |
| 非计划停机 | `equipment_oee_status` + `equipment_oee` | ⚠️ 表结构已建，暂无数据 |
| 实际产出 | `matrix_routerx_operation_lot_batch_resume_log`（operation_type=9） | ✅ 有数据 |
| 理论节拍 | `oee_config.json` 按设备+recipe 配置 | ✅ 可用（待动态化） |
| 良品率 | `first_pass_yield` skill | ✅ 可用 |

## 粒度

- **按设备**：GROUP BY equipment_code
- **按日期**：GROUP BY DATE(start_time)（来自出站记录时间）
- **按产品**：GROUP BY product_code
- **组合**：以上维度可任意组合

## 注意事项

- **计划停机按月配置、按天折算**：`planned_downtime_hours_per_month / 30 × 查询天数`
- **理论节拍必须按 recipe 区分**：不同外延结构生长时间差异极大（GaN HEMT 120min vs 其他），不能用单一标准节拍
- **设备状态分类对齐 SEMI E10**：`engineering`（工程实验）和 `scheduled_maintenance`（计划保养）不计入非计划停机
- **跨天状态记录裁剪**：计算时按查询时间范围裁剪 start_time/end_time
- **世界级基准**：OEE 85%（可用率 90% × 性能率 95% × 良品率 99.5%），化合物半导体实际通常 40%–70%
