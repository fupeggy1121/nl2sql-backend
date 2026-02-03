#!/usr/bin/env python3
"""
自动标注脚本
使用 LLM 为数据库 schema 生成语义标注
"""
import os
import sys
import json
import asyncio
import logging
from typing import Dict, List, Any
from datetime import datetime
from dotenv import load_dotenv

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()


async def auto_annotate_schema():
    """
    自动标注整个数据库 schema
    
    流程:
    1. 扫描数据库获取 schema
    2. 为每个表调用 LLM 生成标注
    3. 保存标注到 Supabase
    4. 返回标注摘要
    """
    try:
        from app.services.schema_annotator import schema_annotator
        from app.tools.scan_schema import DatabaseSchemaScanner
        
        logger.info("=" * 70)
        logger.info("开始 Schema 自动标注")
        logger.info("=" * 70)
        
        # 第一步: 扫描 schema
        logger.info("\n【第一步】扫描数据库 Schema...")
        scanner = DatabaseSchemaScanner()
        schema = scanner.scan_schema()
        
        if not schema.get('tables'):
            logger.error("❌ 未找到任何表")
            return
        
        logger.info(f"✅ 扫描完成: {len(schema['tables'])} 个表\n")
        
        # 第二步: 为每个表生成标注
        logger.info("【第二步】使用 LLM 生成标注...")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        
        all_annotations = []
        
        for i, table in enumerate(schema['tables'], 1):
            table_name = table['name']
            columns = table['columns']
            
            logger.info(f"[{i}/{len(schema['tables'])}] 标注表: {table_name}")
            
            try:
                # 调用 LLM 生成标注
                annotation = await schema_annotator.auto_annotate_table(
                    table_name,
                    columns
                )
                
                all_annotations.append(annotation)
                
                # 显示生成的标注摘要
                if isinstance(annotation, dict) and 'table_name_cn' in annotation:
                    print(f"    ✓ {annotation.get('table_name_cn', table_name)}")
                    if 'description_cn' in annotation:
                        print(f"      描述: {annotation['description_cn'][:50]}...")
                else:
                    print(f"    ✓ 标注生成完成")
                
            except Exception as e:
                logger.error(f"    ✗ 标注失败: {str(e)}")
                continue
        
        logger.info(f"\n✅ 标注生成完成: {len(all_annotations)} 个表")
        
        # 第三步: 保存标注到数据库
        logger.info("\n【第三步】保存标注到数据库...")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        
        saved_tables = []
        saved_columns = 0
        
        for annotation in all_annotations:
            try:
                # 保存表标注
                if isinstance(annotation, dict) and 'table_name_en' in annotation:
                    table_result = await schema_annotator.save_table_annotation(annotation)
                    saved_tables.append(annotation['table_name_en'])
                    
                    # 保存列标注
                    if 'columns' in annotation:
                        column_results = await schema_annotator.save_column_annotations(
                            annotation['table_name_en'],
                            annotation['columns']
                        )
                        saved_columns += len(column_results)
                        
                        logger.info(f"  ✓ {annotation['table_name_en']}: "
                                  f"{len(column_results)} 列标注已保存")
                
            except Exception as e:
                logger.error(f"  ✗ 保存失败: {str(e)}")
                continue
        
        # 显示摘要
        logger.info("\n" + "=" * 70)
        logger.info("【完成摘要】")
        logger.info("=" * 70)
        print(f"\n📊 标注统计:")
        print(f"  • 表数量: {len(saved_tables)}")
        print(f"  • 列数量: {saved_columns}")
        print(f"  • 状态: 待审核 (pending)")
        print(f"\n📌 下一步:")
        print(f"  1. 访问审核界面查看生成的标注")
        print(f"  2. 编辑和审核每个标注")
        print(f"  3. 批准已确认的标注")
        print(f"  4. 使用批准的标注来改进 NL2SQL 的理解")
        
        print(f"\n🔗 API 端点:")
        print(f"  • 获取待审核标注: GET /api/schema/tables/pending")
        print(f"  • 批准标注: POST /api/schema/tables/<id>/approve")
        print(f"  • 获取已批准的元数据: GET /api/schema/metadata")
        
        logger.info("\n✅ 自动标注流程完成")
        
    except ImportError as e:
        logger.error(f"❌ 导入错误: {str(e)}")
        logger.error("请确保已安装所有依赖: pip install -r requirements.txt")
    except Exception as e:
        logger.error(f"❌ 执行失败: {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    print("""
╔════════════════════════════════════════════════════════════════╗
║     Schema 自动标注工具                                         ║
║     使用 DeepSeek LLM 生成数据库语义标注                        ║
╚════════════════════════════════════════════════════════════════╝

【流程】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣  扫描数据库获取 table 和 column 信息
2️⃣  调用 DeepSeek LLM 为每个 table 生成标注
3️⃣  LLM 生成以下内容:
   - 中文表名和列名
   - 中英文描述
   - 业务含义和使用场景
   - 数据类型和示例值
   - 取值范围说明
4️⃣  将标注保存到 Supabase (状态: pending)
5️⃣  在审核界面手动检查和批准标注

【注意】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• 需要先运行: python supabase/create_annotation_tables.py
  来创建标注数据表
  
• 需要配置环境变量:
  - SUPABASE_URL
  - SUPABASE_ANON_KEY
  - DEEPSEEK_API_KEY

【执行】
    """)
    
    # 运行异步函数
    asyncio.run(auto_annotate_schema())


if __name__ == "__main__":
    main()
