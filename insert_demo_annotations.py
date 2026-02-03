#!/usr/bin/env python3
"""
手动插入演示标注数据
用于测试审核和批准流程
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from app.services.supabase_client import get_supabase_client

load_dotenv()


def insert_demo_annotations():
    """插入演示标注数据"""
    supabase = get_supabase_client()
    
    if not supabase.is_connected():
        print("❌ 无法连接到 Supabase")
        return False
    
    # 演示表标注数据
    table_annotations = [
        {
            "table_name": "production_orders",
            "table_name_cn": "生产订单",
            "description_cn": "存储来自客户的生产订单信息",
            "description_en": "Storage for production orders from customers",
            "business_meaning": "用于跟踪和管理生产计划",
            "use_case": "订单录入、生产排期、订单跟踪",
            "status": "pending"
        },
        {
            "table_name": "equipment",
            "table_name_cn": "设备信息",
            "description_cn": "存储生产线中的所有设备信息",
            "description_en": "Storage for all equipment in production line",
            "business_meaning": "设备资产管理和维护追踪",
            "use_case": "设备清单、维保记录、故障报警",
            "status": "pending"
        }
    ]
    
    # 演示列标注数据
    column_annotations = [
        {
            "table_name": "production_orders",
            "column_name": "order_number",
            "column_name_cn": "订单编号",
            "data_type": "varchar",
            "description_cn": "唯一的订单编号",
            "description_en": "Unique order number",
            "example_value": "ORD-2026-001",
            "business_meaning": "用于识别订单",
            "value_range": "6-20 字符",
            "status": "pending"
        },
        {
            "table_name": "production_orders",
            "column_name": "quantity",
            "column_name_cn": "生产数量",
            "data_type": "integer",
            "description_cn": "需要生产的产品数量",
            "description_en": "Quantity of products to produce",
            "example_value": "1000",
            "business_meaning": "生产任务的规模",
            "value_range": "1-999999",
            "status": "pending"
        },
        {
            "table_name": "production_orders",
            "column_name": "status",
            "column_name_cn": "订单状态",
            "data_type": "varchar",
            "description_cn": "订单的当前状态",
            "description_en": "Current status of the order",
            "example_value": "pending, processing, completed, cancelled",
            "business_meaning": "追踪订单生命周期",
            "value_range": "pending, processing, completed, cancelled",
            "status": "pending"
        },
        {
            "table_name": "equipment",
            "column_name": "equipment_code",
            "column_name_cn": "设备编码",
            "data_type": "varchar",
            "description_cn": "设备的唯一识别码",
            "description_en": "Unique identifier for equipment",
            "example_value": "EQ-001",
            "business_meaning": "设备编码",
            "value_range": "3-10 字符",
            "status": "pending"
        },
        {
            "table_name": "equipment",
            "column_name": "equipment_type",
            "column_name_cn": "设备类型",
            "data_type": "varchar",
            "description_cn": "设备的类型分类",
            "description_en": "Type of equipment",
            "example_value": "CNC Machine, Assembly Line, Quality Tester",
            "business_meaning": "设备功能分类",
            "value_range": "CNC, Assembly, Tester, Packer, etc",
            "status": "pending"
        }
    ]
    
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║     插入演示标注数据                                            ║")
    print("╚════════════════════════════════════════════════════════════════╝\n")
    
    try:
        # 插入表标注
        print("📋 插入表标注...")
        for annotation in table_annotations:
            try:
                result = supabase.client.table('schema_table_annotations').insert(
                    annotation
                ).execute()
                print(f"  ✅ {annotation['table_name_cn']}")
            except Exception as e:
                print(f"  ❌ {annotation['table_name_cn']}: {str(e)[:60]}")
        
        # 插入列标注
        print("\n📊 插入列标注...")
        for annotation in column_annotations:
            try:
                result = supabase.client.table('schema_column_annotations').insert(
                    annotation
                ).execute()
                print(f"  ✅ {annotation['table_name']}.{annotation['column_name']}")
            except Exception as e:
                print(f"  ❌ {annotation['table_name']}.{annotation['column_name']}: {str(e)[:60]}")
        
        print("\n✅ 演示数据插入完成！\n")
        
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("【下一步】")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        
        print("1️⃣  启动后端应用:")
        print("   .venv/bin/python run.py\n")
        
        print("2️⃣  查看待审核的标注:")
        print("   curl http://localhost:5000/api/schema/tables/pending\n")
        
        print("3️⃣  批准标注:")
        print("   curl -X POST http://localhost:5000/api/schema/tables/{id}/approve \\")
        print("        -H 'Content-Type: application/json' \\")
        print("        -d '{\"reviewer\": \"admin\", \"notes\": \"approved\"}'\n")
        
        return True
        
    except Exception as e:
        print(f"❌ 插入失败: {str(e)}")
        return False


if __name__ == "__main__":
    success = insert_demo_annotations()
    sys.exit(0 if success else 1)
