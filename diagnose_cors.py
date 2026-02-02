"""
后端 CORS 和路由诊断脚本
测试所有关键端点的 OPTIONS 和实际请求
"""

import requests
import json
from typing import Dict, Any

class CORSDiagnostics:
    """CORS 诊断工具"""
    
    def __init__(self, backend_url: str):
        self.backend_url = backend_url
        self.frontend_origin = "https://zp1v56uxy8rdx5ypatb0ockcb9tr6a-oci3--5173--31fc58ec.local-credentialless.webcontainer-api.io"
    
    def test_endpoint(self, endpoint: str, method: str = "GET") -> Dict[str, Any]:
        """
        测试单个端点
        
        Returns:
            {
                'endpoint': str,
                'method': str,
                'preflight_status': int,
                'preflight_headers': dict,
                'actual_status': int,
                'cors_headers': dict,
                'success': bool
            }
        """
        url = f"{self.backend_url}{endpoint}"
        headers = {
            'Origin': self.frontend_origin,
            'Access-Control-Request-Method': method,
            'Access-Control-Request-Headers': 'Content-Type'
        }
        
        result = {
            'endpoint': endpoint,
            'method': method,
            'preflight_status': None,
            'preflight_headers': {},
            'actual_status': None,
            'cors_headers': {},
            'success': False
        }
        
        try:
            # 1. 测试 OPTIONS 预检请求
            print(f"\n📍 Testing {method} {endpoint}")
            print(f"   Sending OPTIONS preflight request...")
            
            response_options = requests.options(url, headers=headers, timeout=10)
            result['preflight_status'] = response_options.status_code
            result['preflight_headers'] = dict(response_options.headers)
            
            print(f"   ✓ Preflight status: {response_options.status_code}")
            
            # 检查 CORS 响应头
            cors_headers = {
                'Access-Control-Allow-Origin': response_options.headers.get('Access-Control-Allow-Origin'),
                'Access-Control-Allow-Methods': response_options.headers.get('Access-Control-Allow-Methods'),
                'Access-Control-Allow-Headers': response_options.headers.get('Access-Control-Allow-Headers'),
            }
            
            for key, value in cors_headers.items():
                if value:
                    print(f"   ✓ {key}: {value}")
            
            # 2. 测试实际请求
            if response_options.status_code == 200:
                print(f"   Sending actual {method} request...")
                
                if method == "GET":
                    response_actual = requests.get(url, headers={'Origin': self.frontend_origin}, timeout=10)
                elif method == "POST":
                    response_actual = requests.post(
                        url, 
                        headers={'Origin': self.frontend_origin, 'Content-Type': 'application/json'},
                        json={'query': 'test'},
                        timeout=10
                    )
                
                result['actual_status'] = response_actual.status_code
                result['cors_headers'] = {
                    'Access-Control-Allow-Origin': response_actual.headers.get('Access-Control-Allow-Origin'),
                }
                
                print(f"   ✓ Actual request status: {response_actual.status_code}")
                
                result['success'] = (
                    result['preflight_status'] == 200 and
                    result['actual_status'] in [200, 400, 500]  # 不是 404 就算成功
                )
            else:
                print(f"   ✗ Preflight failed with status {response_options.status_code}")
                result['success'] = False
        
        except Exception as e:
            print(f"   ✗ Error: {str(e)}")
            result['success'] = False
        
        return result

def main():
    """运行诊断"""
    
    print("=" * 70)
    print("后端 CORS 和路由诊断")
    print("=" * 70)
    
    # 测试两个后端 URL
    backends = [
        ("Render Production", "https://nl2sql-backend-amok.onrender.com"),
        ("Local Development", "http://localhost:5000"),
    ]
    
    endpoints_to_test = [
        ("/api/query/health", "GET"),
        ("/api/query/check-connection", "GET"),
        ("/api/query/supabase/connection", "GET"),
        ("/api/query/recognize-intent", "POST"),
        ("/api/query/nl-to-sql", "POST"),
    ]
    
    for backend_name, backend_url in backends:
        print(f"\n\n{'='*70}")
        print(f"🔗 Testing: {backend_name}")
        print(f"   URL: {backend_url}")
        print(f"{'='*70}")
        
        diagnostics = CORSDiagnostics(backend_url)
        
        results = []
        for endpoint, method in endpoints_to_test:
            result = diagnostics.test_endpoint(endpoint, method)
            results.append(result)
        
        # 汇总结果
        print(f"\n\n📊 Summary for {backend_name}:")
        print("-" * 70)
        
        passed = sum(1 for r in results if r['success'])
        total = len(results)
        
        for result in results:
            status = "✅" if result['success'] else "❌"
            print(f"{status} {result['method']:4} {result['endpoint']:40} "
                  f"Preflight: {result['preflight_status'] or 'N/A':3} | "
                  f"Actual: {result['actual_status'] or 'N/A':3}")
        
        print(f"\nPassed: {passed}/{total}")
        
        if passed == total:
            print(f"✅ All tests passed for {backend_name}!")
        else:
            print(f"⚠️  Some tests failed for {backend_name}")

if __name__ == '__main__':
    main()
