-- ============================================================
-- Migration: class_synonyms (ontology-based synonym table)
-- Safe to run multiple times (IF NOT EXISTS + ON CONFLICT DO NOTHING)
-- Run in Supabase SQL Editor
-- ============================================================

-- 1. DDL -------------------------------------------------------
CREATE TABLE IF NOT EXISTS class_synonyms (
    id              BIGSERIAL PRIMARY KEY,
    target_uri      TEXT NOT NULL,           -- e.g. 'semi:Equipment'
    target_label_cn TEXT,                    -- e.g. '设备'
    target_type     TEXT DEFAULT 'class',    -- 'class' | 'relation'
    synonym         TEXT NOT NULL,           -- e.g. '机台'
    source          TEXT DEFAULT 'builtin',  -- 'builtin' | 'manual' | 'auto'
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    created_by      TEXT DEFAULT 'system',
    UNIQUE (target_uri, synonym)
);

CREATE INDEX IF NOT EXISTS idx_cs_synonym ON class_synonyms (synonym);
CREATE INDEX IF NOT EXISTS idx_cs_uri     ON class_synonyms (target_uri);
CREATE INDEX IF NOT EXISTS idx_cs_active  ON class_synonyms (is_active);

-- 2. Seed: canonical ontology synonyms from ontology_synonyms.py --------
INSERT INTO class_synonyms (target_uri, target_label_cn, target_type, synonym, source, created_by)
VALUES
  ('semi:Equipment', '设备', 'class', '设备', 'builtin', 'system'),
  ('semi:Equipment', '设备', 'class', 'equipment', 'builtin', 'system'),
  ('semi:Equipment', '设备', 'class', '机台', 'builtin', 'system'),
  ('semi:Equipment', '设备', 'class', '机器', 'builtin', 'system'),
  ('semi:Equipment', '设备', 'class', '装置', 'builtin', 'system'),
  ('semi:Equipment', '设备', 'class', '生产设备', 'builtin', 'system'),
  ('semi:Equipment', '设备', 'class', '工具', 'builtin', 'system'),
  ('semi:Equipment', '设备', 'class', 'machine', 'builtin', 'system'),
  ('semi:Equipment', '设备', 'class', 'tool', 'builtin', 'system'),
  ('semi:Equipment', '设备', 'class', 'device', 'builtin', 'system'),
  ('semi:Equipment', '设备', 'class', 'eqp', 'builtin', 'system'),
  ('semi:Equipment', '设备', 'class', '加工设备', 'builtin', 'system'),
  ('semi:Equipment', '设备', 'class', '工艺设备', 'builtin', 'system'),
  ('semi:Equipment', '设备', 'class', '设备信息', 'builtin', 'system'),
  ('semi:Carrier', '载具', 'class', '载具', 'builtin', 'system'),
  ('semi:Carrier', '载具', 'class', '载体', 'builtin', 'system'),
  ('semi:Carrier', '载具', 'class', '片篮', 'builtin', 'system'),
  ('semi:Carrier', '载具', 'class', '晶圆载体', 'builtin', 'system'),
  ('semi:Carrier', '载具', 'class', '石英舟', 'builtin', 'system'),
  ('semi:Carrier', '载具', 'class', 'carrier', 'builtin', 'system'),
  ('semi:Carrier', '载具', 'class', 'quartz_boat', 'builtin', 'system'),
  ('semi:Carrier', '载具', 'class', 'wafer_carrier', 'builtin', 'system'),
  ('semi:Carrier', '载具', 'class', '装载容器', 'builtin', 'system'),
  ('semi:Carrier', '载具', 'class', '晶圆篮', 'builtin', 'system'),
  ('semi:Carrier', '载具', 'class', '装载器', 'builtin', 'system'),
  ('semi:Wafer', '晶圆', 'class', '晶圆', 'builtin', 'system'),
  ('semi:Wafer', '晶圆', 'class', '晶片', 'builtin', 'system'),
  ('semi:Wafer', '晶圆', 'class', '圆片', 'builtin', 'system'),
  ('semi:Wafer', '晶圆', 'class', 'wafer', 'builtin', 'system'),
  ('semi:Wafer', '晶圆', 'class', 'chip', 'builtin', 'system'),
  ('semi:Wafer', '晶圆', 'class', '芯片', 'builtin', 'system'),
  ('semi:Wafer', '晶圆', 'class', '半导体片', 'builtin', 'system'),
  ('semi:Wafer', '晶圆', 'class', '硅片', 'builtin', 'system'),
  ('semi:ProductionLot', '批次', 'class', '批次', 'builtin', 'system'),
  ('semi:ProductionLot', '批次', 'class', 'lot', 'builtin', 'system'),
  ('semi:ProductionLot', '批次', 'class', '生产批次', 'builtin', 'system'),
  ('semi:ProductionLot', '批次', 'class', '生产批', 'builtin', 'system'),
  ('semi:ProductionLot', '批次', 'class', 'batch', 'builtin', 'system'),
  ('semi:ProductionLot', '批次', 'class', 'lot_id', 'builtin', 'system'),
  ('semi:ProductionLot', '批次', 'class', '批号', 'builtin', 'system'),
  ('semi:ProductionLot', '批次', 'class', '流水号', 'builtin', 'system'),
  ('semi:ProductionLot', '批次', 'class', '本地批次', 'builtin', 'system'),
  ('semi:Sublot', '子批次', 'class', '子批次', 'builtin', 'system'),
  ('semi:Sublot', '子批次', 'class', 'sublot', 'builtin', 'system'),
  ('semi:Sublot', '子批次', 'class', '分批', 'builtin', 'system'),
  ('semi:Sublot', '子批次', 'class', 'sub_lot', 'builtin', 'system'),
  ('semi:Sublot', '子批次', 'class', '子批', 'builtin', 'system'),
  ('semi:Sublot', '子批次', 'class', '子工单', 'builtin', 'system'),
  ('semi:Sublot', '子批次', 'class', 'split_lot', 'builtin', 'system'),
  ('semi:Material', '物料', 'class', '物料', 'builtin', 'system'),
  ('semi:Material', '物料', 'class', '耗材', 'builtin', 'system'),
  ('semi:Material', '物料', 'class', 'material', 'builtin', 'system'),
  ('semi:Material', '物料', 'class', '配件', 'builtin', 'system'),
  ('semi:Material', '物料', 'class', '零件', 'builtin', 'system'),
  ('semi:Material', '物料', 'class', '物资', 'builtin', 'system'),
  ('semi:ProcessStation', '工艺站点', 'class', '站点', 'builtin', 'system'),
  ('semi:ProcessStation', '工艺站点', 'class', '工艺站', 'builtin', 'system'),
  ('semi:ProcessStation', '工艺站点', 'class', '工序', 'builtin', 'system'),
  ('semi:ProcessStation', '工艺站点', 'class', 'station', 'builtin', 'system'),
  ('semi:ProcessStation', '工艺站点', 'class', '制程站', 'builtin', 'system'),
  ('semi:ProcessStation', '工艺站点', 'class', 'process_station', 'builtin', 'system'),
  ('semi:ProcessStation', '工艺站点', 'class', '工艺节点', 'builtin', 'system'),
  ('semi:ProcessStation', '工艺站点', 'class', '制程', 'builtin', 'system'),
  ('semi:ProcessStation', '工艺站点', 'class', '操作', 'builtin', 'system'),
  ('semi:ProcessStation', '工艺站点', 'class', 'operation', 'builtin', 'system'),
  ('semi:ProcessStation', '工艺站点', 'class', 'op', 'builtin', 'system'),
  ('semi:ProcessStation', '工艺站点', 'class', '流程节点', 'builtin', 'system'),
  ('semi:Route', '工艺路线', 'class', '工艺路线', 'builtin', 'system'),
  ('semi:Route', '工艺路线', 'class', '路线', 'builtin', 'system'),
  ('semi:Route', '工艺路线', 'class', '流程', 'builtin', 'system'),
  ('semi:Route', '工艺路线', 'class', 'route', 'builtin', 'system'),
  ('semi:Route', '工艺路线', 'class', 'routing', 'builtin', 'system'),
  ('semi:Route', '工艺路线', 'class', '工序流程', 'builtin', 'system'),
  ('semi:Route', '工艺路线', 'class', '工艺流程', 'builtin', 'system'),
  ('semi:Route', '工艺路线', 'class', '产线', 'builtin', 'system'),
  ('semi:Route', '工艺路线', 'class', '流程路线', 'builtin', 'system'),
  ('semi:Route', '工艺路线', 'class', 'process_flow', 'builtin', 'system'),
  ('semi:Route', '工艺路线', 'class', '工单路线', 'builtin', 'system'),
  ('semi:Recipe', '工艺配方', 'class', '配方', 'builtin', 'system'),
  ('semi:Recipe', '工艺配方', 'class', '工艺配方', 'builtin', 'system'),
  ('semi:Recipe', '工艺配方', 'class', 'recipe', 'builtin', 'system'),
  ('semi:Recipe', '工艺配方', 'class', '工艺参数', 'builtin', 'system'),
  ('semi:Recipe', '工艺配方', 'class', '参数配方', 'builtin', 'system'),
  ('semi:Recipe', '工艺配方', 'class', '制程配方', 'builtin', 'system'),
  ('semi:Recipe', '工艺配方', 'class', '加工配方', 'builtin', 'system'),
  ('semi:Product', '产品', 'class', '产品', 'builtin', 'system'),
  ('semi:Product', '产品', 'class', 'product', 'builtin', 'system'),
  ('semi:Product', '产品', 'class', '产品规格', 'builtin', 'system'),
  ('semi:Product', '产品', 'class', '型号', 'builtin', 'system'),
  ('semi:Product', '产品', 'class', '产品型号', 'builtin', 'system'),
  ('semi:Product', '产品', 'class', '品种', 'builtin', 'system'),
  ('semi:Product', '产品', 'class', '品名', 'builtin', 'system'),
  ('semi:ProductModel', '产品模型', 'class', '产品模型', 'builtin', 'system'),
  ('semi:ProductModel', '产品模型', 'class', 'product_model', 'builtin', 'system'),
  ('semi:ProductModel', '产品模型', 'class', 'product model', 'builtin', 'system'),
  ('semi:ProductModel', '产品模型', 'class', '产品规格模板', 'builtin', 'system'),
  ('semi:ProductModel', '产品模型', 'class', '产品设计', 'builtin', 'system'),
  ('semi:RawMaterial', '原料', 'class', '原料', 'builtin', 'system'),
  ('semi:RawMaterial', '原料', 'class', '原材料', 'builtin', 'system'),
  ('semi:RawMaterial', '原料', 'class', 'raw_material', 'builtin', 'system'),
  ('semi:RawMaterial', '原料', 'class', 'rawmaterial', 'builtin', 'system'),
  ('semi:RawMaterial', '原料', 'class', '生产原料', 'builtin', 'system'),
  ('semi:RawMaterial', '原料', 'class', '基材', 'builtin', 'system'),
  ('semi:Auxiliary', '辅料', 'class', '辅料', 'builtin', 'system'),
  ('semi:Auxiliary', '辅料', 'class', '辅助材料', 'builtin', 'system'),
  ('semi:Auxiliary', '辅料', 'class', 'auxiliary', 'builtin', 'system'),
  ('semi:Auxiliary', '辅料', 'class', 'aux_material', 'builtin', 'system'),
  ('semi:Auxiliary', '辅料', 'class', '耗材', 'builtin', 'system'),
  ('semi:Auxiliary', '辅料', 'class', '工艺耗材', 'builtin', 'system'),
  ('semi:SparePart', '备件', 'class', '备件', 'builtin', 'system'),
  ('semi:SparePart', '备件', 'class', 'spare_part', 'builtin', 'system'),
  ('semi:SparePart', '备件', 'class', 'sparepart', 'builtin', 'system'),
  ('semi:SparePart', '备件', 'class', '备用零件', 'builtin', 'system'),
  ('semi:SparePart', '备件', 'class', '维修备件', 'builtin', 'system'),
  ('semi:SparePart', '备件', 'class', '替换件', 'builtin', 'system'),
  ('semi:ProductionOrder', '生产工单', 'class', '工单', 'builtin', 'system'),
  ('semi:ProductionOrder', '生产工单', 'class', '生产工单', 'builtin', 'system'),
  ('semi:ProductionOrder', '生产工单', 'class', 'production_order', 'builtin', 'system'),
  ('semi:ProductionOrder', '生产工单', 'class', 'wo', 'builtin', 'system'),
  ('semi:ProductionOrder', '生产工单', 'class', '制造工单', 'builtin', 'system'),
  ('semi:ProductionOrder', '生产工单', 'class', '生产指令', 'builtin', 'system'),
  ('semi:ProductionOrder', '生产工单', 'class', 'mo', 'builtin', 'system'),
  ('semi:Action', '生产动作/操作', 'class', '动作', 'builtin', 'system'),
  ('semi:Action', '生产动作/操作', 'class', '操作', 'builtin', 'system'),
  ('semi:Action', '生产动作/操作', 'class', '生产事件', 'builtin', 'system'),
  ('semi:Action', '生产动作/操作', 'class', 'action', 'builtin', 'system'),
  ('semi:Action', '生产动作/操作', 'class', 'event', 'builtin', 'system'),
  ('semi:Action', '生产动作/操作', 'class', '工艺操作', 'builtin', 'system'),
  ('semi:Action', '生产动作/操作', 'class', '生产记录', 'builtin', 'system'),
  ('semi:Action', '生产动作/操作', 'class', '过站记录', 'builtin', 'system'),
  ('semi:Action', '生产动作/操作', 'class', '加工记录', 'builtin', 'system'),
  ('semi:Action', '生产动作/操作', 'class', 'alarm', 'builtin', 'system'),
  ('semi:Action', '生产动作/操作', 'class', '告警', 'builtin', 'system'),
  ('semi:Action', '生产动作/操作', 'class', '生产日志', 'builtin', 'system'),
  ('semi:BOM', '物料清单', 'class', 'BOM', 'builtin', 'system'),
  ('semi:BOM', '物料清单', 'class', 'bom', 'builtin', 'system'),
  ('semi:BOM', '物料清单', 'class', '物料清单', 'builtin', 'system'),
  ('semi:BOM', '物料清单', 'class', '产品BOM', 'builtin', 'system'),
  ('semi:BOM', '物料清单', 'class', 'bill_of_materials', 'builtin', 'system'),
  ('semi:BOM', '物料清单', 'class', '配料单', 'builtin', 'system'),
  ('semi:BOM', '物料清单', 'class', '工艺BOM', 'builtin', 'system'),
  ('semi:BOM', '物料清单', 'class', '产品物料清单', 'builtin', 'system'),
  ('semi:belongsToLot', '晶圆属于批次', 'relation', '晶圆属于哪个批次', 'builtin', 'system'),
  ('semi:belongsToLot', '晶圆属于批次', 'relation', '晶圆对应工单', 'builtin', 'system'),
  ('semi:belongsToLot', '晶圆属于批次', 'relation', '晶圆批次', 'builtin', 'system'),
  ('semi:belongsToLot', '晶圆属于批次', 'relation', '晶圆归属批次', 'builtin', 'system'),
  ('semi:belongsToLot', '晶圆属于批次', 'relation', 'wafer属于哪个lot', 'builtin', 'system'),
  ('semi:belongsToSublot', '晶圆属于子批次', 'relation', '晶圆属于子批次', 'builtin', 'system'),
  ('semi:belongsToSublot', '晶圆属于子批次', 'relation', '晶圆对应子批次', 'builtin', 'system'),
  ('semi:belongsToSublot', '晶圆属于子批次', 'relation', 'wafer的sublot', 'builtin', 'system'),
  ('semi:locatedInSlot', '晶圆位于载具槽位', 'relation', '晶圆在哪个载具', 'builtin', 'system'),
  ('semi:locatedInSlot', '晶圆位于载具槽位', 'relation', '载具里的晶圆', 'builtin', 'system'),
  ('semi:locatedInSlot', '晶圆位于载具槽位', 'relation', '片篮中的晶片', 'builtin', 'system'),
  ('semi:locatedInSlot', '晶圆位于载具槽位', 'relation', '载具装载晶圆', 'builtin', 'system'),
  ('semi:locatedInSlot', '晶圆位于载具槽位', 'relation', '晶圆在哪个片篮', 'builtin', 'system'),
  ('semi:atStation', '当前所处工序', 'relation', '当前工序', 'builtin', 'system'),
  ('semi:atStation', '当前所处工序', 'relation', '当前站点', 'builtin', 'system'),
  ('semi:atStation', '当前所处工序', 'relation', '在制工序', 'builtin', 'system'),
  ('semi:atStation', '当前所处工序', 'relation', '批次在哪个站', 'builtin', 'system'),
  ('semi:atStation', '当前所处工序', 'relation', '工序进度', 'builtin', 'system'),
  ('semi:atStation', '当前所处工序', 'relation', '当前制程', 'builtin', 'system'),
  ('semi:atStation', '当前所处工序', 'relation', '在哪个工序', 'builtin', 'system'),
  ('semi:currentlyOnRoute', '当前工艺路径', 'relation', '当前工艺路线', 'builtin', 'system'),
  ('semi:currentlyOnRoute', '当前工艺路径', 'relation', '晶圆走哪条路线', 'builtin', 'system'),
  ('semi:currentlyOnRoute', '当前工艺路径', 'relation', '初始化路径', 'builtin', 'system'),
  ('semi:basedOnOrder', '批次基于工单创建', 'relation', '批次对应工单', 'builtin', 'system'),
  ('semi:basedOnOrder', '批次基于工单创建', 'relation', '这个批次属于哪个工单', 'builtin', 'system'),
  ('semi:basedOnOrder', '批次基于工单创建', 'relation', '批次来自哪个工单', 'builtin', 'system'),
  ('semi:basedOnOrder', '批次基于工单创建', 'relation', '工单下的批次', 'builtin', 'system'),
  ('semi:containsSublot', '批次包含子批次', 'relation', '批次包含哪些子批', 'builtin', 'system'),
  ('semi:containsSublot', '批次包含子批次', 'relation', '批次分拆的子批次', 'builtin', 'system'),
  ('semi:containsSublot', '批次包含子批次', 'relation', '子批次列表', 'builtin', 'system'),
  ('semi:isCarriedBy', '子批次由载具承载', 'relation', '子批次在哪个载具', 'builtin', 'system'),
  ('semi:isCarriedBy', '子批次由载具承载', 'relation', '载具承载的子批次', 'builtin', 'system'),
  ('semi:hasParentLot', '父批次(溯源)', 'relation', '父批次', 'builtin', 'system'),
  ('semi:hasParentLot', '父批次(溯源)', 'relation', '上级批次', 'builtin', 'system'),
  ('semi:hasParentLot', '父批次(溯源)', 'relation', 'parent lot', 'builtin', 'system'),
  ('semi:hasParentLot', '父批次(溯源)', 'relation', '批次溯源', 'builtin', 'system'),
  ('semi:hasParentLot', '父批次(溯源)', 'relation', '分批来源', 'builtin', 'system'),
  ('semi:hasParentLot', '父批次(溯源)', 'relation', '原始批次', 'builtin', 'system'),
  ('semi:usesRoute', '产品使用工艺路线', 'relation', '产品走哪条路线', 'builtin', 'system'),
  ('semi:usesRoute', '产品使用工艺路线', 'relation', '型号对应工艺路线', 'builtin', 'system'),
  ('semi:usesRoute', '产品使用工艺路线', 'relation', '产品工艺路径', 'builtin', 'system'),
  ('semi:usesRoute', '产品使用工艺路线', 'relation', '产品模型工序流程', 'builtin', 'system'),
  ('semi:consistsOfStation', '路线包含工序节点', 'relation', '路线包含哪些工序', 'builtin', 'system'),
  ('semi:consistsOfStation', '路线包含工序节点', 'relation', '工艺路径中的工序', 'builtin', 'system'),
  ('semi:consistsOfStation', '路线包含工序节点', 'relation', '路线的工序列表', 'builtin', 'system'),
  ('semi:requiresEquipment', '工序需要设备执行', 'relation', '工序需要哪台设备', 'builtin', 'system'),
  ('semi:requiresEquipment', '工序需要设备执行', 'relation', '工序指定设备', 'builtin', 'system'),
  ('semi:requiresEquipment', '工序需要设备执行', 'relation', '这个工序用哪个机台', 'builtin', 'system'),
  ('semi:hostsRecipe', '设备驻留配方', 'relation', '设备运行哪个配方', 'builtin', 'system'),
  ('semi:hostsRecipe', '设备驻留配方', 'relation', '机台驻留配方', 'builtin', 'system'),
  ('semi:hostsRecipe', '设备驻留配方', 'relation', '设备对应工艺配方', 'builtin', 'system'),
  ('semi:hasBOM', '产品关联BOM定义', 'relation', '产品BOM', 'builtin', 'system'),
  ('semi:hasBOM', '产品关联BOM定义', 'relation', '产品物料清单', 'builtin', 'system'),
  ('semi:hasBOM', '产品关联BOM定义', 'relation', '型号对应耗材', 'builtin', 'system'),
  ('semi:hasBOM', '产品关联BOM定义', 'relation', '产品物料', 'builtin', 'system'),
  ('semi:consumesRawMaterial', 'BOM消耗原料', 'relation', '消耗原料', 'builtin', 'system'),
  ('semi:consumesRawMaterial', 'BOM消耗原料', 'relation', 'BOM用哪些原料', 'builtin', 'system'),
  ('semi:consumesRawMaterial', 'BOM消耗原料', 'relation', '原料消耗明细', 'builtin', 'system'),
  ('semi:consumesAuxiliary', 'BOM消耗辅料', 'relation', '消耗辅料', 'builtin', 'system'),
  ('semi:consumesAuxiliary', 'BOM消耗辅料', 'relation', 'BOM用哪些辅料', 'builtin', 'system'),
  ('semi:consumesAuxiliary', 'BOM消耗辅料', 'relation', '耗材明细', 'builtin', 'system'),
  ('semi:requiresSparePart', '设备需要备件', 'relation', '设备需要哪种备件', 'builtin', 'system'),
  ('semi:requiresSparePart', '设备需要备件', 'relation', '维修备件', 'builtin', 'system'),
  ('semi:requiresSparePart', '设备需要备件', 'relation', '设备备件清单', 'builtin', 'system'),
  ('semi:hasInput', '动作输入对象', 'relation', '动作处理对象', 'builtin', 'system'),
  ('semi:hasInput', '动作输入对象', 'relation', '这次操作对象', 'builtin', 'system'),
  ('semi:hasInput', '动作输入对象', 'relation', '加工的批次或晶圆', 'builtin', 'system'),
  ('semi:hasOutput', '动作输出结果', 'relation', '动作产出', 'builtin', 'system'),
  ('semi:hasOutput', '动作输出结果', 'relation', '操作结果', 'builtin', 'system'),
  ('semi:hasOutput', '动作输出结果', 'relation', '加工后的批次或晶圆', 'builtin', 'system')
ON CONFLICT (target_uri, synonym) DO NOTHING;

-- 3. Migrate legacy table_synonyms → class_synonyms -------------------
--    Crosswalk maps Demo_Fab v1 physical table names → semi: URIs
INSERT INTO class_synonyms (target_uri, target_label_cn, target_type, synonym, source, created_by)
SELECT
    CASE ts.table_name
        WHEN 'wafers'                   THEN 'semi:Wafer'
        WHEN 'batches'                  THEN 'semi:ProductionLot'
        WHEN 'carriers'                 THEN 'semi:Carrier'
        WHEN 'equipment'                THEN 'semi:Equipment'
        WHEN 'process_steps'            THEN 'semi:ProcessStation'
        WHEN 'stations'                 THEN 'semi:ProcessStation'
        WHEN 'recipes'                  THEN 'semi:Recipe'
        WHEN 'sub_batches'              THEN 'semi:Sublot'
        WHEN 'production_orders'        THEN 'semi:ProductionOrder'
        WHEN 'products'                 THEN 'semi:Product'
        WHEN 'product_boms'             THEN 'semi:BOM'
        WHEN 'process_routes'           THEN 'semi:Route'
        WHEN 'batch_events'             THEN 'semi:Action'
        WHEN 'alarms'                   THEN 'semi:Action'
        WHEN 'defect_records'           THEN 'semi:Wafer'
        WHEN 'maintenance_records'      THEN 'semi:Equipment'
        WHEN 'production_records'       THEN 'semi:ProductionLot'
        WHEN 'quality_records'          THEN 'semi:Wafer'
        WHEN 'wafer_inspection_results' THEN 'semi:Wafer'
        ELSE NULL
    END                                                          AS target_uri,
    CASE ts.table_name
        WHEN 'wafers'                   THEN '晶圆'
        WHEN 'batches'                  THEN '批次'
        WHEN 'carriers'                 THEN '载具'
        WHEN 'equipment'                THEN '设备'
        WHEN 'process_steps'            THEN '工艺站点'
        WHEN 'stations'                 THEN '工艺站点'
        WHEN 'recipes'                  THEN '工艺配方'
        WHEN 'sub_batches'              THEN '子批次'
        WHEN 'production_orders'        THEN '生产工单'
        WHEN 'products'                 THEN '产品'
        WHEN 'product_boms'             THEN '物料清单'
        WHEN 'process_routes'           THEN '工艺路线'
        WHEN 'batch_events'             THEN '生产动作/事件'
        WHEN 'alarms'                   THEN '告警/动作'
        WHEN 'defect_records'           THEN '晶圆缺陷记录'
        WHEN 'maintenance_records'      THEN '设备维护记录'
        WHEN 'production_records'       THEN '生产记录'
        WHEN 'quality_records'          THEN '质量记录'
        WHEN 'wafer_inspection_results' THEN '晶圆检测结果'
        ELSE ts.table_name
    END                                                          AS target_label_cn,
    'class'                                                      AS target_type,
    ts.synonym                                                   AS synonym,
    COALESCE(ts.source, 'builtin')                               AS source,
    COALESCE(ts.created_by, 'migration')                         AS created_by
FROM table_synonyms ts
WHERE
    ts.synonym IS NOT NULL
    AND ts.synonym != ''
    AND (
        CASE ts.table_name
            WHEN 'wafers'                   THEN 'semi:Wafer'
            WHEN 'batches'                  THEN 'semi:ProductionLot'
            WHEN 'carriers'                 THEN 'semi:Carrier'
            WHEN 'equipment'                THEN 'semi:Equipment'
            WHEN 'process_steps'            THEN 'semi:ProcessStation'
            WHEN 'stations'                 THEN 'semi:ProcessStation'
            WHEN 'recipes'                  THEN 'semi:Recipe'
            WHEN 'sub_batches'              THEN 'semi:Sublot'
            WHEN 'production_orders'        THEN 'semi:ProductionOrder'
            WHEN 'products'                 THEN 'semi:Product'
            WHEN 'product_boms'             THEN 'semi:BOM'
            WHEN 'process_routes'           THEN 'semi:Route'
            WHEN 'batch_events'             THEN 'semi:Action'
            WHEN 'alarms'                   THEN 'semi:Action'
            WHEN 'defect_records'           THEN 'semi:Wafer'
            WHEN 'maintenance_records'      THEN 'semi:Equipment'
            WHEN 'production_records'       THEN 'semi:ProductionLot'
            WHEN 'quality_records'          THEN 'semi:Wafer'
            WHEN 'wafer_inspection_results' THEN 'semi:Wafer'
            ELSE NULL
        END
    ) IS NOT NULL
ON CONFLICT (target_uri, synonym) DO NOTHING;

-- 4. Verify result -------------------------------------------------
SELECT target_uri, target_label_cn, target_type, COUNT(*) AS cnt
FROM class_synonyms
GROUP BY target_uri, target_label_cn, target_type
ORDER BY target_type, target_uri;
