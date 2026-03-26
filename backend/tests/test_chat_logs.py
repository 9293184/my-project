"""对话日志接口测试"""
import pytest
from aisec_app import create_app


@pytest.fixture
def client():
    """创建测试客户端"""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_get_chat_logs(client):
    """测试获取对话日志列表"""
    response = client.get('/api/chat/logs')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'data' in data
    assert 'pagination' in data
    assert isinstance(data['data'], list)


def test_get_chat_logs_with_pagination(client):
    """测试带分页参数的对话日志查询"""
    response = client.get('/api/chat/logs?page=1&page_size=10')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['pagination']['page'] == 1
    assert data['pagination']['page_size'] == 10


def test_get_chat_users(client):
    """测试获取用户列表"""
    response = client.get('/api/chat/users')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'data' in data
    assert isinstance(data['data'], list)


def test_save_chat_log(client):
    """测试保存对话记录"""
    response = client.post('/api/chat/logs', json={
        'model_id': 1,
        'user_id': 'test_user',
        'user_input': 'test input',
        'ai_response': 'test response',
        'input_blocked': False,
        'output_blocked': False,
        'response_time_ms': 100
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
