#!/usr/bin/env python3
"""
Supabase Anon Key 自动化配置脚本
自动检查、验证和配置 SUPABASE_ANON_KEY 和 SUPABASE_URL

使用方式：
    python setup_anon_key.py                              # 交互模式
    python setup_anon_key.py --verify                     # 验证本地配置
    python setup_anon_key.py --test                       # 测试本地连接
    python setup_anon_key.py --render-env                 # 生成 Render 环境配置
    python setup_anon_key.py --verify-render              # 验证 Render 上的配置
    python setup_anon_key.py --verify-render https://... # 用自定义 URL 验证
    python setup_anon_key.py --help                       # 显示帮助
"""

import os
import sys
import json
import re
import argparse
import logging
from typing import Dict, Tuple, Optional
from pathlib import Path
from dotenv import load_dotenv, set_key
import requests

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# 颜色输出
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.ENDC}\n")

def print_success(text: str):
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")

def print_error(text: str):
    print(f"{Colors.RED}❌ {text}{Colors.ENDC}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.ENDC}")

def print_info(text: str):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.ENDC}")

def print_step(num: int, text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}步骤 {num}: {text}{Colors.ENDC}")

class SupabaseSetupSkill:
    """Supabase Anon Key 配置技能"""
    
    def __init__(self, env_file: str = '.env'):
        self.env_file = Path(env_file)
        self.env_vars = {}
        self.load_env()
    
    def load_env(self):
        """加载环境变量"""
        load_dotenv(self.env_file)
        self.env_vars = {
            'SUPABASE_URL': os.getenv('SUPABASE_URL'),
            'SUPABASE_ANON_KEY': os.getenv('SUPABASE_ANON_KEY'),
            'SUPABASE_SERVICE_KEY': os.getenv('SUPABASE_SERVICE_KEY'),
        }
    
    def validate_url(self, url: str) -> Tuple[bool, str]:
        """验证 SUPABASE_URL 格式"""
        if not url:
            return False, "URL 不能为空"
        
        # Supabase URL 格式: https://xxxxxxxxxxxxx.supabase.co
        pattern = r'^https://[a-z0-9]+\.supabase\.co$'
        if not re.match(pattern, url):
            return False, f"URL 格式不正确。应该是: https://xxxxx.supabase.co"
        
        return True, "URL 格式正确"
    
    def validate_anon_key(self, key: str) -> Tuple[bool, str]:
        """验证 SUPABASE_ANON_KEY 格式"""
        if not key:
            return False, "Anon Key 不能为空"
        
        # JWT Token 通常以 eyJ 开头
        if not key.startswith('eyJ'):
            return False, "Anon Key 格式不正确。JWT Token 应该以 'eyJ' 开头"
        
        # 检查长度
        if len(key) < 100:
            return False, f"Anon Key 太短 ({len(key)} 字符)，应该至少 100+ 字符"
        
        # 检查是否包含点号（JWT 三部分）
        if key.count('.') < 2:
            return False, "Anon Key 格式不完整。JWT Token 应该有 3 部分"
        
        return True, "Anon Key 格式正确"
    
    def test_connection(self) -> Tuple[bool, str]:
        """测试 Supabase 连接"""
        url = self.env_vars.get('SUPABASE_URL')
        key = self.env_vars.get('SUPABASE_ANON_KEY')
        
        if not url or not key:
            return False, "缺少 SUPABASE_URL 或 SUPABASE_ANON_KEY"
        
        try:
            from supabase import create_client
            
            client = create_client(url, key)
            # 测试连接
            response = client.table('pg_tables').select('*').limit(1).execute()
            return True, "连接成功"
            
        except ImportError:
            return False, "supabase 包未安装。运行: pip install supabase"
        except Exception as e:
            error_msg = str(e)
            if '401' in error_msg or 'Unauthorized' in error_msg:
                return False, f"认证失败。检查 Anon Key 是否正确: {error_msg}"
            else:
                return False, f"连接失败: {error_msg}"
    
    def check_status(self) -> Dict[str, any]:
        """检查当前配置状态"""
        status = {
            'supabase_url': {
                'set': bool(self.env_vars['SUPABASE_URL']),
                'value': self.env_vars['SUPABASE_URL'] or 'NOT SET',
                'valid': False,
                'message': ''
            },
            'anon_key': {
                'set': bool(self.env_vars['SUPABASE_ANON_KEY']),
                'value': self._mask_key(self.env_vars['SUPABASE_ANON_KEY']),
                'valid': False,
                'message': ''
            },
            'connected': False,
            'connection_message': ''
        }
        
        # 验证 URL
        if status['supabase_url']['set']:
            valid, msg = self.validate_url(self.env_vars['SUPABASE_URL'])
            status['supabase_url']['valid'] = valid
            status['supabase_url']['message'] = msg
        else:
            status['supabase_url']['message'] = 'NOT SET'
        
        # 验证 Anon Key
        if status['anon_key']['set']:
            valid, msg = self.validate_anon_key(self.env_vars['SUPABASE_ANON_KEY'])
            status['anon_key']['valid'] = valid
            status['anon_key']['message'] = msg
        else:
            status['anon_key']['message'] = 'NOT SET'
        
        # 测试连接
        if status['supabase_url']['valid'] and status['anon_key']['valid']:
            connected, msg = self.test_connection()
            status['connected'] = connected
            status['connection_message'] = msg
        
        return status
    
    def setup_interactive(self):
        """交互式设置"""
        print_header("Supabase Anon Key 交互式配置")
        
        print_step(1, "获取 SUPABASE_URL")
        print_info("访问: https://supabase.com/dashboard")
        print_info("选择项目 → Settings → API → Project URL")
        
        supabase_url = input(f"\n请输入 SUPABASE_URL (当前: {self.env_vars['SUPABASE_URL'] or 'NOT SET'}): ").strip()
        
        if supabase_url:
            valid, msg = self.validate_url(supabase_url)
            if valid:
                print_success(f"URL 验证通过: {msg}")
                set_key(self.env_file, 'SUPABASE_URL', supabase_url)
                self.env_vars['SUPABASE_URL'] = supabase_url
            else:
                print_error(f"URL 验证失败: {msg}")
                return
        
        print_step(2, "获取 SUPABASE_ANON_KEY")
        print_info("在同一个 Settings → API 页面")
        print_info("复制 'anon (public)' 密钥")
        
        anon_key = input(f"\n请输入 SUPABASE_ANON_KEY (当前: {self._mask_key(self.env_vars['SUPABASE_ANON_KEY'])}): ").strip()
        
        if anon_key:
            valid, msg = self.validate_anon_key(anon_key)
            if valid:
                print_success(f"Anon Key 验证通过: {msg}")
                set_key(self.env_file, 'SUPABASE_ANON_KEY', anon_key)
                self.env_vars['SUPABASE_ANON_KEY'] = anon_key
            else:
                print_error(f"Anon Key 验证失败: {msg}")
                return
        
        print_step(3, "测试连接")
        print_info("连接到 Supabase...")
        connected, msg = self.test_connection()
        
        if connected:
            print_success(f"Supabase 连接成功！")
        else:
            print_error(f"连接失败: {msg}")
            return
        
        print_header("✅ 配置完成")
        print(f"环境文件已更新: {self.env_file}")
        print_info("现在可以运行后端: python run.py")
    
    def verify_config(self) -> bool:
        """验证现有配置"""
        print_header("配置验证")
        
        status = self.check_status()
        
        print(f"SUPABASE_URL:")
        print(f"  设置: {'✅' if status['supabase_url']['set'] else '❌'}")
        print(f"  值:   {status['supabase_url']['value']}")
        print(f"  验证: {status['supabase_url']['message']}")
        
        print(f"\nSUPABASE_ANON_KEY:")
        print(f"  设置: {'✅' if status['anon_key']['set'] else '❌'}")
        print(f"  值:   {status['anon_key']['value']}")
        print(f"  验证: {status['anon_key']['message']}")
        
        print(f"\n连接状态:")
        if status['connected']:
            print_success(f"Supabase 已连接: {status['connection_message']}")
        else:
            print_error(f"Supabase 未连接: {status['connection_message']}")
        
        all_valid = status['supabase_url']['valid'] and status['anon_key']['valid'] and status['connected']
        
        if all_valid:
            print_header("✅ 配置有效")
        else:
            print_header("❌ 配置有问题")
        
        return all_valid
    
    def generate_render_env(self):
        """生成 Render 环境配置"""
        print_header("Render 环境变量配置")
        
        status = self.check_status()
        
        if not status['supabase_url']['set'] or not status['anon_key']['set']:
            print_error("缺少必要的环境变量。请先运行交互式设置")
            return
        
        print("在 Render Dashboard 中设置以下环境变量:\n")
        print(f"{Colors.BOLD}SUPABASE_URL{Colors.ENDC}")
        print(f"{Colors.CYAN}{self.env_vars['SUPABASE_URL']}{Colors.ENDC}\n")
        
        print(f"{Colors.BOLD}SUPABASE_ANON_KEY{Colors.ENDC}")
        print(f"{Colors.CYAN}{self.env_vars['SUPABASE_ANON_KEY']}{Colors.ENDC}\n")
        
        print(f"{Colors.BOLD}DeepSeek API Key (如果有){Colors.ENDC}")
        deepseek_key = os.getenv('DEEPSEEK_API_KEY')
        if deepseek_key:
            print(f"{Colors.CYAN}{self._mask_key(deepseek_key)}{Colors.ENDC}\n")
        else:
            print(f"{Colors.YELLOW}(未设置){Colors.ENDC}\n")
        
        print_info("步骤:")
        print("1. 登录 Render Dashboard")
        print("2. 选择 nl2sql-backend-amok 服务")
        print("3. 点击 Environment")
        print("4. 添加上述环境变量")
        print("5. 点击 Manual Deploy")
        print("6. 访问健康检查: https://nl2sql-backend-amok.onrender.com/api/query/health")
    
    def verify_render_config(self, render_url: str) -> Dict[str, any]:
        """验证 Render 上的配置"""
        result = {
            'connected': False,
            'status': 'unknown',
            'supabase': 'disconnected',
            'error': None,
            'response': None,
            'backend_healthy': False
        }
        
        # 规范化 URL
        if not render_url.startswith('http'):
            render_url = f'https://{render_url}'
        if render_url.endswith('/'):
            render_url = render_url.rstrip('/')
        
        health_url = f'{render_url}/api/query/health'
        
        try:
            logger.info(f"检查 Render 配置: {health_url}")
            response = requests.get(health_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                result['response'] = data
                result['status'] = data.get('status', 'unknown')
                result['supabase'] = data.get('supabase', 'disconnected')
                result['backend_healthy'] = data.get('status') == 'healthy'
                result['connected'] = data.get('supabase') == 'connected'
                
                if result['connected']:
                    logger.info("✅ Render 上的 Supabase 已连接")
                else:
                    logger.warning("⚠️  Render 上的 Supabase 未连接")
            else:
                result['error'] = f"HTTP {response.status_code}"
                logger.error(f"后端返回错误: {response.status_code}")
        
        except requests.exceptions.Timeout:
            result['error'] = "连接超时。检查 Render URL 是否正确"
            logger.error("连接超时")
        except requests.exceptions.ConnectionError:
            result['error'] = "无法连接到 Render。检查网络和 URL"
            logger.error("连接失败")
        except ValueError:
            result['error'] = "响应不是有效的 JSON"
            logger.error("JSON 解析失败")
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"验证失败: {str(e)}")
        
        return result
    
    @staticmethod
    def _mask_key(key: Optional[str], show_chars: int = 20) -> str:
        """隐藏密钥的大部分内容"""
        if not key:
            return 'NOT SET'
        if len(key) <= show_chars:
            return key
        return f"{key[:show_chars]}...({len(key)} chars)"


def main():
    parser = argparse.ArgumentParser(
        description='Supabase Anon Key 自动化配置脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python setup_anon_key.py              # 交互模式
  python setup_anon_key.py --verify     # 验证本地配置
  python setup_anon_key.py --test       # 测试本地连接
  python setup_anon_key.py --render-env # 生成 Render 配置
  python setup_anon_key.py --verify-render  # 验证 Render 上的配置
        """
    )
    
    parser.add_argument('--verify', action='store_true', help='验证现有配置')
    parser.add_argument('--test', action='store_true', help='测试 Supabase 连接')
    parser.add_argument('--render-env', action='store_true', help='生成 Render 环境配置')
    parser.add_argument('--verify-render', type=str, nargs='?', const='https://nl2sql-backend-amok.onrender.com', 
                        help='验证 Render 上的配置（可选：提供 Render URL）')
    parser.add_argument('--env-file', default='.env', help='.env 文件路径 (默认: .env)')
    
    args = parser.parse_args()
    
    skill = SupabaseSetupSkill(args.env_file)
    
    try:
        if args.verify:
            skill.verify_config()
        elif args.test:
            status = skill.check_status()
            if status['connected']:
                print_success("Supabase 连接成功")
            else:
                print_error(f"Supabase 连接失败: {status['connection_message']}")
        elif args.render_env:
            skill.generate_render_env()
        elif args.verify_render:
            # 验证 Render 上的配置
            print_header("验证 Render 上的配置")
            result = skill.verify_render_config(args.verify_render)
            
            print(f"\n🌐 Render 后端: {args.verify_render}")
            print(f"健康状态: {'✅' if result['backend_healthy'] else '❌'} {result['status']}")
            print(f"Supabase: {'✅' if result['connected'] else '❌'} {result['supabase']}")
            
            if result['error']:
                print_error(f"错误: {result['error']}")
            
            # 显示完整的诊断信息
            if result['response']:
                print("\n📋 完整响应:")
                print(json.dumps(result['response'], indent=2, ensure_ascii=False))
            
            print("\n" + "="*60)
            
            if result['connected']:
                print_header("✅ Render 配置有效")
                print("Supabase 已连接，可以正常使用。")
            else:
                print_header("❌ Render 配置有问题")
                
                # 从诊断信息中提取问题
                if result['response'] and 'diagnosis' in result['response']:
                    diagnosis = result['response']['diagnosis']
                    
                    # 检查具体的配置状态
                    url_set = diagnosis.get('supabase_url_set', '?')
                    key_set = diagnosis.get('supabase_key_set', '?')
                    
                    print(f"\n环境变量状态:")
                    print(f"  SUPABASE_URL: {'✅ 已设置' if url_set == 'YES' else '❌ 未设置'}")
                    print(f"  SUPABASE_ANON_KEY: {'✅ 已设置' if key_set == 'YES' else '❌ 未设置'}")
                    
                    # 显示连接状态
                    conn_status = diagnosis.get('connection_status')
                    if conn_status:
                        print(f"\n连接状态:")
                        print(f"  {conn_status}")
                    
                    # 显示错误信息
                    if result['response'].get('error'):
                        print(f"\n错误详情:")
                        print(f"  {result['response']['error']}")
                    
                    # 提供解决方案
                    if url_set == 'NO' or key_set == 'NO':
                        print("\n⚠️  缺少必要的环境变量")
                        print("\n💡 解决方案:")
                        print("1. 运行: .venv/bin/python setup_anon_key.py --render-env")
                        print("2. 在 Render Dashboard 添加缺失的环境变量")
                        print("3. 点击 Manual Deploy 重新部署")
                    else:
                        print("\n⚠️  环境变量已设置，但连接失败")
                        print("\n💡 可能的原因:")
                        print("1. 密钥格式不正确")
                        print("2. Supabase 项目已删除或暂停")
                        print("3. 密钥已被重新生成")
                        print("\n解决方案:")
                        print("1. 在 Supabase Dashboard 验证密钥是否仍有效")
                        print("2. 如果需要，重新生成密钥")
                        print("3. 更新 Render 环境变量")
                        print("4. 点击 Manual Deploy 重新部署")
                elif result['error']:
                    print(f"\n连接错误: {result['error']}")
                    if "连接超时" in result['error']:
                        print("\n💡 可能是 Render 冷启动，请等待后重试")
        else:
            # 默认交互模式
            skill.setup_interactive()
    
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}操作已取消{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        print_error(f"发生错误: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
