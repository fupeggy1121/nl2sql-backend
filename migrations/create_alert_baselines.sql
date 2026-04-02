-- ============================================================
-- Migration: create_alert_baselines
-- Description: 业务预警基线表 — 支持多级阈值、NL 触发词匹配、动态更新
-- ============================================================

CREATE TABLE IF NOT EXISTS alert_baselines (
  id            text        PRIMARY KEY,
  metric_id     text,                                   -- 关联 metric_definitions key（可选）
  label         text        NOT NULL,                   -- 显示名，如 "一次良率目标线"
  field         text        NOT NULL,                   -- 匹配 yAxisField，如 "yield_rate"
  keywords      text[]      NOT NULL DEFAULT '{}',      -- NL 触发词 ["良率","FPY"]
  scope         jsonb       NOT NULL DEFAULT '{}',      -- 限定范围 {"product":"DRAM-A1","month":"2026-04"}
  thresholds    jsonb       NOT NULL DEFAULT '[]',      -- 多级阈值数组（见下方说明）
  direction     text        NOT NULL DEFAULT 'below',   -- "below"=低于阈值异常, "above"=高于阈值异常
  enabled       boolean     NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  created_by    text        NOT NULL DEFAULT 'system'
);

-- thresholds JSON 结构示例:
-- [
--   {"value": 95, "level": "target",   "color": "#10b981", "label": "目标"},
--   {"value": 90, "level": "warning",  "color": "#f59e0b", "label": "预警"},
--   {"value": 85, "level": "critical", "color": "#ef4444", "label": "严重"}
-- ]

-- direction = "below": 数据 < critical.value 时标红，< warning.value 时标黄
-- direction = "above": 数据 > critical.value 时标红，> warning.value 时标黄

-- 索引: GIN 加速 keywords 数组查询
CREATE INDEX IF NOT EXISTS idx_alert_baselines_keywords
  ON alert_baselines USING GIN(keywords);

-- 索引: 过滤 enabled baselines（最常见查询）
CREATE INDEX IF NOT EXISTS idx_alert_baselines_enabled
  ON alert_baselines(enabled) WHERE enabled = true;

-- 索引: 按 field 查询（匹配 yAxisField）
CREATE INDEX IF NOT EXISTS idx_alert_baselines_field
  ON alert_baselines(field);

-- 示例数据（可选，供开发测试）
-- INSERT INTO alert_baselines (id, label, field, keywords, thresholds, direction)
-- VALUES (
--   'BL-YIELD-01',
--   '一次良率目标线',
--   'first_pass_yield',
--   ARRAY['良率','FPY','一次良率','直通率'],
--   '[{"value":95,"level":"target","color":"#10b981","label":"目标"},{"value":90,"level":"warning","color":"#f59e0b","label":"预警"},{"value":85,"level":"critical","color":"#ef4444","label":"严重"}]'::jsonb,
--   'below'
-- );

-- ============================================================
-- RLS: 允许 anon + service_role 对 alert_baselines 完全访问
-- (与项目内 knowledge_embeddings / agent_interactions 策略保持一致)
-- ============================================================
ALTER TABLE alert_baselines ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow full access to alert_baselines" ON alert_baselines;
CREATE POLICY "Allow full access to alert_baselines"
    ON alert_baselines FOR ALL
    USING (true)
    WITH CHECK (true);
