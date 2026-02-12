-- ============================================================
-- Phase D: RAG 知识库 — pgvector 启用 & 表创建
-- 在 Supabase SQL Editor 中执行此脚本
-- ============================================================

-- 1. 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. 知识嵌入表 — 存储文档向量
CREATE TABLE IF NOT EXISTS knowledge_embeddings (
    id              BIGSERIAL PRIMARY KEY,
    content         TEXT NOT NULL,                      -- 文档内容（分块后的文本）
    metadata        JSONB DEFAULT '{}'::jsonb,           -- 元数据（table_name, column_name, etc.）
    doc_type        VARCHAR(50) NOT NULL,                -- 文档类型: schema / synonym / sql_example / business_rule
    embedding       vector(1536),                        -- 嵌入向量 (OpenAI text-embedding-3-small = 1536 维)
    token_count     INT DEFAULT 0,                       -- 分块 token 数（用于统计）
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 3. 索引
-- IVFFlat 索引用于向量相似度搜索（余弦距离）
-- lists 参数 = sqrt(N)，N 为预估行数，初始设为 10
CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_vector
    ON knowledge_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);

-- doc_type 索引（按类型过滤）
CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_doc_type
    ON knowledge_embeddings (doc_type);

-- metadata GIN 索引（JSONB 查询）
CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_metadata
    ON knowledge_embeddings
    USING GIN (metadata);

-- 3a. RLS — 允许 service_role 和 anon key 完全访问
ALTER TABLE knowledge_embeddings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow full access to knowledge_embeddings" ON knowledge_embeddings;
CREATE POLICY "Allow full access to knowledge_embeddings"
    ON knowledge_embeddings FOR ALL
    USING (true)
    WITH CHECK (true);

-- 4. 向量相似度搜索 RPC 函数
CREATE OR REPLACE FUNCTION match_knowledge(
    query_embedding   vector(1536),
    match_threshold   FLOAT DEFAULT 0.5,
    match_count       INT DEFAULT 5,
    filter_doc_type   VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    id          BIGINT,
    content     TEXT,
    metadata    JSONB,
    doc_type    VARCHAR,
    similarity  FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ke.id,
        ke.content,
        ke.metadata,
        ke.doc_type,
        1 - (ke.embedding <=> query_embedding) AS similarity
    FROM knowledge_embeddings ke
    WHERE
        (filter_doc_type IS NULL OR ke.doc_type = filter_doc_type)
        AND 1 - (ke.embedding <=> query_embedding) > match_threshold
    ORDER BY ke.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- 5. Agent 交互记录表 (Phase C 中已部分实现于内存，现持久化)
CREATE TABLE IF NOT EXISTS agent_interactions (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(64) NOT NULL,
    user_input      TEXT NOT NULL,
    intent          VARCHAR(50),
    generated_sql   TEXT,
    success         BOOLEAN DEFAULT FALSE,
    result_summary  TEXT,
    feedback        SMALLINT,                           -- 用户反馈: 1=好, -1=差, NULL=未评价
    error_message   TEXT,
    retry_count     INT DEFAULT 0,
    query_time_ms   FLOAT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_interactions_session
    ON agent_interactions (session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_interactions_intent
    ON agent_interactions (intent);

-- 5a. RLS for agent_interactions
ALTER TABLE agent_interactions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow full access to agent_interactions" ON agent_interactions;
CREATE POLICY "Allow full access to agent_interactions"
    ON agent_interactions FOR ALL
    USING (true)
    WITH CHECK (true);

-- 6. Agent 会话表
CREATE TABLE IF NOT EXISTS agent_sessions (
    id              VARCHAR(64) PRIMARY KEY,
    user_id         VARCHAR(64),
    title           VARCHAR(200),                       -- 会话标题（自动从首条消息生成）
    turn_count      INT DEFAULT 0,
    last_active     TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 6a. RLS for agent_sessions
ALTER TABLE agent_sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow full access to agent_sessions" ON agent_sessions;
CREATE POLICY "Allow full access to agent_sessions"
    ON agent_sessions FOR ALL
    USING (true)
    WITH CHECK (true);

-- 7. Agent 反馈表
CREATE TABLE IF NOT EXISTS agent_feedback (
    id              BIGSERIAL PRIMARY KEY,
    interaction_id  BIGINT REFERENCES agent_interactions(id),
    session_id      VARCHAR(64),
    rating          SMALLINT NOT NULL,                  -- 1-5 评分
    comment         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_feedback_interaction
    ON agent_feedback (interaction_id);

-- 7a. RLS for agent_feedback
ALTER TABLE agent_feedback ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow full access to agent_feedback" ON agent_feedback;
CREATE POLICY "Allow full access to agent_feedback"
    ON agent_feedback FOR ALL
    USING (true)
    WITH CHECK (true);

-- 8. 更新 updated_at 触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_knowledge_embeddings_updated_at
    BEFORE UPDATE ON knowledge_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- 验证
-- ============================================================
-- SELECT * FROM pg_extension WHERE extname = 'vector';
-- SELECT COUNT(*) FROM knowledge_embeddings;
-- SELECT * FROM match_knowledge(
--     '[0.1, 0.2, ...]'::vector(1536),
--     0.5,  -- threshold
--     5     -- top_k
-- );
