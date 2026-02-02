#!/usr/bin/env python3
"""
Supabase Setup Skill 使用示例
演示如何在 Python 代码中使用 SupabaseSetupSkill
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.skills.supabase_setup import SupabaseSetupSkill
import json


def example_1_check_status():
    """示例 1: 检查配置状态"""
    print("\n" + "="*60)
    print("示例 1: 检查配置状态")
    print("="*60 + "\n")
    
    skill = SupabaseSetupSkill()
    status = skill.check_status()
    
    print("SUPABASE_URL:")
    print(f"  已设置: {status['supabase_url']['set']}")
    print(f"  值: {status['supabase_url']['value']}")
    print(f"  有效: {status['supabase_url']['valid']}")
    print(f"  消息: {status['supabase_url']['message']}")
    
    print("\nSUPABASE_ANON_KEY:")
    print(f"  已设置: {status['anon_key']['set']}")
    print(f"  值: {status['anon_key']['value']}")
    print(f"  有效: {status['anon_key']['valid']}")
    print(f"  消息: {status['anon_key']['message']}")
    
    print(f"\n连接状态:")
    print(f"  已连接: {status['connected']}")
    print(f"  消息: {status['connection_message']}")


def example_2_validate():
    """示例 2: 单独验证 URL 和 Key"""
    print("\n" + "="*60)
    print("示例 2: 验证 URL 和 Key")
    print("="*60 + "\n")
    
    skill = SupabaseSetupSkill()
    
    # 验证 URL
    test_url = "https://kgmyhukvyygudsllypgv.supabase.co"
    valid, msg = skill.validate_url(test_url)
    print(f"验证 URL: {test_url}")
    print(f"  结果: {valid}")
    print(f"  消息: {msg}")
    
    # 验证无效 URL
    invalid_url = "just-some-text"
    valid, msg = skill.validate_url(invalid_url)
    print(f"\n验证无效 URL: {invalid_url}")
    print(f"  结果: {valid}")
    print(f"  消息: {msg}")


def example_3_get_config():
    """示例 3: 获取 Render 配置"""
    print("\n" + "="*60)
    print("示例 3: 获取 Render 配置")
    print("="*60 + "\n")
    
    skill = SupabaseSetupSkill()
    config = skill.get_config_dict()
    
    print("Render 环境变量配置:")
    for key, value in config.items():
        masked_value = skill._mask_key(value) if value else "NOT SET"
        print(f"  {key}={masked_value}")


def example_4_in_app():
    """示例 4: 在应用启动时检查配置"""
    print("\n" + "="*60)
    print("示例 4: 应用启动时检查配置")
    print("="*60 + "\n")
    
    skill = SupabaseSetupSkill()
    status = skill.check_status()
    
    print("应用启动检查:")
    
    if not status['supabase_url']['set']:
        print("  ❌ SUPABASE_URL 未设置")
        return False
    
    if not status['supabase_url']['valid']:
        print(f"  ❌ SUPABASE_URL 无效: {status['supabase_url']['message']}")
        return False
    
    if not status['anon_key']['set']:
        print("  ❌ SUPABASE_ANON_KEY 未设置")
        return False
    
    if not status['anon_key']['valid']:
        print(f"  ❌ SUPABASE_ANON_KEY 无效: {status['anon_key']['message']}")
        return False
    
    if not status['connected']:
        print(f"  ❌ Supabase 连接失败: {status['connection_message']}")
        return False
    
    print("  ✅ 所有检查通过，Supabase 已连接")
    return True


def example_5_masked_keys():
    """示例 5: 安全地隐藏密钥"""
    print("\n" + "="*60)
    print("示例 5: 安全地隐藏密钥")
    print("="*60 + "\n")
    
    skill = SupabaseSetupSkill()
    
    test_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVmZmNiOWU3Nzk4YjJjMGFlODQ3OWRlZTgxOWNhMTM2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE2OTI0MTc4NzMsImV4cCI6MTcwODAwOTg3M30.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    
    masked = skill._mask_key(test_key)
    print(f"原始密钥: {test_key}")
    print(f"隐藏后:  {masked}")
    
    # 短密钥
    short_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    masked_short = skill._mask_key(short_key)
    print(f"\n短密钥:   {short_key}")
    print(f"隐藏后:  {masked_short}")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("Supabase Setup Skill 使用示例")
    print("="*60)
    
    try:
        example_1_check_status()
        example_2_validate()
        example_3_get_config()
        example_4_in_app()
        example_5_masked_keys()
        
        print("\n" + "="*60)
        print("✅ 所有示例完成")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
