"""
Supabase Setup Skill 模块
提供 Supabase 环境变量的验证、测试和配置功能

使用方式：
    from app.skills.supabase_setup import SupabaseSetupSkill
    
    skill = SupabaseSetupSkill()
    skill.setup_interactive()
"""

import os
import re
from typing import Dict, Tuple, Optional
from pathlib import Path
from dotenv import load_dotenv, set_key
import logging

logger = logging.getLogger(__name__)


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
        """
        验证 SUPABASE_URL 格式
        
        Args:
            url: Supabase URL
            
        Returns:
            (是否有效, 消息)
        """
        if not url:
            return False, "URL 不能为空"
        
        # Supabase URL 格式: https://xxxxxxxxxxxxx.supabase.co
        pattern = r'^https://[a-z0-9]+\.supabase\.co$'
        if not re.match(pattern, url):
            return False, f"URL 格式不正确。应该是: https://xxxxx.supabase.co"
        
        return True, "URL 格式正确"
    
    def validate_anon_key(self, key: str) -> Tuple[bool, str]:
        """
        验证 SUPABASE_ANON_KEY 格式
        
        Args:
            key: Anon Key JWT Token
            
        Returns:
            (是否有效, 消息)
        """
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
        """
        测试 Supabase 连接
        
        Returns:
            (是否连接成功, 消息)
        """
        url = self.env_vars.get('SUPABASE_URL')
        key = self.env_vars.get('SUPABASE_ANON_KEY')
        
        if not url or not key:
            return False, "缺少 SUPABASE_URL 或 SUPABASE_ANON_KEY"
        
        try:
            from supabase import create_client
            
            client = create_client(url, key)
            # 测试连接
            response = client.table('pg_tables').select('*').limit(1).execute()
            logger.info("✅ Supabase 连接成功")
            return True, "连接成功"
            
        except ImportError:
            logger.error("supabase 包未安装")
            return False, "supabase 包未安装。运行: pip install supabase"
        except Exception as e:
            error_msg = str(e)
            if '401' in error_msg or 'Unauthorized' in error_msg:
                logger.error(f"认证失败: {error_msg}")
                return False, f"认证失败。检查 Anon Key 是否正确"
            else:
                logger.error(f"连接失败: {error_msg}")
                return False, f"连接失败: {error_msg}"
    
    def check_status(self) -> Dict[str, any]:
        """
        检查当前配置状态
        
        Returns:
            状态字典
        """
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
    
    def save_to_env(self, url: str, anon_key: str) -> bool:
        """
        保存环境变量到 .env 文件
        
        Args:
            url: SUPABASE_URL
            anon_key: SUPABASE_ANON_KEY
            
        Returns:
            是否保存成功
        """
        try:
            set_key(self.env_file, 'SUPABASE_URL', url)
            set_key(self.env_file, 'SUPABASE_ANON_KEY', anon_key)
            logger.info(f"✅ 环境变量已保存到 {self.env_file}")
            return True
        except Exception as e:
            logger.error(f"❌ 保存失败: {str(e)}")
            return False
    
    def get_config_dict(self) -> Dict[str, str]:
        """
        获取配置字典（用于 Render 环境变量）
        
        Returns:
            配置字典
        """
        return {
            'SUPABASE_URL': self.env_vars.get('SUPABASE_URL', ''),
            'SUPABASE_ANON_KEY': self.env_vars.get('SUPABASE_ANON_KEY', ''),
        }
    
    @staticmethod
    def _mask_key(key: Optional[str], show_chars: int = 20) -> str:
        """隐藏密钥的大部分内容"""
        if not key:
            return 'NOT SET'
        if len(key) <= show_chars:
            return key
        return f"{key[:show_chars]}...({len(key)} chars)"
