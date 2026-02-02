"""
LLM 提供者抽象层
支持多个 LLM 服务商（OpenAI、DeepSeek 等）
"""
import logging
import os
from typing import Optional
import requests

logger = logging.getLogger(__name__)


class LLMProvider:
    """LLM 提供者基类"""
    
    def convert_nl_to_sql(self, natural_language: str, schema_info: str = "") -> Optional[str]:
        """
        将自然语言转换为 SQL
        
        Args:
            natural_language: 用户的自然语言查询
            schema_info: 数据库 schema 信息
            
        Returns:
            转换后的 SQL 语句
        """
        raise NotImplementedError


class DeepSeekProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        """
        通用 LLM 生成接口，用于意图识别等任务
        Args:
            prompt: 输入的 prompt（如意图识别 JSON 指令）
        Returns:
            LLM 生成的字符串内容
        """
        if not self.api_key:
            logger.error("DeepSeek API key not configured")
            raise RuntimeError("DeepSeek API key not configured")
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            payload = {
                'model': self.model,
                'messages': [
                    {'role': 'system', 'content': 'You are an expert assistant for intent recognition.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.2,
                'max_tokens': 1000
            }
            logger.info(f"Calling DeepSeek API (generate) with model: {self.model}")
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    content = result['choices'][0]['message']['content'].strip()
                    logger.info(f"DeepSeek generate successful: {content[:80]}...")
                    return content
                else:
                    logger.error("Invalid response from DeepSeek API (generate)")
                    raise RuntimeError("Invalid response from DeepSeek API (generate)")
            else:
                logger.error(f"DeepSeek API error (generate): {response.status_code} - {response.text}")
                raise RuntimeError(f"DeepSeek API error (generate): {response.status_code}")
        except requests.exceptions.Timeout:
            logger.error("DeepSeek API request timeout (generate)")
            raise RuntimeError("DeepSeek API request timeout (generate)")
        except requests.exceptions.RequestException as e:
            logger.error(f"DeepSeek API request error (generate): {str(e)}")
            raise RuntimeError(f"DeepSeek API request error (generate): {str(e)}")
        except Exception as e:
            logger.error(f"Error calling DeepSeek API (generate): {str(e)}")
            raise

    """DeepSeek LLM 提供者"""
    
    def __init__(self):
        """初始化 DeepSeek 提供者"""
        self.api_key = os.getenv('DEEPSEEK_API_KEY', '')
        self.base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
        self.model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
        
        if not self.api_key:
            logger.warning("DeepSeek API key not configured")
    
    def convert_nl_to_sql(self, natural_language: str, schema_info: str = "") -> Optional[str]:
        """
        使用 DeepSeek API 将自然语言转换为 SQL
        
        Args:
            natural_language: 用户的自然语言查询
            schema_info: 数据库 schema 信息
            
        Returns:
            转换后的 SQL 语句
        """
        if not self.api_key:
            logger.error("DeepSeek API key not configured")
            return None
        
        try:
            # 构建系统提示词
            system_prompt = """You are a SQL expert. Convert natural language queries to SQL.
Rules:
1. Only return the SQL query without any explanation
2. The SQL should be valid and executable
3. Use appropriate SQL syntax
4. Optimize for readability"""
            
            if schema_info:
                system_prompt += f"\n\nDatabase Schema:\n{schema_info}"
            
            # 调用 DeepSeek API
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': self.model,
                'messages': [
                    {
                        'role': 'system',
                        'content': system_prompt
                    },
                    {
                        'role': 'user',
                        'content': f"Convert to SQL: {natural_language}"
                    }
                ],
                'temperature': 0.3,
                'max_tokens': 1000
            }
            
            logger.info(f"Calling DeepSeek API with model: {self.model}")
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    sql = result['choices'][0]['message']['content'].strip()
                    logger.info(f"DeepSeek conversion successful: {sql}")
                    return sql
                else:
                    logger.error("Invalid response from DeepSeek API")
                    return None
            else:
                logger.error(f"DeepSeek API error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("DeepSeek API request timeout")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"DeepSeek API request error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error calling DeepSeek API: {str(e)}")
            return None


class OpenAIProvider(LLMProvider):
    """OpenAI LLM 提供者"""
    
    def __init__(self):
        """初始化 OpenAI 提供者"""
        self.api_key = os.getenv('OPENAI_API_KEY', '')
        self.model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
        
        if not self.api_key:
            logger.warning("OpenAI API key not configured")
    
    def convert_nl_to_sql(self, natural_language: str, schema_info: str = "") -> Optional[str]:
        """
        使用 OpenAI API 将自然语言转换为 SQL
        
        Args:
            natural_language: 用户的自然语言查询
            schema_info: 数据库 schema 信息
            
        Returns:
            转换后的 SQL 语句
        """
        if not self.api_key:
            logger.error("OpenAI API key not configured")
            return None
        
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=self.api_key)
            
            system_prompt = """You are a SQL expert. Convert natural language queries to SQL.
Rules:
1. Only return the SQL query without any explanation
2. The SQL should be valid and executable
3. Use appropriate SQL syntax
4. Optimize for readability"""
            
            if schema_info:
                system_prompt += f"\n\nDatabase Schema:\n{schema_info}"
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Convert to SQL: {natural_language}"}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            sql = response.choices[0].message.content.strip()
            logger.info(f"OpenAI conversion successful: {sql}")
            return sql
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            return None


def get_llm_provider() -> LLMProvider:
    """
    根据配置获取 LLM 提供者
    
    Returns:
        LLM 提供者实例
    """
    provider_name = os.getenv('LLM_PROVIDER', 'deepseek').lower()
    
    if provider_name == 'openai':
        logger.info("Using OpenAI as LLM provider")
        return OpenAIProvider()
    elif provider_name == 'deepseek':
        logger.info("Using DeepSeek as LLM provider")
        return DeepSeekProvider()
    else:
        logger.warning(f"Unknown LLM provider: {provider_name}, defaulting to DeepSeek")
        return DeepSeekProvider()
