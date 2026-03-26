"""添加置信度和违规追踪功能"""
import sys
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

import pymysql

conn = pymysql.connect(
    host='localhost',
    user='root',
    password='root',
    database='ai_security_system',
    charset='utf8mb4'
)
cur = conn.cursor()

# 1. 添加置信度字段
try:
    cur.execute('ALTER TABLE chat_logs ADD COLUMN confidence DECIMAL(5,2) DEFAULT NULL AFTER block_reason')
    print('✅ 添加 confidence 字段')
except Exception as e:
    print(f'⚠️ confidence 字段可能已存在: {e}')

# 2. 创建用户违规追踪表
cur.execute('''
    CREATE TABLE IF NOT EXISTS user_violations (
        id INT AUTO_INCREMENT PRIMARY KEY,
        model_id INT NOT NULL COMMENT '模型ID（客户端）',
        user_id VARCHAR(100) NOT NULL COMMENT '用户ID',
        violation_count INT DEFAULT 1 COMMENT '连续违规次数',
        last_violation_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '最后违规时间',
        notified BOOLEAN DEFAULT FALSE COMMENT '是否已通知客户端',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_model_user (model_id, user_id),
        INDEX idx_violation_count (violation_count),
        FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户违规追踪表'
''')
print('✅ 创建 user_violations 表')

# 3. 添加配置项
try:
    cur.execute('''
        INSERT INTO system_config (config_key, config_value, description) 
        VALUES ('violation_threshold', '3', '连续违规触发预警的次数')
    ''')
    print('✅ 添加违规阈值配置')
except:
    print('⚠️ 违规阈值配置已存在')

try:
    cur.execute('''
        INSERT INTO system_config (config_key, config_value, description) 
        VALUES ('violation_reset_hours', '24', '违规计数重置时间（小时）')
    ''')
    print('✅ 添加重置时间配置')
except:
    print('⚠️ 重置时间配置已存在')

conn.commit()
cur.close()
conn.close()
print('\n✅ 数据库更新完成！')
