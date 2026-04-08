"""
语义连接图 —— 基于 relation_mappings 构建 NetworkX DiGraph

架构层级：
  OWL TTL（启动校验） → relation_mappings（语义×物理桥） → JoinGraph（运行时索引）

设计原则：
  - 图节点 = OWL 语义类（如 "semi:ProductionLot"）
  - 图有向边 = OWL ObjectProperty，携带 join_logic（物理表/键）
  - union range（hasInput/hasOutput）展开为各目标类分别建边
  - 不带 range_class 的属性（modifiesStateVector）跳过（不可路径化）
  - BFS 最短路径 → 返回每跳 JoinEdge（含 RelationMapping 引用），
    调用方可直接生成 SQL JOIN 链，无需再回查 TTL
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Tuple

import networkx as nx

if TYPE_CHECKING:
    from .mapping import MappingDictionary, RelationMapping

logger = logging.getLogger(__name__)


@dataclass
class JoinEdge:
    """一条语义路径上的单跳信息"""
    logic_relation: str          # e.g. "semi:belongsToLot"
    from_class: str              # e.g. "semi:Wafer"
    to_class: str                # e.g. "semi:ProductionLot"
    reversed: bool               # True = 沿反向边走（range→domain）
    relation_mapping: "RelationMapping"  # 携带完整物理 join 信息
    identity: bool = False       # True = 子类继承穿越边，无实际 SQL JOIN


@dataclass
class _IdentityRelationMapping:
    """子类继承边的哑元 RelationMapping，不产生任何 SQL JOIN 条件。"""
    logic_relation: str
    domain_class: str
    range_class: str
    domain_table: str
    range_table: str
    description: str = ""
    strategy: str = "Identity"
    join_conditions: list = None  # type: ignore[assignment]
    bridge_table: None = None
    order_by: None = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.join_conditions is None:
            self.join_conditions = []


class JoinGraph:
    """
    基于 relation_mappings 构建的语义连接图。

    节点: OWL class short name（"semi:ProductionLot"）
    有向边 domain→range，edge attr 来自对应的 RelationMapping。
    图同时添加反向边（range→domain），以支持双向路径发现；
    反向边的 logic_relation 前缀 "^" 标识（与 OntologyGraph 保持一致）。
    """

    def __init__(self) -> None:
        self._g: nx.DiGraph = nx.DiGraph()
        self._built: bool = False

    # ----------------------------------------------------------------- #
    # 构建
    # ----------------------------------------------------------------- #

    def build(self, mapping: "MappingDictionary") -> "JoinGraph":
        """
        从已加载的 MappingDictionary 构建图。
        应在 OntologyValidator.validate_relation_mappings() 之后调用，
        确保 domain_class / range_class 与 TTL 一致。
        """
        g = nx.DiGraph()
        edge_count = 0

        for rm in mapping._relation_map_list:
            logic_rel = rm.logic_relation
            domain = rm.domain_class
            range_raw = rm.range_class

            if domain is None or range_raw is None:
                logger.debug(
                    "JoinGraph: 跳过 %s（domain=%s, range=%s）",
                    logic_rel, domain, range_raw,
                )
                continue

            # union range 展开为多条边
            targets: List[str] = (
                range_raw if isinstance(range_raw, list) else [range_raw]
            )

            for target in targets:
                # 正向边 domain → range
                g.add_edge(
                    domain, target,
                    logic_relation=logic_rel,
                    reversed=False,
                    rm=rm,
                )
                # 反向边 range → domain（^前缀，用于双向路径发现）
                g.add_edge(
                    target, domain,
                    logic_relation="^" + logic_rel,
                    reversed=True,
                    rm=rm,
                )
                edge_count += 1

        self._g = g
        self._built = True

        # ----------------------------------------------------------------- #
        # 子类继承边：若 ClassA subclass_of ClassB 且共享同一物理表，
        # 则自动添加 A↔B 的双向零跳边，使所有定义在 B 上的关系
        # 对 A 同样可路径化（如 semi:Material 的关系自动覆盖
        # semi:RawMaterial / semi:Auxiliary / semi:SparePart / semi:Product）
        # ----------------------------------------------------------------- #
        subclass_edge_count = 0
        for cls_uri, pt in mapping._table_by_class.items():
            parent = getattr(pt, "subclass_of", None)
            if not parent:
                continue
            parent_pt = mapping.get_physical_table(parent)
            if not parent_pt or parent_pt.table_name != pt.table_name:
                continue  # 仅对共享同一物理表的父子类添加继承边
            _identity_rm = _IdentityRelationMapping(
                logic_relation=f"subClassOf:{cls_uri}",
                domain_class=cls_uri,
                range_class=parent,
                domain_table=pt.table_name,
                range_table=parent_pt.table_name,
            )
            g.add_edge(
                cls_uri, parent,
                logic_relation=f"subClassOf:{cls_uri}",
                reversed=False,
                rm=_identity_rm,
                identity=True,
            )
            g.add_edge(
                parent, cls_uri,
                logic_relation=f"^subClassOf:{cls_uri}",
                reversed=True,
                rm=_identity_rm,
                identity=True,
            )
            subclass_edge_count += 1
            logger.debug("JoinGraph 继承边: %s ↔ %s（表 %s）", cls_uri, parent, pt.table_name)

        self._built = True
        logger.info(
            "JoinGraph built: %d nodes, %d logical edges (%d directed, %d subclass inheritance)",
            g.number_of_nodes(),
            edge_count,
            g.number_of_edges(),
            subclass_edge_count,
        )
        return self

    # ----------------------------------------------------------------- #
    # 路径查找
    # ----------------------------------------------------------------- #

    def find_path(
        self,
        source_class: str,
        target_class: str,
        intent: Optional[str] = None,
    ) -> Optional[List[JoinEdge]]:
        """
        BFS 最短路径（有向，同时允许反向边）。

        intent 参数保留为向后兼容接口，当前不用于子图过滤；
        路径语义验证在 context_builder._resolve_joins 中通过中间节点纯洁性检查实现。
        """
        if not self._built:
            logger.warning("JoinGraph.find_path called before build()")
            return None

        if source_class == target_class:
            return []

        if source_class not in self._g or target_class not in self._g:
            logger.debug(
                "JoinGraph: 节点不存在: source=%s target=%s",
                source_class, target_class,
            )
            return None

        try:
            node_path: List[str] = nx.shortest_path(
                self._g, source_class, target_class
            )
        except nx.NetworkXNoPath:
            return None
        except nx.NodeNotFound:
            return None

        edges: List[JoinEdge] = []
        for i in range(len(node_path) - 1):
            u, v = node_path[i], node_path[i + 1]
            edge_data = self._g[u][v]
            edges.append(JoinEdge(
                logic_relation=edge_data["logic_relation"],
                from_class=u,
                to_class=v,
                reversed=edge_data["reversed"],
                relation_mapping=edge_data["rm"],
                identity=edge_data.get("identity", False),
            ))
        return edges

    def find_all_shortest_paths(
        self,
        source_class: str,
        target_class: str,
    ) -> List[List[JoinEdge]]:
        """
        返回两类之间所有最短路径（等长）。
        用于路径语义验证：当最短路径存在多条时，
        调用方可依据中间节点纯洁性选择最佳路径。
        """
        if not self._built:
            return []
        if source_class not in self._g or target_class not in self._g:
            return []
        try:
            all_node_paths = list(nx.all_shortest_paths(self._g, source_class, target_class))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

        result = []
        for node_path in all_node_paths:
            edges: List[JoinEdge] = []
            for i in range(len(node_path) - 1):
                u, v = node_path[i], node_path[i + 1]
                edge_data = self._g[u][v]
                edges.append(JoinEdge(
                    logic_relation=edge_data["logic_relation"],
                    from_class=u,
                    to_class=v,
                    reversed=edge_data["reversed"],
                    relation_mapping=edge_data["rm"],
                    identity=edge_data.get("identity", False),
                ))
            result.append(edges)
        return result

    @staticmethod
    def _edge_allowed_for_intent(edge_data: dict, intent: str) -> bool:
        """保留向后兼容，当前不在主路径使用。"""
        rm = edge_data.get("rm")
        if rm is None:
            return True
        if intent in (rm.forbidden_intents or []):
            return False
        applicable = rm.applicable_intents or []
        if applicable and intent not in applicable:
            return False
        return True

    def find_path_undirected(
        self,
        source_class: str,
        target_class: str,
    ) -> Optional[List[JoinEdge]]:
        """
        忽略边方向的 BFS（undirected fallback）。
        当正向路径不存在时可用作备选。
        """
        if not self._built:
            return None
        try:
            ug = self._g.to_undirected()
            node_path = nx.shortest_path(ug, source_class, target_class)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

        edges: List[JoinEdge] = []
        for i in range(len(node_path) - 1):
            u, v = node_path[i], node_path[i + 1]
            if self._g.has_edge(u, v):
                edge_data = self._g[u][v]
            else:
                edge_data = self._g[v][u]
            edges.append(JoinEdge(
                logic_relation=edge_data["logic_relation"],
                from_class=u,
                to_class=v,
                reversed=edge_data["reversed"],
                relation_mapping=edge_data["rm"],
                identity=edge_data.get("identity", False),
            ))
        return edges

    # ----------------------------------------------------------------- #
    # 工具方法
    # ----------------------------------------------------------------- #

    def neighbors(self, class_name: str) -> List[str]:
        """返回某个语义类的直接邻居（所有 range 类）"""
        if class_name not in self._g:
            return []
        return list(self._g.successors(class_name))

    def has_direct_edge(self, source: str, target: str) -> bool:
        return self._g.has_edge(source, target)

    @property
    def node_count(self) -> int:
        return self._g.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._g.number_of_edges() // 2  # 正反向各一条，除2得逻辑边数

    @property
    def is_ready(self) -> bool:
        return self._built


# ─── 模块级单例 ──────────────────────────────────────────────────────────────
_join_graph: Optional[JoinGraph] = None


def get_join_graph() -> Optional[JoinGraph]:
    """获取全局 JoinGraph 单例（lifespan 初始化后可用）"""
    return _join_graph


def init_join_graph(mapping: "MappingDictionary") -> JoinGraph:
    """在 lifespan 中调用，构建并缓存全局 JoinGraph"""
    global _join_graph
    _join_graph = JoinGraph().build(mapping)
    return _join_graph
