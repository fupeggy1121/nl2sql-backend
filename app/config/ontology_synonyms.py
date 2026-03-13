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
            "operation", "op", "流程节点",
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

    "semi:Action": {
        "label_cn": "生产动作/操作",
        "synonyms": [
            "动作", "操作", "生产事件", "action", "event",
            "工艺操作", "生产记录", "过站记录", "加工记录",
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

    "semi:locatedInSlot": {
        "label_cn": "晶圆位于载具槽位",
        "domain": "semi:Wafer", "range": "semi:Carrier",
        "synonyms": [
            "晶圆在哪个载具", "载具里的晶圆", "片篮中的晶片",
            "载具装载晶圆", "晶圆在哪个片篮",
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
    "semi:usesRoute": {
        "label_cn": "产品使用工艺路线",
        "domain": "semi:ProductModel", "range": "semi:Route",
        "synonyms": [
            "产品走哪条路线", "型号对应工艺路线",
            "产品工艺路径", "产品模型工序流程",
        ],
    },

    "semi:consistsOfStation": {
        "label_cn": "路线包含工序节点",
        "domain": "semi:Route", "range": "semi:ProcessStation",
        "synonyms": [
            "路线包含哪些工序", "工艺路径中的工序", "路线的工序列表",
        ],
    },

    "semi:requiresEquipment": {
        "label_cn": "工序需要设备执行",
        "domain": "semi:ProcessStation", "range": "semi:Equipment",
        "synonyms": [
            "工序需要哪台设备", "工序指定设备", "这个工序用哪个机台",
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

    # 2.5 动作驱动
    "semi:hasInput": {
        "label_cn": "动作输入对象",
        "domain": "semi:Action", "range": "semi:ProductionLot | semi:Wafer",
        "synonyms": [
            "动作处理对象", "这次操作对象", "加工的批次或晶圆",
        ],
    },

    "semi:hasOutput": {
        "label_cn": "动作输出结果",
        "domain": "semi:Action", "range": "semi:ProductionLot | semi:Wafer",
        "synonyms": [
            "动作产出", "操作结果", "加工后的批次或晶圆",
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
            "不良代码", "不良原因", "ng_code", "NG码", "NG代码",
            "不良类型", "缺陷代码", "缺陷原因", "缺陷类型",
            "不良品原因", "ng原因", "不良分类", "不良定义",
            "报废原因", "报废代码",
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
        "domain": "semi:ProductionLot",
        "physical_column": "status",
        "synonyms": [
            "状态", "批次状态", "当前状态", "status",
            "生产状态", "在制状态",
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
