-- 数据库 Schema SQL 参考
-- 生成时间: 2026-02-11 09:46:10

-- ==================== 统计查询 ====================

-- 查看所有表的行数
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- ==================== 表查询示例 ====================

-- annotation_audit_log: 注释审计日志 - 注释修改的审计记录
SELECT COUNT(*) FROM annotation_audit_log;
SELECT * FROM annotation_audit_log LIMIT 5;

-- approved_schema_metadata: 批准的元数据 - 经过审批的数据库架构元数据
SELECT COUNT(*) FROM approved_schema_metadata;
SELECT * FROM approved_schema_metadata LIMIT 5;

-- batch_remarks: 批次备注 - 批次的备注说明
SELECT COUNT(*) FROM batch_remarks;
SELECT * FROM batch_remarks LIMIT 5;

-- batches: 批次 - 生产批次主记录
SELECT COUNT(*) FROM batches;
SELECT * FROM batches LIMIT 5;

-- carriers: 载体 - 晶圆载体的基础信息
SELECT COUNT(*) FROM carriers;
SELECT * FROM carriers LIMIT 5;

-- chat_messages: 聊天消息 - NL2SQL 对话系统的消息记录
SELECT COUNT(*) FROM chat_messages;
SELECT * FROM chat_messages LIMIT 5;

-- chat_sessions: 聊天会话 - NL2SQL 对话会话管理
SELECT COUNT(*) FROM chat_sessions;
SELECT * FROM chat_sessions LIMIT 5;

-- custom_process_rules: 自定义工艺规则 - 用户自定义的生产规则
SELECT COUNT(*) FROM custom_process_rules;
SELECT * FROM custom_process_rules LIMIT 5;

-- equipment: 设备 - 生产设备信息
SELECT COUNT(*) FROM equipment;
SELECT * FROM equipment LIMIT 5;

-- equipment_groups: 设备组 - 设备的分组管理
SELECT COUNT(*) FROM equipment_groups;
SELECT * FROM equipment_groups LIMIT 5;

-- feedback: 用户反馈 - 用户对系统的反馈
SELECT COUNT(*) FROM feedback;
SELECT * FROM feedback LIMIT 5;

-- intent_feedback: 意图反馈 - NL2SQL 意图识别的反馈
SELECT COUNT(*) FROM intent_feedback;
SELECT * FROM intent_feedback LIMIT 5;

-- oee_records: OEE 记录 - 设备综合效率记录
SELECT COUNT(*) FROM oee_records;
SELECT * FROM oee_records LIMIT 5;

-- parameter_equipment: 参数设备关联 - 参数与设备的关联关系
SELECT COUNT(*) FROM parameter_equipment;
SELECT * FROM parameter_equipment LIMIT 5;

-- parameter_group_parameters: 参数组参数 - 参数组中包含的具体参数
SELECT COUNT(*) FROM parameter_group_parameters;
SELECT * FROM parameter_group_parameters LIMIT 5;

-- parameter_groups: 参数组 - 参数的分组管理
SELECT COUNT(*) FROM parameter_groups;
SELECT * FROM parameter_groups LIMIT 5;

-- parameters: 参数 - 工艺参数定义和配置
SELECT COUNT(*) FROM parameters;
SELECT * FROM parameters LIMIT 5;

-- process_route_stations: 工艺路线站点 - 工艺路线中的站点配置
SELECT COUNT(*) FROM process_route_stations;
SELECT * FROM process_route_stations LIMIT 5;

-- process_routes: 工艺路线 - 产品生产的工艺路线
SELECT COUNT(*) FROM process_routes;
SELECT * FROM process_routes LIMIT 5;

-- product_boms: 产品 BOM - 产品物料清单
SELECT COUNT(*) FROM product_boms;
SELECT * FROM product_boms LIMIT 5;

-- production_events: 生产事件 - 记录生产过程中发生的各类事件
SELECT COUNT(*) FROM production_events;
SELECT * FROM production_events LIMIT 5;

-- production_orders: 生产订单 - 生产订单主记录
SELECT COUNT(*) FROM production_orders;
SELECT * FROM production_orders LIMIT 5;

-- products: 产品 - 产品信息和规格
SELECT COUNT(*) FROM products;
SELECT * FROM products LIMIT 5;

-- quality_records: 质量记录 - 存储产品质量测量和检验数据
SELECT COUNT(*) FROM quality_records;
SELECT * FROM quality_records LIMIT 5;

-- query_result_feedback: 查询结果反馈 - 查询结果的用户反馈
SELECT COUNT(*) FROM query_result_feedback;
SELECT * FROM query_result_feedback LIMIT 5;

-- saved_reports: 保存的报告 - 用户保存的查询报告
SELECT COUNT(*) FROM saved_reports;
SELECT * FROM saved_reports LIMIT 5;

-- schema_column_annotations: 列注释 - 数据库列的注释说明
SELECT COUNT(*) FROM schema_column_annotations;
SELECT * FROM schema_column_annotations LIMIT 5;

-- schema_relation_annotations: 关系注释 - 表关系的注释说明
SELECT COUNT(*) FROM schema_relation_annotations;
SELECT * FROM schema_relation_annotations LIMIT 5;

-- schema_table_annotations: 表注释 - 数据库表的注释说明
SELECT COUNT(*) FROM schema_table_annotations;
SELECT * FROM schema_table_annotations LIMIT 5;

-- stations: 生产站点 - 生产线上的工作站点
SELECT COUNT(*) FROM stations;
SELECT * FROM stations LIMIT 5;

-- sub_batch_process_log: 子批次工艺日志 - 子批次的工艺过程记录
SELECT COUNT(*) FROM sub_batch_process_log;
SELECT * FROM sub_batch_process_log LIMIT 5;

-- sub_batches: 子批次 - 生产批次的细分单位
SELECT COUNT(*) FROM sub_batches;
SELECT * FROM sub_batches LIMIT 5;

-- wafer_carrier_contents: 晶圆载体内容 - 晶圆在载体中的位置和状态信息
SELECT COUNT(*) FROM wafer_carrier_contents;
SELECT * FROM wafer_carrier_contents LIMIT 5;

-- wafer_inspection_results: 晶圆检测结果 - 记录晶圆在各站点的检测数据和结果
SELECT COUNT(*) FROM wafer_inspection_results;
SELECT * FROM wafer_inspection_results LIMIT 5;

-- wafers: 晶圆 - 晶圆基础信息（ID、批次、类型等）
SELECT COUNT(*) FROM wafers;
SELECT * FROM wafers LIMIT 5;

