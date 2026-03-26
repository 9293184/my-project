"""输入验证器测试"""
import pytest
from pydantic import ValidationError
from aisec_app.validators import CreateModelRequest, SaveKeyRequest, ChatRequest


def test_create_model_request_valid():
    """测试有效的创建模型请求"""
    data = CreateModelRequest(
        name='test_model',
        model_id='test-id',
        url='https://api.example.com',
        api_key='test-key'
    )
    assert data.name == 'test_model'
    assert data.model_id == 'test-id'


def test_create_model_request_empty_name():
    """测试空名称验证"""
    with pytest.raises(ValidationError):
        CreateModelRequest(name='', model_id='test-id')


def test_create_model_request_whitespace_name():
    """测试只包含空格的名称验证"""
    with pytest.raises(ValidationError):
        CreateModelRequest(name='   ', model_id='test-id')


def test_save_key_request_valid():
    """测试有效的保存密钥请求"""
    data = SaveKeyRequest(
        key_name='TEST_KEY',
        key_value='test-value',
        description='test desc'
    )
    assert data.key_name == 'TEST_KEY'
    assert data.key_value == 'test-value'


def test_chat_request_valid():
    """测试有效的对话请求"""
    data = ChatRequest(
        message='Hello',
        model_name='test-model'
    )
    assert data.message == 'Hello'
    assert data.model_name == 'test-model'


def test_chat_request_missing_model():
    """测试缺少模型信息的对话请求"""
    with pytest.raises(ValidationError):
        ChatRequest(message='Hello')
