"""
本体类同义词配置 (Ontology Class Synonyms)

同义词指向本体类 URI（如 semi:Equipment）或本体关系 URI（如 semi:hasParentLot），
不直接绑定物理表名。物理表的解析由映射字典（mapping_prod.json / mapping_demo_fab.json）
在运行时完成，实现不同客户环境下的无缝切换。

数据结构:
  CLASS_SYNONYMS   — 本体类 URI → { label_cn, synonyms: [词, ...] }
  RELATION_SYNONYMS — 本体关系 URI → { label_cn, synonyms: [词, ...] }

维护原则:
  - 本文件只维护"叫法"，不关心物理表名
  - 用户添加的同义词持久化到 class_synonyms 数据库表
  - 本文件作为静态兜底，当数据库不可用时生效
"""

# ─── 本体类同义词 ──────────────────────────────────────────────────────────────
# 每个 URI 对应半导体 CIM 本体中的一个领域对象类

CLASS_SYNONYMS: dict = {

    "semi:Equipment": {
        "label_cn": "设备",
        "synonyms": [
            "设备", "equipment", "机台", "机器", "装置", "生产设备",
            "工具", "machine", "tool", "device", "eqp",
            "加工设备", "工艺设备", "设备信息",
        ],
    },

    "semi:Carrier": {
        "label_cn": "载具",
        "synonyms": [
            "载具", "载体", "片篮", "晶圆载体", "石英舟",
            "carrier", "quartz_boat", "wafer_carrier",
            "装载容器", "晶圆篮", "装载器",
        ],
    },

    "semi:Wafer": {
        "label_cn": "晶圆",
        "synonyms": [
            "晶圆", "晶片", "圆片", "wafer", "chip",
            "芯片", "半导体片", "硅片",
        ],
    },

    "semi:ProductionLot": {
        "label_cn": "批次",
        "synonyms": [
            "批次", "lot", "生产批次", "生产批",
            "batch", "lot_id", "批号", "流水号", "本地批次",
            # 注意："在制品"/"在制"/"wip" 已移至 WIP 过滤器推断路径
            # （_auto_wip_filter + WIP→Wafer class 注入），不在此作 class 匹配
        ],
    },

    "semi:Sublot": {
        "label_cn": "子批次",
        "synonyms": [
            "子批次", "sublot", "分批", "sub_lot",
            "子批", "子工单", "split_lot",
        ],
    },

    "semi:Material": {
        "label_cn": "物料",
        "synonyms": [
            "物料", "耗材", "material", "配件", "零件", "物资",
        ],
    },

    "semi:ProcessStation": {
        "label_cn": "工艺站点",
        "synonyms": [
            "站点", "工艺站", "工序", "station", "制程站",
            "process_station", "工艺节点", "制程", "操作",
            "operation", "流程节点",
            "工站",  # 用户口语写法
        ],
    },

    "semi:Route": {
        "label_cn": "工艺路线",
        "synonyms": [
            "工艺路线", "路线", "流程", "route", "routing",
            "工序流程", "工艺流程", "产线", "流程路线",
            "process_flow", "工单路线",
        ],
    },

    "semi:Recipe": {
        "label_cn": "工艺配方",
        "synonyms": [
            "配方", "工艺配方", "recipe", "工艺参数",
            "参数配方", "制程配方", "加工配方",
        ],
    },

    "semi:Product": {
        "label_cn": "产品",
        "synonyms": [
            "产品", "product", "产品规格", "型号", "产品型号",
            "品种", "品名",
        ],
    },

    "semi:ProductModel": {
        "label_cn": "产品模型",
        "synonyms": [
            "产品模型", "product_model", "product model",
            "产品规格模板", "产品设计",
        ],
    },

    "semi:RawMaterial": {
        "label_cn": "原料",
        "synonyms": [
            "原料", "原材料", "raw_material", "rawmaterial",
            "生产原料", "基材",
            # 外延生长场景：衬底即原料
            "衬底", "衬底片", "基板", "substrate", "衬底原料",
        ],
    },

    "semi:Auxiliary": {
        "label_cn": "辅料",
        "synonyms": [
            "辅料", "辅助材料", "auxiliary", "aux_material",
            "耗材", "工艺耗材",
        ],
    },

    "semi:SparePart": {
        "label_cn": "备件",
        "synonyms": [
            "备件", "spare_part", "sparepart", "备用零件",
            "维修备件", "替换件",
        ],
    },

    "semi:ProductionOrder": {
        "label_cn": "生产工单",
        "synonyms": [
            "工单", "生产工单", "production_order", "wo",
            "制造工单", "生产指令", "mo",
        ],
    },

    "semi:HoldEventRecord": {
        "label_cn": "批次扣留记录",
        "synonyms": [
            "扣留记录", "扣留操作记录", "扣留日志", "扣留历史",
            "hold记录", "hold日志", "hold操作", "hold历史",
            "批次hold记录", "批次扣留历史",
            "holdrecord", "holdeventrecord",
        ],
    },

    "semi:ReleaseEventRecord": {
        "label_cn": "批次释放记录",
        "synonyms": [
            "释放记录", "释放操作记录", "释放日志", "释放历史",
            "release记录", "release日志", "release操作",
            "批次release记录", "批次释放历史",
            "releaserecord", "releaseeventrecord",
        ],
    },

    "semi:SplitEventRecord": {
        "label_cn": "拆批记录",
        "synonyms": [
            "拆批记录", "拆批操作记录", "拆批日志", "拆批历史",
            "拆批", "每次拆批", "拆批时", "拆批操作",
            "split记录", "split日志", "split操作",
            "批次拆批记录",
            "splitrecord", "spliteventrecord",
        ],
    },

    "semi:OpenLotEventRecord": {
        "label_cn": "开批操作执行记录",
        "synonyms": [
            "开批", "投料", "投料开批", "开批记录", "开批历史", "开批操作记录",
            "投料记录", "投料开批记录", "新批次创建", "批次开批",
            "开工单", "投片", "投片记录", "批次投料",
            "openlot", "open_lot", "openloteventrecord",
        ],
    },

    "semi:CreateLocalLotEventRecord": {
        "label_cn": "本地批次创建记录",
        "synonyms": [
            "本地批次创建", "本地开批", "本地投料", "半成品投料",
            "创建本地批次", "本地批次投片", "代工投料",
            "createlocalloteventrecord", "create_local_lot",
        ],
    },

    "semi:ProductionEventRecord": {
        "label_cn": "生产事件记录",
        "synonyms": [
            "批次操作记录", "生产事件记录", "操作日志",
            "批次日志", "批次事件日志", "批次历史记录",
            "所有操作记录", "全部事件记录",
            "production_event_log", "resume_log",
            "operationlog", "eventrecord",
        ],
    },

    "semi:CheckInEventRecord": {
        "label_cn": "批次进站记录",
        "synonyms": [
            "进站记录", "进站历史", "进站操作记录", "进站日志",
            "入站记录", "入站历史", "check-in记录", "checkin记录",
            "进站事件", "进站事件记录", "批次进站",
            "过站记录", "过站历史", "所有过站记录", "过站操作",
            "checkinrecord", "checkineventrecord",
        ],
    },

    "semi:CheckOutEventRecord": {
        "label_cn": "批次出站记录",
        "synonyms": [
            "出站记录", "出站历史", "出站操作记录", "出站日志",
            "check-out记录", "checkout记录",
            "出站事件", "出站事件记录", "批次出站",
            "过站记录", "过站历史", "所有过站记录", "过站操作",
            "checkoutrecord", "checkouteventrecord",
        ],
    },

    "semi:MeasurementPassRecord": {
        "label_cn": "量测录入事件记录",
        "synonyms": [
            "量测录入事件", "量测录入", "量测事件",
            "量测操作", "参数录入事件",
            "measurementpassrecord",
        ],
    },

    "semi:WaferMeasurementSnapshot": {
        "label_cn": "晶圆量测参数快照",
        "synonyms": [
            "量测快照", "量测数据", "量测结果", "量测参数",
            "量测记录", "制程参数", "制程参数记录", "参数采集记录",
            "measurement记录", "参数过站", "量测过站",
            "process_measure_data", "量测参数记录", "制程参数采集",
            "参数快照", "量测参数数据", "量测值",
            "wafermeasurementsnapshot",
            # 常用参数项名称（具体参数词出现时直接路由到量测表）
            "TTV", "测山尘小差", "Bow", "弓高", "WARP", "翠曲",
            "WARP", "RES-CEN", "电阻率", "参数项",
            "参数值", "参数超限", "参数大于", "参数小于",
            "参数超标", "超出阈値", "阈値过滤",
        ],
    },

    "semi:ParamDefinition": {
        "label_cn": "参数定义",
        "synonyms": [
            "参数规格", "参数模型", "param_model",
            "参数元数据", "参数定义实体",
            "paramdefinition",
        ],
    },

    "semi:HoldEventRecord": {
        "label_cn": "批次扣留记录",
        "synonyms": [
            "扣留记录", "hold记录", "批次扣留", "扣留操作记录",
            "扣留历史", "扣留日志", "holdeventrecord",
        ],
    },

    "semi:ReleaseEventRecord": {
        "label_cn": "批次释放记录",
        "synonyms": [
            "释放记录", "release记录", "批次释放", "取消扣留记录",
            "释放操作记录", "释放历史", "releaseeventrecord",
        ],
    },

    "semi:NGRecordEventRecord": {
        "label_cn": "不良录入记录",
        "synonyms": [
            "不良录入", "不良记录", "NG记录", "不良标记记录",
            "不良操作记录", "报废记录", "不良晶圆记录",
            "ngrecord", "ng录入", "ngrecordeventrecord",
        ],
    },

    "semi:WaferTransitionSnapshot": {
        "label_cn": "晶圆迁移快照（不良明细）",
        "synonyms": [
            # 不良统计/分析类查询 — 该表含 ng_code / ng_reason / wafer_type 列
            "不良原因", "不良类型", "不良原因统计", "不良类型统计",
            "不良分析", "不良分布", "各不良原因", "各不良类型",
            "缺陷原因", "缺陷类型", "缺陷分析", "缺陷分布",
            "不良代码统计", "不良码统计", "ng原因", "ng类型",
            "不良明细", "晶圆不良明细", "不良晶圆明细",
        ],
    },

    "semi:MergeEventRecord": {
        "label_cn": "并批记录",
        "synonyms": [
            "并批记录", "合批记录", "并批操作记录", "并批历史",
            "merge记录", "mergeeventrecord",
        ],
    },

    "semi:AccumulateEventRecord": {
        "label_cn": "攒批记录",
        "synonyms": [
            "攒批记录", "攒批操作记录", "攒批历史",
            "accumulate记录", "accumulateeventrecord",
        ],
    },

    "semi:InboundRequest": {
        "label_cn": "入库申请单",
        "synonyms": [
            "入库申请单", "入库申请", "入库请求单", "申请入库",
            "入库申购单", "物料入库申请", "入库申请主单",
            "inboundrequest", "inbound_request", "warehouse_input_bill",
        ],
    },

    "semi:InboundRequestDetail": {
        "label_cn": "入库申请明细",
        "synonyms": [
            "入库申请明细", "入库申请行", "申请入库明细",
            "入库申请行项", "入库申购明细",
            "inboundrequestdetail", "inbound_request_detail", "warehouse_input_bill_detail",
        ],
    },

    "semi:OutboundRequest": {
        "label_cn": "出库申请单",
        "synonyms": [
            "出库申请单", "出库申请", "出库请求单", "申请出库",
            "领料申请单", "出库申请主单", "出库单申请",
            "outboundrequest", "outbound_request", "warehouse_output_bill",
        ],
    },

    "semi:OutboundRequestDetail": {
        "label_cn": "出库申请明细",
        "synonyms": [
            "出库申请明细", "出库申请行", "申请出库明细",
            "出库申请行项", "领料申请明细",
            "outboundrequestdetail", "outbound_request_detail", "warehouse_output_bill_detail",
        ],
    },

    "semi:InboundBillRecord": {
        "label_cn": "入库记录单",
        "synonyms": [
            "入库单", "入库记录单", "入库实绩单", "入库凭证",
            "仓库入库单", "物料入库单", "入库单据", "入库记录票",
            "inboundbillrecord", "inbound_bill_record", "warehouse_input_record_bill",
        ],
    },

    "semi:MaterialInboundSnapshot": {
        "label_cn": "入库快照",
        "synonyms": [
            "入库", "入库记录", "入库明细", "入库记录明细", "入库操作记录",
            "入库快照", "入库快照明细",
            "入库日志", "入库历史", "物料入库记录", "入库行项",
            "入库数量", "入库统计", "入库汇总", "入库总量", "入库排名",
            "materialinbounddetail", "inbound_detail", "warehouse_input_record_bill_detail",
        ],
    },

    "semi:OutboundBillRecord": {
        "label_cn": "出库记录单",
        "synonyms": [
            "出库单", "出库记录单", "出库凭证", "出库单据",
            "仓库出库单", "物料出库单", "出库实绩单", "出库记录票",
            "outboundbillrecord", "outbound_bill_record", "warehouse_output_record_bill",
        ],
    },

    "semi:MaterialOutboundSnapshot": {
        "label_cn": "出库快照",
        "synonyms": [
            "出库", "出库记录", "出库明细", "出库记录明细", "出库操作记录",
            "出库快照", "出库快照明细",
            "出库日志", "出库历史", "物料出库记录",
            "领料记录", "出库单明细", "出库行项",
            "出库数量", "出库统计", "出库汇总", "出库总量", "出库排名",
            "materialoutbounddetail", "outbound_detail", "warehouse_output_record_bill_detail",
        ],
    },

    "semi:Action": {
        "label_cn": "生产动作/操作",
        "synonyms": [
            "动作", "操作", "生产事件", "action", "event",
            "工艺操作", "加工记录",
            "alarm", "告警", "生产日志",
        ],
    },

    "semi:BOM": {
        "label_cn": "物料清单",
        "synonyms": [
            "BOM", "bom", "物料清单", "产品BOM",
            "bill_of_materials", "配料单", "工艺BOM",
            "产品物料清单",
        ],
    },

    # ── 仓库域 ────────────────────────────────────────────────────────────────
    "semi:WarehouseLocation": {
        "label_cn": "库位",
        "synonyms": [
            "仓库", "库位", "仓位", "储位", "库区",
            "仓储位置", "存储位置", "货位", "库位分布",
            "各仓库", "各库位", "每个仓库", "所有仓库",
            "warehouse", "warehouse_location", "warehouse_model",
        ],
    },

    "semi:MaterialBatch": {
        "label_cn": "物料批次（在库批次）",
        "synonyms": [
            # 注意: "批次"/"lot"/"batch"/"批号" 属于 MES semi:ProductionLot，不在此列
            # MaterialBatch 表示 WMS 域的物料实例，也是唯一映射 warehouse_inventory 的类
            "物料批次", "物料实例", "物料批",
            "来料批次", "入库批次", "在库批次",
            # 库存相关词：MaterialBatch = warehouse_inventory，即"在库物料批次"
            "库存", "库存明细", "库存分布", "库存情况", "库存数量",
            "库存明细记录", "在库物料", "在库量", "在库数", "库存清单",
            "物料库存", "当前库存", "实时库存", "库存快照",
            "material_batch", "inventory", "warehouse_inventory",
        ],
    },

    "semi:WarehouseEvent": {
        "label_cn": "库存管理事件",
        "synonyms": [
            "库存事件", "仓库事件", "出入库事件",
            "warehouse_event", "wms_event",
        ],
    },

    "semi:WarehouseEventRecord": {
        "label_cn": "库存管理事件记录",
        "synonyms": [
            "库存记录", "仓库记录", "出入库记录",
            "warehouse_record",
        ],
    },
}


# ─── 本体关系同义词 ────────────────────────────────────────────────────────────
# 对应 semi-cim-ontology.ttl 中定义的 owl:ObjectProperty
# URI 与 TTL 实际属性名完全一致

RELATION_SYNONYMS: dict = {

    # 2.1 Wafer 核心状态向量
    "semi:belongsToLot": {
        "label_cn": "晶圆属于批次",
        "domain": "semi:Wafer", "range": "semi:ProductionLot",
        "synonyms": [
            "晶圆属于哪个批次", "晶圆对应工单", "晶圆批次",
            "晶圆归属批次", "wafer属于哪个lot",
        ],
    },

    "semi:belongsToSublot": {
        "label_cn": "晶圆属于子批次",
        "domain": "semi:Wafer", "range": "semi:Sublot",
        "synonyms": [
            "晶圆属于子批次", "晶圆对应子批次", "wafer的sublot",
        ],
    },

    "semi:atStation": {
        "label_cn": "当前所处工序",
        "domain": "semi:Wafer", "range": "semi:ProcessStation",
        "synonyms": [
            "当前工序", "当前站点", "在制工序", "批次在哪个站",
            "工序进度", "当前制程", "在哪个工序",
        ],
    },

    "semi:currentlyOnRoute": {
        "label_cn": "当前工艺路径",
        "domain": "semi:Wafer", "range": "semi:Route",
        "synonyms": [
            "当前工艺路线", "晶圆走哪条路线", "初始化路径",
        ],
    },

    # 2.2 生产管理层级
    "semi:basedOnOrder": {
        "label_cn": "批次基于工单创建",
        "domain": "semi:ProductionLot", "range": "semi:ProductionOrder",
        "synonyms": [
            "批次对应工单", "这个批次属于哪个工单",
            "批次来自哪个工单", "工单下的批次",
        ],
    },

    "semi:containsSublot": {
        "label_cn": "批次包含子批次",
        "domain": "semi:ProductionLot", "range": "semi:Sublot",
        "synonyms": [
            "批次包含哪些子批", "批次分拆的子批次", "子批次列表",
        ],
    },

    "semi:isCarriedBy": {
        "label_cn": "子批次由载具承载",
        "domain": "semi:Sublot", "range": "semi:Carrier",
        "synonyms": [
            "子批次在哪个载具", "载具承载的子批次",
        ],
    },

    "semi:hasParentLot": {
        "label_cn": "父批次(溯源)",
        "domain": "semi:ProductionLot", "range": "semi:ProductionLot",
        "synonyms": [
            "父批次", "上级批次", "parent lot", "批次溯源",
            "分批来源", "原始批次",
        ],
    },

    # 2.3 工艺约束注入
    "semi:consistsOfStation": {
        "label_cn": "路线包含工序节点",
        "domain": "semi:Route", "range": "semi:ProcessStation",
        "synonyms": [
            "路线包含哪些工序", "工艺路径中的工序", "路线的工序列表",
        ],
    },

    "semi:hostsRecipe": {
        "label_cn": "设备驻留配方",
        "domain": "semi:Equipment", "range": "semi:Recipe",
        "synonyms": [
            "设备运行哪个配方", "机台驻留配方", "设备对应工艺配方",
        ],
    },

    # 2.4 物料与BOM
    "semi:hasBOM": {
        "label_cn": "产品关联BOM定义",
        "domain": "semi:ProductModel", "range": "semi:BOM",
        "synonyms": [
            "产品BOM", "产品物料清单", "型号对应耗材", "产品物料",
        ],
    },

    "semi:consumesRawMaterial": {
        "label_cn": "BOM消耗原料",
        "domain": "semi:BOM", "range": "semi:RawMaterial",
        "synonyms": [
            "消耗原料", "BOM用哪些原料", "原料消耗明细",
        ],
    },

    "semi:consumesAuxiliary": {
        "label_cn": "BOM消耗辅料",
        "domain": "semi:BOM", "range": "semi:Auxiliary",
        "synonyms": [
            "消耗辅料", "BOM用哪些辅料", "耗材明细",
        ],
    },

    "semi:requiresSparePart": {
        "label_cn": "设备需要备件",
        "domain": "semi:Equipment", "range": "semi:SparePart",
        "synonyms": [
            "设备需要哪种备件", "维修备件", "设备备件清单",
        ],
    },

}


# ─── 本体数据属性同义词 ─────────────────────────────────────────────────────────
# DatatypeProperty：同义词命中后触发 WHERE 列过滤，而非 JOIN
# 每条记录格式：URI → { label_cn, domain, physical_column, synonyms }

PROPERTY_SYNONYMS: dict = {

    # ── Wafer 数据属性 ──
    "semi:hasNGCode": {
        "label_cn": "不良代码",
        "domain": "semi:Wafer",
        "physical_column": "ng_code",
        "synonyms": [
            "不良代码", "ng_code", "NG码", "NG代码",
            "缺陷代码", "报废代码",
        ],
    },

    "semi:hasWaferCode": {
        "label_cn": "晶圆编号",
        "domain": "semi:Wafer",
        "physical_column": "wafer_code",
        "synonyms": [
            "晶圆编号", "wafer_code", "wafer编号", "晶圆号",
            "晶圆码", "片号", "晶片编号",
        ],
    },

    "semi:hasSlotNo": {
        "label_cn": "槽位号",
        "domain": "semi:Wafer",
        "physical_column": "slot_no",
        "synonyms": [
            "槽位", "槽位号", "slot_no", "slot号", "slot",
            "装载位置", "载具槽位",
        ],
    },

    "semi:waferLevel": {
        "label_cn": "晶圆质量等级",
        "domain": "semi:Wafer",
        "physical_column": "level",
        "synonyms": [
            "晶圆等级", "质量等级", "wafer等级", "wafer_level",
            "品质等级", "晶圆级别", "ok片", "ng片",
            "良品", "不良品", "loss片", "sample片",
        ],
    },

    # ── 批次数据属性 ──
    "semi:hasLotCode": {
        "label_cn": "批次号",
        "domain": "semi:ProductionLot",
        "physical_column": "current_lot_code",
        "synonyms": [
            "批次号", "批号", "lot_code", "lot号", "批次编号",
            "工单批次号", "生产批号",
        ],
    },

    "semi:hasState": {
        "label_cn": "状态",
        "domain": "semi:Material",
        "physical_column": "status",
        "synonyms": [
            "状态", "批次状态", "当前状态", "status",
            "生产状态", "在制状态",
            "物料状态", "启用状态", "停用状态",
        ],
    },

    "semi:hasProductCode": {
        "label_cn": "产品型号",
        "domain": "semi:ProductionLot",
        "physical_column": "product_code",
        "synonyms": [
            "产品型号", "产品编码", "product_code", "型号",
            "品种", "产品代码",
        ],
    },

    "semi:hasRecipeCode": {
        "label_cn": "配方号",
        "domain": "semi:ProductionLot",
        "physical_column": "recipe_code",
        "synonyms": [
            "配方号", "工艺配方号", "recipe_code", "配方编号",
            "制程配方号",
        ],
    },

    "semi:hasCarrierCode": {
        "label_cn": "载具编号",
        "domain": "semi:ProductionLot",
        "physical_column": "carrier_code",
        "synonyms": [
            "载具编号", "片篮编号", "carrier_code", "载具号",
            "石英舟编号", "载体编号",
        ],
    },

    # ── Material 物料大类/小类数据属性 ──
    "semi:hasMaterialCategory": {
        "label_cn": "物料大类",
        "domain": "semi:Material",
        "physical_column": "type",
        "synonyms": [
            "物料大类", "物料类别", "物料类型", "物料分类",
            "material_category", "material_class",
        ],
    },

    "semi:hasMaterialType": {
        "label_cn": "物料小类",
        "domain": "semi:Material",
        "physical_column": "material_type",
        "synonyms": [
            "物料小类", "物料子类型", "物料子类", "材料小类",
            "material_type", "material_subtype",
        ],
    },

    "semi:hasMaterialCode": {
        "label_cn": "物料编码",
        "domain": "semi:Material",
        "physical_column": "material_no",
        "synonyms": [
            "物料编码", "物料编号", "物料号", "物料代码",
            "material_no", "material_code", "物料主编号",
        ],
    },

    "semi:hasMaterialName": {
        "label_cn": "物料名称",
        "domain": "semi:Material",
        "physical_column": "material_name",
        "synonyms": [
            "物料名称", "物料名", "物料品名", "原料名称",
            "material_name", "物料描述名",
        ],
    },

    "semi:hasMaterialSpec": {
        "label_cn": "物料规格",
        "domain": "semi:Material",
        "physical_column": "material_spec",
        "synonyms": [
            "物料规格", "规格", "规格型号", "料件规格",
            "material_spec", "spec",
        ],
    },

    "semi:hasUnit": {
        "label_cn": "计量单位",
        "domain": "semi:Material",
        "physical_column": "unit",
        "synonyms": [
            "单位", "计量单位", "物料单位", "数量单位",
            "unit", "unit_name",
        ],
    },

    "semi:hasBatchMgmt": {
        "label_cn": "批次管理",
        "domain": "semi:Material",
        "physical_column": "extra->>'$.warehouseBatch'",
        "synonyms": [
            "批次管理", "是否启用批次管理", "启用批次",
            "warehouseBatch", "batch_mgmt",
        ],
    },

    "semi:hasUniqueCodeMgmt": {
        "label_cn": "唯一码管理",
        "domain": "semi:Material",
        "physical_column": "extra->>'$.warehouseUniqueCode'",
        "synonyms": [
            "唯一码管理", "是否启用唯一码", "启用唯一码", "逐件管理",
            "warehouseUniqueCode", "unique_code_mgmt",
        ],
    },
}


# ─── 辅助函数 ──────────────────────────────────────────────────────────────────

_SYNONYM_TO_URI_CACHE: dict | None = None
_URI_TO_LABEL_CACHE: dict | None = None


def get_all_class_uris() -> list[str]:
    """返回所有已定义的本体类 URI 列表"""
    return list(CLASS_SYNONYMS.keys())


def get_all_relation_uris() -> list[str]:
    """返回所有已定义的本体关系 URI 列表"""
    return list(RELATION_SYNONYMS.keys())


def get_all_property_uris() -> list[str]:
    """返回所有已定义的数据属性 URI 列表"""
    return list(PROPERTY_SYNONYMS.keys())


def get_label_cn(uri: str) -> str:
    """根据 URI 获取中文标签"""
    entry = CLASS_SYNONYMS.get(uri) or RELATION_SYNONYMS.get(uri) or PROPERTY_SYNONYMS.get(uri)
    return entry["label_cn"] if entry else uri


def get_target_type(uri: str) -> str:
    """判断 URI 是类（class）、关系（relation）还是数据属性（data_property）"""
    if uri in CLASS_SYNONYMS:
        return "class"
    if uri in RELATION_SYNONYMS:
        return "relation"
    if uri in PROPERTY_SYNONYMS:
        return "data_property"
    return "unknown"


def get_synonym_to_uri_map() -> dict[str, str]:
    """
    返回 {同义词 → URI} 的完整反向索引（带缓存）。
    覆盖 class / relation / data_property 三类。同义词已转为小写。

    Example:
        >>> get_synonym_to_uri_map()['设备']
        'semi:Equipment'
        >>> get_synonym_to_uri_map()['不良代码']
        'semi:hasNGCode'
    """
    global _SYNONYM_TO_URI_CACHE
    if _SYNONYM_TO_URI_CACHE is None:
        _SYNONYM_TO_URI_CACHE = {}
        for uri, info in {**CLASS_SYNONYMS, **RELATION_SYNONYMS, **PROPERTY_SYNONYMS}.items():
            for syn in info.get("synonyms", []):
                _SYNONYM_TO_URI_CACHE[syn.lower()] = uri
    return _SYNONYM_TO_URI_CACHE


def map_keyword_to_uri(keyword: str) -> str | None:
    """
    将关键词映射到本体类/关系 URI，未命中返回 None。

    Example:
        >>> map_keyword_to_uri('批次')
        'semi:ProductionLot'
        >>> map_keyword_to_uri('unknown')
        None
    """
    return get_synonym_to_uri_map().get(keyword.lower().strip())


def get_all_synonyms_flat() -> list[dict]:
    """
    返回扁平化同义词列表（用于静态兜底初始化）。
    每条记录格式与 class_synonyms 数据库表字段对应。
    """
    results = []
    for uri, info in CLASS_SYNONYMS.items():
        for syn in info.get("synonyms", []):
            results.append({
                "id": None,
                "target_uri": uri,
                "target_label_cn": info["label_cn"],
                "target_type": "class",
                "synonym": syn,
                "source": "builtin",
                "is_active": True,
                "created_at": None,
                "created_by": "system",
            })
    for uri, info in RELATION_SYNONYMS.items():
        for syn in info.get("synonyms", []):
            results.append({
                "id": None,
                "target_uri": uri,
                "target_label_cn": info["label_cn"],
                "target_type": "relation",
                "synonym": syn,
                "source": "builtin",
                "is_active": True,
                "created_at": None,
                "created_by": "system",
            })
    for uri, info in PROPERTY_SYNONYMS.items():
        for syn in info.get("synonyms", []):
            results.append({
                "id": None,
                "target_uri": uri,
                "target_label_cn": info["label_cn"],
                "target_type": "data_property",
                "synonym": syn,
                "source": "builtin",
                "is_active": True,
                "created_at": None,
                "created_by": "system",
            })
    return results
