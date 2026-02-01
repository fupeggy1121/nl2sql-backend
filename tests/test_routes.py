"""
测试用例
"""
import pytest
from app import create_app

@pytest.fixture
def app():
    """创建应用fixture"""
    app = create_app('testing')
    return app

@pytest.fixture
def client(app):
    """创建测试客户端fixture"""
    return app.test_client()

def test_health_check(client):
    """测试健康检查端点"""
    response = client.get('/api/query/health')
    assert response.status_code == 200
    assert response.json['status'] == 'healthy'

def test_convert_nl_to_sql(client):
    """测试自然语言转换为 SQL"""
    response = client.post('/api/query/nl-to-sql', 
                          json={'natural_language': '查询所有用户'})
    assert response.status_code == 200
    assert response.json['success'] == True
    assert 'sql' in response.json

def test_convert_nl_to_sql_empty(client):
    """测试空查询"""
    response = client.post('/api/query/nl-to-sql', 
                          json={'natural_language': ''})
    assert response.status_code == 400
    assert response.json['success'] == False

def test_convert_nl_to_sql_missing_field(client):
    """测试缺少必需字段"""
    response = client.post('/api/query/nl-to-sql', json={})
    assert response.status_code == 400
    assert response.json['success'] == False
