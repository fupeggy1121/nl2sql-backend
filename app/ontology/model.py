"""
本体内存图模型

数据类定义 + OntologyGraph 查询接口。
提供类/属性索引、BFS 路径发现、中文标签匹配。
"""
from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .config import MAX_PATH_DEPTH

logger = logging.getLogger(__name__)


# ── 数据类 ──────────────────────────────────────────────

@dataclass
class OntologyClass:
    """本体类（如 semi:Wafer）"""
    uri: str                          # e.g. "semi:Wafer"
    label: str = ""                   # rdfs:label, e.g. "晶圆(Wafer)"
    comment: str = ""                 # rdfs:comment
    parent_uri: str = ""              # rdfs:subClassOf（直接父类）


@dataclass
class OntologyProperty:
    """数据属性（如 semi:hasState）"""
    uri: str
    label: str = ""
    comment: str = ""
    domain_uris: List[str] = field(default_factory=list)   # 可多域（unionOf）
    range_type: str = ""              # xsd:string, xsd:boolean, etc.


@dataclass
class OntologyRelation:
    """对象属性/关系（如 semi:belongsToLot）"""
    uri: str
    label: str = ""
    comment: str = ""
    domain_uri: str = ""              # 起点类 URI
    range_uri: str = ""               # 终点类 URI


# ── 本体图 ──────────────────────────────────────────────

class OntologyGraph:
    """
    本体的内存图表示，支持：
    - 按 URI / 中文标签查找类
    - BFS 最短路径发现（class → class）
    - 获取某类所有直接关系
    """

    def __init__(self):
        # URI → 对象
        self.classes: Dict[str, OntologyClass] = {}
        self.relations: Dict[str, OntologyRelation] = {}
        self.data_properties: Dict[str, OntologyProperty] = {}

        # 邻接表: class_uri → [(relation_uri, target_class_uri)]
        self._adj: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        # 反向邻接: target_class_uri → [(relation_uri, source_class_uri)]
        self._adj_rev: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

        # 中文标签索引: 中文关键词 → class_uri (小写去括号)
        self._label_index: Dict[str, str] = {}

    # ── 构建 ──

    def add_class(self, cls: OntologyClass) -> None:
        self.classes[cls.uri] = cls
        self._index_label(cls.uri, cls.label)

    def add_relation(self, rel: OntologyRelation) -> None:
        self.relations[rel.uri] = rel
        if rel.domain_uri and rel.range_uri:
            self._adj[rel.domain_uri].append((rel.uri, rel.range_uri))
            self._adj_rev[rel.range_uri].append((rel.uri, rel.domain_uri))
        self._index_label(rel.uri, rel.label)

    def add_data_property(self, prop: OntologyProperty) -> None:
        self.data_properties[prop.uri] = prop

    def _index_label(self, uri: str, label: str) -> None:
        """索引中文/英文标签关键词"""
        if not label:
            return
        # "晶圆(Wafer)" → ["晶圆", "wafer"]
        clean = label.replace("(", " ").replace(")", " ").replace("（", " ").replace("）", " ")
        for token in clean.split():
            token_lower = token.strip().lower()
            if token_lower:
                self._label_index[token_lower] = uri

    # ── 查询 ──

    def get_class(self, uri: str) -> Optional[OntologyClass]:
        return self.classes.get(uri)

    def get_relation(self, uri: str) -> Optional[OntologyRelation]:
        return self.relations.get(uri)

    def find_class_by_label(self, keyword: str) -> Optional[OntologyClass]:
        """中文/英文关键词模糊查找类"""
        keyword_lower = keyword.strip().lower()
        # 精确匹配
        uri = self._label_index.get(keyword_lower)
        if uri and uri in self.classes:
            return self.classes[uri]
        # 子串匹配
        for label_key, uri in self._label_index.items():
            if keyword_lower in label_key or label_key in keyword_lower:
                if uri in self.classes:
                    return self.classes[uri]
        return None

    def get_neighbors(self, class_uri: str) -> List[Tuple[str, str]]:
        """获取某类的所有直接出边关系: [(relation_uri, target_class_uri)]"""
        return self._adj.get(class_uri, [])

    def get_reverse_neighbors(self, class_uri: str) -> List[Tuple[str, str]]:
        """获取指向某类的所有入边关系: [(relation_uri, source_class_uri)]"""
        return self._adj_rev.get(class_uri, [])

    def get_class_relations(self, class_uri: str) -> List[OntologyRelation]:
        """获取与某类相关的所有关系（出边 + 入边去重）"""
        seen: Set[str] = set()
        result: List[OntologyRelation] = []
        for rel_uri, _ in self._adj.get(class_uri, []):
            if rel_uri not in seen:
                seen.add(rel_uri)
                rel = self.relations.get(rel_uri)
                if rel:
                    result.append(rel)
        for rel_uri, _ in self._adj_rev.get(class_uri, []):
            if rel_uri not in seen:
                seen.add(rel_uri)
                rel = self.relations.get(rel_uri)
                if rel:
                    result.append(rel)
        return result

    def find_path(
        self,
        source_uri: str,
        target_uri: str,
        max_depth: int = MAX_PATH_DEPTH,
    ) -> Optional[List[Tuple[str, str, str]]]:
        """
        BFS 查找两个类之间的最短路径（双向边）。

        Returns:
            路径列表 [(from_class, relation, to_class), ...] 或 None
        """
        if source_uri == target_uri:
            return []
        if source_uri not in self.classes or target_uri not in self.classes:
            return None

        # BFS (无向：同时走正向和反向边)
        visited: Set[str] = {source_uri}
        queue: deque = deque()
        queue.append((source_uri, []))

        while queue:
            current, path = queue.popleft()
            if len(path) >= max_depth:
                continue

            # 正向边
            for rel_uri, neighbor in self._adj.get(current, []):
                if neighbor == target_uri:
                    return path + [(current, rel_uri, neighbor)]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [(current, rel_uri, neighbor)]))

            # 反向边
            for rel_uri, neighbor in self._adj_rev.get(current, []):
                if neighbor == target_uri:
                    return path + [(current, f"^{rel_uri}", neighbor)]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [(current, f"^{rel_uri}", neighbor)]))

        return None  # 不可达

    def find_all_paths(
        self,
        source_uri: str,
        target_uri: str,
        max_depth: int = MAX_PATH_DEPTH,
    ) -> List[List[Tuple[str, str, str]]]:
        """DFS 查找所有路径（不超过 max_depth 跳），按长度排序。"""
        if source_uri not in self.classes or target_uri not in self.classes:
            return []

        results: List[List[Tuple[str, str, str]]] = []
        self._dfs_paths(source_uri, target_uri, set(), [], results, max_depth)
        results.sort(key=len)
        return results

    def _dfs_paths(
        self,
        current: str,
        target: str,
        visited: Set[str],
        path: List[Tuple[str, str, str]],
        results: List,
        max_depth: int,
    ) -> None:
        if len(path) > max_depth:
            return
        if current == target and path:
            results.append(list(path))
            return

        visited.add(current)

        for rel_uri, neighbor in self._adj.get(current, []):
            if neighbor not in visited:
                path.append((current, rel_uri, neighbor))
                self._dfs_paths(neighbor, target, visited, path, results, max_depth)
                path.pop()

        for rel_uri, neighbor in self._adj_rev.get(current, []):
            if neighbor not in visited:
                path.append((current, f"^{rel_uri}", neighbor))
                self._dfs_paths(neighbor, target, visited, path, results, max_depth)
                path.pop()

        visited.discard(current)

    # ── 统计 ──

    def summary(self) -> Dict:
        return {
            "classes": len(self.classes),
            "relations": len(self.relations),
            "data_properties": len(self.data_properties),
            "label_index_size": len(self._label_index),
        }

    def __repr__(self) -> str:
        s = self.summary()
        return (
            f"OntologyGraph(classes={s['classes']}, "
            f"relations={s['relations']}, "
            f"data_properties={s['data_properties']})"
        )
