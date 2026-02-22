"""
Phase 1 验证：本体加载 + 图模型 + 路径发现
"""
import sys
from pathlib import Path

# 确保项目根在 sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ontology.loader import load_ontology
from app.ontology.model import OntologyGraph

TTL_PATH = ROOT / "app" / "ontology" / "data" / "semi-cim-ontology.ttl"


def _load() -> OntologyGraph:
    return load_ontology(TTL_PATH, force_reload=True)


# ── 1. 基础加载 ──

def test_load_ttl():
    """TTL 文件能正常解析"""
    g = _load()
    assert isinstance(g, OntologyGraph)


def test_class_count():
    """应提取出 14 个 owl:Class (TTL 中定义了 14 个核心类)"""
    g = _load()
    print(f"  Classes ({len(g.classes)}): {sorted(g.classes.keys())}")
    assert len(g.classes) == 14


def test_relation_count():
    """应提取出 ObjectProperty (含 unionOf 展开后可能 > 27)"""
    g = _load()
    unique_uris = set(r.uri for r in g.relations.values())
    print(f"  Unique relation URIs ({len(unique_uris)}): {sorted(unique_uris)}")
    assert len(unique_uris) >= 20  # TTL 中定义了 27 个 ObjectProperty


def test_data_property_count():
    """应提取出 DatatypeProperty + AnnotationProperty"""
    g = _load()
    print(f"  Data properties ({len(g.data_properties)}): {sorted(g.data_properties.keys())}")
    assert len(g.data_properties) >= 3  # hasState, isQualified, hasControlLimit + 2 annotation


# ── 2. 类查找 ──

def test_get_class_by_uri():
    g = _load()
    wafer = g.get_class("semi:Wafer")
    assert wafer is not None
    assert "晶圆" in wafer.label


def test_find_class_by_chinese_label():
    g = _load()
    cls = g.find_class_by_label("晶圆")
    assert cls is not None
    assert cls.uri == "semi:Wafer"


def test_find_class_by_english_label():
    g = _load()
    cls = g.find_class_by_label("Wafer")
    assert cls is not None
    assert cls.uri == "semi:Wafer"


def test_find_class_carrier():
    g = _load()
    cls = g.find_class_by_label("载具")
    assert cls is not None
    assert cls.uri == "semi:Carrier"


def test_find_class_lot():
    g = _load()
    cls = g.find_class_by_label("批次")
    assert cls is not None
    assert "Lot" in cls.uri or "ProductionLot" in cls.uri


def test_find_class_equipment():
    g = _load()
    cls = g.find_class_by_label("设备")
    assert cls is not None
    assert cls.uri == "semi:Equipment"


def test_find_class_station():
    g = _load()
    cls = g.find_class_by_label("工序")
    assert cls is not None
    assert "Station" in cls.uri


# ── 3. 邻接关系 ──

def test_wafer_neighbors():
    """Wafer 应有出边：belongsToLot, locatedInSlot, atStation 等"""
    g = _load()
    neighbors = g.get_neighbors("semi:Wafer")
    rel_uris = [r for r, _ in neighbors]
    print(f"  Wafer outgoing: {rel_uris}")
    assert "semi:belongsToLot" in rel_uris


def test_class_relations():
    """Wafer 的相关关系（出边+入边）"""
    g = _load()
    rels = g.get_class_relations("semi:Wafer")
    rel_labels = [(r.uri, r.label) for r in rels]
    print(f"  Wafer all relations: {rel_labels}")
    assert len(rels) >= 3


def test_lot_has_parent():
    """ProductionLot 应有 hasParentLot 自递归关系"""
    g = _load()
    neighbors = g.get_neighbors("semi:ProductionLot")
    rel_uris = [r for r, _ in neighbors]
    print(f"  ProductionLot outgoing: {rel_uris}")
    assert "semi:hasParentLot" in rel_uris


# ── 4. 路径发现 ──

def test_path_wafer_to_lot():
    """Wafer → ProductionLot: 1 跳 (belongsToLot)"""
    g = _load()
    path = g.find_path("semi:Wafer", "semi:ProductionLot")
    print(f"  Path Wafer→Lot: {path}")
    assert path is not None
    assert len(path) == 1
    assert "belongsToLot" in path[0][1]


def test_path_wafer_to_order():
    """Wafer → ProductionOrder: 2 跳 (Wafer→Lot→Order)"""
    g = _load()
    path = g.find_path("semi:Wafer", "semi:ProductionOrder")
    print(f"  Path Wafer→Order: {path}")
    assert path is not None
    assert len(path) == 2


def test_path_wafer_to_equipment():
    """Wafer → Equipment: 应可达"""
    g = _load()
    path = g.find_path("semi:Wafer", "semi:Equipment")
    print(f"  Path Wafer→Equipment: {path}")
    assert path is not None
    assert len(path) >= 2


def test_path_wafer_to_carrier():
    """Wafer → Carrier: 1-2 跳"""
    g = _load()
    path = g.find_path("semi:Wafer", "semi:Carrier")
    print(f"  Path Wafer→Carrier: {path}")
    assert path is not None
    assert len(path) <= 2


def test_path_same_class():
    """同类路径应返回空列表"""
    g = _load()
    path = g.find_path("semi:Wafer", "semi:Wafer")
    assert path == []


def test_path_unreachable():
    """不存在的类返回 None"""
    g = _load()
    path = g.find_path("semi:Wafer", "semi:NonExistent")
    assert path is None


def test_find_all_paths_wafer_to_station():
    """Wafer → ProcessStation 可能有多条路径"""
    g = _load()
    paths = g.find_all_paths("semi:Wafer", "semi:ProcessStation", max_depth=4)
    print(f"  All paths Wafer→Station ({len(paths)}):")
    for i, p in enumerate(paths):
        print(f"    [{i}] {' → '.join(f'{a} --{r}--> {b}' for a, r, b in p)}")
    assert len(paths) >= 1


def test_find_all_paths_wafer_to_recipe():
    """Wafer → Recipe: 多条路径"""
    g = _load()
    paths = g.find_all_paths("semi:Wafer", "semi:Recipe", max_depth=5)
    print(f"  All paths Wafer→Recipe ({len(paths)}):")
    for i, p in enumerate(paths[:5]):
        print(f"    [{i}] {' → '.join(f'{a} --{r}--> {b}' for a, r, b in p)}")
    assert len(paths) >= 1


# ── 5. 综合 ──

def test_summary():
    g = _load()
    s = g.summary()
    print(f"  Summary: {s}")
    assert s["classes"] == 14
    assert s["label_index_size"] > 0


def test_repr():
    g = _load()
    r = repr(g)
    print(f"  repr: {r}")
    assert "classes=14" in r


if __name__ == "__main__":
    """直接 python 运行，逐个执行测试"""
    import traceback

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for fn in tests:
        name = fn.__name__
        try:
            fn()
            print(f"✅ {name}")
            passed += 1
        except Exception as e:
            print(f"❌ {name}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"Total: {passed + failed} | Passed: {passed} | Failed: {failed}")
