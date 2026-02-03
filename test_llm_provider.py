#!/usr/bin/env python
"""
LLM 提供商连接诊断工具
检查 DeepSeek 或其他 LLM 提供商是否可用
"""

import os
import sys
import requests
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

def check_deepseek():
    """检查 DeepSeek API 连接"""
    print("\n🔍 检查 DeepSeek 配置...")
    print("=" * 50)
    
    api_key = os.getenv('DEEPSEEK_API_KEY', '')
    base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
    model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
    
    # 检查配置
    if not api_key:
        print("❌ DEEPSEEK_API_KEY 未配置")
        return False
    
    if api_key.startswith('sk-'):
        print(f"✅ API Key 已配置: {api_key[:20]}...")
    else:
        print(f"⚠️  API Key 格式可能不正确: {api_key[:20]}...")
    
    print(f"✅ Base URL: {base_url}")
    print(f"✅ Model: {model}")
    
    # 测试 API 连接
    print("\n📡 测试 API 连接...")
    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': model,
            'messages': [
                {
                    'role': 'system',
                    'content': 'You are a test assistant.'
                },
                {
                    'role': 'user',
                    'content': 'Say "Hello" only.'
                }
            ],
            'temperature': 0.1,
            'max_tokens': 10
        }
        
        print(f"🚀 向 {base_url}/chat/completions 发送请求...")
        
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        print(f"📨 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ DeepSeek API 连接成功！")
            
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                print(f"✅ API 响应: {content[:50]}...")
                return True
            else:
                print("⚠️  响应格式不正确")
                print(f"   响应: {json.dumps(result, indent=2)[:200]}...")
                return False
        
        elif response.status_code == 401:
            print("❌ API Key 无效或已过期")
            print(f"   响应: {response.text[:200]}")
            return False
        
        elif response.status_code == 429:
            print("❌ API 限流 (请求过于频繁)")
            print(f"   响应: {response.text[:200]}")
            return False
        
        else:
            print(f"❌ API 错误 ({response.status_code})")
            print(f"   响应: {response.text[:200]}")
            return False
    
    except requests.exceptions.Timeout:
        print("❌ 连接超时 (30秒)")
        print("   可能原因: 网络问题或 API 服务不可用")
        return False
    
    except requests.exceptions.ConnectionError as e:
        print(f"❌ 连接错误: {str(e)[:100]}")
        return False
    
    except Exception as e:
        print(f"❌ 错误: {str(e)[:200]}")
        return False


def check_nlp_functions():
    """检查 NLP 函数可用性"""
    print("\n🔍 检查 NLP 功能...")
    print("=" * 50)
    
    try:
        from app.services.nl2sql_enhanced import NL2SQLEnhanced
        from app.services.unified_query_service import UnifiedQueryService
        
        print("✅ 可以导入 NL2SQLEnhanced")
        print("✅ 可以导入 UnifiedQueryService")
        
        # 创建实例
        service = UnifiedQueryService()
        print("✅ 可以创建 UnifiedQueryService 实例")
        
        return True
    
    except Exception as e:
        print(f"❌ 导入失败: {str(e)[:200]}")
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🔍 NL2SQL LLM 提供商诊断")
    print("=" * 60)
    
    # 加载环境变量
    from dotenv import load_dotenv
    load_dotenv()
    
    # 检查 LLM 提供商
    llm_provider = os.getenv('LLM_PROVIDER', 'deepseek')
    print(f"\n配置的 LLM 提供商: {llm_provider}")
    
    if llm_provider == 'deepseek':
        deepseek_ok = check_deepseek()
    else:
        print(f"⚠️  不支持的 LLM 提供商: {llm_provider}")
        deepseek_ok = False
    
    # 检查 NLP 功能
    nlp_ok = check_nlp_functions()
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 诊断总结")
    print("=" * 60)
    
    if deepseek_ok:
        print("✅ LLM 提供商: 可用")
    else:
        print("❌ LLM 提供商: 不可用")
        print("\n💡 解决方案:")
        print("  1. 验证 DEEPSEEK_API_KEY 是否正确")
        print("  2. 检查 API Key 是否已过期")
        print("  3. 检查网络连接是否正常")
        print("  4. 访问 https://platform.deepseek.com 查看 API 额度")
    
    if nlp_ok:
        print("✅ NLP 功能: 可导入")
    else:
        print("⚠️  NLP 功能: 导入失败")
    
    print("\n" + "=" * 60)
    print("📚 相关文档:")
    print("  - .env 配置: 检查 DEEPSEEK_API_KEY 和 LLM_PROVIDER")
    print("  - DeepSeek 官网: https://platform.deepseek.com")
    print("=" * 60 + "\n")
    
    return 0 if deepseek_ok else 1


if __name__ == '__main__':
    sys.exit(main())
