# 数据库 Schema 完整参考
生成时间: 2026-02-11 09:46:10
总表数: 35

## 表索引
1. [annotation_audit_log](#annotation_audit_log) - 注释审计日志 - 注释修改的审计记录
2. [approved_schema_metadata](#approved_schema_metadata) - 批准的元数据 - 经过审批的数据库架构元数据
3. [batch_remarks](#batch_remarks) - 批次备注 - 批次的备注说明
4. [batches](#batches) - 批次 - 生产批次主记录
5. [carriers](#carriers) - 载体 - 晶圆载体的基础信息
6. [chat_messages](#chat_messages) - 聊天消息 - NL2SQL 对话系统的消息记录
7. [chat_sessions](#chat_sessions) - 聊天会话 - NL2SQL 对话会话管理
8. [custom_process_rules](#custom_process_rules) - 自定义工艺规则 - 用户自定义的生产规则
9. [equipment](#equipment) - 设备 - 生产设备信息
10. [equipment_groups](#equipment_groups) - 设备组 - 设备的分组管理
11. [feedback](#feedback) - 用户反馈 - 用户对系统的反馈
12. [intent_feedback](#intent_feedback) - 意图反馈 - NL2SQL 意图识别的反馈
13. [oee_records](#oee_records) - OEE 记录 - 设备综合效率记录
14. [parameter_equipment](#parameter_equipment) - 参数设备关联 - 参数与设备的关联关系
15. [parameter_group_parameters](#parameter_group_parameters) - 参数组参数 - 参数组中包含的具体参数
16. [parameter_groups](#parameter_groups) - 参数组 - 参数的分组管理
17. [parameters](#parameters) - 参数 - 工艺参数定义和配置
18. [process_route_stations](#process_route_stations) - 工艺路线站点 - 工艺路线中的站点配置
19. [process_routes](#process_routes) - 工艺路线 - 产品生产的工艺路线
20. [product_boms](#product_boms) - 产品 BOM - 产品物料清单
21. [production_events](#production_events) - 生产事件 - 记录生产过程中发生的各类事件
22. [production_orders](#production_orders) - 生产订单 - 生产订单主记录
23. [products](#products) - 产品 - 产品信息和规格
24. [quality_records](#quality_records) - 质量记录 - 存储产品质量测量和检验数据
25. [query_result_feedback](#query_result_feedback) - 查询结果反馈 - 查询结果的用户反馈
26. [saved_reports](#saved_reports) - 保存的报告 - 用户保存的查询报告
27. [schema_column_annotations](#schema_column_annotations) - 列注释 - 数据库列的注释说明
28. [schema_relation_annotations](#schema_relation_annotations) - 关系注释 - 表关系的注释说明
29. [schema_table_annotations](#schema_table_annotations) - 表注释 - 数据库表的注释说明
30. [stations](#stations) - 生产站点 - 生产线上的工作站点
31. [sub_batch_process_log](#sub_batch_process_log) - 子批次工艺日志 - 子批次的工艺过程记录
32. [sub_batches](#sub_batches) - 子批次 - 生产批次的细分单位
33. [wafer_carrier_contents](#wafer_carrier_contents) - 晶圆载体内容 - 晶圆在载体中的位置和状态信息
34. [wafer_inspection_results](#wafer_inspection_results) - 晶圆检测结果 - 记录晶圆在各站点的检测数据和结果
35. [wafers](#wafers) - 晶圆 - 晶圆基础信息（ID、批次、类型等）

---

## annotation_audit_log

**说明**: 注释审计日志 - 注释修改的审计记录

**列数**: 0


---

## approved_schema_metadata

**说明**: 批准的元数据 - 经过审批的数据库架构元数据

**列数**: 13

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `table_name` | text | table_name | production_orders |
| `table_name_cn` | text | table_name_cn | 生产订单 |
| `description_cn` | text | description_cn | 存储来自客户的生产订单信息 |
| `description_en` | text | description_en | Storage for production orde... |
| `business_meaning` | text | business_meaning | 用于跟踪和管理生产计划 |
| `column_name` | text | column_name | order_number |
| `column_name_cn` | text | column_name_cn | 订单编号 |
| `data_type` | text | data_type | varchar |
| `column_description_cn` | text | column_description_cn | 唯一的订单编号 |
| `column_description_en` | text | column_description_en | Unique order number |
| `example_value` | text | example_value | ORD-2026-001 |
| `column_business_meaning` | text | column_business_meaning | 用于识别订单 |
| `value_range` | text | value_range | 6-20 字符 |

### SQL CREATE TABLE

```sql
CREATE TABLE approved_schema_metadata (
  table_name text NOT NULL,
  table_name_cn text NOT NULL,
  description_cn text NOT NULL,
  description_en text NOT NULL,
  business_meaning text NOT NULL,
  column_name text NOT NULL,
  column_name_cn text NOT NULL,
  data_type text NOT NULL,
  column_description_cn text NOT NULL,
  column_description_en text NOT NULL,
  example_value text NOT NULL,
  column_business_meaning text NOT NULL,
  value_range text NOT NULL,
);
```

---

## batch_remarks

**说明**: 批次备注 - 批次的备注说明

**列数**: 0


---

## batches

**说明**: 批次 - 生产批次主记录

**列数**: 22

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | aba03c67-3bf4-417c-b013-43f... |
| `batch_code` | text | batch_code | BATCHQO20O3 |
| `product_code` | text | product_code | P001 |
| `product_name` | text | product_name | Product Alpha |
| `total_qty` | integer | total_qty | 311 |
| `good_qty` | integer | good_qty | 258 |
| `defect_qty` | integer | defect_qty | 53 |
| `status` | text | 状态 - 记录的当前状态 | 待进站 |
| `current_station_code` | text | current_station_code | station13 |
| `current_station_name` | unknown | current_station_name | (NULL) |
| `equipment_code` | text | equipment_code | EQ003 |
| `equipment_name` | text | equipment_name | Equipment B |
| `equipment_chamber` | text | equipment_chamber | Chamber 2 |
| `next_station_code` | text | next_station_code | station11 |
| `next_station_name` | text | next_station_name | Unknown Next Station |
| `product_version` | integer | product_version | 1 |
| `recipe_code` | text | recipe_code | REC002 |
| `ingot_id` | text | ingot_id | ING005 |
| `is_small_batch` | boolean | is_small_batch | False |
| `is_hold` | boolean | is_hold | True |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2025-12-31T02:34:30.306+00:00 |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2025-12-31T02:34:30.306+00:00 |

### SQL CREATE TABLE

```sql
CREATE TABLE batches (
  id text NOT NULL,
  batch_code text NOT NULL,
  product_code text NOT NULL,
  product_name text NOT NULL,
  total_qty integer NOT NULL,
  good_qty integer NOT NULL,
  defect_qty integer NOT NULL,
  status text NOT NULL,
  current_station_code text NOT NULL,
  current_station_name unknown ,
  equipment_code text NOT NULL,
  equipment_name text NOT NULL,
  equipment_chamber text NOT NULL,
  next_station_code text NOT NULL,
  next_station_name text NOT NULL,
  product_version integer NOT NULL,
  recipe_code text NOT NULL,
  ingot_id text NOT NULL,
  is_small_batch boolean NOT NULL,
  is_hold boolean NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
);
```

---

## carriers

**说明**: 载体 - 晶圆载体的基础信息

**列数**: 6

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | b05c9966-c836-4309-9bb5-a5a... |
| `carrier_code` | text | carrier_code | CARCLWIBH |
| `capacity` | integer | capacity | 25 |
| `status` | text | 状态 - 记录的当前状态 | available |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2025-12-31T05:18:42.304+00:00 |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2025-12-31T05:18:42.304+00:00 |

### SQL CREATE TABLE

```sql
CREATE TABLE carriers (
  id text NOT NULL,
  carrier_code text NOT NULL,
  capacity integer NOT NULL,
  status text NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
);
```

---

## chat_messages

**说明**: 聊天消息 - NL2SQL 对话系统的消息记录

**列数**: 9

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | 6477b737-359a-4d35-9f8f-e6b... |
| `session_id` | text | session_id | current_user_session_id |
| `type` | text | 类型 - 对象或参数的类型 | user |
| `content` | text | content | 昨天设备E-001的OEE是多少？ |
| `timestamp` | text | timestamp | 2026-01-28T14:47:57.344+00:00 |
| `intent_data` | unknown | intent_data | (NULL) |
| `result_data` | unknown | result_data | (NULL) |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2026-01-28T14:47:57.76766+0... |
| `clarification_options` | unknown | clarification_options | (NULL) |

### SQL CREATE TABLE

```sql
CREATE TABLE chat_messages (
  id text NOT NULL,
  session_id text NOT NULL,
  type text NOT NULL,
  content text NOT NULL,
  timestamp text NOT NULL,
  intent_data unknown ,
  result_data unknown ,
  created_at text NOT NULL,
  clarification_options unknown ,
);
```

---

## chat_sessions

**说明**: 聊天会话 - NL2SQL 对话会话管理

**列数**: 3

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | session-1769657589377 |
| `name` | text | 名称 - 对象的名称 | 新对话 1 |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2026-01-29T03:33:10.345801+... |

### SQL CREATE TABLE

```sql
CREATE TABLE chat_sessions (
  id text NOT NULL,
  name text NOT NULL,
  created_at text NOT NULL,
);
```

---

## custom_process_rules

**说明**: 自定义工艺规则 - 用户自定义的生产规则

**列数**: 7

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | dfcd43f7-aa18-4e94-a9de-2c1... |
| `name` | text | 名称 - 对象的名称 | 温度超限报警 |
| `description` | text | 描述 - 详细说明 | 当加工温度超出设定范围时触发报警并暂停 |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2025-12-30T05:07:00.463813+... |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2025-12-30T05:07:00.463813+... |
| `status` | text | 状态 - 记录的当前状态 | active |
| `code` | text | 代码 - 对象的编码 | TEMP_CODE |

### SQL CREATE TABLE

```sql
CREATE TABLE custom_process_rules (
  id text NOT NULL,
  name text NOT NULL,
  description text NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
  status text NOT NULL,
  code text NOT NULL,
);
```

---

## equipment

**说明**: 设备 - 生产设备信息

**列数**: 8

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | 33cccc22-2d3c-4aa1-ee9d-9ee... |
| `name` | text | 名称 - 对象的名称 | 清洗机A |
| `code` | text | 代码 - 对象的编码 | CLEANER_A |
| `equipment_group_id` | text | equipment_group_id | a0eebc99-9c0b-4ef8-bb6d-6bb... |
| `description` | text | 描述 - 详细说明 | 第一道清洗设备 |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2026-01-05T05:32:38.02684+0... |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2026-01-05T05:32:38.02684+0... |
| `recipe_id` | unknown | recipe_id | (NULL) |

### SQL CREATE TABLE

```sql
CREATE TABLE equipment (
  id text NOT NULL,
  name text NOT NULL,
  code text NOT NULL,
  equipment_group_id text NOT NULL,
  description text NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
  recipe_id unknown ,
);
```

---

## equipment_groups

**说明**: 设备组 - 设备的分组管理

**列数**: 5

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | a0eebc99-9c0b-4ef8-bb6d-6bb... |
| `name` | text | 名称 - 对象的名称 | 清洗设备组 |
| `description` | text | 描述 - 详细说明 | 用于硅片清洗的设备集合 |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2026-01-05T05:32:38.02684+0... |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2026-01-05T05:32:38.02684+0... |

### SQL CREATE TABLE

```sql
CREATE TABLE equipment_groups (
  id text NOT NULL,
  name text NOT NULL,
  description text NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
);
```

---

## feedback

**说明**: 用户反馈 - 用户对系统的反馈

**列数**: 8

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | e23e449a-53b8-47df-becd-9c1... |
| `message_id` | text | message_id | 1 |
| `feedback_type` | text | feedback_type | helpful |
| `rating` | integer | rating | 3 |
| `comment` | text | comment | (NULL) |
| `query` | text | query | (NULL) |
| `response` | text | response | 您好！我是 MES 数据智能分析助手。我可以帮您分析生... |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2026-02-02T16:58:57.391433+... |

### SQL CREATE TABLE

```sql
CREATE TABLE feedback (
  id text NOT NULL,
  message_id text NOT NULL,
  feedback_type text NOT NULL,
  rating integer NOT NULL,
  comment text NOT NULL,
  query text NOT NULL,
  response text NOT NULL,
  created_at text NOT NULL,
);
```

---

## intent_feedback

**说明**: 意图反馈 - NL2SQL 意图识别的反馈

**列数**: 0


---

## oee_records

**说明**: OEE 记录 - 设备综合效率记录

**列数**: 13

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | 1a00ca06-bf61-42e0-8c96-59c... |
| `equipment_id` | text | 设备 ID - 关联的生产设备 | E-001 |
| `date` | text | date | 2025-12-30 |
| `shift` | text | shift | A |
| `availability` | numeric | availability | 86.91 |
| `performance` | numeric | performance | 92.52 |
| `quality` | numeric | quality | 95.74 |
| `oee` | numeric | oee | 76.98 |
| `planned_time` | integer | planned_time | 480 |
| `actual_time` | integer | actual_time | 417 |
| `total_output` | integer | total_output | 176 |
| `good_output` | integer | good_output | 168 |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2026-01-29T01:39:28.248048+... |

### SQL CREATE TABLE

```sql
CREATE TABLE oee_records (
  id text NOT NULL,
  equipment_id text NOT NULL,
  date text NOT NULL,
  shift text NOT NULL,
  availability numeric NOT NULL,
  performance numeric NOT NULL,
  quality numeric NOT NULL,
  oee numeric NOT NULL,
  planned_time integer NOT NULL,
  actual_time integer NOT NULL,
  total_output integer NOT NULL,
  good_output integer NOT NULL,
  created_at text NOT NULL,
);
```

---

## parameter_equipment

**说明**: 参数设备关联 - 参数与设备的关联关系

**列数**: 3

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `parameter_id` | text | parameter_id | d3eeec22-2f3e-4aa1-bb9a-9ee... |
| `equipment_id` | text | 设备 ID - 关联的生产设备 | 17aa9966-6b7a-4ee5-113b-311... |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2026-01-05T05:32:38.02684+0... |

### SQL CREATE TABLE

```sql
CREATE TABLE parameter_equipment (
  parameter_id text NOT NULL,
  equipment_id text NOT NULL,
  created_at text NOT NULL,
);
```

---

## parameter_group_parameters

**说明**: 参数组参数 - 参数组中包含的具体参数

**列数**: 3

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `parameter_group_id` | text | parameter_group_id | b7c2d660-23a1-4e9f-aa9a-f5d... |
| `parameter_id` | text | parameter_id | 23bd3ba5-b4ad-4f5b-aa47-326... |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2026-01-26T14:15:27.492966+... |

### SQL CREATE TABLE

```sql
CREATE TABLE parameter_group_parameters (
  parameter_group_id text NOT NULL,
  parameter_id text NOT NULL,
  created_at text NOT NULL,
);
```

---

## parameter_groups

**说明**: 参数组 - 参数的分组管理

**列数**: 5

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | b7c2d660-23a1-4e9f-aa9a-f5d... |
| `name` | text | 名称 - 对象的名称 | 体金属检测参数组 |
| `description` | text | 描述 - 详细说明 | 用于体金属检测站点的measurement参数 |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2026-01-26T14:15:27.492966+... |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2026-01-26T14:15:27.492966+... |

### SQL CREATE TABLE

```sql
CREATE TABLE parameter_groups (
  id text NOT NULL,
  name text NOT NULL,
  description text NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
);
```

---

## parameters

**说明**: 参数 - 工艺参数定义和配置

**列数**: 12

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | 18ddff77-7e8d-4ff6-cc4e-4bb... |
| `name` | text | 名称 - 对象的名称 | 压力 |
| `code` | text | 代码 - 对象的编码 | PRESSURE |
| `unit` | text | unit | Torr |
| `description` | text | 描述 - 详细说明 | 工艺过程中的压力 |
| `type` | text | 类型 - 对象或参数的类型 | process |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2026-01-05T05:32:38.02684+0... |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2026-01-05T05:32:38.02684+0... |
| `parameter_type` | text | parameter_type | process |
| `lower_limit` | unknown | lower_limit | (NULL) |
| `upper_limit` | unknown | upper_limit | (NULL) |
| `target_value` | unknown | target_value | (NULL) |

### SQL CREATE TABLE

```sql
CREATE TABLE parameters (
  id text NOT NULL,
  name text NOT NULL,
  code text NOT NULL,
  unit text NOT NULL,
  description text NOT NULL,
  type text NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
  parameter_type text NOT NULL,
  lower_limit unknown ,
  upper_limit unknown ,
  target_value unknown ,
);
```

---

## process_route_stations

**说明**: 工艺路线站点 - 工艺路线中的站点配置

**列数**: 5

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | 5484aeb3-55ab-49f9-8e29-22f... |
| `route_id` | text | route_id | c82728fb-7ab2-40cd-b4bc-a74... |
| `station_id` | text | station_id | 4fe917ee-9b57-4f56-ad35-5f7... |
| `sequence` | integer | sequence | 1 |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2025-12-22T04:56:46.958892+... |

### SQL CREATE TABLE

```sql
CREATE TABLE process_route_stations (
  id text NOT NULL,
  route_id text NOT NULL,
  station_id text NOT NULL,
  sequence integer NOT NULL,
  created_at text NOT NULL,
);
```

---

## process_routes

**说明**: 工艺路线 - 产品生产的工艺路线

**列数**: 9

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | 3ca95efb-1ddd-4c78-87d4-82f... |
| `code` | text | 代码 - 对象的编码 | ROUTE-B |
| `name` | text | 名称 - 对象的名称 | 快速工艺路径B |
| `description` | text | 描述 - 详细说明 | 产品B的快速生产路径 |
| `version` | integer | version | 1 |
| `status` | text | 状态 - 记录的当前状态 | active |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2025-12-22T04:56:46.380445+... |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2025-12-22T04:56:46.380445+... |
| `path_type` | text | path_type | regular_sub |

### SQL CREATE TABLE

```sql
CREATE TABLE process_routes (
  id text NOT NULL,
  code text NOT NULL,
  name text NOT NULL,
  description text NOT NULL,
  version integer NOT NULL,
  status text NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
  path_type text NOT NULL,
);
```

---

## product_boms

**说明**: 产品 BOM - 产品物料清单

**列数**: 12

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | 98a31401-92eb-42ca-8141-71d... |
| `template_name` | text | template_name | 氮化镓外延片标准BOM |
| `template_code` | text | template_code | GAN-EPI-BOM-STD |
| `product_type` | text | product_type | 氮化镓外延片 |
| `version` | text | version | 1.0 |
| `description` | text | 描述 - 详细说明 | 氮化镓外延片标准生产工艺所需物料清单 |
| `status` | text | 状态 - 记录的当前状态 | active |
| `bom_items` | jsonb | bom_items | [{'id': 'item-gan-001', 'un... |
| `total_amount` | numeric | total_amount | 291.0 |
| `created_by` | text | created_by | 系统管理员 |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2025-12-31T09:33:24.612405+... |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2025-12-31T09:33:24.612405+... |

### SQL CREATE TABLE

```sql
CREATE TABLE product_boms (
  id text NOT NULL,
  template_name text NOT NULL,
  template_code text NOT NULL,
  product_type text NOT NULL,
  version text NOT NULL,
  description text NOT NULL,
  status text NOT NULL,
  bom_items jsonb NOT NULL,
  total_amount numeric NOT NULL,
  created_by text NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
);
```

---

## production_events

**说明**: 生产事件 - 记录生产过程中发生的各类事件

**列数**: 13

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | 3f7671c0-4d75-4966-9b9f-472... |
| `equipment_id` | text | 设备 ID - 关联的生产设备 | E-001 |
| `event_type` | text | event_type | PRODUCTION |
| `product_id` | text | 产品 ID - 关联的产品 | P-005 |
| `shift` | text | shift | A |
| `operator` | text | operator | OP-006 |
| `output_qty` | integer | output_qty | 221 |
| `good_qty` | integer | good_qty | 203 |
| `defect_qty` | integer | defect_qty | 18 |
| `cycle_time` | numeric | cycle_time | 27.19016811789144 |
| `downtime` | numeric | downtime | 1.137196164088714 |
| `timestamp` | text | timestamp | 2025-12-30T00:39:25.638+00:00 |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2026-01-29T01:39:26.154221+... |

### SQL CREATE TABLE

```sql
CREATE TABLE production_events (
  id text NOT NULL,
  equipment_id text NOT NULL,
  event_type text NOT NULL,
  product_id text NOT NULL,
  shift text NOT NULL,
  operator text NOT NULL,
  output_qty integer NOT NULL,
  good_qty integer NOT NULL,
  defect_qty integer NOT NULL,
  cycle_time numeric NOT NULL,
  downtime numeric NOT NULL,
  timestamp text NOT NULL,
  created_at text NOT NULL,
);
```

---

## production_orders

**说明**: 生产订单 - 生产订单主记录

**列数**: 19

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | 99ce16a6-7600-4caf-95c8-4ea... |
| `order_type` | text | order_type | 标准工单 |
| `order_number` | text | order_number | WO-2024-1001 |
| `plan_name` | text | plan_name | 氮化镓外延片生产计划1 |
| `product_ref_id` | text | product_ref_id | 5e25ff87-b797-47bf-a040-aee... |
| `product_name` | text | product_name | 氮化镓外延片 |
| `target_quantity` | integer | target_quantity | 2500 |
| `current_progress` | integer | current_progress | 1200 |
| `start_process_station_code` | unknown | start_process_station_code | (NULL) |
| `end_process_station_code` | unknown | end_process_station_code | (NULL) |
| `start_date` | text | start_date | 2025-01-10T08:00:00+00:00 |
| `end_date` | text | end_date | 2025-01-25T17:00:00+00:00 |
| `status` | text | 状态 - 记录的当前状态 | partially scheduled |
| `priority` | text | priority | high |
| `assigned_operator` | text | assigned_operator | 张三 |
| `notes` | text | notes | 需要特殊工艺处理 |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2025-12-31T01:46:03.034085+... |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2025-12-31T01:46:03.034085+... |
| `bom_items` | jsonb | bom_items | [{'id': 'BOM-ITEM-STATION-G... |

### SQL CREATE TABLE

```sql
CREATE TABLE production_orders (
  id text NOT NULL,
  order_type text NOT NULL,
  order_number text NOT NULL,
  plan_name text NOT NULL,
  product_ref_id text NOT NULL,
  product_name text NOT NULL,
  target_quantity integer NOT NULL,
  current_progress integer NOT NULL,
  start_process_station_code unknown ,
  end_process_station_code unknown ,
  start_date text NOT NULL,
  end_date text NOT NULL,
  status text NOT NULL,
  priority text NOT NULL,
  assigned_operator text NOT NULL,
  notes text NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
  bom_items jsonb NOT NULL,
);
```

---

## products

**说明**: 产品 - 产品信息和规格

**列数**: 19

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `supabase_id` | text | supabase_id | c2ddec11-1e2d-4ff0-bb8f-8dd... |
| `id` | integer | 唯一标识符 - 主键 | 53 |
| `product_code` | text | product_code | 9999-0003 |
| `product_name` | text | product_name | SPCZDF06BA-A625BENNN-SPECIAL |
| `product_category` | text | product_category | Wafer |
| `product_category_version` | text | product_category_version | V3 |
| `product_type` | text | product_type | Silicon |
| `customer_name` | text | customer_name | Customer C |
| `description` | text | 描述 - 详细说明 | 6寸抛光片 |
| `status` | text | 状态 - 记录的当前状态 | ACTIVE |
| `specifications` | jsonb | specifications | {} |
| `process_stations` | jsonb | process_stations | [] |
| `station_sub_path_overrides` | jsonb | station_sub_path_overrides | [] |
| `revision_history` | jsonb | revision_history | [] |
| `experimental_deviation_config` | jsonb | experimental_deviation_config | {} |
| `sub_process_configs` | jsonb | sub_process_configs | [] |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2025-12-30T03:00:13.98413+0... |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2025-12-30T03:00:13.98413+0... |
| `main_process_route_id` | unknown | main_process_route_id | (NULL) |

### SQL CREATE TABLE

```sql
CREATE TABLE products (
  supabase_id text NOT NULL,
  id integer NOT NULL,
  product_code text NOT NULL,
  product_name text NOT NULL,
  product_category text NOT NULL,
  product_category_version text NOT NULL,
  product_type text NOT NULL,
  customer_name text NOT NULL,
  description text NOT NULL,
  status text NOT NULL,
  specifications jsonb NOT NULL,
  process_stations jsonb NOT NULL,
  station_sub_path_overrides jsonb NOT NULL,
  revision_history jsonb NOT NULL,
  experimental_deviation_config jsonb NOT NULL,
  sub_process_configs jsonb NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
  main_process_route_id unknown ,
);
```

---

## quality_records

**说明**: 质量记录 - 存储产品质量测量和检验数据

**列数**: 12

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | de363ad7-2a1b-48e7-afa9-335... |
| `equipment_id` | text | 设备 ID - 关联的生产设备 | E-001 |
| `product_id` | text | 产品 ID - 关联的产品 | P-005 |
| `measurement_type` | text | measurement_type | diameter |
| `measurement_value` | numeric | measurement_value | 9.86 |
| `unit` | text | unit | mm |
| `upper_limit` | numeric | upper_limit | 10.2 |
| `lower_limit` | numeric | lower_limit | 9.8 |
| `status` | text | 状态 - 记录的当前状态 | PASS |
| `shift` | text | shift | A |
| `timestamp` | text | timestamp | 2025-12-30T15:31:29.783+00:00 |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2026-01-29T01:39:30.266218+... |

### SQL CREATE TABLE

```sql
CREATE TABLE quality_records (
  id text NOT NULL,
  equipment_id text NOT NULL,
  product_id text NOT NULL,
  measurement_type text NOT NULL,
  measurement_value numeric NOT NULL,
  unit text NOT NULL,
  upper_limit numeric NOT NULL,
  lower_limit numeric NOT NULL,
  status text NOT NULL,
  shift text NOT NULL,
  timestamp text NOT NULL,
  created_at text NOT NULL,
);
```

---

## query_result_feedback

**说明**: 查询结果反馈 - 查询结果的用户反馈

**列数**: 0


---

## saved_reports

**说明**: 保存的报告 - 用户保存的查询报告

**列数**: 0


---

## schema_column_annotations

**说明**: 列注释 - 数据库列的注释说明

**列数**: 16

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | 3f767ed9-7a60-45e1-abb3-3c9... |
| `table_name` | text | table_name | production_orders |
| `column_name` | text | column_name | order_number |
| `column_name_cn` | text | column_name_cn | 订单编号 |
| `data_type` | text | data_type | varchar |
| `description_cn` | text | description_cn | 唯一的订单编号 |
| `description_en` | text | description_en | Unique order number |
| `example_value` | text | example_value | ORD-2026-001 |
| `business_meaning` | text | business_meaning | 用于识别订单 |
| `value_range` | text | value_range | 6-20 字符 |
| `status` | text | 状态 - 记录的当前状态 | approved |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2026-02-03T05:22:40.570529 |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2026-02-03T05:58:54.200158 |
| `created_by` | text | created_by | system |
| `reviewed_by` | text | reviewed_by | admin |
| `rejection_reason` | unknown | rejection_reason | (NULL) |

### SQL CREATE TABLE

```sql
CREATE TABLE schema_column_annotations (
  id text NOT NULL,
  table_name text NOT NULL,
  column_name text NOT NULL,
  column_name_cn text NOT NULL,
  data_type text NOT NULL,
  description_cn text NOT NULL,
  description_en text NOT NULL,
  example_value text NOT NULL,
  business_meaning text NOT NULL,
  value_range text NOT NULL,
  status text NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
  created_by text NOT NULL,
  reviewed_by text NOT NULL,
  rejection_reason unknown ,
);
```

---

## schema_relation_annotations

**说明**: 关系注释 - 表关系的注释说明

**列数**: 0


---

## schema_table_annotations

**说明**: 表注释 - 数据库表的注释说明

**列数**: 13

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | 82885fc0-7927-46c6-9c65-ef7... |
| `table_name` | text | table_name | production_orders |
| `table_name_cn` | text | table_name_cn | 生产订单 |
| `description_cn` | text | description_cn | 存储来自客户的生产订单信息 |
| `description_en` | text | description_en | Storage for production orde... |
| `business_meaning` | text | business_meaning | 用于跟踪和管理生产计划 |
| `use_case` | text | use_case | 订单录入、生产排期、订单跟踪 |
| `status` | text | 状态 - 记录的当前状态 | approved |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2026-02-03T05:22:39.823575 |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2026-02-03T05:25:00.736031 |
| `created_by` | text | created_by | system |
| `reviewed_by` | text | reviewed_by | admin |
| `rejection_reason` | unknown | rejection_reason | (NULL) |

### SQL CREATE TABLE

```sql
CREATE TABLE schema_table_annotations (
  id text NOT NULL,
  table_name text NOT NULL,
  table_name_cn text NOT NULL,
  description_cn text NOT NULL,
  description_en text NOT NULL,
  business_meaning text NOT NULL,
  use_case text NOT NULL,
  status text NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
  created_by text NOT NULL,
  reviewed_by text NOT NULL,
  rejection_reason unknown ,
);
```

---

## stations

**说明**: 生产站点 - 生产线上的工作站点

**列数**: 27

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | 29e27d65-a29d-46ad-94db-373... |
| `code` | text | 代码 - 对象的编码 | 8602 |
| `name` | text | 名称 - 对象的名称 | 体金属检测 |
| `description` | text | 描述 - 详细说明 | 体金属检测 |
| `workshop` | text | workshop | Lot C |
| `station_type` | text | station_type | measurement |
| `linked_processing_station_id` | jsonb | linked_processing_station_id | [None] |
| `equipment_group` | jsonb | equipment_group | ['MET01'] |
| `tool_group` | text | tool_group | (NULL) |
| `personnel_group` | text | personnel_group | (NULL) |
| `work_standards` | text | work_standards | (NULL) |
| `auto_entry` | unknown | auto_entry | (NULL) |
| `auto_exit` | unknown | auto_exit | (NULL) |
| `entry_form_config` | jsonb | entry_form_config | [] |
| `exit_form_config` | jsonb | exit_form_config | [] |
| `process_rules` | jsonb | process_rules | {} |
| `status` | text | 状态 - 记录的当前状态 | active |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2025-12-22T04:56:45.76814+0... |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2025-12-22T04:56:45.76814+0... |
| `processing_unit` | text | processing_unit | Lot |
| `sub_path_configs` | jsonb | sub_path_configs | [] |
| `entry_basket_group` | text | entry_basket_group | (NULL) |
| `exit_basket_group` | text | exit_basket_group | (NULL) |
| `basket_change_mode` | text | basket_change_mode | (NULL) |
| `parameter_group_ids` | jsonb | parameter_group_ids | ['b7c2d660-23a1-4e9f-aa9a-f... |
| `recipe_id` | unknown | recipe_id | (NULL) |
| `equipment_group_ids` | jsonb | equipment_group_ids | [] |

### SQL CREATE TABLE

```sql
CREATE TABLE stations (
  id text NOT NULL,
  code text NOT NULL,
  name text NOT NULL,
  description text NOT NULL,
  workshop text NOT NULL,
  station_type text NOT NULL,
  linked_processing_station_id jsonb NOT NULL,
  equipment_group jsonb NOT NULL,
  tool_group text NOT NULL,
  personnel_group text NOT NULL,
  work_standards text NOT NULL,
  auto_entry unknown ,
  auto_exit unknown ,
  entry_form_config jsonb NOT NULL,
  exit_form_config jsonb NOT NULL,
  process_rules jsonb NOT NULL,
  status text NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
  processing_unit text NOT NULL,
  sub_path_configs jsonb NOT NULL,
  entry_basket_group text NOT NULL,
  exit_basket_group text NOT NULL,
  basket_change_mode text NOT NULL,
  parameter_group_ids jsonb NOT NULL,
  recipe_id unknown ,
  equipment_group_ids jsonb NOT NULL,
);
```

---

## sub_batch_process_log

**说明**: 子批次工艺日志 - 子批次的工艺过程记录

**列数**: 0


---

## sub_batches

**说明**: 子批次 - 生产批次的细分单位

**列数**: 11

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | 59046524-64af-47be-848e-91f... |
| `batch_id` | text | 批次 ID - 关联的生产批次 | 207b7612-7e5a-4b47-914a-979... |
| `sub_batch_code` | text | sub_batch_code | BATCHHDDTFP-SUB-01 |
| `current_carrier_id` | text | current_carrier_id | e3329d0d-8664-4153-9cfc-b3f... |
| `current_station_id` | text | current_station_id | fca17cd2-e8a4-43c9-893a-631... |
| `total_qty` | integer | total_qty | 25 |
| `good_qty` | integer | good_qty | 25 |
| `defect_qty` | integer | defect_qty | 0 |
| `status` | text | 状态 - 记录的当前状态 | 待进站 |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2025-12-31T03:41:49.221+00:00 |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2025-12-31T03:41:49.221+00:00 |

### SQL CREATE TABLE

```sql
CREATE TABLE sub_batches (
  id text NOT NULL,
  batch_id text NOT NULL,
  sub_batch_code text NOT NULL,
  current_carrier_id text NOT NULL,
  current_station_id text NOT NULL,
  total_qty integer NOT NULL,
  good_qty integer NOT NULL,
  defect_qty integer NOT NULL,
  status text NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
);
```

---

## wafer_carrier_contents

**说明**: 晶圆载体内容 - 晶圆在载体中的位置和状态信息

**列数**: 8

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | a6027b26-de22-49a2-988f-94b... |
| `wafer_id` | text | 晶圆 ID - 关联的晶圆 | 209262ff-38b7-4a0d-9b24-339... |
| `carrier_id` | text | 载体 ID - 关联的装载容器 | e3329d0d-8664-4153-9cfc-b3f... |
| `slot_number` | integer | slot_number | 1 |
| `sub_batch_id` | text | sub_batch_id | 59046524-64af-47be-848e-91f... |
| `wafer_type` | text | wafer_type | GOOD |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2026-01-05T02:47:35.278+00:00 |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2026-01-05T02:47:35.278+00:00 |

### SQL CREATE TABLE

```sql
CREATE TABLE wafer_carrier_contents (
  id text NOT NULL,
  wafer_id text NOT NULL,
  carrier_id text NOT NULL,
  slot_number integer NOT NULL,
  sub_batch_id text NOT NULL,
  wafer_type text NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
);
```

---

## wafer_inspection_results

**说明**: 晶圆检测结果 - 记录晶圆在各站点的检测数据和结果

**列数**: 7

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | 545e8355-cf44-4642-8121-607... |
| `wafer_id_code` | text | wafer_id_code | W-BATCHHDDTFP-01-17 |
| `batch_id` | text | 批次 ID - 关联的生产批次 | 207b7612-7e5a-4b47-914a-979... |
| `station_code` | text | 站点代码 - 生产站点编号 | particleInspection |
| `inspection_data` | jsonb | inspection_data | {'grade': '', 'waferType': ... |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2026-01-09T06:59:42+00:00 |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2026-01-09T06:59:42+00:00 |

### SQL CREATE TABLE

```sql
CREATE TABLE wafer_inspection_results (
  id text NOT NULL,
  wafer_id_code text NOT NULL,
  batch_id text NOT NULL,
  station_code text NOT NULL,
  inspection_data jsonb NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
);
```

---

## wafers

**说明**: 晶圆 - 晶圆基础信息（ID、批次、类型等）

**列数**: 6

### 列定义

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | text | 唯一标识符 - 主键 | 209262ff-38b7-4a0d-9b24-339... |
| `wafer_id_code` | text | wafer_id_code | W-BATCHHDDTFP-01-01 |
| `batch_id` | text | 批次 ID - 关联的生产批次 | 207b7612-7e5a-4b47-914a-979... |
| `initial_product_version` | integer | initial_product_version | 3 |
| `created_at` | text | 创建时间 - 记录创建的时间戳 | 2026-01-05T02:47:35.278+00:00 |
| `updated_at` | text | 更新时间 - 记录最后更新的时间戳 | 2026-01-05T02:47:35.278+00:00 |

### SQL CREATE TABLE

```sql
CREATE TABLE wafers (
  id text NOT NULL,
  wafer_id_code text NOT NULL,
  batch_id text NOT NULL,
  initial_product_version integer NOT NULL,
  created_at text NOT NULL,
  updated_at text NOT NULL,
);
```

---

