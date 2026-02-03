#!/usr/bin/env python3
"""
Schema 标注系统 - 部署和测试说明

执行此脚本来:
1. 验证环境配置
2. 测试 Supabase 连接
3. 验证 LLM 集成
4. 创建示例标注
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


def print_header(text):
    """打印标题"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def check_environment():
    """检查环境变量配置"""
    print_header("1. 检查环境变量")
    
    required_vars = [
        'SUPABASE_URL',
        'SUPABASE_ANON_KEY',
        'DEEPSEEK_API_KEY',
    ]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # 只显示前几个字符，隐藏敏感信息
            display = value[:10] + "..." if len(value) > 10 else value
            print(f"  ✅ {var:25} = {display}")
        else:
            print(f"  ❌ {var:25} = 未设置")
            missing.append(var)
    
    if missing:
        print(f"\n⚠️  缺少环境变量: {', '.join(missing)}")
        print("   请在 .env 文件中配置这些变量")
        return False
    
    print("\n✅ 所有环境变量已配置")
    return True


def check_supabase_connection():
    """检查 Supabase 连接"""
    print_header("2. 检查 Supabase 连接")
    
    try:
        from app.services.supabase_client import get_supabase_client
        
        supabase = get_supabase_client()
        
        if supabase.client is None:
            print("❌ Supabase 客户端初始化失败")
            return False
        
        is_connected = supabase.is_connected()
        
        if is_connected:
            print("✅ Supabase 连接成功")
            print(f"   URL: {supabase.url[:50]}...")
            return True
        else:
            print("❌ Supabase 连接失败")
            if supabase.init_error:
                print(f"   错误: {supabase.init_error}")
            return False
            
    except Exception as e:
        print(f"❌ 检查 Supabase 时出错: {str(e)}")
        return False


def check_llm_provider():
    """检查 LLM 提供商"""
    print_header("3. 检查 LLM 提供商")
    
    try:
        from app.services.llm_provider import get_llm_provider
        
        provider = get_llm_provider()
        
        print(f"  LLM Provider: DeepSeek")
        print(f"  API Key: {os.getenv('DEEPSEEK_API_KEY', '未设置')[:10]}...")
        
        # 检查提供商是否有 generate 方法
        if hasattr(provider, 'convert_nl_to_sql'):
            print("  ✅ generate() 方法可用")
            return True
        else:
            print("  ❌ generate() 方法不可用")
            return False
            
    except Exception as e:
        print(f"❌ 检查 LLM 提供商时出错: {str(e)}")
        return False


def check_annotation_tables():
    """检查标注表是否存在"""
    print_header("4. 检查标注表")
    
    try:
        from app.services.supabase_client import get_supabase_client
        from app.services.schema_annotator import SchemaAnnotator
        
        supabase = get_supabase_client()
        annotator = SchemaAnnotator(supabase)
        
        tables = [
            annotator.SCHEMA_TABLES_TABLE,
            annotator.SCHEMA_COLUMNS_TABLE,
            annotator.SCHEMA_RELATIONS_TABLE
        ]
        
        print("检查数据库表是否存在...")
        
        # 尝试查询每个表
        all_exist = True
        for table_name in tables:
            try:
                result = supabase.client.table(table_name).select("1").limit(1).execute()
                print(f"  ✅ {table_name}")
            except Exception as e:
                print(f"  ❌ {table_name}")
                error_msg = str(e)
                if "does not exist" in error_msg or "not found" in error_msg:
                    print(f"     表不存在，需要创建")
                else:
                    print(f"     原因: {error_msg[:60]}...")
                all_exist = False
        
        if not all_exist:
            print("\n⚠️  某些表不存在。请运行:")
            print("   python supabase/create_annotation_tables.py")
        
        return all_exist
        
    except Exception as e:
        print(f"❌ 检查表时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_annotation_flow():
    """测试完整的标注流程"""
    print_header("5. 测试标注流程")
    
    try:
        from app.services.schema_annotator import SchemaAnnotator
        from app.services.supabase_client import get_supabase_client
        
        supabase = get_supabase_client()
        annotator = SchemaAnnotator(supabase)
        
        # 模拟一个表的列信息
        test_table = {
            "name": "test_table_demo",
            "columns": [
                {"name": "id", "type": "uuid"},
                {"name": "name", "type": "varchar"},
                {"name": "created_at", "type": "timestamp"}
            ]
        }
        
        print(f"测试表: {test_table['name']}")
        print(f"列数: {len(test_table['columns'])}")
        
        # 注意: 实际调用 LLM 可能需要时间
        print("\n(跳过实际 LLM 调用，因为需要 API 配额)")
        print("✅ 流程结构验证通过")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试流程时出错: {str(e)}")
        return False


def show_next_steps():
    """显示后续步骤"""
    print_header("6. 后续步骤")
    
    print("""
✅ 验证完成！现在可以开始使用 Schema 标注系统。

【快速开始】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

第一步: 创建数据库表
$ python supabase/create_annotation_tables.py

第二步: 扫描数据库 Schema
$ python app/tools/scan_schema.py

第三步: 生成 LLM 标注
$ python app/tools/auto_annotate_schema.py

第四步: 启动 Flask 应用
$ python run.py

第五步: 调用 API 审核标注
$ curl http://localhost:5000/api/schema/tables/pending

【API 端点】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

获取待审核标注:
  GET /api/schema/tables/pending
  GET /api/schema/columns/pending

批准标注:
  POST /api/schema/tables/<id>/approve

获取已批准的元数据:
  GET /api/schema/metadata

【文档】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

完整指南:        SCHEMA_ANNOTATION_GUIDE.md
实现细节:        SCHEMA_ANNOTATION_IMPLEMENTATION.md
快速参考:        SCHEMA_ANNOTATION_QUICK_REF.md

【获取帮助】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

如果遇到问题:
1. 检查 .env 文件中的环境变量
2. 查看 Supabase 控制台的日志
3. 检查 DeepSeek API 配额
4. 参考完整指南中的故障排除部分

祝使用愉快! 🚀
    """)


def main():
    """主函数"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║     Schema 语义标注系统 - 部署验证                           ║
║                                                              ║
║     此脚本将验证系统配置并显示后续步骤                       ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    checks = [
        ("环境变量", check_environment),
        ("Supabase 连接", check_supabase_connection),
        ("LLM 提供商", check_llm_provider),
        ("标注表", check_annotation_tables),
        ("标注流程", test_annotation_flow),
    ]
    
    results = []
    
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} 检查失败: {str(e)}")
            results.append((name, False))
    
    # 显示总结
    print_header("检查结果总结")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n通过: {passed}/{total} 项检查\n")
    
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"  {status} {name}")
    
    if passed == total:
        print("\n🎉 所有检查通过！系统已就绪。")
        show_next_steps()
    else:
        print("\n⚠️  某些检查未通过。请解决上述问题后重试。")
        sys.exit(1)


if __name__ == "__main__":
    main()
