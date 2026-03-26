"""模型管理接口测试"""
import pytest
from aisec_app import create_app


@pytest.fixture
def client():
    """创建测试客户端"""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_get_models(client):
    """测试获取模型列表"""
    response = client.get('/api/models')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'data' in data
    assert isinstance(data['data'], list)


def test_create_model_success(client):
    """测试创建模型成功"""
    response = client.post('/api/models', json={
        'name': 'test_model',
        'model_id': 'test-model-id',
        'url': 'https://api.example.com',
        'api_key': 'test-key',
        'security_prompt': 'test prompt'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'id' in data['data']


def test_create_model_validation_error(client):
    """测试创建模型时的验证错误"""
    response = client.post('/api/models', json={
        'name': '',
        'model_id': 'test-id'
    })
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False


def test_create_model_missing_fields(client):
    """测试创建模型缺少必填字段"""
    response = client.post('/api/models', json={
        'name': 'test'
    })
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
