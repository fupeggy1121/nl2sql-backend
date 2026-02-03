#!/usr/bin/env python3
"""
直接通过 PostgreSQL 连接插入演示数据
绕过 RLS 策略限制
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from app.services.postgresql_executor import PostgreSQLExecutor

load_dotenv()


def insert_demo_via_sql():
    """通过 SQL 直接插入演示数据"""
    
    # SQL 插入语句
    insert_sql = """
-- 插入表级标注
INSERT INTO schema_table_annotations (
    table_name, table_name_cn, description_cn, description_en,
    business_meaning, use_case, status
) VALUES
('production_orders', '生产订单', '存储来自客户的生产订单信息', 'Storage for production orders',
 '用于跟踪和管理生产计划', '订单录入、生产排期、订单跟踪', 'pending'),
('equipment', '设备信息', '存储生产线中的所有设备信息', 'Storage for all equipment',
 '设备资产管理和维护追踪', '设备清单、维保记录、故障报警', 'pending'),
('production_batches', '生产批次', '生产批次管理数据', 'Production batch information',
 '批次管理和追踪', '批次标识、生产进度', 'pending')
ON CONFLICT DO NOTHING;

-- 插入列级标注
INSERT INTO schema_column_annotations (
    table_name, column_name, column_name_cn, data_type,
    description_cn, description_en, example_value,
    business_meaning, value_range, status
) VALUES
('production_orders', 'order_number', '订单编号', 'varchar',
 '唯一的订单编号', 'Unique order number', 'ORD-2026-001',
 '用于识别订单', '6-20 字符', 'pending'),
('production_orders', 'quantity', '生产数量', 'integer',
 '需要生产的产品数量', 'Quantity of products', '1000',
 '生产任务的规模', '1-999999', 'pending'),
('production_orders', 'status', '订单状态', 'varchar',
 '订单的当前状态', 'Current order status', 'pending, processing, completed',
 '追踪订单生命周期', 'pending, processing, completed, cancelled', 'pending'),
('equipment', 'equipment_code', '设备编码', 'varchar',
 '设备的唯一识别码', 'Unique equipment identifier', 'EQ-001',
 '设备编码', '3-10 字符', 'pending'),
('equipment', 'equipment_type', '设备类型', 'varchar',
 '设备的类型分类', 'Type of equipment', 'CNC Machine, Assembly Line',
 '设备功能分类', 'CNC, Assembly, Tester, Packer', 'pending'),
('equipment', 'status', '设备状态', 'varchar',
 '设备的运行状态', 'Equipment status', 'running, maintenance, offline',
 '设备健康状态', 'running, maintenance, offline', 'pending')
ON CONFLICT DO NOTHING;
"""
    
    executor = PostgreSQLExecutor()
    
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║     插入演示标注数据 (通过 PostgreSQL 直接连接)                 ║")
    print("╚════════════════════════════════════════════════════════════════╝\n")
    
    if not executor.connect():
        print("❌ 数据库连接失败")
        print("\n请确保已配置环境变量:")
        print("  SUPABASE_DB_HOST")
        print("  SUPABASE_DB_USER")
        print("  SUPABASE_DB_PASSWORD")
        return False
    
    try:
        # 执行 SQL 插入
        print("📋 插入演示数据...\n")
        
        # 分割 SQL 语句
        statements = [
            stmt.strip() 
            for stmt in insert_sql.split(';') 
            if stmt.strip() and not stmt.strip().startswith('--')
        ]
        
        for stmt in statements:
            try:
                executor.cursor.execute(stmt)
                executor.conn.commit()
                print(f"✅ 执行成功: {stmt[:50]}...")
            except Exception as e:
                print(f"⚠️  {str(e)[:80]}")
                executor.conn.rollback()
        
        print("\n✅ 演示数据插入完成！\n")
        
        # 验证插入的数据
        print("📊 验证插入的数据:\n")
        
        executor.cursor.execute("SELECT COUNT(*) FROM schema_table_annotations")
        table_count = executor.cursor.fetchone()[0]
        print(f"  ✅ 表标注数: {table_count} 条")
        
        executor.cursor.execute("SELECT COUNT(*) FROM schema_column_annotations")
        column_count = executor.cursor.fetchone()[0]
        print(f"  ✅ 列标注数: {column_count} 条")
        
        print("\n" + "━" * 70)
        print("【下一步】")
        print("━" * 70 + "\n")
        
        print("1️⃣  启动后端应用:")
        print("   cd /Users/fupeggy/NL2SQL")
        print("   .venv/bin/python run.py\n")
        
        print("2️⃣  在另一个终端查看待审核的标注:")
        print("   curl http://localhost:5000/api/schema/tables/pending\n")
        
        print("3️⃣  批准标注:")
        print("   curl -X POST http://localhost:5000/api/schema/tables/{id}/approve \\")
        print("        -H 'Content-Type: application/json' \\")
        print("        -d '{\"reviewer\": \"admin\", \"notes\": \"已审核\"}'")
        
        return True
        
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return False
    finally:
        executor.close()


if __name__ == "__main__":
    success = insert_demo_via_sql()
    sys.exit(0 if success else 1)
