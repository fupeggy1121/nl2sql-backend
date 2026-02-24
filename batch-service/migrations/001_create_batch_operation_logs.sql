-- ============================================================
-- 批次作业操作日志表
-- 记录所有批次操作的完整审计轨迹
-- ============================================================

CREATE TABLE IF NOT EXISTS batch_operation_logs (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id      text        NOT NULL,     -- 关联 batches.id
  batch_code    text,                      -- 冗余批次编码，方便查询
  operation_type text       NOT NULL,      -- instation / outstation / split / merge / cancel_entry / carrier_change / rework / transfer / accumulate
  from_station  text,                      -- 操作前站点
  to_station    text,                      -- 操作后站点
  operator_id   text        DEFAULT 'system',
  remarks       text,
  good_qty_before   integer,
  defect_qty_before integer,
  good_qty_after    integer,
  defect_qty_after  integer,
  details       jsonb       DEFAULT '{}'::jsonb,  -- 操作的额外详情（如拆批配置、并批来源等）
  created_at    timestamptz DEFAULT now()
);

-- 索引：按批次 ID 查询操作历史
CREATE INDEX IF NOT EXISTS idx_batch_operation_logs_batch_id
  ON batch_operation_logs (batch_id);

-- 索引：按操作类型筛选
CREATE INDEX IF NOT EXISTS idx_batch_operation_logs_type
  ON batch_operation_logs (operation_type);

-- 索引：按时间排序
CREATE INDEX IF NOT EXISTS idx_batch_operation_logs_created_at
  ON batch_operation_logs (created_at DESC);

-- 授权
GRANT SELECT, INSERT ON batch_operation_logs TO service_role;
GRANT SELECT ON batch_operation_logs TO authenticated;

COMMENT ON TABLE batch_operation_logs IS '批次作业操作日志 - 记录进站/出站/拆批/并批等所有批次操作的审计轨迹';
