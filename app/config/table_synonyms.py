"""
Table Name Synonyms Mapping Configuration
用于识别各种同义词并将其映射到实际的表名

支持两种模式:
  1. 静态模式 (默认): 使用本文件中的 TABLE_SYNONYMS 字典
  2. 数据库模式: 使用 synonym_manager 服务从数据库加载

Example:
  当用户输入"查询片篮"、"查询载具"等时，都能正确映射到 carriers 表
"""

# 表名同义词映射关系
# 格式: {实际表名: [同义词列表]}
TABLE_SYNONYMS = {
    # Carriers (载体/晶圆载体)
    'carriers': [
        'carriers',  # 表名本身
        'carrier',
        '载体',
        '载具',
        '片篮',
        '晶圆载体',
        '装载容器',
        '装载器',
        'wafer_carrier',
        '晶圆篮',
        '脆弱篮',
        'quartz_boat',
        '石英舟',
    ],
    
    # Wafers (晶圆)
    'wafers': [
        'wafers',  # 表名本身
        'wafer',
        '晶圆',
        '晶片',
        '圆片',
        'chip',
        '芯片',
    ],
    
    # Wafer Inspection Results (检测结果)
    'wafer_inspection_results': [
        'wafer_inspection_results',  # 表名本身
        'inspection_result',
        'inspection',
        '检测结果',
        '检测数据',
        '检验结果',
        '测试结果',
        'inspection_data',
    ],
    
    # Batches (批次)
    'batches': [
        'batches',  # 表名本身
        'batch',
        '批次',
        '批',
        'batch_info',
        '生产批次',
        'lot',
    ],
    
    # Equipment (设备)
    'equipment': [
        'equipment',  # 表名本身
        'device',
        '设备',
        '机器',
        '装置',
        'equipment_info',
        'machine',
        'tool',
    ],
    
    # Production (生产)
    'production_records': [
        'production_records',  # 表名本身
        'production',
        '生产',
        '产出',
        '产量',
        'production_data',
        '生产记录',
    ],
    
    # Quality (质量)
    'quality_metrics': [
        'quality_metrics',  # 表名本身
        'quality',
        '质量',
        '良品率',
        '合格率',
        '质量指标',
        'quality_data',
        'yield',
    ],
    
    # Defects (缺陷)
    'defects': [
        'defects',  # 表名本身
        'defect',
        '缺陷',
        '不良',
        '瑕疵',
        '缺陷信息',
        '不良品',
        'failure',
    ],
    
    # Users (用户)
    'users': [
        'users',  # 表名本身
        'user',
        '用户',
        '人员',
        '操作员',
        'operator',
    ],
    
    # Logs (日志)
    'logs': [
        'logs',  # 表名本身
        'log',
        '日志',
        '记录',
        'system_log',
    ],
}

# 反向索引：从同义词映射回实际表名
# 便于快速查找
_SYNONYM_TO_TABLE_CACHE = None


def get_synonym_to_table_map():
    """
    获取同义词到实际表名的映射缓存
    
    Returns:
        dict: {同义词: 实际表名}
    """
    global _SYNONYM_TO_TABLE_CACHE
    
    if _SYNONYM_TO_TABLE_CACHE is None:
        _SYNONYM_TO_TABLE_CACHE = {}
        for table_name, synonyms in TABLE_SYNONYMS.items():
            for synonym in synonyms:
                _SYNONYM_TO_TABLE_CACHE[synonym.lower()] = table_name
    
    return _SYNONYM_TO_TABLE_CACHE


def map_table_name(keyword: str) -> str:
    """
    将关键词映射到实际的表名
    
    Args:
        keyword: 用户输入的表名关键词（如"片篮"、"载具"等）
    
    Returns:
        str: 实际的表名，如未找到则返回原始输入
    
    Example:
        >>> map_table_name('片篮')
        'carriers'
        >>> map_table_name('晶圆')
        'wafers'
        >>> map_table_name('unknown_table')
        'unknown_table'
    """
    synonym_map = get_synonym_to_table_map()
    normalized_keyword = keyword.lower().strip()
    
    return synonym_map.get(normalized_keyword, keyword)


def is_valid_table_name(keyword: str) -> bool:
    """
    检查关键词是否是有效的表名或其同义词
    
    Args:
        keyword: 表名或同义词
    
    Returns:
        bool: 是否是有效的表名或同义词
    
    Example:
        >>> is_valid_table_name('片篮')
        True
        >>> is_valid_table_name('carriers')
        True
        >>> is_valid_table_name('invalid_table')
        False
    """
    synonym_map = get_synonym_to_table_map()
    return keyword.lower().strip() in synonym_map or keyword in TABLE_SYNONYMS


def get_all_table_names() -> list:
    """
    获取所有支持的表名（不含同义词）
    
    Returns:
        list: 实际表名列表
    """
    return list(TABLE_SYNONYMS.keys())


def get_synonyms_for_table(table_name: str) -> list:
    """
    获取某个表的所有同义词
    
    Args:
        table_name: 实际表名
    
    Returns:
        list: 同义词列表（不含表名本身）
    
    Example:
        >>> get_synonyms_for_table('carriers')
        ['carrier', '载体', '载具', '片篮', ...]
    """
    return TABLE_SYNONYMS.get(table_name, [])
