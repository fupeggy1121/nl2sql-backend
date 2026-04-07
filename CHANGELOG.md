# Changelog

---

## v0.3 — 路由架构重构 (2026-04)

**测试基准：24/26 通过 (92%)，A 维度 10/10 全通**

### 架构变更

#### 废弃双向关键词守卫
- 移除 `supervisor.py` 中的 `_GUARD_A_KEYWORDS`、`_GUARD_B_KEYWORDS`、`_REPORT_KEYWORDS` 关键词列表
- 旧设计的问题：每新增一个 skill 或同义词就需要同步维护三处关键词列表；B07 等用例曾触发 Guard A 误判

#### 新路由：Skill-Aware LLM 路由
- `supervisor.route_request()` 一次 LLM 调用完成路由决策
- 注入完整 `SkillLoader.list_skills()` 列表（含所有 `zh_names`），LLM 做语义匹配
- 返回 `{"route": "skill"/"adhoc"/"analyze", "skill_name": "..."}`
- **新增 skill 只需在 `app/skills/metrics/` 添加 `.md` 文件，无需改任何路由代码**

#### 消除双重 LLM 调用
- `analysis_agent/state.py` 新增 `pre_selected_skill: Optional[str]` 字段
- `method_selector.py` 检查 `pre_selected_skill`：supervisor 已决策则跳过 `_llm_route()`
- 每次查询节省一次 LLM RTT

#### 提示词优先级规范
- `_ROUTE_PROMPT` 注意节明确：Rule 1（skill alias 精确匹配）优先级最高
- "统计"/"按站点统计"/"分布" 等词不改变路由，最终取决于是否命中 skill alias

### Skill 数据改进

#### wafer_wip.md zh_names 精化
- 移除歧义短词（`"在制品"`、`"WIP"`、`"在制"`）——过短会误匹配"批次在加工"等句式
- 重命名 `"各站在制"` → `"各站在制品"`
- 新增精确别名：`"WIP分布"`、`"在制品分布"`、`"wafer在制品"`、`"当前在制品"`
- `standard_definition` 末尾追加"；不是批次计数查询"，辅助 LLM 区分 wafer WIP 与批次计数

### 数据库 / Ontology 修复

#### B04 Hold 查询性能（v0.2 补丁）
- `mapping_prod.json` `LotWIPStatus.Hold.physical_condition` 关联字段由 `lot_id = id` 改为 `lot_code = current_lot_code`
- 利用已有 `idx_lot_code` 索引，查询时间从约 150 s 降至约 21 s
- 背景：`matrix_routerx_operation_lot_batch_resume_log` 表 `lot_id` 字段无索引

### 已知限制（待下阶段处理）

| 用例 | 描述 | 原因 |
|------|------|------|
| B08 | "最近有异常的批次" | 意图模糊，"异常"无明确 ontology 映射，无法生成 SQL |
| C08 | "帮我分析一下生产情况" | 开放性查询，缺乏可执行目标，返回引导性回答 |

建议下阶段为此类模糊意图加入 `clarification_needed` 状态，返回结构化追问。

---

## 数据库注意事项（运维参考）

### Hold 查询索引
- `matrix_routerx_operation_lot_batch_resume_log` 表的 `lot_id` 字段**无索引**
- 当前通过 `lot_code = current_lot_code`（有 `idx_lot_code` 索引）规避全表扫描
- 若业务侧后续为 `lot_id` 加索引，可将 `mapping_prod.json` 中 `LotWIPStatus.Hold.physical_condition` 的关联字段切回 `lot_id = id`

### Hold 状态推导
- 系统中**无独立 status 字段**标记批次是否处于扣留状态
- 扣留状态须通过事件推导：`HoldEventRecord(operation_type=4)` 存在 且 无晚于它的 `ReleaseEventRecord(operation_type=5)`
- 若后续新增 `hold_status` 字段，只需修改 `mapping_prod.json` 中 `LotWIPStatus.Hold.physical_condition`

### BatchStatus.Staged 与 Hold 的区别
- `Staged`（status=80）：批次物理移入线边仓（bank）暂存，独立的 status 值
- `Hold`：生产异常等待工程师判定，无独立 status 字段，完全由事件记录推导
- 两者**不可混用**，自然语言触发词在 `mapping_prod.json` 已明确分开维护

---

## v0.2 — 初始修复 (2026-03)

- A08：WIP 查询正确路由至 `wafer_wip` skill
- B07：子批次趋势查询从 skill 路径纠正为 adhoc
- B04：Hold 批次查询性能优化（详见上方）
