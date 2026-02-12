-- ============================================================
-- 同义词管理表迁移 - 在 Supabase SQL Editor 中执行
-- 创建 table_synonyms / unmatched_query_terms / synonym_audit_log
-- ============================================================

-- 1. 表名同义词管理表
CREATE TABLE IF NOT EXISTS table_synonyms (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(128) NOT NULL,
    synonym VARCHAR(128) NOT NULL,
    source VARCHAR(20) DEFAULT 'manual',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(64) DEFAULT 'system',
    UNIQUE(table_name, synonym)
);

CREATE INDEX IF NOT EXISTS idx_synonym_lookup ON table_synonyms(LOWER(synonym)) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_table_name ON table_synonyms(table_name);

-- 2. 未匹配查询词记录表
CREATE TABLE IF NOT EXISTS unmatched_query_terms (
    id SERIAL PRIMARY KEY,
    term VARCHAR(256) NOT NULL,
    original_query TEXT,
    frequency INTEGER DEFAULT 1,
    suggested_table VARCHAR(128),
    status VARCHAR(20) DEFAULT 'pending',
    reviewed_by VARCHAR(64),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(term)
);

CREATE INDEX IF NOT EXISTS idx_unmatched_status ON unmatched_query_terms(status);
CREATE INDEX IF NOT EXISTS idx_unmatched_frequency ON unmatched_query_terms(frequency DESC);

-- 3. 同义词操作审计日志
CREATE TABLE IF NOT EXISTS synonym_audit_log (
    id SERIAL PRIMARY KEY,
    action VARCHAR(20) NOT NULL,
    table_name VARCHAR(128),
    synonym VARCHAR(128),
    details JSONB,
    performed_by VARCHAR(64) DEFAULT 'system',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_created ON synonym_audit_log(created_at DESC);

-- 4. 开放 PostgREST 访问权限 (anon / authenticated)
--    Supabase 通过 PostgREST 暴露表, 需要 GRANT 给对应角色
ALTER TABLE table_synonyms ENABLE ROW LEVEL SECURITY;
ALTER TABLE unmatched_query_terms ENABLE ROW LEVEL SECURITY;
ALTER TABLE synonym_audit_log ENABLE ROW LEVEL SECURITY;

-- RLS 策略: 允许 anon 和 authenticated 角色完整读写
-- table_synonyms
CREATE POLICY "Allow full access to table_synonyms" ON table_synonyms
    FOR ALL USING (true) WITH CHECK (true);

-- unmatched_query_terms
CREATE POLICY "Allow full access to unmatched_query_terms" ON unmatched_query_terms
    FOR ALL USING (true) WITH CHECK (true);

-- synonym_audit_log
CREATE POLICY "Allow full access to synonym_audit_log" ON synonym_audit_log
    FOR ALL USING (true) WITH CHECK (true);

-- GRANT 表权限给 anon 和 authenticated
GRANT ALL ON table_synonyms TO anon, authenticated;
GRANT ALL ON unmatched_query_terms TO anon, authenticated;
GRANT ALL ON synonym_audit_log TO anon, authenticated;

-- GRANT 序列权限 (INSERT 需要)
GRANT USAGE, SELECT ON SEQUENCE table_synonyms_id_seq TO anon, authenticated;
GRANT USAGE, SELECT ON SEQUENCE unmatched_query_terms_id_seq TO anon, authenticated;
GRANT USAGE, SELECT ON SEQUENCE synonym_audit_log_id_seq TO anon, authenticated;

-- 5. 预置内置同义词 (完整 77 个核心映射，与 table_synonyms.py 一致)
INSERT INTO table_synonyms (table_name, synonym, source, is_active) VALUES
    -- carriers (7)
    ('carriers', 'carriers', 'builtin', TRUE),
    ('carriers', 'carrier', 'builtin', TRUE),
    ('carriers', '载体', 'builtin', TRUE),
    ('carriers', '载具', 'builtin', TRUE),
    ('carriers', '片篮', 'builtin', TRUE),
    ('carriers', '晶圆载体', 'builtin', TRUE),
    ('carriers', '石英舟', 'builtin', TRUE),
    -- wafers (7)
    ('wafers', 'wafers', 'builtin', TRUE),
    ('wafers', 'wafer', 'builtin', TRUE),
    ('wafers', '晶圆', 'builtin', TRUE),
    ('wafers', '晶片', 'builtin', TRUE),
    ('wafers', '芯片', 'builtin', TRUE),
    ('wafers', '硅片', 'builtin', TRUE),
    ('wafers', '磊晶片', 'builtin', TRUE),
    -- wafer_inspection_results (6)
    ('wafer_inspection_results', 'wafer_inspection_results', 'builtin', TRUE),
    ('wafer_inspection_results', '检测结果', 'builtin', TRUE),
    ('wafer_inspection_results', '检测数据', 'builtin', TRUE),
    ('wafer_inspection_results', '检验结果', 'builtin', TRUE),
    ('wafer_inspection_results', '晶圆检测', 'builtin', TRUE),
    ('wafer_inspection_results', '品质检测', 'builtin', TRUE),
    -- batches (6)
    ('batches', 'batches', 'builtin', TRUE),
    ('batches', 'batch', 'builtin', TRUE),
    ('batches', '批次', 'builtin', TRUE),
    ('batches', '生产批次', 'builtin', TRUE),
    ('batches', '批号', 'builtin', TRUE),
    ('batches', '工单', 'builtin', TRUE),
    -- equipment (8)
    ('equipment', 'equipment', 'builtin', TRUE),
    ('equipment', 'device', 'builtin', TRUE),
    ('equipment', '设备', 'builtin', TRUE),
    ('equipment', '机器', 'builtin', TRUE),
    ('equipment', '机台', 'builtin', TRUE),
    ('equipment', '装置', 'builtin', TRUE),
    ('equipment', '仪器', 'builtin', TRUE),
    ('equipment', '工具', 'builtin', TRUE),
    -- production_records (6)
    ('production_records', 'production_records', 'builtin', TRUE),
    ('production_records', '生产记录', 'builtin', TRUE),
    ('production_records', '生产数据', 'builtin', TRUE),
    ('production_records', '制造记录', 'builtin', TRUE),
    ('production_records', '产量记录', 'builtin', TRUE),
    ('production_records', '产出记录', 'builtin', TRUE),
    -- process_steps (7)
    ('process_steps', 'process_steps', 'builtin', TRUE),
    ('process_steps', '工艺步骤', 'builtin', TRUE),
    ('process_steps', '工序', 'builtin', TRUE),
    ('process_steps', '制程', 'builtin', TRUE),
    ('process_steps', '工艺流程', 'builtin', TRUE),
    ('process_steps', '站点', 'builtin', TRUE),
    ('process_steps', '制程步骤', 'builtin', TRUE),
    -- quality_records (6)
    ('quality_records', 'quality_records', 'builtin', TRUE),
    ('quality_records', '质量记录', 'builtin', TRUE),
    ('quality_records', '品质记录', 'builtin', TRUE),
    ('quality_records', '品质数据', 'builtin', TRUE),
    ('quality_records', 'QC记录', 'builtin', TRUE),
    ('quality_records', '质检记录', 'builtin', TRUE),
    -- defect_records (7)
    ('defect_records', 'defect_records', 'builtin', TRUE),
    ('defect_records', '缺陷记录', 'builtin', TRUE),
    ('defect_records', '不良记录', 'builtin', TRUE),
    ('defect_records', '缺陷数据', 'builtin', TRUE),
    ('defect_records', '异常记录', 'builtin', TRUE),
    ('defect_records', '不良品记录', 'builtin', TRUE),
    ('defect_records', 'NG记录', 'builtin', TRUE),
    -- alarms (7)
    ('alarms', 'alarms', 'builtin', TRUE),
    ('alarms', 'alarm', 'builtin', TRUE),
    ('alarms', '报警', 'builtin', TRUE),
    ('alarms', '告警', 'builtin', TRUE),
    ('alarms', '警报', 'builtin', TRUE),
    ('alarms', '异常警报', 'builtin', TRUE),
    ('alarms', '设备报警', 'builtin', TRUE),
    -- recipes (5)
    ('recipes', 'recipes', 'builtin', TRUE),
    ('recipes', 'recipe', 'builtin', TRUE),
    ('recipes', '配方', 'builtin', TRUE),
    ('recipes', '工艺配方', 'builtin', TRUE),
    ('recipes', '制程配方', 'builtin', TRUE),
    -- maintenance_records (5)
    ('maintenance_records', 'maintenance_records', 'builtin', TRUE),
    ('maintenance_records', '维护记录', 'builtin', TRUE),
    ('maintenance_records', '保养记录', 'builtin', TRUE),
    ('maintenance_records', '维修记录', 'builtin', TRUE),
    ('maintenance_records', 'PM记录', 'builtin', TRUE)
ON CONFLICT (table_name, synonym) DO NOTHING;
