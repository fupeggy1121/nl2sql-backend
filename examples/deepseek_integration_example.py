"""
DeepSeek API 集成使用示例
演示如何使用集成的 DeepSeek LLM 功能
"""
import os
import requests
import json
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

BASE_URL = "http://localhost:8000/api/query"

def example_1_health_check():
    """示例 1：检查服务健康状态"""
    print("\n=== 示例 1: 健康检查 ===")
    response = requests.get(f"{BASE_URL}/health")
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2)}")

def example_2_nl_to_sql():
    """示例 2：将自然语言转换为 SQL"""
    print("\n=== 示例 2: 自然语言转 SQL (使用 DeepSeek) ===")
    
    test_queries = [
        "查询所有用户的名字和邮箱",
        "获取id大于100的用户记录",
        "查询2024年1月后注册的用户",
        "统计每个部门的员工数量",
        "找出销售额最高的产品"
    ]
    
    for nl_query in test_queries:
        print(f"\n自然语言: {nl_query}")
        response = requests.post(
            f"{BASE_URL}/nl-to-sql",
            json={"natural_language": nl_query}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result['success']:
                print(f"生成的 SQL: {result['sql']}")
            else:
                print(f"转换失败: {result.get('error', 'Unknown error')}")
        else:
            print(f"请求失败，状态码: {response.status_code}")

def example_3_direct_execution():
    """示例 3：自然语言直接执行查询"""
    print("\n=== 示例 3: 自然语言直接执行 ===")
    
    nl_query = "查询所有活跃用户"
    print(f"自然语言查询: {nl_query}")
    
    response = requests.post(
        f"{BASE_URL}/nl-execute",
        json={"natural_language": nl_query}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"成功: {result['success']}")
        print(f"生成的 SQL: {result.get('sql', 'N/A')}")
        print(f"返回记录数: {result.get('count', 0)}")
        if result.get('data'):
            print(f"返回数据: {json.dumps(result['data'][:2], indent=2)}")
    else:
        print(f"请求失败，状态码: {response.status_code}")

def example_4_configuration_info():
    """示例 4: 显示 DeepSeek 配置信息"""
    print("\n=== 示例 4: 当前配置信息 ===")
    
    llm_provider = os.getenv('LLM_PROVIDER', 'deepseek')
    print(f"LLM 提供商: {llm_provider}")
    
    if llm_provider.lower() == 'deepseek':
        api_key = os.getenv('DEEPSEEK_API_KEY', '未配置')
        base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
        model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
        
        print(f"DeepSeek API URL: {base_url}")
        print(f"DeepSeek Model: {model}")
        print(f"DeepSeek API Key: {api_key[:10]}..." if api_key != '未配置' else "DeepSeek API Key: 未配置")
    
    elif llm_provider.lower() == 'openai':
        api_key = os.getenv('OPENAI_API_KEY', '未配置')
        model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
        
        print(f"OpenAI Model: {model}")
        print(f"OpenAI API Key: {api_key[:10]}..." if api_key != '未配置' else "OpenAI API Key: 未配置")

def main():
    """主函数"""
    print("=" * 60)
    print("DeepSeek API 集成 - 使用示例")
    print("=" * 60)
    
    try:
        # 运行示例
        example_1_health_check()
        example_2_nl_to_sql()
        example_3_direct_execution()
        example_4_configuration_info()
        
        print("\n" + "=" * 60)
        print("所有示例执行完成！")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("\n错误: 无法连接到服务器")
        print("请确保应用已启动: python run.py")
    except Exception as e:
        print(f"\n执行错误: {str(e)}")

if __name__ == "__main__":
    main()
