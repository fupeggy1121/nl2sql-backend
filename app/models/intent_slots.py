"""
IntentSlots — 意图语义槽模型

将意图识别从"分类器"升级为"语义槽填充器（Slot Filling）"。
每个槽位对应 SQL 构造的一个核心要素，作为 context_builder 的定向匹配上下文。

槽位与 SQL 的对应关系：
  subject      → FROM 的主表（来自哪个业务对象）
  dimension_by → GROUP BY 维度
  metric       → SELECT 的聚合字段
  action       → 决定 SQL 结构：LIST/AGGREGATE/COUNT/TREND
  filters      → WHERE 条件提示
  sort_order   → ORDER BY
  limit_n      → LIMIT N
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class IntentSlots:
    """
    语义槽：从用户自然语言中提炼的结构化查询意图。

    设计原则：
      - 每个槽位都是 Optional，允许部分填充
      - 槽位用领域自然语言描述（如 "入库记录"），不直接绑定类名
      - context_builder 用这些描述做定向同义词搜索，而不是硬编码类名
    """

    # 查询的主体对象，对应 FROM 的来源
    # 例如: "入库记录" / "物料" / "库存" / "批次"
    subject: Optional[str] = None

    # 动作类型，对应 SQL 整体结构
    # 枚举: "查询列表" / "统计聚合" / "计数" / "趋势分析"
    action: Optional[str] = None

    # 聚合/分组维度，对应 GROUP BY
    # 例如: "物料" / "仓库" / "工序" / "设备"
    dimension_by: Optional[str] = None

    # 聚合指标，对应 SELECT 中的聚合列
    # 例如: "入库数量" / "库存数量" / "出库数量" / "批次数"
    metric: Optional[str] = None

    # 排序方向
    sort_order: Optional[str] = None  # "DESC" | "ASC"

    # LIMIT N（Top N / 前N）
    limit_n: Optional[int] = None

    # 过滤条件提示（自然语言，让 context_builder 用于值映射匹配）
    # 例如: ["状态=已完成", "时间范围=本月", "仓库=仓库01"]
    filter_hints: List[str] = field(default_factory=list)

    # 原始 LLM 推理说明（调试用）
    reasoning: Optional[str] = None

    def is_aggregate(self) -> bool:
        return self.action == "统计聚合" or (
            self.dimension_by is not None and self.metric is not None
        )

    def has_ranking(self) -> bool:
        return self.limit_n is not None and self.is_aggregate()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "action": self.action,
            "dimension_by": self.dimension_by,
            "metric": self.metric,
            "sort_order": self.sort_order,
            "limit_n": self.limit_n,
            "filter_hints": self.filter_hints,
            "reasoning": self.reasoning,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "IntentSlots":
        if not d:
            return cls()
        return cls(
            subject=d.get("subject"),
            action=d.get("action"),
            dimension_by=d.get("dimension_by"),
            metric=d.get("metric"),
            sort_order=d.get("sort_order"),
            limit_n=d.get("limit_n"),
            filter_hints=d.get("filter_hints") or [],
            reasoning=d.get("reasoning"),
        )
