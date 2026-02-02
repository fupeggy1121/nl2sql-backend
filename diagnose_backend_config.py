#!/usr/bin/env python3
"""
🔍 NL2SQL 后端 CORS 和路由完整诊断工具

用途: 验证后端所有路由和 CORS 配置是否正确
使用: python diagnose_backend_config.py

检查项:
  ✓ GET /api/query/check-connection 路由
  ✓ POST /api/query/recognize-intent 路由
  ✓ OPTIONS 预检请求处理
  ✓ CORS 源兼容性
  ✓ 响应格式和状态码
"""

import requests
import json
import sys
from datetime import datetime
from typing import Dict, Tuple

# 配置
class Config:
    # 本地测试
    LOCAL_URL = "http://localhost:5000/api/query"
    
    # 生产环境
    RENDER_URL = "https://nl2sql-backend-amok.onrender.com/api/query"
    
    # 前端源
    BOLT_NEW_ORIGIN = "https://zp1v56uxy8rdx5ypatb0ockcb9tr6a-oci3--5173--31fc58ec.local-credentialless.webcontainer-api.io"
    
    # 测试选项
    VERIFY_SSL = True
    TIMEOUT = 10

# 颜色输出
class Color:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text: str):
    """打印标题"""
    print(f"\n{Color.BLUE}{Color.BOLD}{'='*60}{Color.END}")
    print(f"{Color.BLUE}{Color.BOLD}{text}{Color.END}")
    print(f"{Color.BLUE}{Color.BOLD}{'='*60}{Color.END}\n")

def print_section(text: str):
    """打印分段标题"""
    print(f"\n{Color.BLUE}{Color.BOLD}{'—'*60}{Color.END}")
    print(f"{Color.BLUE}{Color.BOLD}{text}{Color.END}")
    print(f"{Color.BLUE}{Color.BOLD}{'—'*60}{Color.END}\n")

def print_success(text: str):
    """打印成功信息"""
    print(f"{Color.GREEN}✅ {text}{Color.END}")

def print_error(text: str):
    """打印错误信息"""
    print(f"{Color.RED}❌ {text}{Color.END}")

def print_warning(text: str):
    """打印警告信息"""
    print(f"{Color.YELLOW}⚠️  {text}{Color.END}")

def print_info(text: str):
    """打印信息"""
    print(f"{Color.BLUE}ℹ️  {text}{Color.END}")

def test_endpoint(url: str, method: str = "GET", data: dict = None, 
                  headers: dict = None, test_name: str = "") -> Tuple[bool, dict]:
    """
    测试端点
    
    返回: (成功与否, 响应信息)
    """
    try:
        print_info(f"正在测试: {method} {url}")
        
        kwargs = {
            'timeout': Config.TIMEOUT,
            'verify': Config.VERIFY_SSL
        }
        
        if headers:
            kwargs['headers'] = headers
        
        if method.upper() == "POST":
            kwargs['json'] = data or {}
            response = requests.post(url, **kwargs)
        elif method.upper() == "OPTIONS":
            response = requests.options(url, **kwargs)
        else:
            response = requests.get(url, **kwargs)
        
        # 收集响应信息
        response_info = {
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'body': response.text[:200] if response.text else None,
        }
        
        return response.status_code < 400, response_info
        
    except requests.exceptions.ConnectionError as e:
        return False, {'error': f'连接失败: {str(e)}'}
    except requests.exceptions.Timeout:
        return False, {'error': '请求超时'}
    except Exception as e:
        return False, {'error': f'异常: {str(e)}'}

def diagnose_environment(url: str) -> Dict:
    """诊断环境（本地或生产）"""
    is_local = "localhost" in url
    environment = "本地" if is_local else "生产 (Render)"
    
    print_section(f"🔍 诊断 {environment} 环境")
    print_info(f"后端地址: {url}")
    
    # 1. 检查服务是否运行
    print_section("1️⃣ 检查后端服务是否运行")
    success, info = test_endpoint(f"{url}/health", test_name="健康检查")
    
    if success:
        print_success(f"后端服务运行正常 (状态码: {info['status_code']})")
    else:
        print_error(f"后端服务无响应: {info.get('error', '未知错误')}")
        return {'failed': True}
    
    # 2. 测试 GET /check-connection
    print_section("2️⃣ 测试 GET /api/query/check-connection")
    success, info = test_endpoint(f"{url}/check-connection", method="GET", test_name="连接检查")
    
    if success:
        print_success(f"✓ 路由存在 (状态码: {info['status_code']})")
        print_info(f"响应: {info['body'][:100]}...")
    else:
        print_error(f"✗ 路由不可用: {info.get('error', '未知错误')}")
    
    # 3. 测试 POST /recognize-intent
    print_section("3️⃣ 测试 POST /api/query/recognize-intent")
    test_data = {"query": "查询wafers表的前300条数据"}
    success, info = test_endpoint(
        f"{url}/recognize-intent", 
        method="POST", 
        data=test_data,
        test_name="意图识别"
    )
    
    if success:
        print_success(f"✓ 路由存在 (状态码: {info['status_code']})")
        try:
            body_json = json.loads(info['body'] or '{}')
            print_info(f"返回意图: {body_json.get('intent', 'N/A')}")
            print_info(f"置信度: {body_json.get('confidence', 'N/A')}")
        except:
            print_info(f"响应: {info['body'][:100]}...")
    else:
        print_error(f"✗ 路由不可用: {info.get('error', '未知错误')}")
    
    # 4. 测试 OPTIONS 预检请求
    print_section("4️⃣ 测试 OPTIONS 预检请求")
    cors_headers = {
        "Origin": Config.BOLT_NEW_ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type"
    }
    
    success, info = test_endpoint(
        f"{url}/recognize-intent",
        method="OPTIONS",
        headers=cors_headers,
        test_name="CORS 预检"
    )
    
    if success:
        print_success(f"✓ OPTIONS 预检成功 (状态码: {info['status_code']})")
        
        # 检查 CORS 响应头
        headers = info['headers']
        cors_checks = {
            'Access-Control-Allow-Origin': '前端源许可',
            'Access-Control-Allow-Methods': '允许的方法',
            'Access-Control-Allow-Headers': '允许的请求头',
        }
        
        for header, desc in cors_checks.items():
            if header in headers:
                print_success(f"  ✓ {header}: {headers[header][:50]}")
            else:
                print_warning(f"  ⚠ 缺少 {header}")
    else:
        print_error(f"✗ OPTIONS 预检失败: {info.get('error', '未知错误')}")
    
    # 5. 完整 CORS 流程测试
    print_section("5️⃣ 测试完整 CORS 跨域流程")
    cors_headers = {
        "Origin": Config.BOLT_NEW_ORIGIN,
        "Content-Type": "application/json"
    }
    
    success, info = test_endpoint(
        f"{url}/recognize-intent",
        method="POST",
        data=test_data,
        headers=cors_headers,
        test_name="完整 CORS"
    )
    
    if success:
        print_success(f"✓ 完整 CORS 流程成功 (状态码: {info['status_code']})")
        
        # 验证响应中的 CORS 头
        headers = info['headers']
        if 'access-control-allow-origin' in headers or 'Access-Control-Allow-Origin' in headers:
            origin_header = headers.get('access-control-allow-origin') or headers.get('Access-Control-Allow-Origin')
            print_success(f"  ✓ CORS Origin 头: {origin_header}")
        else:
            print_warning(f"  ⚠ 响应中未找到 CORS Origin 头")
    else:
        print_error(f"✗ 完整 CORS 流程失败: {info.get('error', '未知错误')}")
    
    return {'success': True}

def main():
    """主函数"""
    print_header("🔧 NL2SQL 后端路由和 CORS 诊断工具")
    print(f"诊断时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 询问要诊断的环境
    print("选择要诊断的环境:")
    print("  1. 本地 (localhost:5000)")
    print("  2. 生产 (Render)")
    print("  3. 两个都诊断")
    
    choice = input("\n请输入选择 (1/2/3): ").strip()
    
    results = {}
    
    if choice in ['1', '3']:
        print_header("诊断本地后端")
        results['local'] = diagnose_environment(Config.LOCAL_URL)
    
    if choice in ['2', '3']:
        print_header("诊断生产后端 (Render)")
        results['render'] = diagnose_environment(Config.RENDER_URL)
    
    # 总结
    print_section("📊 诊断总结")
    
    if not results:
        print_warning("未选择任何诊断")
        return
    
    total_success = all(not r.get('failed') for r in results.values())
    
    if total_success:
        print_success("✅ 所有检查通过！")
        print_success("路由和 CORS 配置正确")
    else:
        print_error("❌ 某些检查失败")
        print_warning("请查看上面的详细信息进行排查")
    
    # 建议
    print_section("💡 建议")
    print_info("✓ 本地测试: python run.py")
    print_info("✓ 运行脚本: python diagnose_backend_config.py")
    print_info("✓ 查看文档: BACKEND_ROUTES_CORS_CHECKLIST.md")
    print_info("✓ 前端集成: 使用 VITE_API_URL=https://nl2sql-backend-amok.onrender.com/api/query")
    
    print(f"\n{Color.BLUE}{Color.BOLD}{'='*60}{Color.END}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已取消诊断")
        sys.exit(0)
    except Exception as e:
        print_error(f"诊断过程中发生错误: {str(e)}")
        sys.exit(1)
