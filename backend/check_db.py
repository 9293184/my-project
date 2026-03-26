import pymysql
import sys
sys.stdout.reconfigure(encoding='utf-8')

DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'root',
    'database': 'ai_security_system',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

try:
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    print("="*60)
    print("数据库连接成功！")
    print("="*60)
    
    # 检查模型数量
    cursor.execute("SELECT COUNT(*) as count FROM models")
    model_count = cursor.fetchone()['count']
    print(f"\n模型数量: {model_count}")
    
    if model_count > 0:
        cursor.execute("SELECT id, name, model_id FROM models LIMIT 5")
        models = cursor.fetchall()
        print("\n前5个模型:")
        for model in models:
            print(f"  - {model['name']} ({model['model_id']})")
    
    # 检查API密钥数量
    cursor.execute("SELECT COUNT(*) as count FROM api_keys")
    key_count = cursor.fetchone()['count']
    print(f"\nAPI密钥数量: {key_count}")
    
    # 检查对话日志数量
    cursor.execute("SELECT COUNT(*) as count FROM chat_logs")
    log_count = cursor.fetchone()['count']
    print(f"\n对话日志数量: {log_count}")
    
    # 检查今日对话
    cursor.execute("SELECT COUNT(*) as count FROM chat_logs WHERE DATE(created_at) = CURDATE()")
    today_count = cursor.fetchone()['count']
    print(f"今日对话数量: {today_count}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*60)
    print("数据库检查完成！")
    print("="*60)
    
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
