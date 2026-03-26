"""
直接创建数据库表
"""
import pymysql
import sys

sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'root',
    'database': 'ai_security_system',
    'charset': 'utf8mb4'
}

def main():
    print("🚀 创建数据库表...")
    
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # 1. 模型表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS models (
            id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(100) NOT NULL UNIQUE,
            model_id VARCHAR(100) NOT NULL UNIQUE,
            url VARCHAR(500) DEFAULT NULL,
            api_key VARCHAR(255) DEFAULT NULL,
            security_prompt TEXT DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("✅ 创建表: models")
    
    # 2. API 密钥表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INT PRIMARY KEY AUTO_INCREMENT,
            key_name VARCHAR(100) NOT NULL UNIQUE,
            key_value VARCHAR(255) NOT NULL,
            description VARCHAR(500) DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("✅ 创建表: api_keys")
    
    # 3. 对话记录表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            model_id INT NOT NULL,
            user_input TEXT NOT NULL,
            ai_response TEXT DEFAULT NULL,
            input_blocked BOOLEAN DEFAULT FALSE,
            output_blocked BOOLEAN DEFAULT FALSE,
            block_reason VARCHAR(500) DEFAULT NULL,
            response_time_ms INT DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("✅ 创建表: chat_logs")
    
    # 4. 系统配置表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            id INT PRIMARY KEY AUTO_INCREMENT,
            config_key VARCHAR(100) NOT NULL UNIQUE,
            config_value TEXT DEFAULT NULL,
            description VARCHAR(500) DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("✅ 创建表: system_config")
    
    # 5. 插入示例数据
    try:
        cursor.execute("""
            INSERT INTO models (name, model_id, url, api_key, security_prompt) VALUES 
            (
                '客户端',
                'qwen3-vl-plus',
                'https://dashscope.aliyuncs.com/compatible-mode/v1',
                'your-api-key-here',
                '你必须严格保护患者隐私与数据安全。禁止输出任何患者个人身份信息。'
            )
        """)
        print("✅ 插入示例模型数据")
    except pymysql.err.IntegrityError:
        print("⚠️ 示例数据已存在，跳过")
    
    conn.commit()
    
    # 显示结果
    print("\n📊 已创建的表：")
    cursor.execute("SHOW TABLES")
    for table in cursor.fetchall():
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"   - {table[0]} ({count} 条记录)")
    
    cursor.close()
    conn.close()
    print("\n🎉 完成！")

if __name__ == '__main__':
    main()
