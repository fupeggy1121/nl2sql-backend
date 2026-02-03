"""
Supabase 数据库迁移脚本
创建 Schema 语义标注所需的表

使用方法:
1. 登录 Supabase 控制台
2. 进入 SQL Editor
3. 复制下面的 SQL 执行
或者运行: python supabase/create_annotation_tables.py
"""

# SQL 创建脚本
MIGRATION_SQL = """
-- 1. 表级标注表
CREATE TABLE IF NOT EXISTS schema_table_annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(255) NOT NULL UNIQUE,
    table_name_cn VARCHAR(255),
    description_cn TEXT,
    description_en TEXT,
    business_meaning TEXT,
    use_case TEXT,
    status VARCHAR(50) DEFAULT 'pending', -- pending, approved, rejected
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    created_by VARCHAR(255) DEFAULT 'system',
    reviewed_by VARCHAR(255),
    rejection_reason TEXT,
    
    CONSTRAINT table_name_not_empty CHECK (table_name IS NOT NULL)
);

-- 2. 列级标注表
CREATE TABLE IF NOT EXISTS schema_column_annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(255) NOT NULL,
    column_name VARCHAR(255) NOT NULL,
    column_name_cn VARCHAR(255),
    data_type VARCHAR(100),
    description_cn TEXT,
    description_en TEXT,
    example_value TEXT,
    business_meaning TEXT,
    value_range TEXT,
    status VARCHAR(50) DEFAULT 'pending', -- pending, approved, rejected
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    created_by VARCHAR(255) DEFAULT 'system',
    reviewed_by VARCHAR(255),
    rejection_reason TEXT,
    
    CONSTRAINT table_column_unique UNIQUE(table_name, column_name),
    CONSTRAINT table_column_not_empty CHECK (table_name IS NOT NULL AND column_name IS NOT NULL)
);

-- 3. 关系（外键）标注表
CREATE TABLE IF NOT EXISTS schema_relation_annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_table VARCHAR(255) NOT NULL,
    source_column VARCHAR(255) NOT NULL,
    target_table VARCHAR(255) NOT NULL,
    target_column VARCHAR(255) NOT NULL,
    relation_type VARCHAR(50), -- one_to_one, one_to_many, many_to_many
    relation_name VARCHAR(255),
    description_cn TEXT,
    description_en TEXT,
    status VARCHAR(50) DEFAULT 'pending', -- pending, approved, rejected
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    created_by VARCHAR(255) DEFAULT 'system',
    reviewed_by VARCHAR(255),
    rejection_reason TEXT,
    
    CONSTRAINT relation_unique UNIQUE(source_table, source_column, target_table, target_column)
);

-- 4. 标注历史表（用于追踪变更）
CREATE TABLE IF NOT EXISTS annotation_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    annotation_type VARCHAR(50) NOT NULL, -- table, column, relation
    annotation_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL, -- create, update, approve, reject
    old_value JSONB,
    new_value JSONB,
    actor VARCHAR(255),
    created_at TIMESTAMP DEFAULT now()
);

-- 5. 创建索引以提高查询性能
CREATE INDEX idx_table_annotations_status ON schema_table_annotations(status);
CREATE INDEX idx_table_annotations_table_name ON schema_table_annotations(table_name);
CREATE INDEX idx_column_annotations_status ON schema_column_annotations(status);
CREATE INDEX idx_column_annotations_table_name ON schema_column_annotations(table_name);
CREATE INDEX idx_column_annotations_table_column ON schema_column_annotations(table_name, column_name);
CREATE INDEX idx_relation_annotations_status ON schema_relation_annotations(status);
CREATE INDEX idx_audit_log_annotation_id ON annotation_audit_log(annotation_id);
CREATE INDEX idx_audit_log_created_at ON annotation_audit_log(created_at);

-- 6. 启用 RLS (Row Level Security)
ALTER TABLE schema_table_annotations ENABLE ROW LEVEL SECURITY;
ALTER TABLE schema_column_annotations ENABLE ROW LEVEL SECURITY;
ALTER TABLE schema_relation_annotations ENABLE ROW LEVEL SECURITY;
ALTER TABLE annotation_audit_log ENABLE ROW LEVEL SECURITY;

-- 7. 创建 RLS 策略 - 允许匿名用户读取已批准的标注
CREATE POLICY "Allow read approved annotations" ON schema_table_annotations
    FOR SELECT USING (status = 'approved');

CREATE POLICY "Allow read approved annotations" ON schema_column_annotations
    FOR SELECT USING (status = 'approved');

CREATE POLICY "Allow read approved annotations" ON schema_relation_annotations
    FOR SELECT USING (status = 'approved');

-- 8. 创建视图 - 获取已批准的完整 schema 元数据
CREATE OR REPLACE VIEW approved_schema_metadata AS
SELECT 
    t.table_name,
    t.table_name_cn,
    t.description_cn,
    t.description_en,
    t.business_meaning,
    c.column_name,
    c.column_name_cn,
    c.data_type,
    c.description_cn as column_description_cn,
    c.description_en as column_description_en,
    c.example_value,
    c.business_meaning as column_business_meaning,
    c.value_range
FROM schema_table_annotations t
LEFT JOIN schema_column_annotations c ON t.table_name = c.table_name
WHERE t.status = 'approved' AND (c.status = 'approved' OR c.status IS NULL);

-- 9. 创建函数 - 自动更新 updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 10. 创建触发器
CREATE TRIGGER update_schema_table_annotations_updated_at
    BEFORE UPDATE ON schema_table_annotations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_schema_column_annotations_updated_at
    BEFORE UPDATE ON schema_column_annotations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_schema_relation_annotations_updated_at
    BEFORE UPDATE ON schema_relation_annotations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 完成！
"""


def get_migration_sql() -> str:
    """获取迁移 SQL"""
    return MIGRATION_SQL


def print_instructions():
    """打印使用说明"""
    print("""
╔════════════════════════════════════════════════════════════════╗
║     Supabase 数据库迁移 - Schema 语义标注表                      ║
╚════════════════════════════════════════════════════════════════╝

要创建标注表，请按照以下步骤操作：

方法 1: 在 Supabase 控制台执行 SQL
───────────────────────────────────
1. 打开 https://supabase.com 并登录您的项目
2. 进入左侧菜单 "SQL Editor"
3. 点击 "New query"
4. 复制下面的 SQL 并执行
5. 查看执行结果

方法 2: 使用 Python 脚本
───────────────────────
1. 运行 python supabase/create_annotation_tables.py

【待创建的表】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣  schema_table_annotations
   存储表级标注（表名、中英文描述、业务含义等）

2️⃣  schema_column_annotations
   存储列级标注（列名、数据类型、中英文描述、示例值等）

3️⃣  schema_relation_annotations
   存储关系标注（表间的外键关系、关系类型等）

4️⃣  annotation_audit_log
   存储标注变更历史（用于追踪谁修改了什么）

【标注流程】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. LLM 自动生成初始标注 → 状态: pending
2. 审核人员审查标注 → 状态: approved/rejected
3. 如果被拒绝，可修改后重新提交
4. 批准的标注用于改进 NL2SQL 的理解

【字段说明】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

表标注字段:
  - table_name_cn: 表的中文名称
  - description_cn: 表的中文描述
  - description_en: 表的英文描述  
  - business_meaning: 业务含义
  - use_case: 使用场景

列标注字段:
  - column_name_cn: 列的中文名称
  - data_type: 数据类型
  - example_value: 示例值
  - business_meaning: 业务含义
  - value_range: 取值范围

【下一步】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

表创建完成后：
1. 运行 python app/services/schema_annotator.py 来测试服务
2. 调用 API 端点开始标注流程
3. 在前端审核界面审核和编辑标注

    """)


if __name__ == "__main__":
    print_instructions()
    print("\n【SQL 脚本】")
    print("=" * 70)
    print(MIGRATION_SQL)
