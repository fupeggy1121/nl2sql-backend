"""
本体模块配置
"""
from pathlib import Path

# 本体数据目录
ONTOLOGY_DATA_DIR = Path(__file__).parent / "data"

# 默认 TTL 本体文件
DEFAULT_TTL_PATH = ONTOLOGY_DATA_DIR / "semi-cim-ontology.ttl"

# 本体 namespace 前缀
SEMI_NS = "http://www.semanticweb.org/semi-mes/ontology#"

# 缓存策略：是否在首次加载后缓存本体图
CACHE_ONTOLOGY = True

# 路径发现最大深度（防止递归关系无限展开）
MAX_PATH_DEPTH = 10
