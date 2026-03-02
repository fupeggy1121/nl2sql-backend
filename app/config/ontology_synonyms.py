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
# 本体关系描述两个类之间的业务联系，用于跨表查询的意图识别
# 当用户表达"设备处理的批次"/"批次所在的工艺站"等跨表查询意图时触发

RELATION_SYNONYMS: dict = {

    "semi:hasParentLot": {
        "label_cn": "父批次关联",
        "synonyms": [
            "父批次", "上级批次", "parent lot", "批次溯源",
            "分批来源", "原始批次",
        ],
    },

    "semi:EquipmentProcessesLot": {
        "label_cn": "设备加工批次",
        "synonyms": [
            "设备加工", "批次加工设备", "加工记录",
            "设备处理批次", "哪台设备加工",
        ],
    },

    "semi:LotAtStation": {
        "label_cn": "批次所在站点",
        "synonyms": [
            "批次在哪个站", "当前工序", "当前站点",
            "在制站点", "工序进度",
        ],
    },

    "semi:CarrierContainsWafer": {
        "label_cn": "载具包含晶圆",
        "synonyms": [
            "载具里的晶圆", "片篮中的晶片", "载具装载",
            "晶圆在哪个载具",
        ],
    },

    "semi:WaferBelongsToLot": {
        "label_cn": "晶圆所属批次",
        "synonyms": [
            "晶圆属于哪个批次", "晶圆对应工单",
            "晶圆批次",
        ],
    },

    "semi:ProductUsesRecipe": {
        "label_cn": "产品使用配方",
        "synonyms": [
            "产品配方", "型号对应工艺", "产品工艺配方",
        ],
    },

    "semi:LotFollowsRoute": {
        "label_cn": "批次走工艺路线",
        "synonyms": [
            "批次工艺路线", "工单路线", "工单流程",
            "批次走哪条路线",
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


def get_label_cn(uri: str) -> str:
    """根据 URI 获取中文标签"""
    entry = CLASS_SYNONYMS.get(uri) or RELATION_SYNONYMS.get(uri)
    return entry["label_cn"] if entry else uri


def get_target_type(uri: str) -> str:
    """判断 URI 是类（class）还是关系（relation）"""
    if uri in CLASS_SYNONYMS:
        return "class"
    if uri in RELATION_SYNONYMS:
        return "relation"
    return "unknown"


def get_synonym_to_uri_map() -> dict[str, str]:
    """
    返回 {同义词 → URI} 的完整反向索引（带缓存）。
    同义词已转为小写。

    Example:
        >>> get_synonym_to_uri_map()['设备']
        'semi:Equipment'
        >>> get_synonym_to_uri_map()['lot']
        'semi:ProductionLot'
    """
    global _SYNONYM_TO_URI_CACHE
    if _SYNONYM_TO_URI_CACHE is None:
        _SYNONYM_TO_URI_CACHE = {}
        for uri, info in {**CLASS_SYNONYMS, **RELATION_SYNONYMS}.items():
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
    return results
