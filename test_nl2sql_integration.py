#!/usr/bin/env python3
"""
测试 NL2SQL 与 Schema Annotation 集成
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000/api"

def test_schema_metadata():
    """测试获取 schema 元数据"""
    print("\n1️⃣ 获取 Schema 元数据")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BASE_URL}/query/schema-metadata")
        if response.status_code == 200:
            data = response.json()
            summary = data.get('summary', {})
            print(f"✅ 成功加载元数据")
            print(f"   表数量: {summary.get('tables', 0)}")
            print(f"   列数量: {summary.get('columns', 0)}")
            if summary.get('table_names'):
                print(f"   表名: {', '.join(summary['table_names'])}")
            return True
        else:
            print(f"❌ 状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_nl_to_sql_enhanced(query):
    """测试增强的 NL2SQL 转换"""
    print(f"\n2️⃣ NL2SQL 增强转换: {query}")
    print("=" * 60)
    
    try:
        response = requests.post(
            f"{BASE_URL}/query/nl-to-sql/enhanced",
            json={"natural_language": query}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✅ 转换成功")
                print(f"   SQL: {data['sql']}")
                summary = data.get('metadata_summary', {})
                if summary:
                    print(f"   使用元数据: 表={summary.get('tables', 0)}, 列={summary.get('columns', 0)}")
                return True
            else:
                print(f"❌ 转换失败: {data.get('error')}")
                return False
        else:
            print(f"❌ 状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_nl_to_sql_comparison():
    """对比基础和增强模式"""
    print("\n3️⃣ 对比基础和增强模式")
    print("=" * 60)
    
    test_query = "查询生产订单信息"
    
    # 基础模式
    print(f"查询: {test_query}")
    print()
    
    try:
        response = requests.post(
            f"{BASE_URL}/query/nl-to-sql",
            json={"natural_language": test_query, "use_enhanced": False}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"基础模式 SQL: {data['sql']}")
        
        # 增强模式
        response = requests.post(
            f"{BASE_URL}/query/nl-to-sql",
            json={"natural_language": test_query, "use_enhanced": True}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"增强模式 SQL: {data['sql']}")
                
        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_refresh_metadata():
    """测试刷新元数据"""
    print("\n4️⃣ 刷新 Schema 元数据")
    print("=" * 60)
    
    try:
        response = requests.post(f"{BASE_URL}/query/schema-metadata/refresh")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                summary = data.get('summary', {})
                print(f"✅ 元数据刷新成功")
                print(f"   表数量: {summary.get('tables', 0)}")
                print(f"   列数量: {summary.get('columns', 0)}")
                return True
            else:
                print(f"❌ 刷新失败: {data.get('error')}")
                return False
        else:
            print(f"❌ 状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def main():
    """主测试函数"""
    print("╔════════════════════════════════════════════════════════════╗")
    print("║   🧪 NL2SQL + Schema Annotation 集成测试                   ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    # 检查后端是否运行
    try:
        response = requests.get(f"{BASE_URL}/query/health", timeout=2)
    except Exception as e:
        print(f"\n❌ 无法连接到后端: {e}")
        print("请确保后端正在运行: python run.py")
        sys.exit(1)
    
    results = []
    
    # 测试 1: 获取元数据
    results.append(("获取元数据", test_schema_metadata()))
    
    # 测试 2: 增强模式转换
    test_queries = [
        "查询所有生产订单",
        "显示设备信息",
        "查询订单数量",
    ]
    
    for query in test_queries:
        results.append((f"转换: {query}", test_nl_to_sql_enhanced(query)))
    
    # 测试 3: 对比两种模式
    results.append(("对比模式", test_nl_to_sql_comparison()))
    
    # 测试 4: 刷新元数据
    results.append(("刷新元数据", test_refresh_metadata()))
    
    # 打印总结
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {test_name}")
    
    print()
    print(f"总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print(f"\n⚠️ 有 {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
