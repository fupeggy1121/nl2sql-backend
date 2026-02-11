# 数据库学习指南

## 📚 快速参考

### 最常用的 5 张表
1. **quality_records** (6,200 行) - 质量检验数据
2. **wafer_inspection_results** (7,113 行) - 晶圆检测结果
3. **batches** - 生产批次
4. **stations** - 生产站点
5. **products** - 产品信息

### 查询复杂度等级

**低** (适合初学者)
- SELECT * FROM quality_records LIMIT 10
- SELECT COUNT(*) FROM batches
- SELECT * FROM stations WHERE name LIKE '%'

**中** (需要理解关系)
- 批次到子批次的查询
- 站点到生产事件的关联
- 产品到质量记录的统计

**高** (需要业务逻辑)
- OEE 指标计算
- 多层级的生产流程追踪
- 质量趋势分析跨时间序列

## 🎯 常见 NL2SQL 查询模式

### 统计查询
- "各站点的生产数量统计"
- "最近7天的质量记录"
- "设备故障次数排名"

### 趋势查询
- "质量检测合格率趋势"
- "设备 OEE 变化"
- "产品产量变化"

### 关联查询
- "查找某批次的所有检测结果"
- "显示某产品的所有质量记录"
- "统计各设备的故障情况"

## 📊 表设计特点

### 时间序列类表
- quality_records, production_events, oee_records
- 特点: 大数据量、频繁查询、需要分组统计
- 优化: 按时间分区查询、使用索引

### 主数据表
- products, stations, equipment, batches
- 特点: 变更频率低、维度清晰、常用于GROUP BY
- 用途: 维度表、统计基础

### 关系表
- wafer_carrier_contents, parameter_group_parameters
- 特点: 记录多对多关系、数据量中等
- 用途: 关联查询、关系验证

## 💡 实用查询技巧

1. **了解数据分布**
   - SELECT COUNT(*) FROM quality_records GROUP BY status

2. **时间范围查询**
   - WHERE created_at >= NOW() - INTERVAL '7 days'

3. **防止笛卡尔积**
   - 明确使用 INNER JOIN 而不是 WHERE 条件

4. **聚合查询性能**
   - 先过滤再分组，使用 HAVING 而不是 WHERE

## 🔍 故障排查

- 数据为空: 检查时间范围和过滤条件
- 查询慢: 检查是否需要添加索引或修改联接条件
- 数据不匹配: 验证外键关系是否正确建立
