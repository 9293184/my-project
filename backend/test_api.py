import requests
import sys
sys.stdout.reconfigure(encoding='utf-8')

API_BASE = 'http://localhost:8000/api'

print("="*60)
print("测试后端 API")
print("="*60)

# 测试健康检查
print("\n1. 测试健康检查 /api/health")
try:
    response = requests.get(f'{API_BASE}/health')
    print(f"   状态码: {response.status_code}")
    print(f"   响应: {response.json()}")
except Exception as e:
    print(f"   错误: {e}")

# 测试统计数据
print("\n2. 测试统计数据 /api/stats")
try:
    response = requests.get(f'{API_BASE}/stats')
    print(f"   状态码: {response.status_code}")
    data = response.json()
    print(f"   响应: {data}")
    if data.get('success'):
        stats = data.get('data', {})
        print(f"   - 模型数量: {stats.get('model_count')}")
        print(f"   - 安全策略: {stats.get('security_count')}")
        print(f"   - API密钥: {stats.get('apikey_count')}")
        print(f"   - 今日对话: {stats.get('chat_count')}")
except Exception as e:
    print(f"   错误: {e}")

# 测试模型列表
print("\n3. 测试模型列表 /api/models")
try:
    response = requests.get(f'{API_BASE}/models')
    print(f"   状态码: {response.status_code}")
    data = response.json()
    print(f"   成功: {data.get('success')}")
    if data.get('success'):
        models = data.get('data', [])
        print(f"   模型数量: {len(models)}")
        for model in models:
            print(f"   - {model.get('name')} ({model.get('model_id')})")
except Exception as e:
    print(f"   错误: {e}")

print("\n" + "="*60)
