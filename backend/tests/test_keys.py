"""API密钥管理接口测试"""
import pytest
from aisec_app import create_app


@pytest.fixture
def client():
    """创建测试客户端"""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_get_keys(client):
    """测试获取API密钥列表"""
    response = client.get('/api/keys')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'data' in data
    assert isinstance(data['data'], list)


def test_save_key_success(client):
    """测试保存API密钥成功"""
    response = client.post('/api/keys', json={
        'key_name': 'TEST_KEY',
        'key_value': 'test-key-value-123',
        'description': 'Test key description'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True


def test_save_key_validation_error(client):
    """测试保存API密钥时的验证错误"""
    response = client.post('/api/keys', json={
        'key_name': '',
        'key_value': 'test-value'
    })
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
