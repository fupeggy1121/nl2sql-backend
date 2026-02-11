#!/usr/bin/env python3
"""
数据库迁移脚本 - 创建同义词管理和反馈表
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.postgresql_executor import PostgreSQLExecutor

SQL = """
-- ============================================
-- 表名同义词管理表
-- ============================================
CREATE TABLE IF NOT EXISTS table_synonyms (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(128) NOT NULL,        -- 实际数据库表名
    synonym VARCHAR(128) NOT NULL,           -- 同义词/别名
    source VARCHAR(20) DEFAULT 'manual',     -- 来源: manual(手动), auto(自动推荐), builtin(内置)
    is_active BOOLEAN DEFAULT TRUE,          -- 是否启用
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(64) DEFAULT 'system',
    UNIQUE(table_name, synonym)
);

CREATE INDEX IF NOT EXISTS idx_synonym_lookup ON table_synonyms(LOWER(synonym)) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_table_name ON table_synonyms(table_name);

-- ============================================
-- 未匹配查询词记录表 (反馈学习)
-- ============================================
CREATE TABLE IF NOT EXISTS unmatched_query_terms (
    id SERIAL PRIMARY KEY,
    term VARCHAR(256) NOT NULL,              -- 未匹配的查询词
    original_query TEXT,                     -- 原始完整查询
    frequency INTEGER DEFAULT 1,            -- 出现频次
    suggested_table VARCHAR(128),            -- 系统推荐的目标表 (可选)
    status VARCHAR(20) DEFAULT 'pending',    -- pending / approved / rejected / ignored
    reviewed_by VARCHAR(64),                 -- 审核人
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(term)
);

CREATE INDEX IF NOT EXISTS idx_unmatched_status ON unmatched_query_terms(status);
CREATE INDEX IF NOT EXISTS idx_unmatched_frequency ON unmatched_query_terms(frequency DESC);

-- ============================================
-- 同义词操作审计日志
-- ============================================
CREATE TABLE IF NOT EXISTS synonym_audit_log (
    id SERIAL PRIMARY KEY,
    action VARCHAR(20) NOT NULL,             -- add / update / delete / approve / reject
    table_name VARCHAR(128),
    synonym VARCHAR(128),
    details JSONB,                           -- 额外信息
    performed_by VARCHAR(64) DEFAULT 'system',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_created ON synonym_audit_log(created_at DESC);
"""


def run_migration():
    """执行数据库迁移"""
    executor = PostgreSQLExecutor()
    
    if not executor.connect():
        print("❌ 数据库连接失败，无法执行迁移")
        return False
    
    try:
        print("📦 开始创建同义词管理表...")
        executor.execute_query(SQL)
        print("✅ 同义词管理表创建成功")
        
        # 导入内置同义词到数据库
        from app.config.table_synonyms import TABLE_SYNONYMS
        
        inserted = 0
        for table_name, synonyms in TABLE_SYNONYMS.items():
            for synonym in synonyms:
                try:
                    executor.execute_query(
                        """INSERT INTO table_synonyms (table_name, synonym, source, is_active)
                           VALUES (%s, %s, 'builtin', TRUE)
                           ON CONFLICT (table_name, synonym) DO NOTHING""",
                        (table_name, synonym.lower())
                    )
                    inserted += 1
                except Exception as e:
                    print(f"  ⚠️ 插入 {synonym} -> {table_name} 失败: {e}")
        
        print(f"✅ 已导入 {inserted} 条内置同义词映射")
        return True
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        return False
    finally:
        executor.close()


if __name__ == '__main__':
    success = run_migration()
    sys.exit(0 if success else 1)
