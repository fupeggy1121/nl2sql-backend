"""
DeepSeek API 集成测试
测试 LLM 提供商和 NL2SQL 转换功能
"""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from app import create_app
from app.services.llm_provider import DeepSeekProvider, OpenAIProvider, get_llm_provider
from app.services.nl2sql import NL2SQLConverter


@pytest.fixture
def app():
    """创建测试应用"""
    app = create_app('testing')
    return app


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return app.test_client()


class TestDeepSeekProvider:
    """DeepSeek 提供商测试"""
    
    def test_provider_initialization(self):
        """测试提供商初始化"""
        provider = DeepSeekProvider()
        assert provider is not None
        assert hasattr(provider, 'api_key')
        assert hasattr(provider, 'base_url')
        assert hasattr(provider, 'model')
    
    @patch('app.services.llm_provider.requests.post')
    def test_successful_conversion(self, mock_post):
        """测试成功的 NL 转 SQL 转换"""
        provider = DeepSeekProvider()
        provider.api_key = 'test_key'
        
        # Mock DeepSeek API 响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [
                {
                    'message': {
                        'content': 'SELECT * FROM users'
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        result = provider.convert_nl_to_sql('查询所有用户')
        
        assert result == 'SELECT * FROM users'
        assert mock_post.called
    
    @patch('app.services.llm_provider.requests.post')
    def test_api_error_handling(self, mock_post):
        """测试 API 错误处理"""
        provider = DeepSeekProvider()
        provider.api_key = 'test_key'
        
        # Mock API 错误
        mock_post.side_effect = Exception('API Error')
        
        result = provider.convert_nl_to_sql('查询所有用户')
        
        assert result is None
    
    @patch('app.services.llm_provider.requests.post')
    def test_timeout_handling(self, mock_post):
        """测试超时处理"""
        provider = DeepSeekProvider()
        provider.api_key = 'test_key'
        
        import requests
        mock_post.side_effect = requests.exceptions.Timeout('Timeout')
        
        result = provider.convert_nl_to_sql('查询所有用户')
        
        assert result is None


class TestOpenAIProvider:
    """OpenAI 提供商测试"""
    
    def test_provider_initialization(self):
        """测试 OpenAI 提供商初始化"""
        provider = OpenAIProvider()
        assert provider is not None
        assert hasattr(provider, 'api_key')
        assert hasattr(provider, 'model')


class TestNL2SQLConverter:
    """NL2SQL 转换器测试"""
    
    def test_converter_initialization(self):
        """测试转换器初始化"""
        converter = NL2SQLConverter()
        assert converter is not None
        assert hasattr(converter, 'llm_provider')
        assert hasattr(converter, 'schema_info')
    
    def test_set_schema(self):
        """测试设置 schema"""
        converter = NL2SQLConverter()
        schema = {
            'users': {'id': 'INT', 'name': 'VARCHAR', 'email': 'VARCHAR'}
        }
        
        converter.set_schema(schema)
        
        assert converter.schema_info == schema
    
    @patch.object(DeepSeekProvider, 'convert_nl_to_sql')
    def test_convert_with_llm(self, mock_convert):
        """测试使用 LLM 进行转换"""
        mock_convert.return_value = 'SELECT * FROM users'
        
        converter = NL2SQLConverter()
        result = converter.convert('查询所有用户')
        
        assert result == 'SELECT * FROM users'
    
    def test_fallback_conversion(self):
        """测试备选转换方案"""
        converter = NL2SQLConverter()
        
        # 模拟 LLM 失败
        with patch.object(converter.llm_provider, 'convert_nl_to_sql', return_value=None):
            result = converter.convert('查询所有用户')
            
            # 应该返回备选 SQL
            assert result is not None
            assert 'SELECT' in result or 'INSERT' in result or 'UPDATE' in result or 'DELETE' in result


class TestGetLLMProvider:
    """LLM 提供商工厂函数测试"""
    
    @patch.dict(os.environ, {'LLM_PROVIDER': 'deepseek'})
    def test_get_deepseek_provider(self):
        """测试获取 DeepSeek 提供商"""
        provider = get_llm_provider()
        assert isinstance(provider, DeepSeekProvider)
    
    @patch.dict(os.environ, {'LLM_PROVIDER': 'openai'})
    def test_get_openai_provider(self):
        """测试获取 OpenAI 提供商"""
        provider = get_llm_provider()
        assert isinstance(provider, OpenAIProvider)
    
    @patch.dict(os.environ, {'LLM_PROVIDER': 'unknown'}, clear=False)
    def test_default_provider(self):
        """测试默认提供商"""
        provider = get_llm_provider()
        # 应该默认返回 DeepSeek
        assert isinstance(provider, DeepSeekProvider)


class TestAPIIntegration:
    """API 集成测试"""
    
    def test_nl_to_sql_endpoint(self, client):
        """测试 NL 转 SQL 端点"""
        response = client.post(
            '/api/query/nl-to-sql',
            json={'natural_language': '查询所有用户'}
        )
        
        assert response.status_code == 200
        assert response.json['success'] is True
        assert 'sql' in response.json
    
    def test_nl_to_sql_empty_input(self, client):
        """测试空输入"""
        response = client.post(
            '/api/query/nl-to-sql',
            json={'natural_language': ''}
        )
        
        assert response.status_code == 400
        assert response.json['success'] is False
    
    def test_nl_to_sql_missing_field(self, client):
        """测试缺少必需字段"""
        response = client.post(
            '/api/query/nl-to-sql',
            json={}
        )
        
        assert response.status_code == 400
        assert response.json['success'] is False


class TestSchemaFormatting:
    """Schema 格式化测试"""
    
    def test_format_empty_schema(self):
        """测试空 schema 格式化"""
        converter = NL2SQLConverter()
        result = converter._format_schema()
        assert result == ""
    
    def test_format_schema_with_tables(self):
        """测试有表的 schema 格式化"""
        converter = NL2SQLConverter()
        schema = {
            'users': {'id': 'INT', 'name': 'VARCHAR'},
            'orders': {'id': 'INT', 'user_id': 'INT'}
        }
        converter.set_schema(schema)
        
        result = converter._format_schema()
        
        assert 'users' in result
        assert 'orders' in result
        assert 'id' in result
        assert 'INT' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
