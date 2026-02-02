#!/usr/bin/env python3
"""
服务联通性测试脚本
测试范围：
1. 后端服务健康检查
2. 前后端通信测试
3. Supabase数据库连接测试
4. NL2SQL端点功能测试
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

def print_header(title):
    """打印测试标题"""
    print("\n" + "="*60)
    print(f"🔍 {title}")
    print("="*60)

def print_success(msg):
    """打印成功消息"""
    print(f"✅ {msg}")

def print_error(msg):
    """打印错误消息"""
    print(f"❌ {msg}")

def print_info(msg):
    """打印信息消息"""
    print(f"ℹ️  {msg}")

def print_warning(msg):
    """打印警告消息"""
    print(f"⚠️  {msg}")

# ============================================================================
# 第1部分：后端服务检查
# ============================================================================

def test_backend_health():
    """测试后端服务健康状态"""
    print_header("后端服务健康检查")
    
    try:
        from app import create_app
        app = create_app()
        print_success("应用导入成功")
        
        # 创建测试客户端
        with app.test_client() as client:
            response = client.get('/api/query/health')
            if response.status_code == 200:
                data = response.get_json()
                print_success(f"后端服务正常运行: {data}")
                return True
            else:
                print_error(f"后端服务异常 (状态码: {response.status_code})")
                return False
    except Exception as e:
        print_error(f"后端服务检查失败: {str(e)}")
        return False

# ============================================================================
# 第2部分：Supabase连接检查
# ============================================================================

def test_supabase_connection():
    """测试Supabase数据库连接"""
    print_header("Supabase数据库连接检查")
    
    try:
        from app.services.supabase_client import get_supabase_client
        
        # 获取Supabase客户端
        sb = get_supabase_client()
        if not sb:
            print_error("Supabase客户端初始化失败")
            return False
        
        print_success("Supabase客户端初始化成功")
        
        # 测试数据库连接
        try:
            # 尝试查询一个小的表
            result = sb.client.table('wafers').select('id').limit(1).execute()
            print_success(f"Supabase数据库连接正常")
            print_info(f"查询示例: {len(result.data)} 条记录")
            return True
        except Exception as e:
            print_error(f"数据库查询失败: {str(e)}")
            return False
            
    except Exception as e:
        print_error(f"Supabase连接检查失败: {str(e)}")
        return False

# ============================================================================
# 第3部分：NL2SQL端点测试
# ============================================================================

def test_nl2sql_endpoint():
    """测试NL2SQL转换端点"""
    print_header("NL2SQL端点测试")
    
    try:
        from app import create_app
        app = create_app()
        
        test_queries = [
            "查询所有用户",
            "显示wafers表的前100条数据",
            "SELECT * FROM wafers LIMIT 10",
        ]
        
        with app.test_client() as client:
            for query in test_queries:
                print_info(f"测试查询: {query}")
                response = client.post(
                    '/api/query/nl-to-sql',
                    json={'natural_language': query}
                )
                
                if response.status_code == 200:
                    data = response.get_json()
                    if data.get('success'):
                        print_success(f"✓ 生成SQL: {data.get('sql', 'N/A')}")
                    else:
                        print_warning(f"⚠ 转换失败: {data.get('error', 'Unknown error')}")
                else:
                    print_error(f"❌ 状态码 {response.status_code}")
        
        return True
    except Exception as e:
        print_error(f"NL2SQL端点测试失败: {str(e)}")
        return False

# ============================================================================
# 第4部分：查询执行测试
# ============================================================================

def test_query_execution():
    """测试查询执行"""
    print_header("查询执行测试")
    
    try:
        from app.services.query_executor import QueryExecutor
        from app.services.supabase_client import get_supabase_client
        
        sb = get_supabase_client()
        if not sb:
            print_error("无法初始化Supabase客户端")
            return False
        
        executor = QueryExecutor(sb)
        print_success("查询执行器初始化成功")
        
        # 测试简单查询
        test_sql = "SELECT * FROM wafers LIMIT 5"
        print_info(f"执行测试SQL: {test_sql}")
        
        result = executor.execute_query(test_sql)
        if result:
            print_success(f"查询成功执行，返回 {len(result)} 条记录")
            if result:
                print_info(f"样本数据: {result[0]}")
            return True
        else:
            print_warning("查询返回空结果")
            return True
            
    except Exception as e:
        print_error(f"查询执行失败: {str(e)}")
        return False

# ============================================================================
# 第5部分：远程服务测试（如果应用在线）
# ============================================================================

def test_remote_connectivity(url):
    """测试远程服务连接"""
    print_header(f"远程服务连接测试: {url}")
    
    try:
        # 测试健康检查端点
        print_info(f"测试远程健康检查端点...")
        response = requests.get(f"{url}/api/query/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"远程服务正常: {data}")
            
            # 测试NL2SQL端点
            print_info("测试远程NL2SQL端点...")
            response = requests.post(
                f"{url}/api/query/nl-to-sql",
                json={'natural_language': '查询所有用户'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print_success(f"NL2SQL远程端点正常: {data}")
                return True
            else:
                print_warning(f"NL2SQL端点异常 (状态码: {response.status_code})")
                return False
        else:
            print_error(f"远程服务异常 (状态码: {response.status_code})")
            return False
            
    except requests.exceptions.Timeout:
        print_error("远程服务请求超时")
        return False
    except Exception as e:
        print_error(f"远程服务测试失败: {str(e)}")
        return False

# ============================================================================
# 主测试函数
# ============================================================================

def main():
    """运行所有测试"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  NL2SQL 服务联通性测试套件".center(58) + "║")
    print("║" + f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    
    results = {}
    
    # 1. 后端服务检查
    results['Backend Health'] = test_backend_health()
    
    # 2. Supabase连接检查
    results['Supabase Connection'] = test_supabase_connection()
    
    # 3. NL2SQL端点测试
    results['NL2SQL Endpoint'] = test_nl2sql_endpoint()
    
    # 4. 查询执行测试
    results['Query Execution'] = test_query_execution()
    
    # 5. 远程服务测试（可选）
    print_header("远程服务测试（可选）")
    remote_urls = [
        # 如果有部署在线的服务，添加URL
        # "https://your-deployed-service.com",
    ]
    
    if remote_urls:
        for url in remote_urls:
            results[f'Remote Service ({url})'] = test_remote_connectivity(url)
    else:
        print_info("未配置远程服务URL，跳过远程测试")
        print_info("如需测试远程服务，请编辑此脚本并添加URL到 remote_urls 列表")
    
    # ========================================================================
    # 测试总结
    # ========================================================================
    
    print_header("测试总结")
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    # 计算通过率
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    success_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"\n总体通过率: {passed}/{total} ({success_rate:.0f}%)")
    
    if success_rate == 100:
        print_success("所有测试通过！系统运行正常 🎉")
    elif success_rate >= 75:
        print_warning("大部分测试通过，但存在些许问题")
    else:
        print_error("存在多个测试失败，请检查配置")
    
    print()

if __name__ == '__main__':
    main()
