# 快速参考: Schema批注和NL2SQL整合

## 🚀 快速开始

### 1. 检查系统状态
```bash
curl http://localhost:8000/api/schema/status
```

### 2. 查看已批准的元数据
```bash
curl http://localhost:8000/api/schema/metadata | jq .
```

### 3. 测试增强SQL生成
```bash
curl -X POST http://localhost:8000/api/query/nl-to-sql/enhanced \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "查询所有生产订单的订单编号和生产数量"}'
```

---

## 📊 Schema 元数据

### 表 1: production_orders (生产订单)
| 列名 | 中文 | 类型 | 业务含义 |
|------|------|------|---------|
| order_number | 订单编号 | varchar | 用于识别订单 |
| quantity | 生产数量 | integer | 生产任务的规模 |
| status | 订单状态 | varchar | 追踪订单生命周期 |

### 表 2: equipment (设备信息)
| 列名 | 中文 | 类型 | 业务含义 |
|------|------|------|---------|
| equipment_code | 设备编码 | varchar | 设备编码 |
| equipment_type | 设备类型 | varchar | 设备功能分类 |

---

## 🔧 常用API

### Schema API

#### 1. 获取待审核列注解
```bash
curl http://localhost:8000/api/schema/columns/pending
```

#### 2. 批准列注解
```bash
curl -X POST http://localhost:8000/api/schema/columns/{annotation_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"reviewed_by": "admin", "notes": "Approved"}'
```

#### 3. 获取Schema状态
```bash
curl http://localhost:8000/api/schema/status
```

### NL2SQL API

#### 1. 标准转换
```bash
curl -X POST http://localhost:8000/api/query/nl-to-sql \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "查询订单", "use_enhanced": true}'
```

#### 2. 增强转换
```bash
curl -X POST http://localhost:8000/api/query/nl-to-sql/enhanced \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "查询所有待处理的生产订单"}'
```

#### 3. 获取元数据
```bash
curl http://localhost:8000/api/query/schema-metadata
```

#### 4. 刷新元数据
```bash
curl -X POST http://localhost:8000/api/query/schema-metadata/refresh
```

---

## 📝 批准注解脚本

### 使用已提供的批准脚本
```bash
python approve_annotations.py
```

脚本会:
- 自动查找所有待审核的列注解
- 批量批准所有注解
- 验证最终状态

---

## 💡 示例查询

### 查询生产订单
```
自然语言: "显示所有状态为processing的生产订单"
生成SQL: SELECT order_number, quantity, status FROM production_orders WHERE status = 'processing'
```

### 查询设备信息
```
自然语言: "列出所有CNC机器的设备编码"
生成SQL: SELECT equipment_code FROM equipment WHERE equipment_type = 'CNC'
```

### 复杂查询
```
自然语言: "统计每个设备类型的生产订单数量"
生成SQL: SELECT e.equipment_type, COUNT(p.order_number) as count 
         FROM equipment e 
         LEFT JOIN production_orders p ON e.equipment_code = p.equipment_code 
         GROUP BY e.equipment_type
```

---

## ⚙️ 文件位置

| 文件 | 说明 |
|------|------|
| `app/services/nl2sql_enhanced.py` | 增强NL2SQL转换器 |
| `app/routes/schema_routes.py` | Schema API路由 |
| `app/routes/query_routes.py` | NL2SQL API路由 |
| `approve_annotations.py` | 批量批准脚本 |
| `SCHEMA_SCAN_AND_APPROVAL_REPORT.md` | 详细报告 |

---

## 🔍 故障排除

### 问题: 元数据未更新
**解决**: 
```bash
curl -X POST http://localhost:8000/api/query/schema-metadata/refresh
```

### 问题: 待审核注解显示不正确
**解决**: 检查数据库连接
```bash
curl http://localhost:8000/api/schema/status
```

### 问题: 增强SQL生成结果不理想
**解决**: 检查元数据是否正确加载
```bash
curl http://localhost:8000/api/query/schema-metadata | jq '.metadata'
```

---

## 📈 监控和维护

### 定期检查
- 每周检查系统状态
- 监控待审核注解数量
- 验证NL2SQL转换质量

### 更新流程
1. 新增表或列时，自动扫描会生成注解
2. 检查待审核列表
3. 批准所有新注解
4. 刷新元数据缓存

---

**最后更新**: 2026-02-03  
**系统状态**: ✅ 就绪  
**批准注解**: 5/5 完成
