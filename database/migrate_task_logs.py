"""创建 evaluation_task_logs 表"""
import pymysql

conn = pymysql.connect(
    host="localhost", user="root", password="root",
    database="ai_security_system", charset="utf8mb4",
)
cur = conn.cursor()
cur.execute("""
    CREATE TABLE IF NOT EXISTS evaluation_task_logs (
        id INT PRIMARY KEY AUTO_INCREMENT,
        task_id INT NOT NULL,
        level VARCHAR(10) NOT NULL DEFAULT 'info',
        message VARCHAR(2000) NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (task_id) REFERENCES evaluation_tasks(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
conn.commit()
print("evaluation_task_logs table created")
cur.execute("CREATE INDEX IF NOT EXISTS idx_task_logs_task_id ON evaluation_task_logs(task_id)")
conn.commit()
print("index created")
conn.close()
