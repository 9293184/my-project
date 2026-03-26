"""临时脚本：创建 evaluation_tasks 和 evaluation_reports 表"""
import pymysql

conn = pymysql.connect(host='localhost', user='root', password='root', database='ai_security_system')
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS evaluation_tasks (
    id INT PRIMARY KEY AUTO_INCREMENT,
    task_name VARCHAR(200) NOT NULL,
    model_id INT DEFAULT NULL,
    model_name VARCHAR(100) DEFAULT NULL,
    task_type ENUM('adversarial','prompt_injection','jailbreak','poison_detection','comprehensive') NOT NULL DEFAULT 'comprehensive',
    status ENUM('pending','running','completed','failed','cancelled') NOT NULL DEFAULT 'pending',
    config JSON DEFAULT NULL,
    result JSON DEFAULT NULL,
    summary TEXT DEFAULT NULL,
    total_samples INT DEFAULT 0,
    attack_success INT DEFAULT 0,
    defense_success INT DEFAULT 0,
    risk_score DECIMAL(5,2) DEFAULT NULL,
    started_at DATETIME DEFAULT NULL,
    completed_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""")
print("evaluation_tasks OK")

cursor.execute("""
CREATE TABLE IF NOT EXISTS evaluation_reports (
    id INT PRIMARY KEY AUTO_INCREMENT,
    task_id INT NOT NULL,
    report_name VARCHAR(300) NOT NULL,
    report_format ENUM('json','html') NOT NULL DEFAULT 'json',
    content LONGTEXT NOT NULL,
    file_size INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES evaluation_tasks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""")
print("evaluation_reports OK")

# 创建索引（忽略已存在的错误）
indexes = [
    "CREATE INDEX idx_eval_tasks_status ON evaluation_tasks(status)",
    "CREATE INDEX idx_eval_tasks_model_id ON evaluation_tasks(model_id)",
    "CREATE INDEX idx_eval_tasks_created_at ON evaluation_tasks(created_at)",
    "CREATE INDEX idx_eval_reports_task_id ON evaluation_reports(task_id)",
    "CREATE INDEX idx_eval_reports_created_at ON evaluation_reports(created_at)",
]
for sql in indexes:
    try:
        cursor.execute(sql)
    except pymysql.err.OperationalError:
        pass  # 索引已存在

conn.commit()
cursor.close()
conn.close()
print("All done!")
